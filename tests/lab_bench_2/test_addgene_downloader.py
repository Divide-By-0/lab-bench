import io
import json
from pathlib import Path
from typing import Mapping

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from lab_bench_2.addgene_downloader import (
    AddgeneDownloader,
    AddgeneDownloadError,
    HttpResponse,
    parse_plasmid_id,
    validate_genbank,
)


def _genbank_bytes() -> bytes:
    record = SeqRecord(Seq("ATGCGTACGTAG"), id="test", name="test")
    record.annotations = {"molecule_type": "DNA", "topology": "circular"}
    record.features = [
        SeqFeature(FeatureLocation(0, 12), type="source"),
        SeqFeature(FeatureLocation(0, 6), type="CDS", qualifiers={"label": ["GFP"]}),
    ]
    handle = io.StringIO()
    SeqIO.write(record, handle, "genbank")
    return handle.getvalue().encode()


def _metadata(url: str) -> bytes:
    return json.dumps(
        {
            "sequences": {
                "public_addgene_full_sequences": [
                    {"id": 353936, "name": "Addgene verified", "genbank_url": url}
                ],
                "public_user_full_sequences": [],
            }
        }
    ).encode()


class FakeRequest:
    def __init__(self, responses: Mapping[str, list[HttpResponse]]) -> None:
        self.responses = {url: list(values) for url, values in responses.items()}
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, headers))
        return self.responses[url].pop(0)


def test_parse_plasmid_id_accepts_id_and_canonical_url() -> None:
    assert parse_plasmid_id("181752") == 181752
    assert parse_plasmid_id("https://www.addgene.org/181752/") == 181752
    with pytest.raises(ValueError, match="Expected an Addgene"):
        parse_plasmid_id("https://example.org/181752")


def test_preferred_falls_back_when_addgene_has_no_full_genbank() -> None:
    downloader = AddgeneDownloader(token="secret", request=lambda url, headers: None)  # type: ignore[arg-type,return-value]
    entries = downloader._sequence_entries(  # noqa: SLF001 - policy regression test
        {
            "sequences": {
                "public_addgene_full_sequences": [{"id": 1}],
                "public_user_full_sequences": [
                    {"id": 2, "genbank_url": "https://media.addgene.org/2.gbk"}
                ],
            }
        },
        "preferred",
    )

    assert entries == [
        (
            "public_user_full_sequences",
            {"id": 2, "genbank_url": "https://media.addgene.org/2.gbk"},
        )
    ]


def test_downloads_validated_gbk_and_does_not_forward_token(tmp_path: Path) -> None:
    media_url = "https://media.addgene.org/example/181752.gbk"
    api_url = (
        "https://api.developers.addgene.org/catalog/plasmid-with-sequences/181752/"
    )
    request = FakeRequest(
        {
            api_url: [HttpResponse(200, api_url, {}, _metadata(media_url))],
            media_url: [
                HttpResponse(
                    200,
                    media_url,
                    {
                        "Content-Disposition": 'attachment; filename="addgene-plasmid-181752-sequence-353936.gbk"'
                    },
                    _genbank_bytes(),
                )
            ],
        }
    )
    downloader = AddgeneDownloader(
        token="secret",
        request=request,
        min_delay=0,
        max_delay=0,
    )

    manifest = downloader.download_many([181752], tmp_path)

    assert manifest["errors"] == []
    assert manifest["results"][0]["feature_count"] == 2
    assert manifest["results"][0]["length"] == 12
    assert (tmp_path / "addgene-plasmid-181752-sequence-353936.gbk").is_file()
    assert request.calls[0][1]["Authorization"] == "Token secret"
    assert "Authorization" not in request.calls[1][1]


def test_valid_cache_avoids_api_request(tmp_path: Path) -> None:
    path = tmp_path / "addgene-plasmid-181752-sequence-353936.gbk"
    path.write_bytes(_genbank_bytes())

    def unexpected_request(url: str, headers: Mapping[str, str]) -> HttpResponse:
        raise AssertionError((url, headers))

    downloader = AddgeneDownloader(token="secret", request=unexpected_request)
    records = downloader.download_plasmid(181752, tmp_path)

    assert len(records) == 1
    assert records[0].status == "cached"


def test_retries_rate_limit_and_honors_retry_after(tmp_path: Path) -> None:
    media_url = "https://media.addgene.org/example/181752.gbk"
    api_url = (
        "https://api.developers.addgene.org/catalog/plasmid-with-sequences/181752/"
    )
    request = FakeRequest(
        {
            api_url: [HttpResponse(200, api_url, {}, _metadata(media_url))],
            media_url: [
                HttpResponse(429, media_url, {"Retry-After": "7"}, b"slow down"),
                HttpResponse(200, media_url, {}, _genbank_bytes()),
            ],
        }
    )
    sleeps: list[float] = []
    downloader = AddgeneDownloader(
        token="secret",
        request=request,
        min_delay=0,
        max_delay=0,
        sleep=sleeps.append,
    )

    downloader.download_plasmid(181752, tmp_path)

    assert 7.0 in sleeps
    assert len(request.calls) == 3


def test_rejects_html_or_empty_sequence() -> None:
    with pytest.raises(AddgeneDownloadError, match="missing LOCUS"):
        validate_genbank(b"<html>login</html>")


def test_requires_catalog_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADDGENE_TOKEN", raising=False)

    def unexpected_request(url: str, headers: Mapping[str, str]) -> HttpResponse:
        raise AssertionError((url, headers))

    downloader = AddgeneDownloader(token="", request=unexpected_request)
    with pytest.raises(AddgeneDownloadError, match="requires ADDGENE_TOKEN"):
        downloader.download_plasmid(181752, tmp_path)

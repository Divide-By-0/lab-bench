import io
import json
from pathlib import Path
from typing import Mapping

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from lab_bench_2.addgene_downloader import AddgeneDownloadError, HttpResponse
from lab_bench_2.addgene_web_downloader import (
    AddgeneWebDownloader,
    decrypt_chrome_cookie_value,
    parse_sequence_sections,
    select_sequence_ids,
)

SEQUENCES_HTML = """
<section id="nav">ignore /browse/sequence/999/</section>
<section id="addgene-full">
  <a href="/browse/sequence/353936/">Analyze</a>
  <div id="btn-analyze-sequence-353936"></div>
</section>
<section id="user-full">
  <a href="/browse/sequence/111111/">Depositor</a>
</section>
"""


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


class FakeRequest:
    def __init__(self, responses: Mapping[str, list[HttpResponse]]) -> None:
        self.responses = {url: list(values) for url, values in responses.items()}
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, headers))
        return self.responses[url].pop(0)


def test_parse_sequence_sections_keeps_addgene_before_depositor() -> None:
    grouped = parse_sequence_sections(SEQUENCES_HTML)
    assert grouped["public_addgene_full_sequences"] == ["353936"]
    assert grouped["public_user_full_sequences"] == ["111111"]
    assert select_sequence_ids(grouped, "preferred") == [
        ("public_addgene_full_sequences", "353936")
    ]
    assert select_sequence_ids(grouped, "depositor") == [
        ("public_user_full_sequences", "111111")
    ]


def test_downloads_via_public_discovery_and_session_cookie(
    tmp_path: Path,
) -> None:
    media_url = (
        "https://media.addgene.org/snapgene-media/v1/sequences/353936/uuid/"
        "addgene-plasmid-181752-sequence-353936.gbk"
    )
    sequences_url = "https://www.addgene.org/181752/sequences/"
    collection_url = (
        "https://www.addgene.org/api/get-sequence-file-collection/353936/"
    )
    request = FakeRequest(
        {
            sequences_url: [
                HttpResponse(
                    200,
                    sequences_url,
                    {
                        "Set-Cookie": "__Secure_media_edge_auth=refreshed-edge; Path=/"
                    },
                    SEQUENCES_HTML.encode(),
                )
            ],
            collection_url: [
                HttpResponse(
                    200,
                    collection_url,
                    {},
                    json.dumps(
                        {"inProgress": False, "genbankUrl": media_url}
                    ).encode(),
                )
            ],
            media_url: [
                HttpResponse(
                    200,
                    media_url,
                    {
                        "Content-Disposition": (
                            'attachment; filename="addgene-plasmid-181752-sequence-353936.gbk"'
                        )
                    },
                    _genbank_bytes(),
                )
            ],
        }
    )
    downloader = AddgeneWebDownloader(
        cookies={"__Secure_media_edge_auth": "secret-session"},
        request=request,
        min_delay=0,
        max_delay=0,
    )

    manifest = downloader.download_many([181752], tmp_path)

    assert manifest["errors"] == []
    assert manifest["transport"] == "chrome-session-http"
    result = manifest["results"][0]
    assert result["status"] == "downloaded-via-chrome-session"
    assert result["sequence_id"] == "353936"
    assert "secret-session" not in json.dumps(manifest)
    assert (tmp_path / "addgene-plasmid-181752-sequence-353936.gbk").is_file()
    assert "Cookie" in request.calls[2][1]
    assert "refreshed-edge" in request.calls[2][1]["Cookie"]


def test_session_rejection_stops_the_batch(tmp_path: Path) -> None:
    sequences_url = "https://www.addgene.org/181752/sequences/"
    request = FakeRequest(
        {
            sequences_url: [HttpResponse(403, sequences_url, {}, b"denied")],
            "https://www.addgene.org/128652/sequences/": [
                HttpResponse(200, "", {}, SEQUENCES_HTML.encode())
            ],
        }
    )
    downloader = AddgeneWebDownloader(
        cookies={"__Secure_media_edge_auth": "secret-session"},
        request=request,
        min_delay=0,
        max_delay=0,
    )

    manifest = downloader.download_many([181752, 128652], tmp_path)

    assert len(manifest["errors"]) == 1
    assert "signed-in Chrome session" in manifest["errors"][0]["error"]
    assert manifest["results"] == []


def test_rejects_non_genbank_media_body(tmp_path: Path) -> None:
    media_url = "https://media.addgene.org/x/addgene-plasmid-181752-sequence-1.gbk"
    sequences_url = "https://www.addgene.org/181752/sequences/"
    collection_url = (
        "https://www.addgene.org/api/get-sequence-file-collection/353936/"
    )
    request = FakeRequest(
        {
            sequences_url: [
                HttpResponse(200, sequences_url, {}, SEQUENCES_HTML.encode())
            ],
            collection_url: [
                HttpResponse(
                    200,
                    collection_url,
                    {},
                    json.dumps(
                        {"inProgress": False, "genbankUrl": media_url}
                    ).encode(),
                )
            ],
            media_url: [HttpResponse(200, media_url, {}, b"<html>login</html>")],
        }
    )
    downloader = AddgeneWebDownloader(
        cookies={"__Secure_media_edge_auth": "secret-session"},
        request=request,
        min_delay=0,
        max_delay=0,
    )

    with pytest.raises(AddgeneDownloadError, match="non-GenBank"):
        downloader.download_plasmid(181752, tmp_path)


def test_decrypt_chrome_cookie_value_strips_digest_prefix() -> None:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key = b"0123456789abcdef"
    plaintext = b"d" * 32 + b"en"
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16))
    encrypted = b"v10" + cipher.encryptor().update(padded) + cipher.encryptor().finalize()

    assert decrypt_chrome_cookie_value(encrypted, key) == "en"

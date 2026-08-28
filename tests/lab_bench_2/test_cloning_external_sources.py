from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from lab_bench_2.cloning_external_sources import (
    CachedHttpClient,
    CachedResponse,
    ExternalSourceError,
    IgemRegistryClient,
    fetch_rebase_neb_catalog,
    parse_rebase_enzymes,
    parse_rebase_references,
)
from lab_bench_2.cloning_inventory import feature_signature


class NetworkResponse:
    def __init__(self, url: str) -> None:
        self.url = url
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self) -> NetworkResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok": true}'

    def geturl(self) -> str:
        return self.url


def _response(body: str, url: str = "https://example.invalid/source") -> CachedResponse:
    return CachedResponse(
        body=body.encode(),
        url=url,
        fetched_at="2026-08-27T00:00:00+00:00",
        sha256="digest",
        headers={},
        cache_status="fetched",
    )


class RebaseHttp:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads

    def get(self, url: str, *, cache_key: str, refresh: bool) -> CachedResponse:
        del cache_key, refresh
        return _response(self.payloads[url.rsplit("/", 1)[-1]], url)


class IgemHttp:
    def get_json(
        self, url: str, *, cache_key: str, refresh: bool
    ) -> tuple[Any, CachedResponse]:
        del cache_key, refresh
        parsed = urlsplit(url)
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        payload: Any
        if parsed.path == "/docs-json":
            payload = {"info": {"title": "Registry", "version": "1.0"}}
        elif parsed.path == "/v1/parts/roles":
            payload = {
                "data": (
                    [
                        {
                            "accession": "SO:0000316",
                            "label": "CDS",
                            "definition": "protein coding region",
                            "source": "SO",
                            "synonyms": ["coding sequence"],
                        },
                        {
                            "uuid": "role-tag",
                            "accession": "SO:0000324",
                            "label": "Tag",
                            "definition": "identifying sequence tag",
                            "source": "SO",
                            "synonyms": [],
                        },
                    ]
                    if page == 1
                    else []
                ),
                "page": page,
                "total": 2,
            }
        elif parsed.path == "/v1/parts/categories":
            payload = {
                "data": (
                    [
                        {
                            "uuid": "category-cas9",
                            "label": "//function/crispr/cas9",
                            "value": "//function/crispr/cas9",
                            "description": "",
                        }
                    ]
                    if page == 1
                    else []
                ),
                "page": page,
                "total": 1,
            }
        elif parsed.path == "/v1/parts":
            payload = {"data": [], "page": 1, "total": 42}
        elif parsed.path == "/v1/parts/slugs/bba-k4587111":
            payload = {
                "uuid": "part-flag",
                "name": "BBa_K4587111",
                "slug": "bba-k4587111",
                "title": "FLAG Tag",
                "description": "A detection tag.",
                "sequence": "GACTACAAGGACGATGATGATAAA",
                "usageCount": 6,
                "role": {
                    "uuid": "role-tag",
                    "accession": "SO:0000324",
                    "label": "Tag",
                },
            }
        else:
            raise AssertionError(url)
        return payload, _response(json.dumps(payload), url)


class IgemWrongRoleHttp(IgemHttp):
    def get_json(
        self, url: str, *, cache_key: str, refresh: bool
    ) -> tuple[Any, CachedResponse]:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if parsed.path == "/v1/parts" and query.get("search"):
            payload = {
                "data": [
                    {
                        "name": "BBa_TEST_WRONG_ROLE",
                        "slug": "bba-test-wrong-role",
                        "title": "Test promoter",
                        "sequenceLength": 6,
                        "usageCount": 1,
                        "role": {"accession": "SO:0000316", "label": "CDS"},
                    }
                ],
                "page": 1,
                "total": 1,
            }
            return payload, _response(json.dumps(payload), url)
        if parsed.path == "/v1/parts/slugs/bba-test-wrong-role":
            payload = {
                "uuid": "part-wrong-role",
                "name": "BBa_TEST_WRONG_ROLE",
                "slug": "bba-test-wrong-role",
                "title": "Test promoter",
                "description": "An intentionally wrong-role test candidate.",
                "sequence": "AAAAAA",
                "usageCount": 1,
                "role": {"accession": "SO:0000316", "label": "CDS"},
            }
            return payload, _response(json.dumps(payload), url)
        return super().get_json(url, cache_key=cache_key, refresh=refresh)


def test_http_cache_reuses_validated_response_and_rejects_other_hosts(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def open_url(request: Any, *, timeout: float) -> NetworkResponse:
        del timeout
        calls.append(str(request.full_url))
        return NetworkResponse(str(request.full_url))

    client = CachedHttpClient(
        tmp_path,
        allowed_hosts=["api.registry.igem.org"],
        min_delay=0,
        open_url=open_url,
    )

    first = client.get("https://api.registry.igem.org/test", cache_key="test-response")
    second = client.get("https://api.registry.igem.org/test", cache_key="test-response")
    third = client.get(
        "https://api.registry.igem.org/test?different=1",
        cache_key="test-response",
    )

    assert first.cache_status == "fetched"
    assert second.cache_status == "cache-hit"
    assert third.cache_status == "fetched"
    assert calls == [
        "https://api.registry.igem.org/test",
        "https://api.registry.igem.org/test?different=1",
    ]
    with pytest.raises(ExternalSourceError, match="non-allowlisted"):
        client.get("https://example.org/test", cache_key="bad-host")


def test_parses_rebase_cut_geometry_and_supplier_records() -> None:
    enzyme_text = """# REBASE version 608
AatII GACGTC 6 2 0 5 1 0 0
"""
    reference_text = """# REBASE version 608
AatII
Acetobacter aceti

2(6)
IFO 3281
BINRV
1
Example reference.
//
"""

    assert parse_rebase_enzymes(enzyme_text)["AatII"] == {
        "name": "AatII",
        "recognition_site": "GACGTC",
        "recognition_length": 6,
        "cut_count": 2,
        "blunt": False,
        "cut_5prime": 5,
        "cut_3prime": 1,
        "second_cut_5prime": 0,
        "second_cut_3prime": 0,
    }
    assert parse_rebase_references(reference_text)["AatII"]["supplier_codes"] == [
        "B",
        "I",
        "N",
        "R",
        "V",
    ]


def test_rebase_catalog_filters_to_neb_and_records_release(tmp_path: Path) -> None:
    common = "# REBASE version 608\n# Rich Roberts Jul 31 2026\n"
    client = RebaseHttp(
        {
            "link_emboss_e": common
            + "AatII GACGTC 6 2 0 5 1 0 0\nEcoRV GATATC 6 2 1 3 3 0 0\n",
            "link_emboss_s": common
            + "B Thermo Fisher Scientific\nN New England Biolabs\n",
            "link_emboss_r": common
            + "AatII\norganism\n\n\nsource\nN\n0\n//\n"
            + "EcoRV\norganism\n\n\nsource\nB\n0\n//\n",
        }
    )

    catalog = fetch_rebase_neb_catalog(tmp_path, http=client)  # type: ignore[arg-type]

    assert catalog["source"]["release"] == "608"
    assert catalog["source"]["release_date"] == "Jul 31 2026"
    assert [item["name"] for item in catalog["enzymes"]] == ["AatII"]


def test_rebase_rejects_mismatched_releases(tmp_path: Path) -> None:
    client = RebaseHttp(
        {
            "link_emboss_e": "# REBASE version 608\nAatII GACGTC 6 2 0 5 1 0 0\n",
            "link_emboss_s": "# REBASE version 607\nN New England Biolabs\n",
            "link_emboss_r": "# REBASE version 608\n",
        }
    )

    with pytest.raises(ExternalSourceError, match="disagree"):
        fetch_rebase_neb_catalog(tmp_path, http=client)  # type: ignore[arg-type]


def test_igem_vocabulary_builds_role_and_function_aliases(tmp_path: Path) -> None:
    vocabulary = IgemRegistryClient(
        tmp_path,
        http=IgemHttp(),  # type: ignore[arg-type]
    ).fetch_vocabulary()

    assert vocabulary["summary"] == {
        "published_part_count": 42,
        "role_count": 2,
        "category_count": 1,
        "functional_category_count": 1,
        "feature_query_count": 0,
        "specific_part_match_count": 0,
        "part_match_error_count": 0,
    }
    assert (
        vocabulary["indexes"]["role_alias_to_terms"]["coding sequence"][0]["accession"]
        == "SO:0000316"
    )
    assert (
        vocabulary["indexes"]["category_alias_to_terms"]["cas9"][0]["path"]
        == "//function/crispr/cas9"
    )


def test_igem_flag_match_is_specific_and_translation_verified(tmp_path: Path) -> None:
    source_sequence = "GATTACAAAGACGATGACGATAAG"
    signature = feature_signature("FLAG", source_sequence)
    vocabulary = IgemRegistryClient(
        tmp_path,
        http=IgemHttp(),  # type: ignore[arg-type]
    ).fetch_vocabulary(
        [
            {
                "feature_signature": signature,
                "label": "FLAG",
                "normalized_label": "flag",
                "functional_roles": ["coding_sequence", "epitope_tag"],
                "nucleotide_sequence": source_sequence,
                "nucleotide_length": len(source_sequence),
                "translation": "DYKDDDDK",
            }
        ]
    )

    match = vocabulary["indexes"]["feature_signature_to_part_matches"][signature][0]
    assert match["name"] == "BBa_K4587111"
    assert match["url"] == "https://registry.igem.org/parts/bba-k4587111"
    assert match["description"] == "A detection tag."
    assert match["role"]["accession"] == "SO:0000324"
    assert match["role"]["label"] == "Tag"
    assert match["evidence"]["nucleotide_exact"] is False
    assert match["evidence"]["translated_peptide_exact"] is True
    assert match["evidence"]["expected_functional_role"] is True
    assert match["evidence"]["source_feature_type_used_as_role"] is False
    assert match["selected"] is True
    assert match["review_required"] is False


def test_igem_does_not_select_exact_sequence_with_wrong_role(tmp_path: Path) -> None:
    source_sequence = "AAAAAA"
    signature = feature_signature("Test promoter", source_sequence)
    vocabulary = IgemRegistryClient(
        tmp_path,
        http=IgemWrongRoleHttp(),  # type: ignore[arg-type]
    ).fetch_vocabulary(
        [
            {
                "feature_signature": signature,
                "label": "Test promoter",
                "normalized_label": "test promoter",
                "functional_roles": ["promoter"],
                "nucleotide_sequence": source_sequence,
                "nucleotide_length": len(source_sequence),
                "translation": "",
            }
        ]
    )

    match = vocabulary["indexes"]["feature_signature_to_part_matches"][signature][0]
    assert match["evidence"]["nucleotide_exact"] is True
    assert match["evidence"]["expected_functional_role"] is False
    assert match["evidence"]["source_feature_type_used_as_role"] is False
    assert match["selected"] is False
    assert vocabulary["summary"]["specific_part_match_count"] == 0

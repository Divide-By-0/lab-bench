"""Fetch versioned public vocabularies used to enrich cloning inventories."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from lab_bench_2.cloning_inventory import normalize_label

REBASE_BASE_URL = "https://rebase.neb.com/rebase"
IGEM_API_BASE_URL = "https://api.registry.igem.org"
IGEM_REGISTRY_PART_URL = "https://registry.igem.org/parts"
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
REBASE_ENZYME_FIELD_COUNT = 9
REBASE_REFERENCE_HEADER_FIELD_COUNT = 7
MAX_IGEM_PART_DETAILS_PER_FEATURE = 8

# A tiny, auditable override table is appropriate for canonical aliases whose
# Registry search has many synonymous entries. The evidence block still records
# whether the source nucleotide or translated peptide actually matches the part.
IGEM_CANONICAL_PART_SLUGS = {"flag": "bba-k4587111"}

EXPECTED_IGEM_ROLE_ACCESSIONS = {
    "affinity_tag": ("SO:0000324", "SO:0000807"),
    "coding_sequence": ("SO:0000316",),
    "enhancer": ("SO:0000165", "IGEM:0000006"),
    "epitope_tag": ("SO:0000324", "SO:0000807"),
    "genome_editor": ("SO:0000316",),
    "intron_or_splicing": ("SO:0000188", "IGEM:0000036"),
    "localization_signal": ("SO:0001527", "IGEM:0000010", "SO:0000417"),
    "origin_of_replication": ("SO:0000296",),
    "promoter": ("SO:0000167", "IGEM:0000006"),
    "protein_binding_site": ("SO:0000057", "SO:0000410", "IGEM:0000006"),
    "selection_marker": ("SO:0002232", "SO:0000316"),
    "terminator_or_polya": ("SO:0000141", "SO:0000551"),
}


class ExternalSourceError(RuntimeError):
    """Raised when a cloning-data source cannot be fetched or parsed."""


@dataclass(frozen=True)
class CachedResponse:
    """A cached or newly fetched HTTP response with immutable provenance."""

    body: bytes
    url: str
    fetched_at: str
    sha256: str
    headers: dict[str, str]
    cache_status: str

    def provenance(self) -> dict[str, Any]:
        """Return the serializable provenance fields for this response."""
        return {
            "url": self.url,
            "fetched_at": self.fetched_at,
            "sha256": self.sha256,
            "headers": self.headers,
            "cache_status": self.cache_status,
        }


OpenUrl = Callable[..., Any]
SleepFunction = Callable[[float], None]
MonotonicFunction = Callable[[], float]


class CachedHttpClient:
    """Serial HTTPS client with validation, retry, and a content-addressed cache."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        allowed_hosts: Sequence[str],
        min_delay: float = 0.2,
        retries: int = 3,
        timeout: float = 60.0,
        open_url: OpenUrl | None = None,
        sleep: SleepFunction = time.sleep,
        monotonic: MonotonicFunction = time.monotonic,
    ) -> None:
        if min_delay < 0 or retries < 0 or timeout <= 0:
            raise ValueError("Require nonnegative delay/retries and positive timeout")
        self.cache_dir = cache_dir.expanduser().resolve()
        self.allowed_hosts = {host.casefold() for host in allowed_hosts}
        self.min_delay = min_delay
        self.retries = retries
        self.timeout = timeout
        self._open_url = open_url or _default_open_url
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: float | None = None

    def get(self, url: str, *, cache_key: str, refresh: bool = False) -> CachedResponse:
        """Fetch one allowlisted HTTPS URL, reusing a validated cache by default."""
        self._validate_url(url)
        body_path, metadata_path = self._cache_paths(cache_key)
        if not refresh:
            cached = self._read_cache(body_path, metadata_path, expected_url=url)
            if cached is not None:
                return cached

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait_for_rate_limit()
            request = Request(
                url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "User-Agent": "lab-bench-cloning-source-inventory/1.0",
                },
            )
            self._last_request_at = self._monotonic()
            try:
                with self._open_url(request, timeout=self.timeout) as response:
                    body = response.read()
                    headers = _selected_headers(response.headers)
                    final_url = str(response.geturl())
                self._validate_url(final_url)
                if not body:
                    raise ExternalSourceError(f"Empty response from {url}")
                result = CachedResponse(
                    body=body,
                    url=final_url,
                    fetched_at=datetime.now(UTC).isoformat(),
                    sha256=hashlib.sha256(body).hexdigest(),
                    headers=headers,
                    cache_status="fetched",
                )
                self._write_cache(body_path, metadata_path, result, request_url=url)
                return result
            except HTTPError as exc:
                last_error = exc
                if exc.code not in RETRYABLE_HTTP_STATUSES or attempt >= self.retries:
                    break
                self._sleep(_retry_delay(exc.headers, attempt))
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                self._sleep(float(2**attempt))
        raise ExternalSourceError(
            f"Could not fetch {url}: {last_error}"
        ) from last_error

    def get_json(
        self, url: str, *, cache_key: str, refresh: bool = False
    ) -> tuple[Any, CachedResponse]:
        """Fetch and decode a JSON response."""
        response = self.get(url, cache_key=cache_key, refresh=refresh)
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalSourceError(f"Invalid JSON from {url}") from exc
        return payload, response

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").casefold() not in self.allowed_hosts
        ):
            raise ExternalSourceError(f"Refusing non-allowlisted source URL: {url}")

    def _cache_paths(self, cache_key: str) -> tuple[Path, Path]:
        safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", cache_key).strip("_")
        if not safe_key:
            raise ValueError("cache_key must contain a filename-safe character")
        source_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:12]
        stem = f"{safe_key[:80]}-{source_hash}"
        return self.cache_dir / f"{stem}.body", self.cache_dir / f"{stem}.json"

    def _read_cache(
        self, body_path: Path, metadata_path: Path, *, expected_url: str
    ) -> CachedResponse | None:
        try:
            body = body_path.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(body).hexdigest()
            if digest != metadata["sha256"] or not body:
                return None
            url = str(metadata["url"])
            request_url = str(metadata.get("request_url") or url)
            if request_url != expected_url:
                return None
            self._validate_url(url)
            headers = {
                str(key): str(value)
                for key, value in dict(metadata.get("headers") or {}).items()
            }
            return CachedResponse(
                body=body,
                url=url,
                fetched_at=str(metadata["fetched_at"]),
                sha256=digest,
                headers=headers,
                cache_status="cache-hit",
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_cache(
        self,
        body_path: Path,
        metadata_path: Path,
        result: CachedResponse,
        *,
        request_url: str,
    ) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        body_temp = body_path.with_suffix(body_path.suffix + ".tmp")
        metadata_temp = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
        body_temp.write_bytes(result.body)
        metadata = {**result.provenance(), "request_url": request_url}
        metadata_temp.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        body_temp.replace(body_path)
        metadata_temp.replace(metadata_path)

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.min_delay - (self._monotonic() - self._last_request_at)
        if remaining > 0:
            self._sleep(remaining)


def fetch_rebase_neb_catalog(
    cache_dir: Path,
    *,
    refresh: bool = False,
    http: CachedHttpClient | None = None,
) -> dict[str, Any]:
    """Fetch the current REBASE restriction catalog sold by NEB (supplier N)."""
    client = http or CachedHttpClient(
        cache_dir / "rebase",
        allowed_hosts=["rebase.neb.com"],
        min_delay=0.2,
    )
    source_responses = {
        name: client.get(
            f"{REBASE_BASE_URL}/{link}", cache_key=f"rebase-{name}", refresh=refresh
        )
        for name, link in (
            ("enzymes", "link_emboss_e"),
            ("references", "link_emboss_r"),
            ("suppliers", "link_emboss_s"),
        )
    }
    texts = {
        name: response.body.decode("utf-8")
        for name, response in source_responses.items()
    }
    releases = {_parse_rebase_release(text) for text in texts.values()}
    if len(releases) != 1:
        raise ExternalSourceError(
            f"REBASE source files disagree on release: {releases}"
        )
    release = releases.pop()
    suppliers = parse_rebase_suppliers(texts["suppliers"])
    if suppliers.get("N") != "New England Biolabs":
        raise ExternalSourceError("REBASE supplier N is not New England Biolabs")
    enzymes = parse_rebase_enzymes(texts["enzymes"])
    references = parse_rebase_references(texts["references"])
    biopython_names, biopython_version = _biopython_neb_names()

    catalog = []
    for name, reference in references.items():
        supplier_codes = reference["supplier_codes"]
        enzyme = enzymes.get(name)
        if "N" not in supplier_codes or enzyme is None:
            continue
        catalog.append(
            {
                **enzyme,
                "organism": reference["organism"],
                "isoschizomers": reference["isoschizomers"],
                "methylation": reference["methylation"],
                "source": reference["source"],
                "supplier_codes": supplier_codes,
                "supplier_names": [
                    suppliers[code] for code in supplier_codes if code in suppliers
                ],
                "reference_count": reference["reference_count"],
                "analysis_supported_by_biopython": name in biopython_names,
            }
        )
    catalog.sort(key=lambda item: str(item["name"]))
    rebase_names = {str(item["name"]) for item in catalog}
    return {
        "schema_version": 1,
        "source": {
            "name": "REBASE",
            "release": release,
            "release_date": _parse_rebase_release_date(texts["enzymes"]),
            "supplier_code": "N",
            "supplier_name": suppliers["N"],
            "files": {
                name: response.provenance()
                for name, response in source_responses.items()
            },
        },
        "enzyme_count": len(catalog),
        "enzymes": catalog,
        "biopython_comparison": {
            "biopython_version": biopython_version,
            "supplier_n_count": len(biopython_names),
            "overlap_count": len(rebase_names & biopython_names),
            "only_in_live_rebase": sorted(rebase_names - biopython_names),
            "only_in_biopython": sorted(biopython_names - rebase_names),
        },
    }


class IgemRegistryClient:
    """Read the anonymous, published subset of the iGEM Registry API."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        refresh: bool = False,
        http: CachedHttpClient | None = None,
    ) -> None:
        self.refresh = refresh
        self.http = http or CachedHttpClient(
            cache_dir / "igem",
            allowed_hosts=["api.registry.igem.org"],
            min_delay=2.1,
        )

    def fetch_vocabulary(
        self, feature_queries: Sequence[Mapping[str, Any]] = ()
    ) -> dict[str, Any]:
        """Fetch current vocabularies and evidence-ranked public part matches."""
        openapi, openapi_response = self._get_json("/docs-json", "openapi")
        roles, role_responses = self._get_paginated(
            "/v1/parts/roles", {"deprecated": "false"}, "roles"
        )
        categories, category_responses = self._get_paginated(
            "/v1/parts/categories", {}, "categories"
        )
        part_page, part_response = self._get_json(
            "/v1/parts", "parts-count", {"page": 1, "pageSize": 1}
        )
        if not isinstance(openapi, dict) or not isinstance(part_page, dict):
            raise ExternalSourceError("iGEM returned an unexpected schema")
        role_aliases = _igem_role_alias_index(roles)
        category_aliases = _igem_category_alias_index(categories)
        part_matches, part_match_responses, part_match_errors = (
            self._fetch_specific_part_matches(feature_queries, roles)
        )
        info = openapi.get("info") or {}
        return {
            "schema_version": 1,
            "source": {
                "name": "iGEM Registry",
                "api_base_url": IGEM_API_BASE_URL,
                "api_title": str(info.get("title") or ""),
                "api_version": str(info.get("version") or ""),
                "access": "anonymous published records",
                "openapi": openapi_response.provenance(),
                "pages": [
                    response.provenance()
                    for response in [*role_responses, *category_responses]
                ],
                "parts_count_request": part_response.provenance(),
                "part_match_requests": [
                    response.provenance() for response in part_match_responses
                ],
                "part_match_errors": part_match_errors,
            },
            "summary": {
                "published_part_count": int(part_page.get("total") or 0),
                "role_count": len(roles),
                "category_count": len(categories),
                "functional_category_count": sum(
                    _category_path(item).startswith("//function/")
                    for item in categories
                ),
                "feature_query_count": len(feature_queries),
                "specific_part_match_count": sum(
                    any(bool(part.get("selected")) for part in matches)
                    for matches in part_matches.values()
                ),
                "part_match_error_count": len(part_match_errors),
            },
            "roles": sorted(roles, key=lambda item: str(item.get("accession") or "")),
            "categories": sorted(
                categories, key=lambda item: _category_path(item).casefold()
            ),
            "indexes": {
                "role_alias_to_terms": role_aliases,
                "category_alias_to_terms": category_aliases,
                "feature_signature_to_part_matches": part_matches,
            },
        }

    def _fetch_specific_part_matches(
        self,
        feature_queries: Sequence[Mapping[str, Any]],
        roles: Sequence[Mapping[str, Any]],
    ) -> tuple[
        dict[str, list[dict[str, Any]]], list[CachedResponse], list[dict[str, str]]
    ]:
        del roles
        matches: dict[str, list[dict[str, Any]]] = {}
        responses: list[CachedResponse] = []
        errors: list[dict[str, str]] = []
        seen_signatures: set[str] = set()
        for query in feature_queries:
            signature = str(query.get("feature_signature") or "")
            label = str(query.get("normalized_label") or "")
            if not signature or not label or signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            canonical_slug = IGEM_CANONICAL_PART_SLUGS.get(label)
            if canonical_slug:
                try:
                    payload, response = self._get_json(
                        f"/v1/parts/slugs/{canonical_slug}",
                        f"part-{canonical_slug}",
                    )
                except ExternalSourceError as exc:
                    errors.append({"feature_signature": signature, "error": str(exc)})
                    continue
                responses.append(response)
                if isinstance(payload, Mapping):
                    matches[signature] = [
                        _igem_part_candidate(
                            payload,
                            query,
                            canonical=True,
                            expected_accessions=_expected_role_accessions(query),
                            provenance=response.provenance(),
                        )
                    ]
                continue

            expected_accessions = _expected_role_accessions(query)
            length = int(query.get("nucleotide_length") or 0)
            parameters: dict[str, Any] = {
                "page": 1,
                "pageSize": 100,
                "search": str(query.get("label") or label),
            }
            if length:
                parameters.update({"minLength": length, "maxLength": length})
            try:
                payload, search_response = self._get_json(
                    "/v1/parts",
                    "part-search-"
                    f"{hashlib.sha256(signature.encode()).hexdigest()[:24]}",
                    parameters,
                )
            except ExternalSourceError as exc:
                errors.append({"feature_signature": signature, "error": str(exc)})
                continue
            responses.append(search_response)
            raw_parts = payload.get("data", []) if isinstance(payload, Mapping) else []
            candidates = [part for part in raw_parts if isinstance(part, Mapping)]
            candidates.sort(
                key=lambda part: _igem_part_preliminary_score(
                    part, query, expected_accessions
                ),
                reverse=True,
            )
            evaluated: list[dict[str, Any]] = []
            for part in candidates[:MAX_IGEM_PART_DETAILS_PER_FEATURE]:
                slug = str(part.get("slug") or "")
                if not slug:
                    continue
                try:
                    detail, detail_response = self._get_json(
                        f"/v1/parts/slugs/{slug}", f"part-{slug}"
                    )
                except ExternalSourceError as exc:
                    errors.append(
                        {
                            "feature_signature": signature,
                            "part_slug": slug,
                            "error": str(exc),
                        }
                    )
                    continue
                responses.append(detail_response)
                if isinstance(detail, Mapping):
                    evaluated.append(
                        _igem_part_candidate(
                            detail,
                            query,
                            canonical=False,
                            expected_accessions=expected_accessions,
                            provenance=detail_response.provenance(),
                        )
                    )
            evaluated.sort(key=_igem_part_sort_key, reverse=True)
            selected = next(
                (
                    part
                    for part in evaluated
                    if part["evidence"]["expected_functional_role"]
                    and (
                        part["evidence"]["nucleotide_exact"]
                        or part["evidence"]["translated_peptide_exact"]
                    )
                ),
                None,
            )
            if selected is not None:
                selected["selected"] = True
            if evaluated:
                matches[signature] = evaluated[:3]
        return matches, responses, errors

    def _get_paginated(
        self, route: str, parameters: Mapping[str, Any], cache_prefix: str
    ) -> tuple[list[dict[str, Any]], list[CachedResponse]]:
        page = 1
        total: int | None = None
        items: list[dict[str, Any]] = []
        responses: list[CachedResponse] = []
        while total is None or len(items) < total:
            payload, response = self._get_json(
                route,
                f"{cache_prefix}-page-{page}",
                {**parameters, "page": page, "pageSize": 100},
            )
            if not isinstance(payload, dict) or not isinstance(
                payload.get("data"), list
            ):
                raise ExternalSourceError(f"Unexpected paginated iGEM result: {route}")
            page_items = payload["data"]
            typed_items = [item for item in page_items if isinstance(item, dict)]
            if len(typed_items) != len(page_items):
                raise ExternalSourceError(f"Non-object item in iGEM result: {route}")
            items.extend(typed_items)
            responses.append(response)
            total = int(payload.get("total") or 0)
            if not page_items:
                break
            page += 1
        return items, responses

    def _get_json(
        self,
        route: str,
        cache_key: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Any, CachedResponse]:
        query = f"?{urlencode(parameters, doseq=True)}" if parameters else ""
        return self.http.get_json(
            f"{IGEM_API_BASE_URL}{route}{query}",
            cache_key=f"igem-{cache_key}",
            refresh=self.refresh,
        )


def fetch_cloning_external_sources(
    cache_dir: Path,
    *,
    refresh: bool = False,
    include_rebase: bool = True,
    include_igem: bool = True,
    feature_queries: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Fetch the independent external catalogs used by cloning inventories."""
    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": {},
    }
    sources = result["sources"]
    if not isinstance(sources, dict):
        raise AssertionError("sources must be a mapping")
    if include_rebase:
        sources["rebase_neb"] = fetch_rebase_neb_catalog(cache_dir, refresh=refresh)
    if include_igem:
        sources["igem_registry"] = IgemRegistryClient(
            cache_dir, refresh=refresh
        ).fetch_vocabulary(feature_queries)
    return result


def _expected_role_accessions(query: Mapping[str, Any]) -> tuple[str, ...]:
    accessions: set[str] = set()
    functional_roles = query.get("functional_roles") or []
    if isinstance(functional_roles, Sequence) and not isinstance(
        functional_roles, (str, bytes)
    ):
        for role in functional_roles:
            accessions.update(EXPECTED_IGEM_ROLE_ACCESSIONS.get(str(role), ()))
    return tuple(sorted(accessions))


def _igem_part_preliminary_score(
    part: Mapping[str, Any],
    query: Mapping[str, Any],
    expected_accessions: Sequence[str],
) -> float:
    label = normalize_label(str(query.get("label") or ""))
    title = normalize_label(str(part.get("title") or ""))
    name = normalize_label(str(part.get("name") or ""))
    source_length = int(query.get("nucleotide_length") or 0)
    candidate_length = int(part.get("sequenceLength") or 0)
    role = part.get("role")
    role_accession = (
        str(role.get("accession") or "") if isinstance(role, Mapping) else ""
    )
    score = SequenceMatcher(None, label, title).ratio() * 40
    if label and label in {title, name}:
        score += 80
    elif label and all(token in title.split() for token in label.split()):
        score += 35
    if source_length and source_length == candidate_length:
        score += 40
    if role_accession in expected_accessions:
        score += 30
    score += min(float(part.get("usageCount") or 0), 20.0) / 4
    return score


def _igem_part_candidate(
    part: Mapping[str, Any],
    query: Mapping[str, Any],
    *,
    canonical: bool,
    expected_accessions: Sequence[str],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    from Bio.Seq import Seq

    source_sequence = str(query.get("nucleotide_sequence") or "").upper()
    source_translation = _normalize_translation(str(query.get("translation") or ""))
    candidate_sequence = str(part.get("sequence") or "").upper()
    candidate_translation = ""
    if candidate_sequence and len(candidate_sequence) % 3 == 0:
        candidate_translation = _normalize_translation(
            str(Seq(candidate_sequence).translate())  # type: ignore[no-untyped-call]
        )
    nucleotide_exact = bool(source_sequence) and candidate_sequence in {
        source_sequence,
        str(Seq(source_sequence).reverse_complement()),  # type: ignore[no-untyped-call]
    }
    translated_exact = bool(source_translation) and (
        candidate_translation == source_translation
    )
    identity = _same_length_identity(source_sequence, candidate_sequence)
    role = part.get("role")
    role_mapping = role if isinstance(role, Mapping) else {}
    role_accession = str(role_mapping.get("accession") or "")
    slug = str(part.get("slug") or "")
    evidence = {
        "canonical_alias": canonical,
        "nucleotide_exact": nucleotide_exact,
        "same_length_nucleotide_identity_percent": identity,
        "source_translation": source_translation,
        "candidate_translation": candidate_translation,
        "translated_peptide_exact": translated_exact,
        "expected_functional_role": role_accession in expected_accessions,
        "source_feature_type_used_as_role": False,
    }
    selected = (
        canonical
        and role_accession in expected_accessions
        and (nucleotide_exact or translated_exact)
    )
    return {
        "uuid": str(part.get("uuid") or ""),
        "name": str(part.get("name") or ""),
        "slug": slug,
        "url": f"{IGEM_REGISTRY_PART_URL}/{slug}",
        "title": str(part.get("title") or ""),
        "description": str(part.get("description") or ""),
        "role": {
            "uuid": str(role_mapping.get("uuid") or ""),
            "accession": role_accession,
            "label": str(role_mapping.get("label") or ""),
            "definition": str(role_mapping.get("definition") or ""),
            "source": str(role_mapping.get("source") or ""),
        },
        "sequence_length": len(candidate_sequence),
        "sequence_sha256": (
            hashlib.sha256(candidate_sequence.encode("ascii")).hexdigest()
            if candidate_sequence
            else ""
        ),
        "usage_count": int(part.get("usageCount") or 0),
        "selected": selected,
        "review_required": not (nucleotide_exact or translated_exact),
        "selection_method": (
            "canonical source-label alias, expected iGEM role, and "
            "sequence/translation evidence"
            if canonical
            else "ranked public search with expected iGEM role and "
            "sequence/translation evidence"
        ),
        "evidence": evidence,
        "source": {str(key): value for key, value in provenance.items()},
    }


def _normalize_translation(sequence: str) -> str:
    return re.sub(r"[^A-Z*]", "", sequence.upper()).rstrip("*")


def _same_length_identity(left: str, right: str) -> float | None:
    if not left or len(left) != len(right):
        return None
    return round(
        100 * sum(a == b for a, b in zip(left, right, strict=True)) / len(left), 3
    )


def _igem_part_sort_key(
    part: Mapping[str, Any],
) -> tuple[int, int, int, int, float, int]:
    evidence = part.get("evidence")
    evidence_mapping = evidence if isinstance(evidence, Mapping) else {}
    identity = evidence_mapping.get("same_length_nucleotide_identity_percent")
    return (
        int(bool(evidence_mapping.get("canonical_alias"))),
        int(bool(evidence_mapping.get("expected_functional_role"))),
        int(bool(evidence_mapping.get("nucleotide_exact"))),
        int(bool(evidence_mapping.get("translated_peptide_exact"))),
        float(identity) if isinstance(identity, (int, float)) else -1.0,
        int(part.get("usage_count") or 0),
    )


def parse_rebase_enzymes(text: str) -> dict[str, dict[str, Any]]:
    """Parse the REBASE EMBOSS enzyme-pattern file."""
    enzymes: dict[str, dict[str, Any]] = {}
    for line in _data_lines(text):
        fields = line.split()
        if len(fields) != REBASE_ENZYME_FIELD_COUNT:
            raise ExternalSourceError(f"Malformed REBASE enzyme row: {line}")
        name, recognition_site = fields[:2]
        try:
            length, cut_count, blunt, cut_5, cut_3, second_5, second_3 = map(
                int, fields[2:]
            )
        except ValueError as exc:
            raise ExternalSourceError(f"Malformed REBASE cut geometry: {line}") from exc
        enzymes[name] = {
            "name": name,
            "recognition_site": recognition_site.upper(),
            "recognition_length": length,
            "cut_count": cut_count,
            "blunt": bool(blunt),
            "cut_5prime": cut_5,
            "cut_3prime": cut_3,
            "second_cut_5prime": second_5,
            "second_cut_3prime": second_3,
        }
    return enzymes


def parse_rebase_suppliers(text: str) -> dict[str, str]:
    """Parse the REBASE EMBOSS supplier file."""
    suppliers: dict[str, str] = {}
    for line in _data_lines(text):
        code, separator, name = line.partition(" ")
        if len(code) != 1 or not separator or not name.strip():
            raise ExternalSourceError(f"Malformed REBASE supplier row: {line}")
        suppliers[code] = name.strip()
    return suppliers


def parse_rebase_references(text: str) -> dict[str, dict[str, Any]]:
    """Parse supplier and source fields from REBASE EMBOSS reference records."""
    records: dict[str, dict[str, Any]] = {}
    blocks = re.split(r"^//\s*$", text, flags=re.MULTILINE)
    for block in blocks:
        lines = [
            line.rstrip() for line in block.splitlines() if not line.startswith("#")
        ]
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            continue
        if len(lines) < REBASE_REFERENCE_HEADER_FIELD_COUNT:
            raise ExternalSourceError(f"Malformed REBASE reference entry: {lines[0]}")
        try:
            reference_count = int(lines[6].strip())
        except ValueError as exc:
            raise ExternalSourceError(
                f"Malformed REBASE reference count for {lines[0]}"
            ) from exc
        supplier_codes = list(lines[5].strip())
        records[lines[0].strip()] = {
            "organism": lines[1].strip(),
            "isoschizomers": [
                item.strip() for item in lines[2].split(",") if item.strip()
            ],
            "methylation": lines[3].strip(),
            "source": lines[4].strip(),
            "supplier_codes": supplier_codes,
            "reference_count": reference_count,
        }
    return records


def _data_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _parse_rebase_release(text: str) -> str:
    match = re.search(r"REBASE version\s+(\d+)", text)
    if not match:
        raise ExternalSourceError("REBASE file has no release number")
    return match.group(1)


def _parse_rebase_release_date(text: str) -> str:
    match = re.search(r"\b([A-Z][a-z]{2}\s+\d{1,2}\s+\d{4})\b", text)
    return match.group(1) if match else "unknown"


def _biopython_neb_names() -> tuple[set[str], str]:
    try:
        from Bio import __version__ as biopython_version
        from Bio.Restriction import Restriction_Dictionary
    except ModuleNotFoundError:
        return set(), "not installed"
    names = {str(name) for name in Restriction_Dictionary.suppliers["N"][1]}
    return names, biopython_version


def _igem_role_alias_index(
    roles: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    aliases: dict[str, dict[str, dict[str, str]]] = {}
    for role in roles:
        term = {
            "accession": str(role.get("accession") or ""),
            "label": str(role.get("label") or ""),
            "definition": str(role.get("definition") or ""),
            "source": str(role.get("source") or ""),
        }
        raw_aliases = [term["label"], *list(role.get("synonyms") or [])]
        for raw_alias in raw_aliases:
            alias = normalize_label(str(raw_alias))
            if alias:
                aliases.setdefault(alias, {})[term["accession"]] = term
    return {
        alias: sorted(terms.values(), key=lambda term: term["accession"])
        for alias, terms in sorted(aliases.items())
    }


def _igem_category_alias_index(
    categories: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    aliases: dict[str, dict[str, dict[str, str]]] = {}
    for category in categories:
        category_path = _category_path(category)
        term = {
            "uuid": str(category.get("uuid") or ""),
            "path": category_path,
            "description": str(category.get("description") or ""),
        }
        raw_aliases = [category_path, category_path.rsplit("/", 1)[-1]]
        for raw_alias in raw_aliases:
            alias = normalize_label(raw_alias)
            if alias:
                aliases.setdefault(alias, {})[term["uuid"]] = term
    return {
        alias: sorted(terms.values(), key=lambda term: term["path"])
        for alias, terms in sorted(aliases.items())
    }


def _category_path(category: Mapping[str, Any]) -> str:
    return str(category.get("value") or category.get("label") or "")


def _selected_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    selected = {}
    for key in (
        "Content-Type",
        "Content-Length",
        "ETag",
        "Last-Modified",
        "X-RateLimit-Limit-Short",
        "X-RateLimit-Limit-Medium",
        "X-RateLimit-Limit-Large",
    ):
        value = headers.get(key)
        if value is not None:
            selected[key.casefold()] = str(value)
    return selected


class _CurlResponse:
    def __init__(self, body: bytes, headers: dict[str, str], final_url: str) -> None:
        self._body = body
        self.headers = headers
        self._final_url = final_url

    def __enter__(self) -> _CurlResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._final_url


def _default_open_url(request: Request, *, timeout: float) -> Any:
    curl = shutil.which("curl")
    if curl is None:
        return urlopen(request, timeout=timeout)
    with tempfile.TemporaryDirectory(prefix="lab-bench-source-fetch-") as temp_dir:
        temp_path = Path(temp_dir)
        body_path = temp_path / "body"
        headers_path = temp_path / "headers"
        command = [
            curl,
            "--fail-with-body",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(timeout),
            "--dump-header",
            str(headers_path),
            "--output",
            str(body_path),
            "--write-out",
            "%{url_effective}",
        ]
        for key, value in request.header_items():
            command.extend(["--header", f"{key}: {value}"])
        command.append(request.full_url)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout + 5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise URLError(str(exc)) from exc
        if result.returncode != 0:
            raise URLError((result.stderr or "curl request failed").strip())
        body = body_path.read_bytes()
        headers = _parse_curl_headers(headers_path.read_text(errors="replace"))
        return _CurlResponse(body, headers, result.stdout.strip() or request.full_url)


def _parse_curl_headers(text: str) -> dict[str, str]:
    blocks = [block for block in re.split(r"\r?\n\r?\n", text) if block.strip()]
    header_block = next(
        (block for block in reversed(blocks) if block.startswith("HTTP/")), ""
    )
    headers: dict[str, str] = {}
    for line in header_block.splitlines()[1:]:
        key, separator, value = line.partition(":")
        if separator:
            headers[key.strip()] = value.strip()
    return headers


def _retry_delay(headers: Any, attempt: int) -> float:
    retry_after = headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(0.0, min(float(retry_after), 120.0))
        except ValueError:
            pass
    return float(2**attempt)

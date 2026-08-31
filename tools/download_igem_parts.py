#!/usr/bin/env python3
"""Download iGEM Registry parts as annotated GenBank and optional FASTA files.

The legacy ``parts.igem.org/cgi/xml/part.cgi`` endpoint is no longer reliable.
This tool uses the current Registry API, resolves human-readable part names to
UUIDs, downloads the Registry's GenBank export, and augments it with subpart and
sequence-feature annotations exposed by the API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

API_BASE = "https://api.registry.igem.org/v1"
REGISTRY_BASE = "https://registry.igem.org"
USER_AGENT = "igem-parts-downloader/1.0 (+https://registry.igem.org)"
DEFAULT_REQUEST_DELAY = 1.1
DEFAULT_PAGE_SIZE = 100
MIN_PART_URL_SEGMENTS = 2
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_MIN = 500
HTTP_SERVER_ERROR_MAX = 600

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class IGEMError(RuntimeError):
    """Raised when a Registry request or downloaded record is invalid."""


def _verified_ssl_context() -> ssl.SSLContext:
    """Use Certifi when Python.org macOS builds have no configured CA file."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


@dataclass(frozen=True)
class HTTPResponse:
    body: bytes
    headers: Mapping[str, str]
    url: str


@dataclass(frozen=True)
class DownloadResult:
    part_name: str
    genbank_path: Path
    metadata_path: Path | None
    fasta_path: Path | None
    added_annotations: int
    annotation_warnings: tuple[str, ...]


def normalize_part_identifier(value: str) -> str:
    """Convert an iGEM accession or Registry URL to its current API slug."""
    candidate = value.strip()
    if not candidate:
        raise ValueError("Part identifier cannot be empty")

    if "://" in candidate:
        parsed = urlparse(candidate)
        host = parsed.netloc.lower()
        supported_hosts = {
            "parts.igem.org",
            "registry.igem.org",
            "www.parts.igem.org",
            "www.registry.igem.org",
        }
        if host not in supported_hosts:
            raise ValueError(f"Not an iGEM Registry URL: {value!r}")
        path_parts = [part for part in parsed.path.split("/") if part]
        if host.endswith("parts.igem.org") and path_parts and path_parts[-1].lower().startswith("part:"):
            candidate = path_parts[-1]
        elif len(path_parts) >= MIN_PART_URL_SEGMENTS and path_parts[-2].lower() == "parts":
            candidate = path_parts[-1]
        else:
            raise ValueError(f"Registry URL does not identify a part: {value!r}")

    if candidate.lower().startswith("part:"):
        candidate = candidate[5:]

    slug = candidate.lower().replace("_", "-")
    if not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"Invalid iGEM part identifier: {value!r}")
    return slug


class IGEMClient:
    """Small, dependency-free client for the public iGEM Registry API."""

    def __init__(
        self,
        *,
        api_base: str = API_BASE,
        request_delay: float = DEFAULT_REQUEST_DELAY,
        retries: int = 4,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.request_delay = max(0.0, request_delay)
        self.retries = max(0, retries)
        self.timeout = timeout
        self._sleep = sleep
        self._ssl_context = ssl_context or _verified_ssl_context()
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            wait = self.request_delay - (time.monotonic() - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _retry_delay(error: HTTPError, attempt: int) -> float:
        retry_after = error.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return min(16.0, 2.0**attempt)

    def request(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        accept: str = "application/json",
        extra_headers: Mapping[str, str] | None = None,
    ) -> HTTPResponse:
        """Make a throttled API request with retries for transient failures."""
        url = f"{self.api_base}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {"Accept": accept, "User-Agent": USER_AGENT}
        if extra_headers:
            headers.update(extra_headers)
        request = Request(url, headers=headers)

        for attempt in range(self.retries + 1):
            self._throttle()
            try:
                with urlopen(  # noqa: S310
                    request,
                    timeout=self.timeout,
                    context=self._ssl_context,
                ) as response:
                    headers = {key.lower(): value for key, value in response.headers.items()}
                    return HTTPResponse(response.read(), headers, response.geturl())
            except HTTPError as error:
                retryable = (
                    error.code == HTTP_TOO_MANY_REQUESTS
                    or HTTP_SERVER_ERROR_MIN <= error.code < HTTP_SERVER_ERROR_MAX
                )
                if retryable and attempt < self.retries:
                    self._sleep(self._retry_delay(error, attempt))
                    continue
                detail = error.read(500).decode("utf-8", errors="replace").strip()
                suffix = f": {detail}" if detail else ""
                raise IGEMError(f"iGEM API returned HTTP {error.code} for {url}{suffix}") from error
            except URLError as error:
                if attempt < self.retries:
                    self._sleep(min(16.0, 2.0**attempt))
                    continue
                raise IGEMError(f"Could not reach iGEM API at {url}: {error.reason}") from error

        raise AssertionError("request retry loop ended unexpectedly")

    def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        response = self.request(path, params=params)
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise IGEMError(f"iGEM API returned invalid JSON from {response.url}") from error
        if not isinstance(payload, dict):
            raise IGEMError(f"iGEM API returned an unexpected JSON value from {response.url}")
        return payload

    def fetch_part(self, identifier: str) -> dict[str, Any]:
        candidate = identifier.strip()
        if _UUID_RE.fullmatch(candidate):
            part = self.get_json(f"parts/{quote(candidate)}")
        else:
            slug = normalize_part_identifier(candidate)
            part = self.get_json(f"parts/slugs/{quote(slug)}")
        if not isinstance(part.get("uuid"), str) or not isinstance(part.get("name"), str):
            raise IGEMError(f"Registry response for {identifier!r} is missing its UUID or name")
        return part

    def fetch_paginated(self, path: str) -> list[dict[str, Any]]:
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            payload = self.get_json(
                path,
                params={"page": page, "pageSize": DEFAULT_PAGE_SIZE},
            )
            data = payload.get("data")
            if not isinstance(data, list):
                raise IGEMError(f"Registry paginated response from {path!r} has no data list")
            items.extend(item for item in data if isinstance(item, dict))
            total = payload.get("total")
            if not data or not isinstance(total, int) or len(items) >= total:
                return items
            page += 1

    def fetch_genbank(self, part_uuid: str) -> str:
        response = self.request(
            f"parts/{quote(part_uuid)}.gb",
            accept="chemical/x-genbank,text/plain;q=0.9",
        )
        try:
            genbank = response.body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise IGEMError(f"Registry GenBank export for {part_uuid} is not UTF-8") from error
        validate_genbank(genbank)
        return genbank

    def fetch_fasta(self, part_uuid: str) -> bytes:
        response = self.request(
            f"parts/{quote(part_uuid)}.fasta",
            accept="chemical/x-fasta,text/plain;q=0.9",
        )
        if not response.body.lstrip().startswith(b">"):
            raise IGEMError(f"Registry FASTA export for {part_uuid} is invalid")
        return response.body


def validate_genbank(genbank: str) -> None:
    stripped = genbank.lstrip()
    if not stripped.startswith("LOCUS "):
        raise IGEMError("Registry GenBank export does not start with a LOCUS record")
    if "\nFEATURES " not in genbank or "\nORIGIN" not in genbank:
        raise IGEMError("Registry GenBank export is missing FEATURES or ORIGIN")
    if not genbank.rstrip().endswith("//"):
        raise IGEMError("Registry GenBank export is incomplete")


def _role_details(annotation: Mapping[str, Any]) -> tuple[str, str]:
    role = annotation.get("role")
    if not isinstance(role, Mapping):
        return "", ""
    label = role.get("label")
    accession = role.get("accession")
    return (
        label if isinstance(label, str) else "",
        accession if isinstance(accession, str) else "",
    )


def _feature_key(role_label: str, accession: str) -> str:
    by_accession = {
        "SO:0000139": "RBS",
        "SO:0000141": "terminator",
        "SO:0000167": "promoter",
        "SO:0000296": "rep_origin",
        "SO:0000316": "CDS",
        "SO:0000552": "polyA_signal",
        "SO:0000704": "gene",
    }
    if accession in by_accession:
        return by_accession[accession]
    normalized = role_label.casefold().replace("_", " ").replace("-", " ")
    by_label = {
        "cds": "CDS",
        "coding sequence": "CDS",
        "gene": "gene",
        "operator": "regulatory",
        "origin of replication": "rep_origin",
        "promoter": "promoter",
        "rbs": "RBS",
        "ribosome binding site": "RBS",
        "terminator": "terminator",
    }
    return by_label.get(normalized, "misc_feature")


def _location(
    locations: Iterable[Mapping[str, Any]],
    *,
    strand: str,
    sequence_length: int,
) -> str:
    segments: list[str] = []
    for location in locations:
        start = location.get("start")
        end = location.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("feature location is not an integer range")
        if start < 1 or end < start or end > sequence_length:
            raise ValueError(f"feature location {start}..{end} is outside 1..{sequence_length}")
        segments.append(str(start) if start == end else f"{start}..{end}")
    if not segments:
        raise ValueError("feature has no locations")
    result = segments[0] if len(segments) == 1 else f"join({','.join(segments)})"
    if strand.casefold() == "reverse":
        result = f"complement({result})"
    return result


def _clean_qualifier(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().replace('"', "'")


def _qualifier(name: str, value: Any) -> str:
    # Values emitted here are deliberately concise, so preserving one qualifier
    # per line is both GenBank-compatible and friendlier to SnapGene import.
    cleaned = _clean_qualifier(value)
    return f"{'':21}/{name}=\"{cleaned}\"\n"


def _feature_block(
    *,
    key: str,
    location: str,
    label: str,
    note: str,
) -> str:
    return (
        f"     {key:<16}{location}\n"
        + _qualifier("label", label)
        + _qualifier("note", note)
    )


def _existing_feature_labels(genbank: str) -> set[str]:
    feature_table = genbank.split("\nORIGIN", maxsplit=1)[0]
    return {
        match.group(1).casefold()
        for match in re.finditer(r'^\s+/label="([^"]+)"\s*$', feature_table, re.MULTILINE)
    }


def enrich_genbank(
    genbank: str,
    *,
    sequence_length: int,
    sequence_features: Iterable[Mapping[str, Any]],
    composition: Iterable[Mapping[str, Any]],
) -> tuple[str, int, tuple[str, ...]]:
    """Add API feature and composition annotations missing from an export."""
    validate_genbank(genbank)
    existing_labels = _existing_feature_labels(genbank)
    additions: list[str] = []
    warnings: list[str] = []

    annotations: list[tuple[str, Mapping[str, Any]]] = [
        *(('sequence feature', item) for item in sequence_features),
        *(('component', item) for item in composition),
    ]
    for kind, annotation in annotations:
        if kind == "component":
            label_value = annotation.get("componentName")
            ranges: list[Mapping[str, Any]] = [annotation]
        else:
            label_value = annotation.get("label")
            locations = annotation.get("locations")
            ranges = (
                [item for item in locations if isinstance(item, Mapping)]
                if isinstance(locations, list)
                else []
            )
        label = _clean_qualifier(label_value or kind.title())
        if label.casefold() in existing_labels:
            continue

        strand = annotation.get("strand")
        try:
            location = _location(
                ranges,
                strand=strand if isinstance(strand, str) else "forward",
                sequence_length=sequence_length,
            )
        except ValueError as error:
            warnings.append(f"Skipped {kind} {label!r}: {error}")
            continue

        role_label, accession = _role_details(annotation)
        note_parts = [f"iGEM {kind}"]
        if role_label:
            note_parts.append(f"{role_label} ({accession})" if accession else role_label)
        uuid = annotation.get("componentUUID") or annotation.get("uuid")
        if isinstance(uuid, str):
            note_parts.append(f"UUID {uuid}")
        additions.append(
            _feature_block(
                key=_feature_key(role_label, accession),
                location=location,
                label=label,
                note="; ".join(note_parts),
            )
        )
        existing_labels.add(label.casefold())

    if not additions:
        return genbank, 0, tuple(warnings)
    marker = "\nORIGIN"
    enriched = genbank.replace(marker, "\n" + "".join(additions).rstrip("\n") + marker, 1)
    validate_genbank(enriched)
    return enriched, len(additions), tuple(warnings)


def _safe_filename(value: str) -> str:
    safe = _SAFE_FILENAME_RE.sub("_", value).strip("._")
    if not safe:
        raise IGEMError(f"Registry returned an unsafe empty filename for {value!r}")
    return safe


def _write(path: Path, data: bytes, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (pass --force to replace it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.part")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_outputs_available(paths: Iterable[Path], *, force: bool) -> None:
    if force:
        return
    existing = [path for path in paths if path.exists()]
    if existing:
        joined = ", ".join(map(str, existing))
        raise FileExistsError(f"output already exists: {joined} (pass --force to replace it)")


def download_part(
    client: IGEMClient,
    identifier: str,
    output_dir: Path,
    *,
    include_fasta: bool = False,
    include_metadata: bool = True,
    force: bool = False,
) -> DownloadResult:
    """Download one part and retain all public annotation API responses."""
    part = client.fetch_part(identifier)
    part_uuid = str(part["uuid"])
    part_name = str(part["name"])
    sequence = part.get("sequence")
    if not isinstance(sequence, str) or not sequence:
        raise IGEMError(f"{part_name} has no public DNA sequence")

    base_name = _safe_filename(part_name)
    genbank_path = output_dir / f"{base_name}.gb"
    metadata_path = output_dir / f"{base_name}.igem.json" if include_metadata else None
    fasta_path = output_dir / f"{base_name}.fasta" if include_fasta else None
    _ensure_outputs_available(
        (path for path in (genbank_path, metadata_path, fasta_path) if path is not None),
        force=force,
    )

    sequence_features = client.fetch_paginated(f"parts/{quote(part_uuid)}/sequence-features")
    composition = client.fetch_paginated(f"parts/{quote(part_uuid)}/composition")
    genbank = client.fetch_genbank(part_uuid)
    genbank, added, warnings = enrich_genbank(
        genbank,
        sequence_length=len(sequence),
        sequence_features=sequence_features,
        composition=composition,
    )
    fasta = client.fetch_fasta(part_uuid) if fasta_path is not None else None

    _write(genbank_path, genbank.encode("utf-8"), force=force)
    if metadata_path is not None:
        metadata = {
            "part": part,
            "sequenceFeatures": sequence_features,
            "composition": composition,
            "downloads": {
                "registry": f"{REGISTRY_BASE}/parts/{part.get('slug', '')}",
                "genbank": f"{client.api_base}/parts/{part_uuid}.gb",
                "fasta": f"{client.api_base}/parts/{part_uuid}.fasta",
            },
            "genbankEnrichment": {
                "annotationsAdded": added,
                "warnings": list(warnings),
            },
        }
        _write(
            metadata_path,
            (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode(),
            force=force,
        )
    if fasta_path is not None and fasta is not None:
        _write(fasta_path, fasta, force=force)

    return DownloadResult(
        part_name=part_name,
        genbank_path=genbank_path,
        metadata_path=metadata_path,
        fasta_path=fasta_path,
        added_annotations=added,
        annotation_warnings=warnings,
    )


def _identifiers_from_file(path: Path) -> list[str]:
    identifiers: list[str] = []
    for line in path.read_text().splitlines():
        content = line.split("#", maxsplit=1)[0]
        identifiers.extend(value for value in re.split(r"[,\s]+", content) if value)
    return identifiers


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download iGEM parts from the current Registry API as annotated GenBank "
            "files that can be opened by SnapGene."
        )
    )
    parser.add_argument("parts", nargs="*", help="Part accessions, slugs, UUIDs, or Registry URLs")
    parser.add_argument(
        "--from-file",
        type=Path,
        action="append",
        default=[],
        help="Read comma- or whitespace-separated part identifiers from a file",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("igem-parts"))
    parser.add_argument("--fasta", action="store_true", help="Also download FASTA files")
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not save the full iGEM metadata/annotation JSON sidecar",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing output files")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY,
        help=f"Seconds between API calls (default: {DEFAULT_REQUEST_DELAY})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    identifiers = list(args.parts)
    try:
        for path in args.from_file:
            identifiers.extend(_identifiers_from_file(path))
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if not identifiers:
        print("error: provide at least one part or use --from-file", file=sys.stderr)
        return 2

    client = IGEMClient(request_delay=args.request_delay)
    failures = 0
    for identifier in identifiers:
        try:
            result = download_part(
                client,
                identifier,
                args.output,
                include_fasta=args.fasta,
                include_metadata=not args.no_metadata,
                force=args.force,
            )
        except (IGEMError, OSError, ValueError) as error:
            failures += 1
            print(f"FAILED {identifier}: {error}", file=sys.stderr)
            continue
        paths = [result.genbank_path]
        if result.metadata_path is not None:
            paths.append(result.metadata_path)
        if result.fasta_path is not None:
            paths.append(result.fasta_path)
        print(
            f"Downloaded {result.part_name}: {', '.join(map(str, paths))} "
            f"({result.added_annotations} API annotations added)"
        )
        for warning in result.annotation_warnings:
            print(f"  warning: {warning}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

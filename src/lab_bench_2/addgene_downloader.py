"""Rate-limited, validated Addgene GenBank downloads.

The durable batch path is Addgene's read-only Developers API. The API requires
an approved Catalog token; this module deliberately does not read browser
profiles, cookies, usernames, or passwords.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from email.message import Message
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

API_BASE = "https://api.developers.addgene.org"
API_HOST = urlsplit(API_BASE).hostname
DEFAULT_USER_AGENT = (
    "lab-bench-cloning-inventory/0.1 (+https://github.com/Generality-Labs/lab-bench)"
)
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
HTTP_OK = 200
HTTP_NOT_FOUND = 404
SEQUENCE_BUCKETS = {
    "addgene": ("public_addgene_full_sequences",),
    "depositor": ("public_user_full_sequences",),
    "preferred": (
        "public_addgene_full_sequences",
        "public_user_full_sequences",
    ),
    "all": (
        "public_addgene_full_sequences",
        "public_user_full_sequences",
    ),
}


class AddgeneDownloadError(RuntimeError):
    """A safe, user-actionable Addgene download failure."""


@dataclass(frozen=True)
class HttpResponse:
    """Minimal HTTP response used by the downloader and its tests."""

    status: int
    url: str
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class DownloadRecord:
    """Provenance and validation details for one downloaded sequence."""

    plasmid_id: int
    status: str
    source_bucket: str
    sequence_id: str
    sequence_name: str
    download_url: str
    filename: str
    sha256: str
    length: int
    topology: str
    feature_count: int


RequestFunction = Callable[[str, Mapping[str, str]], HttpResponse]
SleepFunction = Callable[[float], None]


def parse_plasmid_id(value: str | int) -> int:
    """Parse an Addgene integer id or canonical plasmid URL."""
    if isinstance(value, int):
        plasmid_id = value
    else:
        candidate = value.strip()
        if candidate.isdigit():
            plasmid_id = int(candidate)
        else:
            match = re.fullmatch(r"https?://(?:www\.)?addgene\.org/(\d+)/?", candidate)
            if not match:
                raise ValueError(
                    f"Expected an Addgene plasmid id or /<id>/ URL, got {value!r}"
                )
            plasmid_id = int(match.group(1))
    if plasmid_id <= 0:
        raise ValueError(f"Addgene plasmid ids must be positive, got {plasmid_id}")
    return plasmid_id


class AddgeneDownloader:
    """Download full annotated GenBank records from Addgene's Developers API."""

    def __init__(
        self,
        *,
        token: str | None = None,
        proxy_url: str | None = None,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        request: RequestFunction | None = None,
        sleep: SleepFunction = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if min_delay < 0 or max_delay < min_delay:
            raise ValueError("Require 0 <= min_delay <= max_delay")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.token = (token or os.environ.get("ADDGENE_TOKEN", "")).strip()
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._sleep = sleep
        self._random_uniform = random_uniform
        self._request_count = 0
        self._request = request or self._build_request(proxy_url)

    @staticmethod
    def _build_request(proxy_url: str | None) -> RequestFunction:
        # With no explicit proxy, ProxyHandler reads the standard *_PROXY env vars.
        proxy_handler = ProxyHandler(
            {"http": proxy_url, "https": proxy_url} if proxy_url else None
        )
        opener = build_opener(proxy_handler)

        def request(url: str, headers: Mapping[str, str]) -> HttpResponse:
            req = Request(url, headers=dict(headers))
            try:
                with opener.open(req, timeout=30) as response:
                    return HttpResponse(
                        status=response.status,
                        url=response.url,
                        headers=dict(response.headers.items()),
                        body=response.read(),
                    )
            except HTTPError as exc:
                return HttpResponse(
                    status=exc.code,
                    url=exc.url,
                    headers=dict(exc.headers.items()),
                    body=exc.read(),
                )
            except URLError as exc:
                raise AddgeneDownloadError(
                    f"Network error reaching Addgene: {exc.reason}"
                ) from exc

        return request

    def _headers(self, url: str, accept: str) -> dict[str, str]:
        headers = {"Accept": accept, "User-Agent": self.user_agent}
        # Never forward the API token to a URL returned by the API unless it is
        # still on the exact official API host.
        if self.token and urlsplit(url).hostname == API_HOST:
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def _polite_delay(self) -> None:
        if self._request_count:
            self._sleep(self._random_uniform(self.min_delay, self.max_delay))

    def _get(self, url: str, accept: str) -> HttpResponse:
        for attempt in range(self.max_retries + 1):
            self._polite_delay()
            self._request_count += 1
            response = self._request(url, self._headers(url, accept))
            if response.status == HTTP_OK:
                return response
            if response.status in {401, 403}:
                raise AddgeneDownloadError(
                    "Addgene rejected the request. Confirm ADDGENE_TOKEN is valid "
                    "and approved for the Catalog scope."
                )
            if response.status == HTTP_NOT_FOUND:
                raise AddgeneDownloadError(f"Addgene resource not found: {url}")
            if (
                response.status not in RETRYABLE_STATUS_CODES
                or attempt >= self.max_retries
            ):
                raise AddgeneDownloadError(
                    f"Addgene returned HTTP {response.status} for {url}"
                )
            retry_after = _retry_after_seconds(response.headers)
            backoff = min(60.0, 2.0**attempt)
            self._sleep(max(retry_after, backoff))
        raise AssertionError("unreachable")

    def _plasmid_metadata(self, plasmid_id: int) -> dict[str, Any]:
        if not self.token:
            raise AddgeneDownloadError(
                "Batch Addgene sequence access requires ADDGENE_TOKEN with the "
                "Catalog scope. Request access at https://developers.addgene.org/. "
                "This tool intentionally does not extract cookies from signed-in browsers."
            )
        url = f"{API_BASE}/catalog/plasmid-with-sequences/{plasmid_id}/"
        response = self._get(url, "application/json")
        try:
            data = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AddgeneDownloadError(
                f"Addgene returned invalid JSON for plasmid {plasmid_id}"
            ) from exc
        if not isinstance(data, dict):
            raise AddgeneDownloadError(
                f"Addgene returned an unexpected payload for plasmid {plasmid_id}"
            )
        return data

    def _sequence_entries(
        self, metadata: Mapping[str, Any], policy: str
    ) -> list[tuple[str, Mapping[str, Any]]]:
        if policy not in SEQUENCE_BUCKETS:
            raise ValueError(f"Unknown sequence-source policy: {policy}")
        sequences = metadata.get("sequences") or {}
        if not isinstance(sequences, dict):
            return []
        entries: list[tuple[str, Mapping[str, Any]]] = []
        for bucket in SEQUENCE_BUCKETS[policy]:
            candidates = sequences.get(bucket) or []
            bucket_entries: list[tuple[str, Mapping[str, Any]]] = []
            if isinstance(candidates, list):
                bucket_entries.extend(
                    (bucket, entry) for entry in candidates if isinstance(entry, dict)
                )
            bucket_entries = [
                entry for entry in bucket_entries if entry[1].get("genbank_url")
            ]
            entries.extend(bucket_entries)
            if bucket_entries and policy == "preferred":
                break
        seen_urls: set[str] = set()
        unique_entries = []
        for entry in entries:
            url = str(entry[1]["genbank_url"])
            if url not in seen_urls:
                seen_urls.add(url)
                unique_entries.append(entry)
        return unique_entries

    def download_plasmid(
        self,
        plasmid_id: int,
        output_dir: Path,
        *,
        sequence_source: str = "preferred",
        refresh: bool = False,
    ) -> list[DownloadRecord]:
        """Download every full GBK selected by ``sequence_source`` for one plasmid."""
        output_dir.mkdir(parents=True, exist_ok=True)
        if not refresh and sequence_source == "preferred":
            cached = self._cached_records(plasmid_id, output_dir)
            if cached:
                return cached

        metadata = self._plasmid_metadata(plasmid_id)
        entries = self._sequence_entries(metadata, sequence_source)
        if not entries:
            raise AddgeneDownloadError(
                f"Addgene {plasmid_id} has no public full GenBank sequence "
                f"for policy {sequence_source!r}."
            )

        records = []
        for bucket, entry in entries:
            url = str(entry["genbank_url"])
            if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
                raise AddgeneDownloadError(
                    f"Addgene returned an unsafe GenBank URL for plasmid {plasmid_id}"
                )
            response = self._get(url, "text/plain,application/octet-stream;q=0.9")
            stats = validate_genbank(response.body)
            filename = _download_filename(
                response.headers,
                response.url,
                plasmid_id=plasmid_id,
                sequence_id=str(entry.get("id") or "unknown"),
            )
            destination = output_dir / filename
            _atomic_write(destination, response.body)
            records.append(
                DownloadRecord(
                    plasmid_id=plasmid_id,
                    status="downloaded",
                    source_bucket=bucket,
                    sequence_id=str(entry.get("id") or ""),
                    sequence_name=str(entry.get("name") or ""),
                    download_url=url,
                    filename=filename,
                    sha256=hashlib.sha256(response.body).hexdigest(),
                    length=stats["length"],
                    topology=stats["topology"],
                    feature_count=stats["feature_count"],
                )
            )
        return records

    def _cached_records(
        self, plasmid_id: int, output_dir: Path
    ) -> list[DownloadRecord]:
        cached = []
        for path in sorted(output_dir.glob(f"addgene-plasmid-{plasmid_id}-*.gbk")):
            try:
                body = path.read_bytes()
                stats = validate_genbank(body)
            except (OSError, AddgeneDownloadError):
                continue
            cached.append(
                DownloadRecord(
                    plasmid_id=plasmid_id,
                    status="cached",
                    source_bucket="cached",
                    sequence_id="",
                    sequence_name="",
                    download_url="",
                    filename=path.name,
                    sha256=hashlib.sha256(body).hexdigest(),
                    length=stats["length"],
                    topology=stats["topology"],
                    feature_count=stats["feature_count"],
                )
            )
        return cached

    def download_many(
        self,
        plasmid_ids: list[int],
        output_dir: Path,
        *,
        sequence_source: str = "preferred",
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Download a list while preserving successes when individual ids fail."""
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for plasmid_id in dict.fromkeys(plasmid_ids):
            try:
                downloaded = self.download_plasmid(
                    plasmid_id,
                    output_dir,
                    sequence_source=sequence_source,
                    refresh=refresh,
                )
                results.extend(asdict(record) for record in downloaded)
            except AddgeneDownloadError as exc:
                errors.append({"plasmid_id": plasmid_id, "error": str(exc)})
        return {
            "schema_version": 1,
            "sequence_source": sequence_source,
            "results": results,
            "errors": errors,
        }


def validate_genbank(body: bytes) -> dict[str, Any]:
    """Parse a single GenBank record and return basic validation statistics."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AddgeneDownloadError(
            "Downloaded sequence is not UTF-8 GenBank text"
        ) from exc
    if not text.lstrip().startswith("LOCUS"):
        raise AddgeneDownloadError(
            "Downloaded response is not GenBank text (missing LOCUS header)"
        )
    try:
        from Bio import SeqIO

        record = SeqIO.read(  # type: ignore[no-untyped-call]
            io.StringIO(text), "genbank"
        )
    except (ImportError, ValueError) as exc:
        raise AddgeneDownloadError(f"Downloaded GenBank did not parse: {exc}") from exc
    if not record.seq:
        raise AddgeneDownloadError("Downloaded GenBank contains an empty sequence")
    return {
        "length": len(record.seq),
        "topology": str(record.annotations.get("topology") or "unknown"),
        "feature_count": len(record.features),
    }


def _retry_after_seconds(headers: Mapping[str, str]) -> float:
    value = next((v for key, v in headers.items() if key.lower() == "retry-after"), "0")
    try:
        return min(120.0, max(0.0, float(value)))
    except ValueError:
        return 0.0


def _download_filename(
    headers: Mapping[str, str],
    response_url: str,
    *,
    plasmid_id: int,
    sequence_id: str,
) -> str:
    filename = ""
    disposition = next(
        (v for key, v in headers.items() if key.lower() == "content-disposition"),
        "",
    )
    if disposition:
        message = Message()
        message["content-disposition"] = disposition
        filename = message.get_filename() or ""
    if not filename:
        filename = Path(unquote(urlsplit(response_url).path)).name
    expected_prefix = f"addgene-plasmid-{plasmid_id}-"
    if not filename.lower().endswith(
        (".gb", ".gbk", ".gbff")
    ) or not filename.casefold().startswith(expected_prefix):
        filename = f"addgene-plasmid-{plasmid_id}-sequence-{sequence_id}.gbk"
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")
    if not filename:
        raise AddgeneDownloadError("Could not derive a safe output filename")
    return filename


def _atomic_write(path: Path, body: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(body)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

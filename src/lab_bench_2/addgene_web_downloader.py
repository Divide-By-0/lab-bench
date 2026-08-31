"""Scale-oriented Addgene GBK downloads through a signed-in Chrome session.

Discovery uses public Addgene HTML and the public sequence-file-collection
API. The GenBank bytes themselves are gated by Addgene's 15-minute
media-edge cookie. Cookies are read from Chrome, refreshed from
www.addgene.org Set-Cookie, cached at ~/.cache/lab-bench-addgene/cookies.json
(mode 0600), and never written to git or download manifests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from lab_bench_2.addgene_downloader import (
    HTTP_NOT_FOUND,
    HTTP_OK,
    RETRYABLE_STATUS_CODES,
    AddgeneDownloadError,
    DownloadRecord,
    HttpResponse,
    RequestFunction,
    SleepFunction,
    _atomic_write,
    _download_filename,
    _retry_after_seconds,
    validate_genbank,
)

SITE_ORIGIN = "https://www.addgene.org"
COLLECTION_API = SITE_ORIGIN + "/api/get-sequence-file-collection/{sequence_id}/"
# Media-edge auth is a 15-minute cookie minted on www.addgene.org HTML
# responses. A non-browser UA makes those responses omit the cookie.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ADDGENE_HOST_SUFFIX = ".addgene.org"
CHROME_SAFE_STORAGE_SERVICE = "Chrome Safe Storage"
CHROME_SAFE_STORAGE_ACCOUNTS = ("Chrome", "Google Chrome")
# Chromium prepends a SHA-256 digest to OSCrypt plaintext on macOS.
CHROME_COOKIE_DIGEST_PREFIX = 32
CHROME_COOKIE_V10_PREFIX = b"v10"
PBKDF2_ITERATIONS = 1003
PBKDF2_KEY_LEN = 16
SEQUENCE_ID_RE = re.compile(
    r"/browse/sequence/(\d+)/"
    r"|id=[\"'](?:btn-analyze-sequence|sequence-avatar)-(\d+)[\"']"
    r"|/sequences/(\d+)/"
)
SECTION_RE = re.compile(
    r"<section\b([^>]*)>(.*?)</section>",
    re.IGNORECASE | re.DOTALL,
)
SECTION_ID_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.IGNORECASE)
SECTION_BUCKETS = {
    "addgene-full": "public_addgene_full_sequences",
    "user-full": "public_user_full_sequences",
    "depositor-full": "public_user_full_sequences",
}
SEQUENCE_BUCKET_ORDER = {
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
CookieDecryptFunction = Callable[[bytes, bytes], str]
KeychainPasswordFunction = Callable[[], bytes]
MEDIA_COOKIE_NAME = "__Secure_media_edge_auth"
COOKIE_CACHE_DIR = Path.home() / ".cache" / "lab-bench-addgene"
COOKIE_CACHE_FILE = COOKIE_CACHE_DIR / "cookies.json"
MEDIA_COOKIE_REFRESH_SKEW = 60.0
KEEP_FRESH_INTERVAL = 14 * 60.0


@dataclass(frozen=True)
class SequenceEntry:
    """One public full-sequence pointer resolved from Addgene HTML + JSON."""

    plasmid_id: int
    sequence_id: str
    source_bucket: str
    genbank_url: str


def default_chrome_profile() -> Path:
    """Return the macOS Chrome Default profile directory."""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "Google"
        / "Chrome"
        / "Default"
    )


def chrome_cookie_databases(profile: Path) -> list[Path]:
    """Return existing Chrome cookie DB paths for a profile, newest first."""
    candidates = [profile / "Network" / "Cookies", profile / "Cookies"]
    return [path for path in candidates if path.is_file()]


def decrypt_chrome_cookie_value(encrypted: bytes, key: bytes) -> str:
    """Decrypt one Chrome v10 cookie value using the Keychain-derived AES key."""
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if not encrypted.startswith(CHROME_COOKIE_V10_PREFIX):
        raise AddgeneDownloadError("Chrome cookie is not in the supported v10 format")
    # REASON: Chrome still stores macOS cookies as AES-128-CBC with a space IV.
    # The live value is unreadable without this; using AES-GCM here fails because
    # Chromium's macOS OSCrypt path is CBC. Plaintext starts with a 32-byte
    # digest that must be stripped or session cookies look like garbage.
    cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16))
    ciphertext = encrypted[len(CHROME_COOKIE_V10_PREFIX) :]
    plain = cipher.decryptor().update(ciphertext) + cipher.decryptor().finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(plain) + unpadder.finalize()
    if len(data) <= CHROME_COOKIE_DIGEST_PREFIX:
        raise AddgeneDownloadError("Chrome cookie plaintext is shorter than the digest prefix")
    return data[CHROME_COOKIE_DIGEST_PREFIX:].decode("utf-8")


def chrome_os_crypt_key(
    *,
    read_password: KeychainPasswordFunction | None = None,
) -> bytes:
    """Derive Chrome's macOS OSCrypt key from the login Keychain."""
    password = (read_password or _read_chrome_safe_storage_password)()
    return hashlib.pbkdf2_hmac(
        "sha1",
        password,
        b"saltysalt",
        PBKDF2_ITERATIONS,
        dklen=PBKDF2_KEY_LEN,
    )


def load_chrome_addgene_cookies(
    *,
    profile: Path | None = None,
    decrypt: CookieDecryptFunction = decrypt_chrome_cookie_value,
    read_password: KeychainPasswordFunction | None = None,
) -> dict[str, str]:
    """Load Addgene cookies from Chrome into memory. Values are never written."""
    profile_dir = profile or default_chrome_profile()
    databases = chrome_cookie_databases(profile_dir)
    if not databases:
        raise AddgeneDownloadError(
            f"No Chrome cookie database found under {profile_dir}. "
            "Sign in to Addgene in Google Chrome and retry."
        )
    key = chrome_os_crypt_key(read_password=read_password)
    cookies: dict[str, str] = {}
    last_error: str | None = None
    for database in databases:
        try:
            cookies.update(_cookies_from_copied_db(database, key, decrypt))
        except (OSError, sqlite3.Error, AddgeneDownloadError) as exc:
            last_error = str(exc)
            continue
    if "__Secure_media_edge_auth" not in cookies:
        detail = f" ({last_error})" if last_error else ""
        raise AddgeneDownloadError(
            "Chrome has no Addgene media-edge session cookie. Sign in at "
            f"https://www.addgene.org/ and retry.{detail}"
        )
    return cookies


def parse_sequence_sections(html: str) -> dict[str, list[str]]:
    """Extract full-sequence ids in page order, grouped by HTML section."""
    grouped: dict[str, list[str]] = {bucket: [] for bucket in SECTION_BUCKETS.values()}
    seen: set[str] = set()

    def add(bucket: str, sequence_id: str) -> None:
        if sequence_id in seen:
            return
        seen.add(sequence_id)
        grouped.setdefault(bucket, []).append(sequence_id)

    found_section = False
    for attrs, body in SECTION_RE.findall(html):
        match = SECTION_ID_RE.search(attrs)
        if not match:
            continue
        bucket = SECTION_BUCKETS.get(match.group(1))
        if bucket is None:
            continue
        found_section = True
        for sequence_id in _sequence_ids(body):
            add(bucket, sequence_id)
    if not found_section:
        for sequence_id in _sequence_ids(html):
            add("public_addgene_full_sequences", sequence_id)
    return grouped


def select_sequence_ids(
    grouped: Mapping[str, list[str]], policy: str
) -> list[tuple[str, str]]:
    """Apply the same preferred/addgene/depositor/all policy as the API path."""
    if policy not in SEQUENCE_BUCKET_ORDER:
        raise ValueError(f"Unknown sequence-source policy: {policy}")
    selected: list[tuple[str, str]] = []
    for bucket in SEQUENCE_BUCKET_ORDER[policy]:
        entries = [(bucket, sequence_id) for sequence_id in grouped.get(bucket, [])]
        selected.extend(entries)
        if entries and policy == "preferred":
            break
    return selected


def media_cookie_expires_at(cookies: Mapping[str, str]) -> int | None:
    """Return Unix expiry of ``__Secure_media_edge_auth``, if it is a JWT."""
    token = cookies.get(MEDIA_COOKIE_NAME) or ""
    parts = token.split(".")
    if "." not in token:
        return None
    # Addgene's media-edge token puts JSON in the first segment.
    for candidate in (parts[0], parts[1] if len(parts) > 1 else ""):
        padded = candidate + "=" * ((4 - len(candidate) % 4) % 4)
        try:
            data = json.loads(base64.urlsafe_b64decode(padded))
        except (ValueError, json.JSONDecodeError):
            continue
        exp = data.get("exp") if isinstance(data, dict) else None
        if isinstance(exp, int):
            return exp
    return None


def media_seconds_remaining(
    cookies: Mapping[str, str], *, now: float | None = None
) -> float:
    """Seconds until the media-edge cookie expires. Negative means expired."""
    expiry = media_cookie_expires_at(cookies)
    if expiry is None:
        return -1.0
    return float(expiry) - (time.time() if now is None else now)


def save_cookie_cache(
    cookies: Mapping[str, str], path: Path | None = None
) -> Path:
    """Write cookies to the user cache file (mode 0600). Not for git."""
    destination = path or COOKIE_CACHE_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cookies": dict(cookies),
        "cookie_header": _cookie_header(cookies),
        "media_edge_exp": media_cookie_expires_at(cookies),
        "updated_at": int(time.time()),
    }
    destination.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    destination.chmod(0o600)
    return destination


def load_cookie_cache(path: Path | None = None) -> dict[str, str] | None:
    """Load a previously saved cookie cache, or None if missing/invalid."""
    source = path or COOKIE_CACHE_FILE
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    cookies = payload.get("cookies") if isinstance(payload, dict) else None
    if not isinstance(cookies, dict):
        return None
    return {str(key): str(value) for key, value in cookies.items()}


class AddgeneWebDownloader:
    """Download full GBK files through Addgene's website plus a Chrome session."""

    def __init__(
        self,
        *,
        cookies: Mapping[str, str] | None = None,
        chrome_profile: Path | None = None,
        proxy_url: str | None = None,
        min_delay: float = 0.4,
        max_delay: float = 1.2,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        request: RequestFunction | None = None,
        sleep: SleepFunction = time.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
        cookie_loader: Callable[[], Mapping[str, str]] | None = None,
        cookie_cache: Path | None = COOKIE_CACHE_FILE,
        persist_cookies: bool | None = None,
    ) -> None:
        if min_delay < 0 or max_delay < min_delay:
            raise ValueError("Require 0 <= min_delay <= max_delay")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.chrome_profile = chrome_profile
        self._sleep = sleep
        self._random_uniform = random_uniform
        self._request_count = 0
        self._request = request or self._build_request(proxy_url)
        self._cookie_loader = cookie_loader
        self._cookie_cache = cookie_cache
        self._persist_cookies = persist_cookies if persist_cookies is not None else cookies is None
        self._reload_from_chrome = cookies is None
        if cookies is not None:
            self.cookies = dict(cookies)
        elif cookie_loader is not None:
            self.cookies = dict(cookie_loader())
        else:
            cached = load_cookie_cache(cookie_cache)
            if cached and media_seconds_remaining(cached) > MEDIA_COOKIE_REFRESH_SKEW:
                self.cookies = cached
            else:
                self.cookies = load_chrome_addgene_cookies(profile=chrome_profile)
                self.refresh_session()

    @staticmethod
    def _build_request(proxy_url: str | None) -> RequestFunction:
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
                        headers=_headers_with_set_cookies(response.headers),
                        body=response.read(),
                    )
            except HTTPError as exc:
                return HttpResponse(
                    status=exc.code,
                    url=exc.url or url,
                    headers=_headers_with_set_cookies(exc.headers),
                    body=exc.read(),
                )
            except URLError as exc:
                raise AddgeneDownloadError(
                    f"Network error reaching Addgene: {exc.reason}"
                ) from exc

        return request

    def _absorb_set_cookies(self, headers: Mapping[str, str]) -> None:
        raw = ""
        for key, value in headers.items():
            if key.lower() == "set-cookie":
                raw = f"{raw}\n{value}" if raw else value
        for line in raw.splitlines():
            assignment = line.split(";", 1)[0]
            if "=" not in assignment:
                continue
            name, _, value = assignment.partition("=")
            name = name.strip()
            if name:
                self.cookies[name] = value
        if self._persist_cookies:
            save_cookie_cache(self.cookies, self._cookie_cache)

    def refresh_session(self) -> Mapping[str, str]:
        """Reload Chrome cookies if needed and mint a fresh media-edge cookie."""
        if self._reload_from_chrome:
            loader = self._cookie_loader or (
                lambda: load_chrome_addgene_cookies(profile=self.chrome_profile)
            )
            try:
                self.cookies.update(dict(loader()))
            except AddgeneDownloadError:
                if MEDIA_COOKIE_NAME not in self.cookies:
                    raise
        url = f"{SITE_ORIGIN}/"
        response = self._request(url, self._headers(url, "text/html"))
        self._absorb_set_cookies(response.headers)
        if MEDIA_COOKIE_NAME not in self.cookies:
            raise AddgeneDownloadError(
                "Addgene media-edge cookie did not refresh. Sign in at "
                "https://www.addgene.org/ in Chrome and retry."
            )
        expiry = media_cookie_expires_at(self.cookies)
        if expiry is not None and float(expiry) - time.time() <= 0:
            raise AddgeneDownloadError(
                "Addgene media-edge cookie did not refresh. Sign in at "
                "https://www.addgene.org/ in Chrome and retry."
            )
        return self.cookies

    def ensure_fresh_media_cookie(self) -> None:
        """Refresh when the 15-minute media-edge JWT is missing or near expiry."""
        expiry = media_cookie_expires_at(self.cookies)
        if expiry is None:
            return
        if float(expiry) - time.time() > MEDIA_COOKIE_REFRESH_SKEW:
            return
        self.refresh_session()

    def keep_fresh(self, *, interval: float = KEEP_FRESH_INTERVAL) -> None:
        """Refresh the media-edge cookie on a loop. interval is seconds."""
        if interval <= 0:
            raise ValueError("keep-fresh interval must be positive")
        while True:
            self.refresh_session()
            remaining = media_seconds_remaining(self.cookies)
            print(f"Addgene media-edge cookie fresh for {int(remaining)}s", flush=True)
            wait = min(interval, max(30.0, remaining - MEDIA_COOKIE_REFRESH_SKEW))
            self._sleep(wait)

    def _headers(self, url: str, accept: str) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": self.user_agent,
            "Referer": f"{SITE_ORIGIN}/",
        }
        host = (urlsplit(url).hostname or "").casefold()
        if host == "addgene.org" or host.endswith(ADDGENE_HOST_SUFFIX):
            headers["Cookie"] = _cookie_header(self.cookies)
        return headers

    def _polite_delay(self) -> None:
        if self._request_count:
            self._sleep(self._random_uniform(self.min_delay, self.max_delay))

    def _get(self, url: str, accept: str) -> HttpResponse:
        host = (urlsplit(url).hostname or "").casefold()
        is_media = host == "media.addgene.org" or host.endswith(".media.addgene.org")
        refreshed = False
        for attempt in range(self.max_retries + 1):
            if is_media:
                self.ensure_fresh_media_cookie()
            self._polite_delay()
            self._request_count += 1
            response = self._request(url, self._headers(url, accept))
            self._absorb_set_cookies(response.headers)
            if response.status == HTTP_OK:
                return response
            if response.status in {401, 403}:
                raise AddgeneDownloadError(
                    "Addgene rejected the signed-in Chrome session. Sign in at "
                    "https://www.addgene.org/ in Chrome and retry."
                )
            if response.status == HTTP_NOT_FOUND:
                if is_media and not refreshed:
                    self.refresh_session()
                    refreshed = True
                    continue
                if is_media:
                    raise AddgeneDownloadError(
                        "Addgene media returned 404. The Chrome media-edge cookie "
                        "is missing or expired; sign in at https://www.addgene.org/."
                    )
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

    def discover_sequences(
        self, plasmid_id: int, *, sequence_source: str = "preferred"
    ) -> list[SequenceEntry]:
        """Resolve public full-sequence GenBank URLs for one plasmid id."""
        page = self._get(
            f"{SITE_ORIGIN}/{plasmid_id}/sequences/",
            "text/html",
        )
        html = page.body.decode("utf-8", errors="replace")
        if "anonymous-user-sequence-alert" in html and "addgene-full" not in html:
            raise AddgeneDownloadError(
                f"Addgene {plasmid_id} sequence page is not readable."
            )
        grouped = parse_sequence_sections(html)
        selected = select_sequence_ids(grouped, sequence_source)
        if not selected:
            raise AddgeneDownloadError(
                f"Addgene {plasmid_id} has no public full sequence id "
                f"for policy {sequence_source!r}."
            )
        entries: list[SequenceEntry] = []
        seen_urls: set[str] = set()
        for bucket, sequence_id in selected:
            collection = self._sequence_collection(sequence_id)
            url = str(collection.get("genbankUrl") or "")
            if not _safe_addgene_gbk_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            entries.append(
                SequenceEntry(
                    plasmid_id=plasmid_id,
                    sequence_id=sequence_id,
                    source_bucket=bucket,
                    genbank_url=url,
                )
            )
            if sequence_source == "preferred":
                break
        if not entries:
            raise AddgeneDownloadError(
                f"Addgene {plasmid_id} has no public full GenBank URL "
                f"for policy {sequence_source!r}."
            )
        return entries

    def _sequence_collection(self, sequence_id: str) -> dict[str, Any]:
        response = self._get(
            COLLECTION_API.format(sequence_id=sequence_id),
            "application/json",
        )
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AddgeneDownloadError(
                f"Addgene returned invalid JSON for sequence {sequence_id}"
            ) from exc
        if not isinstance(payload, dict):
            raise AddgeneDownloadError(
                f"Addgene returned an unexpected collection payload for {sequence_id}"
            )
        if payload.get("inProgress"):
            raise AddgeneDownloadError(
                f"Addgene sequence {sequence_id} is still generating files."
            )
        return payload

    def download_plasmid(
        self,
        plasmid_id: int,
        output_dir: Path,
        *,
        sequence_source: str = "preferred",
        refresh: bool = False,
    ) -> list[DownloadRecord]:
        """Download the GBK files selected by ``sequence_source`` for one plasmid."""
        output_dir.mkdir(parents=True, exist_ok=True)
        if not refresh and sequence_source == "preferred":
            cached = self._cached_records(plasmid_id, output_dir)
            if cached:
                return cached
        entries = self.discover_sequences(
            plasmid_id, sequence_source=sequence_source
        )
        records = []
        for entry in entries:
            response = self._get(
                entry.genbank_url, "text/plain,application/octet-stream;q=0.9"
            )
            if not response.body.lstrip().startswith(b"LOCUS"):
                raise AddgeneDownloadError(
                    "Addgene media returned a non-GenBank body. The Chrome session "
                    "is missing or expired; sign in at https://www.addgene.org/."
                )
            stats = validate_genbank(response.body)
            filename = _download_filename(
                response.headers,
                response.url,
                plasmid_id=plasmid_id,
                sequence_id=entry.sequence_id,
            )
            destination = output_dir / filename
            _atomic_write(destination, response.body)
            records.append(
                DownloadRecord(
                    plasmid_id=plasmid_id,
                    status="downloaded-via-chrome-session",
                    source_bucket=entry.source_bucket,
                    sequence_id=entry.sequence_id,
                    sequence_name="",
                    download_url=entry.genbank_url,
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
        """Download a list serially, keeping per-plasmid successes and errors."""
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
                if "sign in" in str(exc).casefold():
                    break
        return {
            "schema_version": 1,
            "transport": "chrome-session-http",
            "sequence_source": sequence_source,
            "results": results,
            "errors": errors,
        }


def _sequence_ids(html: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for match in SEQUENCE_ID_RE.finditer(html):
        sequence_id = next(group for group in match.groups() if group)
        if sequence_id not in seen:
            seen.add(sequence_id)
            ids.append(sequence_id)
    return ids


def _safe_addgene_gbk_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    return (
        parsed.scheme == "https"
        and (host == "addgene.org" or host.endswith(ADDGENE_HOST_SUFFIX))
        and parsed.path.casefold().endswith((".gb", ".gbk", ".gbff"))
    )


def _cookie_header(cookies: Mapping[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def _headers_with_set_cookies(headers: object | None) -> dict[str, str]:
    if headers is None:
        return {}
    items = getattr(headers, "items", None)
    merged = {str(key): str(value) for key, value in items()} if callable(items) else {}
    get_all = getattr(headers, "get_all", None)
    if callable(get_all):
        set_cookies = get_all("Set-Cookie") or []
        if set_cookies:
            merged["Set-Cookie"] = "\n".join(str(value) for value in set_cookies)
    return merged


def _read_chrome_safe_storage_password() -> bytes:
    last_error = "unknown Keychain error"
    for account in CHROME_SAFE_STORAGE_ACCOUNTS:
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-w",
                    "-s",
                    CHROME_SAFE_STORAGE_SERVICE,
                    "-a",
                    account,
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
        except FileNotFoundError as exc:
            raise AddgeneDownloadError(
                "The Chrome-session downloader requires macOS Keychain access."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AddgeneDownloadError(
                "Timed out reading Chrome's Keychain password."
            ) from exc
        except subprocess.CalledProcessError as exc:
            last_error = (exc.stderr or exc.stdout or b"").decode("utf-8", "replace").strip()
            continue
        password = result.stdout.strip()
        if password:
            return password
    raise AddgeneDownloadError(
        "Could not read Chrome Safe Storage from Keychain. Unlock the login "
        f"keychain and retry. {last_error}"
    )


def _cookies_from_copied_db(
    database: Path,
    key: bytes,
    decrypt: CookieDecryptFunction,
) -> dict[str, str]:
    # REASON: Chrome holds an exclusive lock on the live cookie SQLite file.
    # Opening it in place fails or reads a torn WAL snapshot while the browser
    # is running. Copying the DB (and WAL/SHM sidecars) is the supported way to
    # get a consistent read without quitting Chrome. Deleting the copy is
    # required so decrypted material is not left on disk; only names/hosts live
    # in the in-memory dict returned to the downloader.
    copy_dir = Path(tempfile.mkdtemp(prefix="addgene-chrome-cookies-"))
    try:
        copied = copy_dir / database.name
        shutil.copy2(database, copied)
        for suffix in ("-wal", "-shm"):
            sidecar = database.parent / f"{database.name}{suffix}"
            if sidecar.is_file():
                shutil.copy2(sidecar, copy_dir / sidecar.name)
        connection = sqlite3.connect(copied)
        try:
            rows = connection.execute(
                "SELECT host_key, name, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%addgene.org%'"
            )
            cookies: dict[str, str] = {}
            for host_key, name, encrypted in rows:
                if not isinstance(encrypted, (bytes, memoryview)):
                    continue
                try:
                    cookies[str(name)] = decrypt(bytes(encrypted), key)
                except (AddgeneDownloadError, UnicodeDecodeError, ValueError):
                    continue
            return cookies
        finally:
            connection.close()
    finally:
        shutil.rmtree(copy_dir, ignore_errors=True)

#!/usr/bin/env python3
"""Download validated Addgene GenBank files from a list of plasmid ids."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lab_bench_2.addgene_downloader import (
    AddgeneDownloader,
    AddgeneDownloadError,
    parse_plasmid_id,
)
from lab_bench_2.addgene_web_downloader import AddgeneWebDownloader


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download full annotated GBK files from Addgene plasmid ids. "
            "Default is the signed-in Chrome HTTP session (no API token). "
            "Use --via api with ADDGENE_TOKEN for the Developers API."
        )
    )
    parser.add_argument(
        "plasmids",
        nargs="*",
        help="Addgene ids or canonical https://www.addgene.org/<id>/ URLs",
    )
    parser.add_argument(
        "--ids-file",
        type=Path,
        help="UTF-8 text file with one Addgene id or URL per line",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--sequence-source",
        choices=("preferred", "addgene", "depositor", "all"),
        default="preferred",
        help="Prefer Addgene-verified full sequences, then depositor full sequences",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-query Addgene even when a validated local GBK is cached",
    )
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument(
        "--proxy-url",
        help=(
            "Optional fixed HTTP(S) proxy. Standard HTTPS_PROXY/NO_PROXY environment "
            "variables are honored when omitted; rotating proxies are unsupported."
        ),
    )
    parser.add_argument(
        "--via",
        choices=("chrome-session", "api", "chrome"),
        default="chrome-session",
        help=(
            "chrome-session: public discovery + HTTP GBK download using the "
            "signed-in Chrome cookie store (default, scales). "
            "api: Developers API with ADDGENE_TOKEN. "
            "chrome: one Chrome window per plasmid (small lists only)."
        ),
    )
    parser.add_argument(
        "--chrome-profile",
        type=Path,
        help="Chrome profile directory (default: ~/Library/Application Support/Google/Chrome/Default)",
    )
    parser.add_argument(
        "--chrome-download-dir",
        type=Path,
        default=Path.home() / "Downloads",
        help="Chrome download directory for --via chrome (default: ~/Downloads)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Manifest path (default: <output-dir>/addgene-download-manifest.json)",
    )
    return parser.parse_args()


def _inputs(args: argparse.Namespace) -> list[int]:
    values = list(args.plasmids)
    if args.ids_file:
        values.extend(
            line.strip()
            for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not values:
        raise ValueError("Provide at least one plasmid id or --ids-file")
    return [parse_plasmid_id(value) for value in values]


def main() -> int:
    args = _arguments()
    try:
        plasmid_ids = _inputs(args)
        if args.via == "api":
            downloader = AddgeneDownloader(
                proxy_url=args.proxy_url,
                min_delay=args.min_delay,
                max_delay=args.max_delay,
                max_retries=args.max_retries,
            )
            manifest = downloader.download_many(
                plasmid_ids,
                args.output_dir,
                sequence_source=args.sequence_source,
                refresh=args.refresh,
            )
        elif args.via == "chrome":
            from lab_bench_2.addgene_chrome_downloader import ChromeAddgeneDownloader

            chrome = ChromeAddgeneDownloader(
                download_dir=args.chrome_download_dir,
                min_delay=args.min_delay,
                max_delay=args.max_delay,
            )
            manifest = chrome.download_many(
                plasmid_ids,
                args.output_dir,
                download_all=args.sequence_source == "all",
                refresh=args.refresh,
            )
        else:
            downloader = AddgeneWebDownloader(
                chrome_profile=args.chrome_profile,
                proxy_url=args.proxy_url,
                min_delay=args.min_delay,
                max_delay=args.max_delay,
                max_retries=args.max_retries,
            )
            manifest = downloader.download_many(
                plasmid_ids,
                args.output_dir,
                sequence_source=args.sequence_source,
                refresh=args.refresh,
            )
    except (OSError, ValueError, AddgeneDownloadError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    manifest_path = args.manifest or args.output_dir / "addgene-download-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Downloaded/cached {len(manifest['results'])} sequence(s); "
        f"{len(manifest['errors'])} plasmid(s) failed. Manifest: {manifest_path}"
    )
    for error in manifest["errors"]:
        print(f"  Addgene {error['plasmid_id']}: {error['error']}", file=sys.stderr)
    return 1 if manifest["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

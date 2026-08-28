---
name: addgene-gbk-download
description: >
  Download Addgene plasmid GenBank (.gbk) files from plasmid IDs using a
  signed-in Chrome session. Captures and refreshes the 15-minute
  __Secure_media_edge_auth cookie, retries when it expires, and batch-downloads
  a list of plasmids. Use when the user asks to download Addgene GBKs, capture
  Addgene cookies, keep the media-edge cookie fresh, or runs
  /addgene-gbk-download.
---

# Addgene GBK download

Stay signed in at https://www.addgene.org/ in Chrome. Sequence IDs and GenBank URLs are public. The `.gbk` bytes need cookie `__Secure_media_edge_auth` (15 minutes) plus `addgene.org`. Do not put cookie values in git, chat, or manifests.

## Batch plasmids

```bash
uv run python tools/download_addgene_gbk.py \
  --ids-file plasmids.txt \
  --output-dir /path/to/gbk
```

`plasmids.txt` is one Addgene id or `https://www.addgene.org/<id>/` per line. IDs can also be CLI args. Default `--via chrome-session` reads Chrome cookies, refreshes media-edge on `www.addgene.org` Set-Cookie, and re-mints the cookie if a media request 404s.

## Keep the cookie fresh

The media-edge JWT lasts 900 seconds. Refresh from Chrome + `www.addgene.org` before it dies:

```bash
uv run python tools/download_addgene_gbk.py --keep-fresh
```

Default interval is 840 seconds. Cache (mode 0600, never git): `~/.cache/lab-bench-addgene/cookies.json`. Prints remaining lifetime only, not cookie values.

## If download 404s

1. Confirm Chrome is signed in to Addgene.
2. Re-run the same command. The downloader reloads Chrome cookies and hits `www.addgene.org` to mint a new media-edge cookie, then retries the GBK.
3. Do not drive one Chrome window per plasmid. That path was deleted; notes to regenerate it live in `src/lab_bench_2/CLONING_SEQUENCE_DATA.md`.

## Do not

- Direct `curl` of the UUID `.gbk` URL without that Cookie header (Cloudflare 404).
- Write cookie values into the repo or PR text.
- Use `--via api` unless `ADDGENE_TOKEN` is already approved.

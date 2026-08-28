# iGEM parts downloader

The old `parts.igem.org/cgi/xml/part.cgi` endpoint is blocked by CloudFront in
many environments. `download_igem_parts.py` uses the current public API at
`https://api.registry.igem.org/v1` instead.

Run it from the repository root:

```bash
.venv/bin/python tools/download_igem_parts.py BBa_J23100 BBa_B0015 --fasta
```

Or download a larger list (comma-separated, whitespace-separated, and comments
are accepted):

```bash
.venv/bin/python tools/download_igem_parts.py --from-file parts.txt -o downloaded-parts
```

For each part, the tool writes:

- `<part>.gb`: GenBank from iGEM, enriched with any sequence features and
  composite-subpart boundaries returned by the current API.
- `<part>.igem.json`: the complete part, sequence-feature, and composition
  metadata responses, including provenance URLs.
- `<part>.fasta`: the native iGEM FASTA export when `--fasta` is requested.

SnapGene can open the `.gb` file directly and display its feature map. The
public iGEM API does not provide native SnapGene `.dna` files; after opening the
GenBank file, use SnapGene's **Save As** command if a `.dna` copy is required.

The API publishes both short- and medium-window rate limits. The downloader
therefore spaces calls by 1.1 seconds and retries HTTP 429 and transient server
errors. Use `--request-delay` only if you know a different limit applies. On
Python.org macOS installations without a configured system CA file, the tool
automatically uses Certifi's CA bundle when Certifi is available; it never
disables TLS certificate verification.

## Distribution kit

The Registry's Distribution page embeds the WellRead plate inventory. To
snapshot every occupied well in the current kit, including its full physical
plasmid sequence and kit metadata, run:

```bash
.venv/bin/python tools/download_igem_distribution.py --year 2026 --fasta
```

This writes one circular GenBank file per well, optional individual and combined
FASTA files, CSV/JSON manifests, the raw public inventory snapshot, and a README
with QC totals. Records flagged with sequence discrepancies or sequencing
failures are retained and clearly annotated so that the directory represents
the complete physical kit.

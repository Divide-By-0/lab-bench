# Scientific Python stack for the agentic solver's sandboxed python/bash tools.
# Versions are pinned for reproducible builds. pydna constrains biopython,
# numpy, pandas, and scipy, so bump them as a set (re-resolve, don't pin
# individually). pymupdf/pdfplumber give the agent PDF text/table extraction
# (file-bearing tags copy PDFs into the sandbox); they are independent of the
# pydna-constrained set, so pin them on their own. The base image is
# intentionally left unpinned: it must track the inspect tool-support protocol
# of the installed inspect_ai.
FROM aisiuk/inspect-tool-support

RUN pip install --no-cache-dir \
    biopython==1.87 \
    pydna==5.5.12 \
    primer3-py==2.3.0 \
    pandas==3.0.3 \
    numpy==2.4.6 \
    scipy==1.17.1 \
    pymupdf==1.27.2.3 \
    pdfplumber==0.11.9 \
    dill==0.4.0

# REASON: agents were burning tool calls reading pydna's own source
# (/usr/local/lib/.../pydna/design.py) and issuing web searches to work out its API --
# it is a small library with a non-obvious surface (assembly2 vs the deprecated
# assembly, circular_assembly_fragments, primer_design). Bake the API reference into
# the image so that is a local file read instead.
RUN mkdir -p /opt/docs && \
    for m in pydna.design pydna.assembly2 pydna.amplify pydna.dseqrecord pydna.primer \
             pydna.parsers pydna.readers pydna.tm Bio.Restriction primer3; do \
      python -m pydoc "$m" > "/opt/docs/${m}.txt" 2>/dev/null || true; \
    done && \
    ls /opt/docs

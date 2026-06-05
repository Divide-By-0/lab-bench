# Scientific Python stack for the agentic solver's sandboxed python/bash tools.
# Versions are pinned for reproducible builds. pydna constrains biopython,
# numpy, pandas, and scipy, so bump them as a set (re-resolve, don't pin
# individually). The base image is intentionally left unpinned: it must track
# the inspect tool-support protocol of the installed inspect_ai.
FROM aisiuk/inspect-tool-support

RUN pip install --no-cache-dir \
    biopython==1.87 \
    pydna==5.5.12 \
    primer3-py==2.3.0 \
    pandas==3.0.3 \
    numpy==2.4.6 \
    scipy==1.17.1

#!/usr/bin/env python3
"""Add cloning assembly comparison events to existing Inspect eval logs."""

from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path
from urllib.parse import quote

import httpx
from Bio import SeqIO
from inspect_ai.event import InfoEvent
from inspect_ai.log import EvalLog, EvalSample, read_eval_log, write_eval_log

from lab_bench_2.cloning_visualization import cloning_comparison_markdown

GCS_BUCKET = "labbench2-data-public"
GCS_API_URL = f"https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o"
GCS_DOWNLOAD_URL = f"https://storage.googleapis.com/{GCS_BUCKET}"
COMPARISON_SOURCE = "cloning sequence comparison"

PEG10_ID = "61e4b666-1ee5-4046-b304-d57e183c8593"
DCAS9_ID = "31d22b22-0d48-41a4-88ed-b46ff451be52"
NPAS4_ID = "a4bf037c-2477-4cca-9ca3-12c5ee63c44f"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing .eval logs")
    parser.add_argument("output_dir", type=Path, help="Directory for enriched copies")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        required=True,
        help="Writable cache for public benchmark sequence files",
    )
    parser.add_argument(
        "--suffix",
        default="_genbank",
        help="Suffix added to copied log filenames (default: _genbank)",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        help="Optional directory of corrected <question-id>_assembled.fa references",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Regenerate sequence-comparison events already present in a log",
    )
    return parser.parse_args()


def _question_ids(log: EvalLog) -> set[str]:
    return {
        str(sample.metadata["id"])
        for sample in log.samples or []
        if sample.metadata.get("tag") == "cloning"
        and sample.metadata.get("id")
        and not (
            sample.metadata.get("files_path") and sample.metadata.get("reference_path")
        )
    }


def _list_objects(client: httpx.Client, prefix: str) -> list[str]:
    objects: list[str] = []
    page_token: str | None = None
    while True:
        params = {"prefix": prefix}
        if page_token:
            params["pageToken"] = page_token
        response = client.get(GCS_API_URL, params=params)
        response.raise_for_status()
        body = response.json()
        objects.extend(item["name"] for item in body.get("items", []))
        page_token = body.get("nextPageToken")
        if not page_token:
            return objects


def _download(client: httpx.Client, object_name: str, destination: Path) -> None:
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    url = f"{GCS_DOWNLOAD_URL}/{quote(object_name, safe='/')}"
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with temporary.open("wb") as output:
            for chunk in response.iter_bytes():
                output.write(chunk)
    temporary.replace(destination)


def download_sample_files(cache_dir: Path, question_ids: set[str]) -> None:
    """Download each question directory and its hidden reference assembly."""
    cache_root = cache_dir / GCS_BUCKET
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for question_id in sorted(question_ids):
            prefix = f"cloning/{question_id}/"
            for object_name in _list_objects(client, prefix):
                relative = object_name.removeprefix(prefix)
                if relative:
                    _download(
                        client,
                        object_name,
                        cache_root / "cloning" / question_id / relative,
                    )
            reference_name = f"{question_id}_assembled.fa"
            _download(
                client,
                f"validation/{reference_name}",
                cache_root / "validation" / reference_name,
            )
            print(f"downloaded {question_id}")


def apply_pr_repairs(cache_dir: Path) -> None:
    """Apply the same three data repairs documented in Divide-By-0 PR #1."""
    cache_root = cache_dir / GCS_BUCKET

    peg10 = (
        cache_root / "cloning" / PEG10_ID / "Homo_sapiens_ENST00000612748_1_sequence.fa"
    )
    if peg10.exists():
        records = list(SeqIO.parse(peg10, "fasta"))
        if len(records) > 1:
            SeqIO.write([records[0]], peg10, "fasta")

    reference = cache_root / "validation" / f"{DCAS9_ID}_assembled.fa"
    donor_path = cache_root / "cloning" / DCAS9_ID / "plv-ef1a-ires-blast.gb"
    if reference.exists() and donor_path.exists():
        donor = str(SeqIO.read(donor_path, "genbank").seq).upper()
        ires, blast = donor[6768:7318], donor[7318:7772]
        record = SeqIO.read(reference, "fasta")
        sequence = str(record.seq).upper()
        if blast not in sequence:
            insertion = sequence.find(ires)
            if insertion < 0:
                raise RuntimeError("Cannot apply dCas9 repair: IRES not found")
            record.seq = type(record.seq)(
                sequence[: insertion + len(ires)]
                + blast
                + sequence[insertion + len(ires) :]
            )
            SeqIO.write([record], reference, "fasta")

    npas4_dir = cache_root / "cloning" / NPAS4_ID
    old_name = npas4_dir / "addgene-plasmid-105539-sequence-457689 (1).gbk"
    new_name = npas4_dir / "addgene-plasmid-105539-sequence-457689.gbk"
    if old_name.exists() and not new_name.exists():
        shutil.copy2(old_name, new_name)


def _answer(sample: EvalSample) -> str:
    cloning_score = (sample.scores or {}).get("cloning_scorer")
    if cloning_score and cloning_score.answer:
        return cloning_score.answer
    return sample.output.completion


async def enrich_sample(
    sample: EvalSample,
    cache_dir: Path,
    reference_dir: Path | None = None,
    replace_existing: bool = False,
) -> bool:
    if sample.metadata.get("tag") != "cloning":
        return False
    existing_comparisons = [
        event
        for event in sample.events
        if event.event == "info" and event.source == COMPARISON_SOURCE
    ]
    if existing_comparisons and not replace_existing:
        return False
    if existing_comparisons:
        sample.events = [
            event
            for event in sample.events
            if not (event.event == "info" and event.source == COMPARISON_SOURCE)
        ]

    question_id = str(sample.metadata["id"])
    cache_root = cache_dir / GCS_BUCKET
    local_files_path = sample.metadata.get("files_path")
    base_dir = (
        Path(str(local_files_path))
        if local_files_path
        else cache_root / "cloning" / question_id
    )
    local_reference_path = sample.metadata.get("reference_path")
    reference_path = (
        reference_dir / f"{question_id}_assembled.fa"
        if reference_dir is not None
        else Path(str(local_reference_path))
        if local_reference_path
        else cache_root / "validation" / f"{question_id}_assembled.fa"
    )
    if not base_dir.is_dir() or not reference_path.is_file():
        raise FileNotFoundError(
            f"Cannot enrich {question_id}: files={base_dir}, reference={reference_path}"
        )
    try:
        markdown = await cloning_comparison_markdown(
            answer=_answer(sample),
            base_dir=base_dir,
            reference_path=reference_path,
            validator_params=sample.metadata.get("validator_params") or {},
        )
    except Exception as exc:
        markdown = (
            "### Cloning sequence comparison\n\n"
            f"Could not reconstruct this comparison: `{type(exc).__name__}: {exc}`"
        )
    score = (sample.scores or {}).get("cloning_scorer")
    if score is not None:
        score_metadata = score.metadata or {}
        original_explanation = str(
            score_metadata.get(
                "sequence_comparison_original_explanation", score.explanation or ""
            )
        )
        score.explanation = f"{original_explanation}\n\n---\n\n{markdown}"
        score.metadata = {
            **score_metadata,
            "sequence_comparison_backfilled": True,
            "sequence_comparison_original_explanation": original_explanation,
        }

    score_event_index = next(
        (
            index
            for index in range(len(sample.events) - 1, -1, -1)
            if sample.events[index].event == "score"
        ),
        len(sample.events) - 1,
    )
    neighboring_event = sample.events[score_event_index]
    if (
        score is not None
        and neighboring_event.event == "score"
        and neighboring_event.scorer == "cloning_scorer"
    ):
        neighboring_event.score = score.model_copy(deep=True)
    sample.events.insert(
        score_event_index + 1,
        InfoEvent(
            data=markdown,
            source=COMPARISON_SOURCE,
            span_id=neighboring_event.span_id,
            timestamp=neighboring_event.timestamp,
            working_start=neighboring_event.working_start,
            metadata={"backfilled": True, "question_id": question_id},
        ),
    )
    print(f"rendered {question_id}")
    return True


async def enrich_logs(
    source_dir: Path,
    output_dir: Path,
    cache_dir: Path,
    suffix: str,
    reference_dir: Path | None = None,
    replace_existing: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logs: list[tuple[Path, EvalLog]] = []
    question_ids: set[str] = set()
    for source_path in sorted(source_dir.glob("*.eval")):
        log = read_eval_log(source_path)
        logs.append((source_path, log))
        question_ids.update(_question_ids(log))

    download_sample_files(cache_dir, question_ids)
    apply_pr_repairs(cache_dir)

    for source_path, log in logs:
        changed = False
        for sample in log.samples or []:
            changed = (
                await enrich_sample(
                    sample,
                    cache_dir,
                    reference_dir,
                    replace_existing=replace_existing,
                )
                or changed
            )
        destination = output_dir / f"{source_path.stem}{suffix}{source_path.suffix}"
        if changed:
            write_eval_log(log, destination)
        else:
            shutil.copy2(source_path, destination)
        print(f"wrote {destination}")


def main() -> None:
    args = parse_args()
    asyncio.run(
        enrich_logs(
            args.source_dir,
            args.output_dir,
            args.cache_dir,
            args.suffix,
            args.reference_dir,
            args.replace_existing,
        )
    )


if __name__ == "__main__":
    main()

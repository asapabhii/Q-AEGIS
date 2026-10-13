"""Convert a FOIArchive export into the FR-1 labelled CSV, ``SPEC.md`` 3.2.

FOIArchive (``HistoryLab/foiarchive``, CC-BY-NC-4.0, gated) carries real
government classification markings, which is why it is the label ground truth
for the sensitivity classifier. This script maps those markings onto the three
model tiers and writes the CSV contract in ``docs/classifier-dataset.md``
(columns ``content,label,source_id,split``).

Two inputs are supported:

- A local JSON Lines file (one record per line), the default path once Abhinav
  has downloaded the gated dataset.
- The HuggingFace dataset directly (``--hf-dataset HistoryLab/foiarchive``),
  streamed so the ~8 GB corpus is never fully materialised. Requires the
  ``datasets`` package and an accepted licence on the dataset page.

Marking → tier mapping (deliberately strict; unmapped markings are skipped, not
guessed, and their counts are reported):

    unclassified                      -> PUBLIC
    confidential                      -> CONFIDENTIAL
    secret, top secret                -> RESTRICTED

INTERNAL is never emitted: it is a policy-layer tier, not a model output. Any
handling caveat after a ``/`` (``secret/nodis``) is ignored for the base
marking. Records whose marking is not one of the four named markings (for
example "limited official use") are skipped, because mapping them would either
downgrade a controlled document or invent a label the corpus does not assert.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from app.classifier.labels import SensitivityLabel

#: Base markings we trust to map. Matched against the marking's leading token(s)
#: after lowercasing and dropping any ``/caveat`` suffix. Order matters: "top
#: secret" and "secret" both resolve to RESTRICTED, but "top secret" is checked
#: as a phrase so it is never mistaken for something milder.
_MARKING_RULES: tuple[tuple[str, SensitivityLabel], ...] = (
    ("top secret", SensitivityLabel.RESTRICTED),
    ("secret", SensitivityLabel.RESTRICTED),
    ("confidential", SensitivityLabel.CONFIDENTIAL),
    ("unclassified", SensitivityLabel.PUBLIC),
)


def map_marking(raw: str | None) -> SensitivityLabel | None:
    """Map a FOIArchive classification marking to a model tier, or None.

    Returns None for a missing, empty, or unrecognised marking. The caller
    skips such records rather than guessing a label the corpus never asserted.
    """
    if not raw:
        return None
    base = str(raw).strip().lower().split("/", 1)[0].strip()
    if not base:
        return None
    for prefix, label in _MARKING_RULES:
        if base == prefix or base.startswith(prefix + " "):
            return label
    return None


@dataclass(frozen=True)
class PrepStats:
    """What the run produced, for an honest, auditable summary."""

    written: int
    skipped_blank: int
    skipped_short: int
    skipped_unmapped: int
    skipped_duplicate: int
    per_label: dict[str, int]
    unmapped_markings: dict[str, int]


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield one dict per non-blank line of a JSON Lines file."""
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_number}: invalid JSON") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Line {line_number}: expected a JSON object")
            yield record


def _iter_hf(
    dataset: str,
    config: str | None,
    split: str,
    data_files: str | list[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield records streamed from a HuggingFace dataset.

    ``data_files`` pins a specific file inside the repo when the dataset holds
    several files of differing formats (e.g. a repo shipping both ``cables.csv``
    and ``cables_parsed.jsonl``); left unset, the dataset's own layout is used.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Reading --hf-dataset requires the 'datasets' package. Install it "
            "in a data-prep environment, or export the dataset to JSONL first."
        ) from exc
    stream = load_dataset(
        dataset, config, split=split, streaming=True, data_files=data_files
    )
    for record in stream:
        yield dict(record)


def convert(
    records: Iterable[dict[str, Any]],
    output_path: Path,
    *,
    content_field: str,
    label_field: str,
    id_field: str,
    min_chars: int,
    max_chars: int,
    test_fraction: float,
    seed: int,
    content_cleaner: Callable[[str], str] | None = None,
) -> PrepStats:
    """Write the labelled CSV from ``records`` and return a run summary.

    Records are deduplicated by content, length-filtered, and marking-mapped.
    A deterministic per-row hash assigns the stratified ``train``/``test`` split
    so the same input always yields the same split without holding every row in
    memory.

    ``content_cleaner`` transforms the raw content before every check. It exists
    so a source that prints its own classification inside the document text
    (e.g. diplomatic cables headed ``S E C R E T``) can have that marking
    scrubbed out; otherwise the model would learn to read the label off the page
    instead of learning genuine sensitivity features. Cleaning that empties a
    record makes it count as blank.
    """
    rng = random.Random(seed)
    seen: set[str] = set()
    written = 0
    skipped_blank = skipped_short = skipped_unmapped = skipped_duplicate = 0
    per_label: dict[str, int] = {}
    unmapped: dict[str, int] = {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["content", "label", "source_id", "split"]
        )
        writer.writeheader()
        for record in records:
            content = str(record.get(content_field) or "")
            if content_cleaner is not None:
                content = content_cleaner(content)
            content = content.strip()
            if not content:
                skipped_blank += 1
                continue
            label = map_marking(record.get(label_field))
            if label is None:
                skipped_unmapped += 1
                marking = str(record.get(label_field) or "").strip().lower()
                unmapped[marking] = unmapped.get(marking, 0) + 1
                continue
            if len(content) < min_chars:
                skipped_short += 1
                continue
            if len(content) > max_chars:
                content = content[:max_chars]
            key = content.casefold()
            if key in seen:
                skipped_duplicate += 1
                continue
            seen.add(key)

            split = "test" if rng.random() < test_fraction else "train"
            writer.writerow(
                {
                    "content": content,
                    "label": label.value,
                    "source_id": str(record.get(id_field) or "").strip(),
                    "split": split,
                }
            )
            written += 1
            per_label[label.value] = per_label.get(label.value, 0) + 1

    return PrepStats(
        written=written,
        skipped_blank=skipped_blank,
        skipped_short=skipped_short,
        skipped_unmapped=skipped_unmapped,
        skipped_duplicate=skipped_duplicate,
        per_label=per_label,
        unmapped_markings=unmapped,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Local JSON Lines export.")
    source.add_argument(
        "--hf-dataset", help="HuggingFace dataset id, e.g. HistoryLab/foiarchive."
    )
    parser.add_argument("--hf-config", default=None, help="HuggingFace config name.")
    parser.add_argument("--hf-split", default="train", help="HuggingFace split.")
    parser.add_argument(
        "--hf-data-files",
        default=None,
        help=(
            "Pin a specific file inside the HF repo, e.g. cables_parsed.jsonl, "
            "when the repo ships several files of differing formats."
        ),
    )
    parser.add_argument("--output", type=Path, required=True, help="CSV to write.")
    parser.add_argument("--content-field", default="body")
    parser.add_argument("--label-field", default="classification")
    parser.add_argument("--id-field", default="doc_id")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--max-chars", type=int, default=20000)
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help=(
            "Cap the number of source records read (a smoke-test / sampling "
            "aid). Reads from the start of the stream, so use only for smoke "
            "tests unless the source order is randomised."
        ),
    )
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for FOIArchive → CSV preparation."""
    args = _build_parser().parse_args(argv)
    if args.input is not None:
        records: Iterable[dict[str, Any]] = _iter_jsonl(args.input)
    else:
        records = _iter_hf(
            args.hf_dataset, args.hf_config, args.hf_split, args.hf_data_files
        )
    if args.max_records is not None:
        records = islice(records, args.max_records)

    stats = convert(
        records,
        args.output,
        content_field=args.content_field,
        label_field=args.label_field,
        id_field=args.id_field,
        min_chars=args.min_chars,
        max_chars=args.max_chars,
        test_fraction=args.test_fraction,
        seed=args.seed,
    )
    summary = {
        "output": str(args.output),
        "written": stats.written,
        "per_label": stats.per_label,
        "skipped": {
            "blank": stats.skipped_blank,
            "too_short": stats.skipped_short,
            "unmapped_marking": stats.skipped_unmapped,
            "duplicate": stats.skipped_duplicate,
        },
        "unmapped_markings": dict(
            sorted(stats.unmapped_markings.items(), key=lambda kv: -kv[1])
        ),
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if stats.written > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Convert the gretel synthetic-PII finance corpus into the FR-1 labelled CSV.

``gretelai/synthetic_pii_finance_multilingual`` (Apache-2.0, ungated) is a fully
synthetic corpus of finance-domain documents, each annotated with
character-offset ``pii_spans`` naming the *class* of personal or regulated data
it contains. It holds no real personal data and carries a permissive licence, so
— unlike a leaked-cable corpus — the trained artifact can be shipped and
redistributed without a provenance or privacy caveat. That is why it is the
label ground truth for the sensitivity classifier (``SPEC.md`` 3.2).

The classifier predicts document *sensitivity* (harm on disclosure), so this
script derives each document's tier from the classes of PII present, taking the
most sensitive class (fail-safe: a document is only as low-risk as its most
sensitive element). The mapping is grounded in standard data-handling
categories, not the dataset's own taxonomy:

    RESTRICTED   regulated secrets / authenticators / financial-instrument
                 numbers / government-issued IDs — disclosure enables fraud or
                 identity theft (PCI-DSS / GLBA / eIDAS territory).
    CONFIDENTIAL direct contact / linkage / network-identity data — identifies
                 or reaches an individual but is not a regulated secret; also
                 the fail-safe tier for any PII class not explicitly listed.
    PUBLIC       no PII, or only non-identifying business metadata (a name, a
                 company, a date) that is ubiquitous in ordinary correspondence
                 and low-harm on its own.

Names and dates are non-elevating on purpose: a letter that names a person or
company but carries no contact, location, financial or credential detail is
genuinely low-sensitivity, and treating every name as CONFIDENTIAL would both
collapse the PUBLIC tier and overstate the harm of routine correspondence. An
unrecognised PII class is treated as CONFIDENTIAL, never PUBLIC, so a new
annotation type can never silently downgrade a document. INTERNAL is never
emitted (it is a policy-layer tier, not a model output).

Output is the CSV contract in ``docs/classifier-dataset.md`` (columns
``content,label,source_id,split``), ready for ``python -m app.classifier.training``.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import sys
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Iterator

from app.classifier.labels import SensitivityLabel

#: Disclosure enables fraud/identity theft; regulated under PCI-DSS / GLBA / etc.
RESTRICTED_TYPES: frozenset[str] = frozenset(
    {
        "password",
        "api_key",
        "ssn",
        "passport_number",
        "driver_license_number",
        "credit_card_number",
        "credit_card_security_code",
        "cvv",
        "account_pin",
        "iban",
        "bban",
        "swift_bic_code",
        "bank_routing_number",
        "aba_routing_number",
        "tax_id",
        "national_id",
    }
)

#: Direct contact / linkage / network-identity data. Listed for an honest
#: summary; the mapping treats *any* non-restricted, elevating class the same.
CONFIDENTIAL_TYPES: frozenset[str] = frozenset(
    {
        "email",
        "phone_number",
        "street_address",
        "date_of_birth",
        "customer_id",
        "employee_id",
        "user_name",
        "local_latlng",
        "ipv4",
        "ipv6",
    }
)

#: Non-identifying business metadata: ubiquitous in correspondence, low-harm on
#: its own, so it never by itself raises a document above PUBLIC.
NON_ELEVATING_TYPES: frozenset[str] = frozenset(
    {
        "name",
        "first_name",
        "last_name",
        "company",
        "date",
        "time",
        "date_time",
    }
)


def label_for_spans(span_labels: Iterable[str]) -> SensitivityLabel:
    """Return the most sensitive tier implied by a document's PII classes.

    Fail-safe: the document takes the tier of its most sensitive element,
    RESTRICTED outranks everything, an unrecognised class counts as
    CONFIDENTIAL, and a document with no PII (or only non-elevating metadata)
    is PUBLIC.
    """
    tier = SensitivityLabel.PUBLIC
    for raw in span_labels:
        name = (raw or "").strip().lower()
        if not name or name in NON_ELEVATING_TYPES:
            continue
        if name in RESTRICTED_TYPES:
            return SensitivityLabel.RESTRICTED  # nothing outranks RESTRICTED
        tier = SensitivityLabel.CONFIDENTIAL
    return tier


def _span_labels(raw: Any) -> tuple[list[str], bool]:
    """Extract PII class names from a record's ``pii_spans`` value.

    The gretel corpus stores ``pii_spans`` as a JSON string of
    ``{"label", "start", "end"}`` objects; a local JSONL export may already hold
    the parsed list. Returns ``(labels, ok)``; ``ok`` is False only when the
    value is present but unparseable, so the caller can skip it rather than
    mislabel a document as PUBLIC on a parse failure.
    """
    if raw is None or raw == "":
        return [], True
    spans: Any = raw
    if isinstance(spans, str):
        try:
            spans = json.loads(spans)
        except json.JSONDecodeError:
            return [], False
    if not isinstance(spans, list):
        return [], False
    labels: list[str] = []
    for span in spans:
        if isinstance(span, dict):
            value = span.get("label")
            if value:
                labels.append(str(value))
    return labels, True


@dataclass(frozen=True)
class PrepStats:
    """What the run produced, for an honest, auditable summary."""

    written: int
    skipped_blank: int
    skipped_short: int
    skipped_bad_spans: int
    skipped_duplicate: int
    per_label: dict[str, int]
    seen_types: dict[str, int]
    unknown_types: dict[str, int]


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


def _iter_hf(dataset: str, config: str | None, split: str) -> Iterator[dict[str, Any]]:
    """Yield records streamed from a HuggingFace dataset (never fully loaded)."""
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Reading --hf-dataset requires the 'datasets' package. Install it "
            "in a data-prep environment, or export the dataset to JSONL first."
        ) from exc
    stream = load_dataset(dataset, config, split=split, streaming=True)
    for record in stream:
        yield dict(record)


def convert(
    records: Iterable[dict[str, Any]],
    output_path: Path,
    *,
    content_field: str,
    spans_field: str,
    id_field: str,
    min_chars: int,
    max_chars: int,
    test_fraction: float,
    seed: int,
) -> PrepStats:
    """Write the labelled CSV from ``records`` and return a run summary.

    Records are span-mapped to a tier, deduplicated by content, length-filtered,
    and assigned a stratified ``train``/``test`` split. Every PII class seen is
    counted, and any class outside the three known sets is reported separately so
    a new annotation type surfaces for review instead of being silently folded
    into CONFIDENTIAL.
    """
    rng = random.Random(seed)
    seen: set[str] = set()
    written = skipped_blank = skipped_short = skipped_bad_spans = 0
    skipped_duplicate = 0
    per_label: dict[str, int] = {}
    seen_types: collections.Counter[str] = collections.Counter()
    unknown_types: collections.Counter[str] = collections.Counter()
    known = RESTRICTED_TYPES | CONFIDENTIAL_TYPES | NON_ELEVATING_TYPES

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["content", "label", "source_id", "split"]
        )
        writer.writeheader()
        for record in records:
            content = str(record.get(content_field) or "").strip()
            if not content:
                skipped_blank += 1
                continue
            labels, ok = _span_labels(record.get(spans_field))
            if not ok:
                skipped_bad_spans += 1
                continue
            for raw in labels:
                key = raw.strip().lower()
                if key:
                    seen_types[key] += 1
                    if key not in known:
                        unknown_types[key] += 1
            label = label_for_spans(labels)
            if len(content) < min_chars:
                skipped_short += 1
                continue
            if len(content) > max_chars:
                content = content[:max_chars]
            dedup_key = content.casefold()
            if dedup_key in seen:
                skipped_duplicate += 1
                continue
            seen.add(dedup_key)
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
        skipped_bad_spans=skipped_bad_spans,
        skipped_duplicate=skipped_duplicate,
        per_label=per_label,
        seen_types=dict(seen_types),
        unknown_types=dict(unknown_types),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Local JSON Lines export.")
    source.add_argument(
        "--hf-dataset",
        nargs="?",
        const="gretelai/synthetic_pii_finance_multilingual",
        help=(
            "HuggingFace dataset id; bare flag defaults to "
            "gretelai/synthetic_pii_finance_multilingual."
        ),
    )
    parser.add_argument("--hf-config", default=None, help="HuggingFace config name.")
    parser.add_argument("--hf-split", default="train", help="HuggingFace split.")
    parser.add_argument("--output", type=Path, required=True, help="CSV to write.")
    parser.add_argument("--content-field", default="generated_text")
    parser.add_argument("--spans-field", default="pii_spans")
    parser.add_argument("--id-field", default="index")
    parser.add_argument("--min-chars", type=int, default=64)
    parser.add_argument("--max-chars", type=int, default=20000)
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help=(
            "Cap the number of source records read (a smoke-test aid). Reads "
            "from the start of the stream, so use only for smoke tests."
        ),
    )
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gretel synthetic-PII → CSV preparation."""
    args = _build_parser().parse_args(argv)
    if args.input is not None:
        records: Iterable[dict[str, Any]] = _iter_jsonl(args.input)
    else:
        records = _iter_hf(args.hf_dataset, args.hf_config, args.hf_split)
    if args.max_records is not None:
        records = islice(records, args.max_records)

    stats = convert(
        records,
        args.output,
        content_field=args.content_field,
        spans_field=args.spans_field,
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
            "bad_spans": stats.skipped_bad_spans,
            "duplicate": stats.skipped_duplicate,
        },
        "pii_types_seen": dict(sorted(stats.seen_types.items(), key=lambda kv: -kv[1])),
        "unknown_types_mapped_confidential": dict(
            sorted(stats.unknown_types.items(), key=lambda kv: -kv[1])
        ),
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if stats.written > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

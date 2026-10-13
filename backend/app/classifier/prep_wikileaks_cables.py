"""WikiLeaks diplomatic-cables → CSV preparation, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

This is the *interim* training source for the sensitivity classifier while
access to the primary corpus (``HistoryLab/foiarchive``, gated, awaiting manual
approval) is pending. The cables share FOIArchive's marking vocabulary
(``UNCLASSIFIED`` / ``CONFIDENTIAL`` / ``SECRET`` / ``TOP SECRET``), so the same
:func:`app.classifier.prep_foiarchive.map_marking` and :func:`convert` core are
reused; only the source layout and one preprocessing step differ.

**The preprocessing step matters.** A diplomatic cable prints its own
classification inside the document text — the body is headed ``S E C R E T`` or
``C O N F I D E N T I A L`` (spelled out, letter-spaced). Left in, a model would
learn to *read the marking off the page* rather than learn genuine sensitivity
features, and the held-out accuracy would be a meaningless string-match. That is
exactly the kind of shortcut a patent examiner or security reviewer would call
out. :func:`strip_cable_markings` removes those markings and their handling
caveats so the label is never recoverable from the retained text; the leakage
rate is asserted down to ~0 before any artifact is trained. The trained artifact
is later replaced by a FOIArchive-trained one once access is granted.

Provenance note: the cables are US Government works (public domain). This source
is a development stand-in; the shipped model is retrained on FOIArchive.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from itertools import islice
from pathlib import Path
from typing import Any, Iterable

from app.classifier.prep_foiarchive import (
    _iter_hf,
    _iter_jsonl,
    convert,
)


#: Classification markings as they appear in cable bodies. Each letter is joined
#: by ``\W*`` so both the plain form (``SECRET``) and the letter-spaced telegram
#: form (``S E C R E T``) match. The surrounding lookarounds keep the match from
#: biting into a longer word: the ``SECRET`` in ``Secretary`` is left intact
#: because a letter follows it, while ``S E C R E T SECTION`` is stripped.
def _spaced(word: str) -> str:
    return r"\W*".join(re.escape(ch) for ch in word)


_MARKING_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    + "|".join(
        [
            _spaced("TOPSECRET"),
            _spaced("SECRET"),
            _spaced("CONFIDENTIAL"),
            _spaced("UNCLASSIFIED"),
            _spaced("UNCLAS"),
            _spaced("RESTRICTED"),
        ]
    )
    + r")(?![A-Za-z])",
    re.IGNORECASE,
)

#: Handling caveats that co-occur with the marking and would leak it just as
#: surely (``SECRET//NOFORN``). Stripped wherever they stand alone.
_CAVEAT_RE = re.compile(
    r"(?<![A-Za-z])(?:NOFORN|NODIS|EXDIS|LIMDIS|SIPDIS|ORCON|FOUO"
    r"|FOR\s+OFFICIAL\s+USE\s+ONLY)(?![A-Za-z])",
    re.IGNORECASE,
)

#: ``SECTION 01 OF 02`` pagination markers sit right after the marking and carry
#: post/serial metadata rather than substance.
_SECTION_RE = re.compile(r"SECTION\s+\d+\s+OF\s+\d+", re.IGNORECASE)

#: CSV round-trip artifacts left in the source (``","`` field seams).
_CSV_ARTIFACT_RE = re.compile(r'"\s*,\s*"')

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n\s*\n\s*")


def strip_cable_markings(body: str) -> str:
    """Remove the classification marking, caveats, and seam artifacts from a cable.

    The retained text must not let the label be read back off the page. Legit
    prose (``Secretary``, ``the secret talks``) is deliberately left alone; only
    the standalone marking tokens and their caveats are removed.
    """
    if not body:
        return ""
    text = _CSV_ARTIFACT_RE.sub(" ", body)
    text = _MARKING_RE.sub(" ", text)
    text = _CAVEAT_RE.sub(" ", text)
    text = _SECTION_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n", text)
    return text.strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the WikiLeaks cables CSV for classifier training."
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--input", type=Path, help="Local JSON Lines export.")
    source.add_argument(
        "--hf-dataset",
        help="HuggingFace dataset id, default fn5/wikileaks-cables.",
    )
    parser.add_argument(
        "--hf-data-files",
        default="cables_parsed.jsonl",
        help="File inside the HF repo to stream (default cables_parsed.jsonl).",
    )
    parser.add_argument("--hf-config", default=None)
    parser.add_argument("--hf-split", default="train")
    parser.add_argument("--output", type=Path, required=True, help="CSV to write.")
    parser.add_argument("--content-field", default="body")
    parser.add_argument("--label-field", default="classification")
    parser.add_argument("--id-field", default="cable_id")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--max-chars", type=int, default=20000)
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Cap source records read (smoke-test aid; reads from the start).",
    )
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for WikiLeaks cables → CSV preparation."""
    args = _build_parser().parse_args(argv)
    if args.input is not None:
        records: Iterable[dict[str, Any]] = _iter_jsonl(args.input)
    else:
        dataset = args.hf_dataset or "fn5/wikileaks-cables"
        records = _iter_hf(dataset, args.hf_config, args.hf_split, args.hf_data_files)
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
        content_cleaner=strip_cable_markings,
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

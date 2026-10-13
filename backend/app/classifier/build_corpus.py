"""Build a broad, multi-genre labelled corpus for the FR-1 classifier.

The first trained model learned only the diplomatic-cable register, so arbitrary
out-of-domain documents (a resume, an invoice, a code file) fell back to PUBLIC.
This orchestrator assembles a genuinely multi-genre corpus so the model learns
sensitivity signals across genres, not just cable prose:

* **Cables** -- the real ``HistoryLab``/WikiLeaks diplomatic corpus, already
  carrying PUBLIC/CONFIDENTIAL/RESTRICTED markings. Downsampled to keep every
  scarce RESTRICTED row and cap the majority classes.
* **20 Newsgroups** -- real, diverse public discussion (sklearn; optional, the
  build degrades gracefully if the dataset cannot be fetched offline).
* **Local source files** -- real code/docs from this repo, a public-ish genre the
  cable model never saw.
* **Synthetic sensitive documents** (:mod:`app.classifier.synth`) -- business,
  clinical, engineering, and legal genres that CARRY validated identifiers, the
  breadth the real corpora lack for the sensitive tiers.

Every candidate is relabelled by *weak supervision*: the final label is
``max_rank(genre_prior, detector_label)`` -- the source's own prior, escalated
whenever the high-precision detectors validate a hard identifier actually present
in the text. Detectors can only raise a label, so this never launders a sensitive
document down to PUBLIC; it only lifts a mislabelled-benign prior when real
sensitive content is structurally proven. The output is the ``content,label,
source_id`` CSV that :mod:`app.classifier.training` streams.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Iterator

from app.classifier import synth
from app.classifier.detectors import detect
from app.classifier.labels import SensitivityLabel, most_sensitive_of

csv.field_size_limit(10**9)

Candidate = tuple[str, SensitivityLabel, str]

#: Skip these when harvesting local source: secrets, vendored code, build junk,
#: and the corpus data dir itself must never be pulled into a training file.
_SKIP_DIRS = {
    ".git",
    ".claude",
    ".codex",
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
    "artifacts",
    "data",
    "config",
    "infra",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
}
_CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".rego", ".sql"}
_MIN_CHARS = 40
_MAX_CHARS = 20000


def _final_label(content: str, prior: SensitivityLabel) -> SensitivityLabel:
    """Weak-supervision label: the prior, escalated by any validated detector."""
    detector_label, _ = detect(content)
    if detector_label is None:
        return prior
    return most_sensitive_of([prior, detector_label])


def _clip(content: str) -> str:
    """Bound document length so one giant file cannot dominate a minibatch."""
    return content[:_MAX_CHARS]


def _iter_cables(
    path: Path, rng: random.Random, *, cap_per_majority: int
) -> Iterator[Candidate]:
    """Stream the cables CSV, keeping every RESTRICTED row and reservoir-capping
    the PUBLIC/CONFIDENTIAL majorities so the corpus is not swamped by cables."""
    kept: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            content = (row.get("content") or "").strip()
            raw = (row.get("label") or "").strip().upper()
            if len(content) < _MIN_CHARS:
                continue
            try:
                prior = SensitivityLabel(raw)
            except ValueError:
                continue
            if prior is not SensitivityLabel.RESTRICTED:
                # Probabilistic downsample of the majority classes to the cap.
                seen = kept.get(raw, 0)
                if seen >= cap_per_majority and rng.random() > 0.02:
                    continue
                kept[raw] = seen + 1
            sid = (row.get("source_id") or f"cable-{index}").strip()
            yield _clip(content), _final_label(content, prior), f"cable:{sid}"


def _iter_newsgroups(limit: int) -> Iterator[Candidate]:
    """Real diverse public posts via sklearn; yields nothing if unavailable."""
    try:
        from sklearn.datasets import fetch_20newsgroups
    except ImportError:
        print("[build_corpus] sklearn unavailable; skipping 20 Newsgroups")
        return
    try:
        bunch = fetch_20newsgroups(
            subset="train",
            remove=("headers", "footers", "quotes"),
        )
    except Exception as exc:  # noqa: BLE001 - network/cache failure is non-fatal
        print(f"[build_corpus] 20 Newsgroups fetch failed ({exc}); skipping")
        return
    count = 0
    for index, text in enumerate(bunch.data):
        content = (text or "").strip()
        if len(content) < _MIN_CHARS:
            continue
        yield _clip(content), _final_label(content, SensitivityLabel.PUBLIC), (
            f"20ng:{index}"
        )
        count += 1
        if count >= limit:
            break


def _iter_local_code(root: Path, limit: int) -> Iterator[Candidate]:
    """Real repo source files as a public-genre signal, detector-escalated."""
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= limit:
            break
        if not path.is_file() or path.suffix.lower() not in _CODE_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.name.startswith(".env"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if len(content) < _MIN_CHARS:
            continue
        rel = path.relative_to(root).as_posix()
        yield _clip(content), _final_label(
            content, SensitivityLabel.PUBLIC
        ), f"code:{rel}"
        count += 1


def _iter_synth(per_tier: int, seed: int) -> Iterator[Candidate]:
    """Synthetic sensitive documents, relabelled by the same detector pass."""
    for content, prior, sid in synth.iter_documents(per_tier=per_tier, seed=seed):
        yield content, _final_label(content, prior), sid


def build(
    output: Path,
    *,
    cables: Path | None,
    synth_per_tier: int,
    newsgroups_limit: int,
    code_root: Path | None,
    max_code: int,
    cap_per_majority: int,
    seed: int,
) -> dict[str, int]:
    """Stream every configured source into ``output`` and return label counts."""
    rng = random.Random(seed)
    counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    sources: list[Iterator[Candidate]] = [_iter_synth(synth_per_tier, seed)]
    if cables is not None and cables.is_file():
        sources.append(_iter_cables(cables, rng, cap_per_majority=cap_per_majority))
    elif cables is not None:
        print(f"[build_corpus] cables file not found at {cables}; skipping")
    if newsgroups_limit > 0:
        sources.append(_iter_newsgroups(newsgroups_limit))
    if code_root is not None:
        sources.append(_iter_local_code(code_root, max_code))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["content", "label", "source_id"])
        for source in sources:
            for content, label, sid in source:
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                writer.writerow([content, label.value, sid])
                counts[label.value] = counts.get(label.value, 0) + 1
    return counts


def main() -> None:
    """CLI entry point for building the multi-genre training corpus."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("data/multigenre_corpus.csv")
    )
    parser.add_argument(
        "--cables", type=Path, default=Path("data/wikileaks_cables.csv")
    )
    parser.add_argument("--synth-per-tier", type=int, default=2000)
    parser.add_argument("--newsgroups-limit", type=int, default=8000)
    parser.add_argument("--code-root", type=Path, default=Path("."))
    parser.add_argument("--max-code", type=int, default=800)
    parser.add_argument("--cap-per-majority", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument(
        "--no-newsgroups", action="store_true", help="Skip the 20 Newsgroups source"
    )
    parser.add_argument(
        "--no-code", action="store_true", help="Skip harvesting local source files"
    )
    args = parser.parse_args()

    counts = build(
        args.output,
        cables=args.cables,
        synth_per_tier=args.synth_per_tier,
        newsgroups_limit=0 if args.no_newsgroups else args.newsgroups_limit,
        code_root=None if args.no_code else args.code_root,
        max_code=args.max_code,
        cap_per_majority=args.cap_per_majority,
        seed=args.seed,
    )
    total = sum(counts.values())
    print(f"[build_corpus] wrote {total} rows to {args.output}")
    for label in ("PUBLIC", "CONFIDENTIAL", "RESTRICTED"):
        print(f"  {label}: {counts.get(label, 0)}")
    if total == 0:
        sys.exit("[build_corpus] no rows produced; check the source paths")


if __name__ == "__main__":
    main()

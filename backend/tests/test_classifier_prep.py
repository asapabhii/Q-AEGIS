"""FOIArchive → CSV preparation tests, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

The mapping is deliberately strict: only the four named markings map, unmapped
markings are skipped (never guessed), and INTERNAL is never emitted.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.classifier.labels import SensitivityLabel
from app.classifier.prep_foiarchive import convert, map_marking


def test_map_marking_covers_the_named_markings() -> None:
    assert map_marking("Unclassified") is SensitivityLabel.PUBLIC
    assert map_marking("confidential") is SensitivityLabel.CONFIDENTIAL
    assert map_marking("Secret") is SensitivityLabel.RESTRICTED
    assert map_marking("Top Secret") is SensitivityLabel.RESTRICTED
    # Handling caveats after a slash are ignored for the base marking.
    assert map_marking("Secret/NODIS") is SensitivityLabel.RESTRICTED
    assert map_marking("Top Secret/EXDIS") is SensitivityLabel.RESTRICTED


def test_map_marking_skips_unmapped_and_empty() -> None:
    assert map_marking("Limited Official Use") is None
    assert map_marking("official use only") is None
    assert map_marking("") is None
    assert map_marking(None) is None


def test_map_marking_never_emits_internal() -> None:
    values = {
        map_marking(m) for m in ["Unclassified", "Confidential", "Secret", "Top Secret"]
    }
    assert SensitivityLabel.INTERNAL not in values


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_convert_writes_contract_and_reports_skips(tmp_path: Path) -> None:
    records = [
        {"body": "u" * 300, "classification": "Unclassified", "doc_id": "d1"},
        {"body": "c" * 300, "classification": "Confidential", "doc_id": "d2"},
        {"body": "s" * 300, "classification": "Secret", "doc_id": "d3"},
        {"body": "x" * 300, "classification": "Limited Official Use", "doc_id": "d4"},
        {"body": "", "classification": "Secret", "doc_id": "d5"},
        {"body": "short", "classification": "Secret", "doc_id": "d6"},
    ]
    out = tmp_path / "dataset.csv"

    stats = convert(
        records,
        out,
        content_field="body",
        label_field="classification",
        id_field="doc_id",
        min_chars=200,
        max_chars=20000,
        test_fraction=0.0,
        seed=42,
    )

    assert stats.written == 3
    assert stats.per_label == {
        "PUBLIC": 1,
        "CONFIDENTIAL": 1,
        "RESTRICTED": 1,
    }
    assert stats.skipped_unmapped == 1
    assert stats.unmapped_markings == {"limited official use": 1}
    assert stats.skipped_blank == 1
    assert stats.skipped_short == 1

    written = _read_csv(out)
    assert {row["label"] for row in written} == {
        "PUBLIC",
        "CONFIDENTIAL",
        "RESTRICTED",
    }
    assert all(row["split"] == "train" for row in written)
    assert sorted(row["source_id"] for row in written) == ["d1", "d2", "d3"]


def test_convert_deduplicates_identical_content(tmp_path: Path) -> None:
    records = [
        {"body": "same body text " * 30, "classification": "Secret", "doc_id": "a"},
        {"body": "same body text " * 30, "classification": "Secret", "doc_id": "b"},
    ]
    out = tmp_path / "dataset.csv"

    stats = convert(
        records,
        out,
        content_field="body",
        label_field="classification",
        id_field="doc_id",
        min_chars=10,
        max_chars=20000,
        test_fraction=0.0,
        seed=1,
    )

    assert stats.written == 1
    assert stats.skipped_duplicate == 1


def test_convert_truncates_overlong_content(tmp_path: Path) -> None:
    records = [
        {"body": "z" * 5000, "classification": "Secret", "doc_id": "a"},
    ]
    out = tmp_path / "dataset.csv"

    convert(
        records,
        out,
        content_field="body",
        label_field="classification",
        id_field="doc_id",
        min_chars=10,
        max_chars=1000,
        test_fraction=0.0,
        seed=1,
    )

    row = _read_csv(out)[0]
    assert len(row["content"]) == 1000

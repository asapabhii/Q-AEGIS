"""Tests for the FR-1 classifier dataset/training runway.

These tests do not claim the real classifier is finished. They pin the dataset
contract that must be satisfied before ``stub_classifier.py`` can be replaced.
"""

from pathlib import Path

import pytest

from app.classifier.training import (
    MIN_ROWS_PER_LABEL,
    dataset_fingerprint,
    load_labelled_csv,
)


def _write_dataset(path: Path, rows: list[tuple[str, str]]) -> None:
    body = "content,label,source_id,split\n"
    body += "\n".join(
        f"{content},{label},src-{index},train"
        for index, (content, label) in enumerate(rows)
    )
    path.write_text(body + "\n", encoding="utf-8")


def test_load_labelled_csv_accepts_real_label_contract(tmp_path: Path) -> None:
    rows: list[tuple[str, str]] = []
    for label in ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]:
        for index in range(MIN_ROWS_PER_LABEL):
            rows.append((f"{label.lower()} labelled text {index}", label))
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    examples = load_labelled_csv(dataset_path)

    assert len(examples) == MIN_ROWS_PER_LABEL * 4
    assert dataset_fingerprint(examples) == dataset_fingerprint(examples)


def test_load_labelled_csv_rejects_stub_distillation_shape(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "content,label\nstub output only,CONFIDENTIAL\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="examples per label"):
        load_labelled_csv(dataset_path)


def test_load_labelled_csv_rejects_unknown_label(tmp_path: Path) -> None:
    rows = [("some text", "SECRET")] * (MIN_ROWS_PER_LABEL * 4)
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    with pytest.raises(ValueError, match="label must be one of"):
        load_labelled_csv(dataset_path)

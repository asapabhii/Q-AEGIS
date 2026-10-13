"""Tests for the FR-1 classifier dataset/training contract.

These pin the labelled-data contract the trainer enforces: the three model
tiers only (INTERNAL is a policy-layer tier, rejected here), a minimum per-label
count, and a stable dataset fingerprint.
"""

from pathlib import Path

import pytest

from app.classifier.training import (
    MIN_ROWS_PER_LABEL,
    ML_LABELS,
    dataset_fingerprint,
    load_labelled_csv,
    train_from_csv_streaming,
)

_ML_LABEL_VALUES = [label.value for label in ML_LABELS]


def _write_dataset(path: Path, rows: list[tuple[str, str]]) -> None:
    body = "content,label,source_id,split\n"
    body += "\n".join(
        f"{content},{label},src-{index},train"
        for index, (content, label) in enumerate(rows)
    )
    path.write_text(body + "\n", encoding="utf-8")


def test_ml_labels_exclude_internal() -> None:
    assert "INTERNAL" not in _ML_LABEL_VALUES
    assert set(_ML_LABEL_VALUES) == {"PUBLIC", "CONFIDENTIAL", "RESTRICTED"}


def test_load_labelled_csv_accepts_real_label_contract(tmp_path: Path) -> None:
    rows: list[tuple[str, str]] = []
    for label in _ML_LABEL_VALUES:
        for index in range(MIN_ROWS_PER_LABEL):
            rows.append((f"{label.lower()} labelled text {index}", label))
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    examples = load_labelled_csv(dataset_path)

    assert len(examples) == MIN_ROWS_PER_LABEL * len(_ML_LABEL_VALUES)
    assert dataset_fingerprint(examples) == dataset_fingerprint(examples)


def test_load_labelled_csv_rejects_internal_as_policy_tier(tmp_path: Path) -> None:
    rows = [("internal labelled text", "INTERNAL")] * (MIN_ROWS_PER_LABEL * 3)
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    with pytest.raises(ValueError, match="policy-layer tier"):
        load_labelled_csv(dataset_path)


def test_load_labelled_csv_requires_two_distinct_labels(tmp_path: Path) -> None:
    rows = [("only one class here", "CONFIDENTIAL")] * (MIN_ROWS_PER_LABEL + 1)
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    with pytest.raises(ValueError, match="two distinct labels"):
        load_labelled_csv(dataset_path)


def test_load_labelled_csv_rejects_thin_class(tmp_path: Path) -> None:
    rows = [("public text", "PUBLIC")] * MIN_ROWS_PER_LABEL
    rows += [("restricted text", "RESTRICTED")]  # only one, below the floor
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    with pytest.raises(ValueError, match="examples per label"):
        load_labelled_csv(dataset_path)


def test_load_labelled_csv_rejects_unknown_label(tmp_path: Path) -> None:
    rows = [("some text", "COSMIC")] * (MIN_ROWS_PER_LABEL * 3)
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path, rows)

    with pytest.raises(ValueError, match="label must be one of"):
        load_labelled_csv(dataset_path)


def _write_learnable_dataset(path: Path, per_label: int) -> None:
    """Write a CSV whose text is class-separable so a real model can fit it."""
    vocab = {
        "PUBLIC": "press release bulletin newsletter public announcement",
        "CONFIDENTIAL": "confidential internal memo restricted distribution note",
        "RESTRICTED": "clandestine covert operation sensitive dossier briefing",
    }
    lines = ["content,label,source_id,split"]
    index = 0
    for label in _ML_LABEL_VALUES:
        for token in range(per_label):
            text = f"{vocab[label]} record number {token} filler words here"
            lines.append(f"{text},{label},src-{index},train")
            index += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_train_from_csv_streaming_trains_full_corpus_out_of_core(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.csv"
    _write_learnable_dataset(dataset_path, per_label=40)
    output_dir = tmp_path / "artifacts"

    artifact = train_from_csv_streaming(
        dataset_path,
        output_dir,
        version="streaming-test-1.0.0",
        batch_size=16,
        epochs=3,
        n_features=2**16,
        test_fraction=0.2,
        calibration_fraction=0.2,
    )

    assert artifact.exists()
    report_path = output_dir / "streaming-test-1.0.0.evaluation.json"
    assert report_path.exists()

    import joblib

    bundle = joblib.load(artifact)
    assert bundle["model_version"] == "streaming-test-1.0.0"
    assert bundle["dataset_fingerprint"]
    model = bundle["model"]
    # The runtime loader requires calibrated probabilities and known classes.
    assert hasattr(model, "predict_proba")
    assert set(model.classes_).issubset(set(_ML_LABEL_VALUES))
    proba = model.predict_proba(["clandestine covert operation dossier"])[0]
    assert abs(sum(proba) - 1.0) < 1e-6


def test_train_from_csv_streaming_rejects_thin_train_fold(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    _write_learnable_dataset(dataset_path, per_label=2)  # too few after split
    output_dir = tmp_path / "artifacts"

    with pytest.raises(ValueError, match="training rows after the split"):
        train_from_csv_streaming(
            dataset_path,
            output_dir,
            version="streaming-thin-1.0.0",
            batch_size=8,
            epochs=1,
            n_features=2**14,
        )

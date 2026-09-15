"""Training utilities for the future FR-1 Scikit-learn classifier.

This module is not used by the runtime classifier yet. It exists to make the
dataset dependency executable and reviewable: real training requires a labelled
CSV that follows ``docs/classifier-dataset.md``. Until such data exists,
``stub_classifier.py`` remains the explicitly labelled production stub.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.classifier.labels import SensitivityLabel

REQUIRED_COLUMNS = {"content", "label"}
ALLOWED_SPLITS = {"train", "validation", "test"}
MIN_ROWS_PER_LABEL = 5


@dataclass(frozen=True)
class LabelledExample:
    """One human-labelled classifier training example."""

    content: str
    label: SensitivityLabel
    source_id: str | None = None
    split: str | None = None


def load_labelled_csv(path: Path) -> list[LabelledExample]:
    """Load and validate the FR-1 labelled dataset CSV.

    Raises:
        ValueError: if required columns, labels, content, split names, or class
            counts are invalid.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"Dataset missing required column(s): {sorted(missing)}")

        examples: list[LabelledExample] = []
        for line_number, row in enumerate(reader, start=2):
            content = (row.get("content") or "").strip()
            if not content:
                raise ValueError(f"Line {line_number}: content must not be blank")

            raw_label = (row.get("label") or "").strip().upper()
            try:
                label = SensitivityLabel(raw_label)
            except ValueError as exc:
                allowed = ", ".join(item.value for item in SensitivityLabel)
                raise ValueError(
                    f"Line {line_number}: label must be one of {allowed}"
                ) from exc

            raw_split = (row.get("split") or "").strip().lower()
            split = raw_split or None
            if split is not None and split not in ALLOWED_SPLITS:
                raise ValueError(
                    f"Line {line_number}: split must be one of "
                    f"{sorted(ALLOWED_SPLITS)}"
                )

            source_id = (row.get("source_id") or "").strip() or None
            examples.append(
                LabelledExample(
                    content=content,
                    label=label,
                    source_id=source_id,
                    split=split,
                )
            )

    _validate_label_coverage(examples)
    return examples


def dataset_fingerprint(examples: Iterable[LabelledExample]) -> str:
    """Return a stable SHA-256 fingerprint for a labelled dataset."""
    payload = [
        {
            "content_hash": hashlib.sha256(example.content.encode("utf-8")).hexdigest(),
            "label": example.label.value,
            "source_id": example.source_id,
            "split": example.split,
        }
        for example in examples
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def train_from_csv(dataset_path: Path, output_dir: Path, *, version: str) -> Path:
    """Train a TF-IDF + calibrated linear classifier from a real labelled CSV.

    The Scikit-learn dependency is intentionally imported inside this function
    so normal runtime and CI paths do not pretend the real classifier exists.
    """
    try:
        import joblib
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics import classification_report
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.svm import LinearSVC
    except ImportError as exc:
        raise RuntimeError(
            "Training requires scikit-learn and joblib. Install them in a "
            "training environment before running this command."
        ) from exc

    examples = load_labelled_csv(dataset_path)
    texts = [example.content for example in examples]
    labels = [example.label.value for example in examples]
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2)),
            ("clf", CalibratedClassifierCV(LinearSVC(class_weight="balanced"))),
        ]
    )
    model.fit(train_texts, train_labels)

    predictions = model.predict(test_texts)
    report = classification_report(
        test_labels,
        predictions,
        labels=[label.value for label in SensitivityLabel],
        output_dict=True,
        zero_division=0,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{version}.joblib"
    report_path = output_dir / f"{version}.evaluation.json"
    joblib.dump(model, artifact_path)
    report_path.write_text(
        json.dumps(
            {
                "model_version": version,
                "dataset_fingerprint": dataset_fingerprint(examples),
                "test_size": len(test_texts),
                "report": report,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact_path


def _validate_label_coverage(examples: list[LabelledExample]) -> None:
    if not examples:
        raise ValueError("Dataset must contain at least one labelled row")
    counts = {label: 0 for label in SensitivityLabel}
    for example in examples:
        counts[example.label] += 1
    too_small = {
        label.value: count
        for label, count in counts.items()
        if count < MIN_ROWS_PER_LABEL
    }
    if too_small:
        raise ValueError(
            "Dataset must contain at least "
            f"{MIN_ROWS_PER_LABEL} examples per label; got {too_small}"
        )


def main() -> None:
    """CLI entry point for offline classifier training."""
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/classifier"))
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    artifact = train_from_csv(args.dataset, args.output_dir, version=args.version)
    print(artifact)


if __name__ == "__main__":
    main()

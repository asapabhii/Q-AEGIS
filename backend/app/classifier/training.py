"""Training for the FR-1 Scikit-learn sensitivity classifier, ``SPEC.md`` 3.2.

Produces the artifact the runtime loads: :func:`train_from_csv` fits a
TF-IDF + calibrated linear model on a real labelled CSV
(``docs/classifier-dataset.md``) and writes a ``{version}.joblib`` metadata
bundle plus a ``{version}.evaluation.json`` report. Point
``Settings.classifier_model_path`` at the bundle to activate the trained engine
(:mod:`app.classifier.model_classifier`); until an artifact exists, the keyword
engine in :mod:`app.classifier.stub_classifier` remains the labelled fallback.

The model predicts only the markings a public corpus actually carries
(PUBLIC/CONFIDENTIAL/RESTRICTED). INTERNAL is a policy-layer tier and is
rejected from training data rather than synthesised. Do not train on synthetic
labels or on the keyword stub's own outputs; that would only distill the stub.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from app.classifier.labels import SensitivityLabel

REQUIRED_COLUMNS = {"content", "label"}
ALLOWED_SPLITS = {"train", "validation", "test"}
MIN_ROWS_PER_LABEL = 5

#: INTERNAL is a policy-layer tier, never a model output: no public corpus
#: carries an "internal" marking, and inventing one would train the model on a
#: synthetic label. The trained model predicts only these markings; INTERNAL is
#: assigned downstream by policy. See ``docs/classifier-dataset.md``.
POLICY_ONLY_LABELS: frozenset[SensitivityLabel] = frozenset({SensitivityLabel.INTERNAL})
ML_LABELS: tuple[SensitivityLabel, ...] = tuple(
    label for label in SensitivityLabel if label not in POLICY_ONLY_LABELS
)


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
        _require_columns(reader.fieldnames)
        examples = [
            _parse_row(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]

    _validate_label_coverage(examples)
    return examples


def _require_columns(fieldnames: Iterable[str] | None) -> None:
    """Raise if the dataset is missing a required column."""
    missing = REQUIRED_COLUMNS - set(fieldnames or [])
    if missing:
        raise ValueError(f"Dataset missing required column(s): {sorted(missing)}")


def _parse_row(row: dict[str, str], line_number: int) -> LabelledExample:
    """Validate and coerce one CSV row into a :class:`LabelledExample`.

    Shared by the in-memory loader and the streaming trainer so both enforce the
    identical label contract (three model tiers, INTERNAL rejected as a
    policy-layer tier, known split names only).
    """
    content = (row.get("content") or "").strip()
    if not content:
        raise ValueError(f"Line {line_number}: content must not be blank")

    raw_label = (row.get("label") or "").strip().upper()
    try:
        label = SensitivityLabel(raw_label)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SensitivityLabel)
        raise ValueError(f"Line {line_number}: label must be one of {allowed}") from exc
    if label in POLICY_ONLY_LABELS:
        raise ValueError(
            f"Line {line_number}: {label.value} is a policy-layer tier, "
            "not a model output; training data must not contain it. "
            f"Allowed labels: {', '.join(item.value for item in ML_LABELS)}."
        )

    raw_split = (row.get("split") or "").strip().lower()
    split = raw_split or None
    if split is not None and split not in ALLOWED_SPLITS:
        raise ValueError(
            f"Line {line_number}: split must be one of {sorted(ALLOWED_SPLITS)}"
        )

    source_id = (row.get("source_id") or "").strip() or None
    return LabelledExample(
        content=content,
        label=label,
        source_id=source_id,
        split=split,
    )


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


def _split_bucket(
    key: str, *, seed: int, test_fraction: float, calibration_fraction: float
) -> str:
    """Assign a row deterministically to ``train``/``calibration``/``test``.

    The bucket is a pure function of the row key and seed, so the same corpus
    always produces the same split without holding every row in memory — the
    out-of-core analogue of a seeded ``train_test_split``.
    """
    digest = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()
    fraction = (int(digest[:8], 16) % 1_000_000) / 1_000_000
    if fraction < test_fraction:
        return "test"
    if fraction < test_fraction + calibration_fraction:
        return "calibration"
    return "train"


def _iter_parsed_rows(path: Path) -> Iterator[LabelledExample]:
    """Yield validated :class:`LabelledExample` rows one at a time from a CSV.

    Unlike :func:`load_labelled_csv` this never materialises the whole corpus,
    so a dataset larger than memory can be streamed through the trainer.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames)
        for line_number, row in enumerate(reader, start=2):
            yield _parse_row(row, line_number)


def train_from_csv_streaming(
    dataset_path: Path,
    output_dir: Path,
    *,
    version: str,
    batch_size: int = 2000,
    epochs: int = 5,
    n_features: int = 2**20,
    test_fraction: float = 0.1,
    calibration_fraction: float = 0.1,
    seed: int = 42,
) -> Path:
    """Train the FR-1 classifier out-of-core on a corpus larger than memory.

    The in-memory :func:`train_from_csv` fits a TF-IDF vocabulary over the whole
    corpus at once, which cannot scale past available RAM. This path instead uses
    a stateless :class:`HashingVectorizer` and an :class:`SGDClassifier` trained
    by repeated ``partial_fit`` over minibatches, so peak memory is bounded by
    ``batch_size`` rather than corpus size — the entire labelled set is trained
    on, in ``epochs`` streaming passes, without ever holding it all in memory.

    Calibrated probabilities are preserved (the runtime's fail-safe threshold
    depends on them): the incrementally-fitted linear model is wrapped in a
    prefit :class:`CalibratedClassifierCV` fitted on a held-out calibration slice,
    and a separate held-out test slice produces the evaluation report. The
    artifact is the same ``{model, model_version, labels, dataset_fingerprint}``
    bundle the runtime loader expects, so this trainer is a drop-in for large
    corpora.
    """
    try:
        import joblib
        import numpy as np
        import scipy.sparse as sp
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.feature_extraction.text import (
            HashingVectorizer,
            TfidfTransformer,
        )
        from sklearn.linear_model import SGDClassifier
        from sklearn.metrics import classification_report
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Training requires scikit-learn and joblib. Install them in a "
            "training environment before running this command."
        ) from exc

    # Raw hashed term counts (norm=None): the IDF weighting and L2 normalisation
    # are applied by the TfidfTransformer stage below. Emitting plain counts here
    # lets us accumulate document frequencies out-of-core and reconstruct the same
    # TF-IDF representation the in-memory trainer uses, which the minority
    # (RESTRICTED) class depends on — plain term-frequency alone loses the
    # rare-discriminative-term signal and collapses minority recall.
    vectorizer = HashingVectorizer(
        ngram_range=(1, 2),
        alternate_sign=False,
        norm=None,
        n_features=n_features,
    )

    # Pass one: stream the whole corpus once to validate it, learn the label set
    # and train-fold counts, compute an order-stable fingerprint, accumulate the
    # per-feature document frequency over the train fold (bounded — one dense
    # vector of length n_features, not the corpus), and buffer the (small)
    # calibration and test folds. The large train fold is NOT buffered; it is
    # re-streamed each epoch below.
    train_counts: dict[str, int] = {}
    cal_texts: list[str] = []
    cal_labels: list[str] = []
    test_texts: list[str] = []
    test_labels: list[str] = []
    document_frequency = np.zeros(n_features, dtype=np.float64)
    df_batch: list[str] = []

    def _accumulate_df(texts: list[str]) -> None:
        """Add the batch's per-feature document frequency into the running total."""
        counts = vectorizer.transform(texts)
        indicator = counts.copy()
        indicator.data = np.ones_like(indicator.data)
        document_frequency[:] += np.asarray(indicator.sum(axis=0)).ravel()

    fingerprint = hashlib.sha256()
    for example in _iter_parsed_rows(dataset_path):
        content_hash = hashlib.sha256(example.content.encode("utf-8")).hexdigest()
        fingerprint.update(
            f"{content_hash}|{example.label.value}|{example.source_id}\n".encode(
                "utf-8"
            )
        )
        bucket = _split_bucket(
            example.source_id or example.content,
            seed=seed,
            test_fraction=test_fraction,
            calibration_fraction=calibration_fraction,
        )
        if bucket == "test":
            test_texts.append(example.content)
            test_labels.append(example.label.value)
        elif bucket == "calibration":
            cal_texts.append(example.content)
            cal_labels.append(example.label.value)
        else:
            train_counts[example.label.value] = (
                train_counts.get(example.label.value, 0) + 1
            )
            df_batch.append(example.content)
            if len(df_batch) >= batch_size:
                _accumulate_df(df_batch)
                df_batch = []
    if df_batch:
        _accumulate_df(df_batch)

    _validate_streaming_folds(train_counts, cal_labels, test_labels)
    classes = np.array(sorted(train_counts))

    # Build the TF-IDF stage from the streamed document frequencies using the
    # exact scikit-learn smooth-IDF formula, then inject it so the whole corpus
    # matrix is never materialised. The transform then matches what the in-memory
    # TfidfVectorizer would produce for the same tokens.
    n_train_docs = sum(train_counts.values())
    idf = np.log((1.0 + n_train_docs) / (1.0 + document_frequency)) + 1.0
    tfidf = TfidfTransformer(norm="l2", use_idf=True, smooth_idf=True)
    tfidf.fit(sp.csr_matrix((1, n_features), dtype=np.float64))
    tfidf.idf_ = idf

    def _features(texts: list[str]) -> object:
        """Hashed counts → injected TF-IDF, the representation the model sees."""
        return tfidf.transform(vectorizer.transform(texts))

    # Passes two..N+1: minibatch SGD over the re-streamed train fold. classes= is
    # required on the very first partial_fit and forbidden thereafter.
    # SGD's partial_fit rejects class_weight="balanced" (it cannot see the whole
    # target at once), so compute the identical balanced weights up front from the
    # known train-fold frequencies and pass them explicitly. loss="hinge" is the
    # linear-SVM objective the in-memory trainer's LinearSVC optimises; probability
    # is recovered by the prefit sigmoid calibration below, matching that path.
    total_train = sum(train_counts.values())
    class_weight = {
        label: total_train / (len(train_counts) * count)
        for label, count in train_counts.items()
    }
    classifier = SGDClassifier(
        loss="hinge", class_weight=class_weight, random_state=seed
    )
    rng = random.Random(seed)
    first_batch = True

    def _fit_batch(texts: list[str], labels: list[str]) -> None:
        nonlocal first_batch
        order = list(range(len(texts)))
        rng.shuffle(order)
        matrix = _features([texts[i] for i in order])
        target = [labels[i] for i in order]
        classifier.partial_fit(matrix, target, classes=classes if first_batch else None)
        first_batch = False

    for _ in range(epochs):
        batch_texts: list[str] = []
        batch_labels: list[str] = []
        for example in _iter_parsed_rows(dataset_path):
            bucket = _split_bucket(
                example.source_id or example.content,
                seed=seed,
                test_fraction=test_fraction,
                calibration_fraction=calibration_fraction,
            )
            if bucket != "train":
                continue
            batch_texts.append(example.content)
            batch_labels.append(example.label.value)
            if len(batch_texts) >= batch_size:
                _fit_batch(batch_texts, batch_labels)
                batch_texts, batch_labels = [], []
        if batch_texts:
            _fit_batch(batch_texts, batch_labels)

    # Calibrate on the held-out calibration fold so predict_proba is meaningful,
    # then assemble the stateless vectorizer + IDF stage + calibrated model into
    # one pipeline the runtime loads unchanged.
    calibrated = _calibrate_prefit(
        CalibratedClassifierCV, classifier, _features(cal_texts), cal_labels
    )
    model = Pipeline(
        [
            ("vectorizer", vectorizer),
            ("tfidf", tfidf),
            ("classifier", calibrated),
        ]
    )

    predictions = calibrated.predict(_features(test_texts))
    present_labels = classes.tolist()
    report = classification_report(
        test_labels,
        predictions,
        labels=present_labels,
        output_dict=True,
        zero_division=0,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{version}.joblib"
    report_path = output_dir / f"{version}.evaluation.json"
    digest = fingerprint.hexdigest()
    joblib.dump(
        {
            "model": model,
            "model_version": version,
            "labels": present_labels,
            "dataset_fingerprint": digest,
        },
        artifact_path,
    )
    report_path.write_text(
        json.dumps(
            {
                "model_version": version,
                "dataset_fingerprint": digest,
                "labels": present_labels,
                "training_method": "streaming-hashing-tfidf-svm",
                "n_features": n_features,
                "epochs": epochs,
                "train_size": sum(train_counts.values()),
                "calibration_size": len(cal_labels),
                "test_size": len(test_labels),
                "report": report,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact_path


def _calibrate_prefit(
    calibrated_cls: type, estimator: object, matrix: object, labels: list[str]
) -> object:
    """Fit a prefit probability calibrator, tolerant of the sklearn version.

    ``cv="prefit"`` is deprecated from scikit-learn 1.6 in favour of wrapping the
    fitted estimator in ``FrozenEstimator``; this uses the frozen form when
    available and the legacy keyword otherwise, so the trainer runs cleanly on
    either and never trips ``filterwarnings=error`` under the test suite.
    """
    try:
        from sklearn.frozen import FrozenEstimator

        calibrator = calibrated_cls(FrozenEstimator(estimator), method="sigmoid")
    except ImportError:  # pragma: no cover - older scikit-learn
        calibrator = calibrated_cls(estimator, method="sigmoid", cv="prefit")
    calibrator.fit(matrix, labels)
    return calibrator


def _validate_streaming_folds(
    train_counts: dict[str, int], cal_labels: list[str], test_labels: list[str]
) -> None:
    """Guard the out-of-core split the same way the in-memory loader guards its."""
    if len(train_counts) < 2:
        raise ValueError(
            "Dataset must contain at least two distinct labels to train a "
            f"classifier; got {sorted(train_counts)}"
        )
    too_small = {
        label: count
        for label, count in train_counts.items()
        if count < MIN_ROWS_PER_LABEL
    }
    if too_small:
        raise ValueError(
            "Every label needs at least "
            f"{MIN_ROWS_PER_LABEL} training rows after the split; got {too_small}"
        )
    if not cal_labels:
        raise ValueError("Calibration fold is empty; increase calibration_fraction")
    if not test_labels:
        raise ValueError("Test fold is empty; increase test_fraction")


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
    # Only the labels actually present are model classes; INTERNAL is excluded
    # at load time, so the report never invents a row for a policy-only tier.
    present_labels = sorted({example.label.value for example in examples})
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
        labels=present_labels,
        output_dict=True,
        zero_division=0,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{version}.joblib"
    report_path = output_dir / f"{version}.evaluation.json"
    fingerprint = dataset_fingerprint(examples)
    # A metadata bundle, not the bare pipeline: the runtime loader
    # (app/classifier/model_classifier.py) reads model_version and the label set
    # from here so every stored classification is attributable.
    joblib.dump(
        {
            "model": model,
            "model_version": version,
            "labels": present_labels,
            "dataset_fingerprint": fingerprint,
        },
        artifact_path,
    )
    report_path.write_text(
        json.dumps(
            {
                "model_version": version,
                "dataset_fingerprint": fingerprint,
                "labels": present_labels,
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
    counts: dict[SensitivityLabel, int] = {}
    for example in examples:
        counts[example.label] = counts.get(example.label, 0) + 1
    if len(counts) < 2:
        raise ValueError(
            "Dataset must contain at least two distinct labels to train a "
            f"classifier; got {sorted(label.value for label in counts)}"
        )
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
    parser.add_argument(
        "--streaming",
        action="store_true",
        help=(
            "Train out-of-core (HashingVectorizer + minibatch SGD) so a corpus "
            "larger than RAM is trained on in full. Use for large datasets; the "
            "default in-memory TF-IDF path suits datasets that fit in memory."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--n-features", type=int, default=2**20)
    args = parser.parse_args()
    if args.streaming:
        artifact = train_from_csv_streaming(
            args.dataset,
            args.output_dir,
            version=args.version,
            batch_size=args.batch_size,
            epochs=args.epochs,
            n_features=args.n_features,
        )
    else:
        artifact = train_from_csv(args.dataset, args.output_dir, version=args.version)
    print(artifact)


if __name__ == "__main__":
    main()

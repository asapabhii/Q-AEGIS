"""Trained-model classifier engine tests, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

These assert the properties that must survive the swap from keyword rules to a
trained model: graceful fallback when no artifact is present, the keyword rules
as an escalation-only override, the low-confidence fail-safe, and loud failure
on a misconfigured artifact (never a silent downgrade to keywords).
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pytest

import app.classifier as classifier
from app.classifier import model_classifier
from app.classifier.labels import SensitivityLabel
from app.config import get_settings


class _FakeModel:
    """A stand-in for a trained pipeline with fixed calibrated probabilities."""

    def __init__(self, classes: list[str], proba: list[float]):
        self.classes_ = list(classes)
        self._proba = list(proba)

    def predict_proba(self, texts: list[str]) -> list[list[float]]:
        return [list(self._proba) for _ in texts]


def _dump_bundle(
    tmp_path: Path,
    *,
    model: object,
    version: str = "test-tfidf-svc-1.0.0",
    labels: list[str] | None = None,
) -> Path:
    path = tmp_path / f"{version}.joblib"
    joblib.dump(
        {
            "model": model,
            "model_version": version,
            "labels": labels or getattr(model, "classes_", []),
        },
        path,
    )
    return path


def _activate(monkeypatch: pytest.MonkeyPatch, path: Path | str) -> None:
    monkeypatch.setenv("CLASSIFIER_MODEL_PATH", str(path))
    get_settings.cache_clear()


def test_falls_back_to_keyword_engine_when_unconfigured() -> None:
    # No CLASSIFIER_MODEL_PATH set by the settings fixture.
    assert model_classifier.is_active() is False
    assert classifier.active_model_version() == classifier.KEYWORD_MODEL_VERSION
    result = classifier.classify("a press release for public distribution")
    assert result.model_version == classifier.KEYWORD_MODEL_VERSION


def test_falls_back_when_configured_path_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _activate(monkeypatch, tmp_path / "does-not-exist.joblib")
    assert model_classifier.is_active() is False
    result = classifier.classify("some ordinary text")
    assert result.model_version == classifier.KEYWORD_MODEL_VERSION


def test_high_confidence_prediction_is_not_escalated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = _FakeModel(
        classes=["PUBLIC", "CONFIDENTIAL", "RESTRICTED"],
        proba=[0.90, 0.07, 0.03],
    )
    _activate(monkeypatch, _dump_bundle(tmp_path, model=model))

    result = classifier.classify("an unremarkable paragraph of text")

    assert model_classifier.is_active() is True
    assert result.sensitivity_label is SensitivityLabel.PUBLIC
    assert result.base_label is SensitivityLabel.PUBLIC
    assert result.is_defaulted is False
    assert result.confidence == pytest.approx(0.90)
    assert result.model_version == "test-tfidf-svc-1.0.0"


def test_low_confidence_prediction_escalates_toward_more_protection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Best class is PUBLIC but only 0.40 — below the 0.60 default threshold.
    model = _FakeModel(
        classes=["PUBLIC", "CONFIDENTIAL", "RESTRICTED"],
        proba=[0.40, 0.35, 0.25],
    )
    _activate(monkeypatch, _dump_bundle(tmp_path, model=model))

    result = classifier.classify("ambiguous text with no keyword hits")

    assert result.base_label is SensitivityLabel.PUBLIC
    assert result.is_defaulted is True
    # Escalated one step: PUBLIC -> INTERNAL.
    assert result.sensitivity_label is SensitivityLabel.INTERNAL


def test_keyword_rule_overrides_a_confident_but_wrong_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Model is confidently PUBLIC, but the text contains a hard identifier.
    model = _FakeModel(
        classes=["PUBLIC", "CONFIDENTIAL", "RESTRICTED"],
        proba=[0.95, 0.03, 0.02],
    )
    _activate(monkeypatch, _dump_bundle(tmp_path, model=model))

    result = classifier.classify("please store the user's SSN in this record")

    # The RESTRICTED keyword rule raises the base; the model never downgrades it.
    assert result.base_label is SensitivityLabel.RESTRICTED
    assert result.sensitivity_label is SensitivityLabel.RESTRICTED
    assert "ssn" in result.matched_keywords
    # High model confidence means no additional fail-safe escalation was needed.
    assert result.is_defaulted is False


def test_keyword_rule_never_downgrades_a_sensitive_model_prediction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Model says RESTRICTED confidently; a milder PUBLIC keyword must not lower it.
    model = _FakeModel(
        classes=["PUBLIC", "CONFIDENTIAL", "RESTRICTED"],
        proba=[0.02, 0.08, 0.90],
    )
    _activate(monkeypatch, _dump_bundle(tmp_path, model=model))

    result = classifier.classify("this press release is for public distribution")

    assert result.base_label is SensitivityLabel.RESTRICTED
    assert result.sensitivity_label is SensitivityLabel.RESTRICTED


def test_malformed_artifact_fails_loud_not_silent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "bad.joblib"
    joblib.dump({"not_a_model": True}, path)
    _activate(monkeypatch, path)

    # is_active() only checks presence; the load must raise rather than quietly
    # degrade to the keyword engine (a silent downgrade of the whole classifier).
    assert model_classifier.is_active() is True
    with pytest.raises(model_classifier.ModelArtifactError):
        classifier.classify("anything")


def test_artifact_missing_version_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = _FakeModel(classes=["PUBLIC", "RESTRICTED"], proba=[0.5, 0.5])
    path = tmp_path / "noversion.joblib"
    joblib.dump({"model": model, "labels": model.classes_}, path)
    _activate(monkeypatch, path)

    with pytest.raises(model_classifier.ModelArtifactError, match="model_version"):
        model_classifier.classify("text")


def test_artifact_with_unknown_label_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = _FakeModel(classes=["PUBLIC", "COSMIC"], proba=[0.5, 0.5])
    _activate(monkeypatch, _dump_bundle(tmp_path, model=model))

    with pytest.raises(model_classifier.ModelArtifactError, match="unknown label"):
        model_classifier.classify("text")


def test_training_artifact_is_loadable_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A model produced by training.py loads and classifies through the runtime."""
    pytest.importorskip("sklearn")
    from app.classifier.training import train_from_csv

    header = "content,label,source_id,split\n"
    rows = []
    # Three separable classes with enough rows for the calibration CV.
    corpus = {
        "PUBLIC": "public bulletin community newsletter open notice",
        "CONFIDENTIAL": "confidential salary payroll internal finance memo",
        "RESTRICTED": "classified secret dossier operation intelligence brief",
    }
    for label, base in corpus.items():
        for i in range(20):
            rows.append(f"{base} number {i},{label},src-{label}-{i},train")
    dataset = tmp_path / "dataset.csv"
    dataset.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")

    artifact = train_from_csv(
        dataset, tmp_path / "artifacts", version="foiarchive-tfidf-svc-test"
    )
    assert artifact.exists()

    _activate(monkeypatch, artifact)
    assert model_classifier.is_active() is True
    result = classifier.classify("classified secret dossier operation brief")
    assert result.model_version == "foiarchive-tfidf-svc-test"
    assert result.sensitivity_label in set(SensitivityLabel)

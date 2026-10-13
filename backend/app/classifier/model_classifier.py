"""Trained sensitivity classifier, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

This is the real model engine that supersedes the keyword STUB once a trained
artifact exists. It loads a Scikit-learn pipeline produced by
:mod:`app.classifier.training` and turns its calibrated probabilities into a
:class:`~app.classifier.result.ClassificationResult`, preserving every security
property the keyword engine established:

- **Fail-safe escalation.** A prediction whose calibrated confidence is below
  the configured threshold escalates one step toward more protection, exactly as
  the keyword engine does. This survives the model swap; ``PRD.md`` Risk R1.
- **Keyword rules as an escalation-only override.** The high-precision keyword
  rules (SSN, secret markings, and so on) can only push the label *up*. A rule
  firing more sensitive than the model overrides the model toward protection; a
  rule never downgrades the model. So the trained model cannot silently miss a
  hard identifier the rules would have caught.
- **INTERNAL is never a model output.** The model predicts only the markings
  present in its training corpus (PUBLIC/CONFIDENTIAL/RESTRICTED). INTERNAL is a
  policy-layer tier assigned elsewhere; see ``docs/classifier-dataset.md``.

The engine is selected at runtime by :func:`app.classifier.classify`: it is used
only when ``Settings.classifier_model_path`` names an artifact that exists,
otherwise the keyword engine remains in force. Loading is cached by path and
file mtime, so a rotated artifact is picked up without a restart.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from app.classifier.detectors import apply_detectors
from app.classifier.labels import SensitivityLabel, escalate, rank
from app.classifier.result import ClassificationResult
from app.classifier.stub_classifier import _score, _select_base_label
from app.config import get_settings


class ModelArtifactError(RuntimeError):
    """A configured classifier artifact is missing, unreadable, or malformed."""


class _LoadedModel:
    """A trained pipeline plus the metadata needed to attribute its output."""

    def __init__(self, *, model: Any, model_version: str, classes: tuple[str, ...]):
        self.model = model
        self.model_version = model_version
        self.classes = classes


_LOCK = threading.Lock()
#: Cache keyed by ``(absolute_path, mtime_ns)`` so a rotated artifact reloads.
_CACHE: dict[tuple[str, int], _LoadedModel] = {}


def _load_artifact(path: Path) -> _LoadedModel:
    """Load and validate a trained artifact, caching by path + mtime.

    Security / trust boundary: ``joblib.load`` unpickles the artifact, and
    unpickling is arbitrary code execution. ``path`` comes solely from the
    operator-set ``CLASSIFIER_MODEL_PATH`` config (never from request data or
    any untrusted input), so this deserializes only an operator-provisioned
    file. That invariant must hold: never point ``CLASSIFIER_MODEL_PATH`` at a
    location a lower-trust party can write.

    Raises:
        ModelArtifactError: if the file is missing, joblib is unavailable, or
            the payload is not a recognized training artifact.
    """
    try:
        stat = path.stat()
    except OSError as exc:
        raise ModelArtifactError(f"Classifier artifact not found: {path}") from exc

    key = (str(path.resolve()), stat.st_mtime_ns)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        try:
            import joblib
        except ImportError as exc:  # pragma: no cover - joblib ships with sklearn
            raise ModelArtifactError(
                "Loading a trained classifier requires joblib. Install the "
                "training extras, or unset classifier_model_path to use the "
                "keyword engine."
            ) from exc

        # Unpickle of an operator-controlled path only (see docstring): the
        # path is config, never request-derived.
        payload = joblib.load(path)
        loaded = _coerce_payload(payload, path)
        _CACHE[key] = loaded
        return loaded


def _coerce_payload(payload: Any, path: Path) -> _LoadedModel:
    """Validate a loaded joblib payload into a :class:`_LoadedModel`."""
    if not isinstance(payload, dict) or "model" not in payload:
        raise ModelArtifactError(
            f"Artifact {path} is not a Q-AEGIS classifier bundle "
            "(expected a dict with a 'model' key produced by training.py)."
        )
    model = payload["model"]
    if not hasattr(model, "predict_proba"):
        raise ModelArtifactError(
            f"Artifact {path} model does not expose predict_proba; the trained "
            "pipeline must be calibrated (CalibratedClassifierCV)."
        )
    version = str(payload.get("model_version") or "").strip()
    if not version:
        raise ModelArtifactError(f"Artifact {path} is missing model_version.")

    classes = tuple(str(c) for c in getattr(model, "classes_", ()))
    for raw in classes:
        try:
            SensitivityLabel(raw)
        except ValueError as exc:
            raise ModelArtifactError(
                f"Artifact {path} predicts unknown label {raw!r}."
            ) from exc
    return _LoadedModel(model=model, model_version=version, classes=classes)


def active_model_version() -> str | None:
    """Return the configured model's version, or None when none is active."""
    path = _configured_path()
    if path is None:
        return None
    return _load_artifact(path).model_version


def _configured_path() -> Path | None:
    """Return the configured artifact path if set and present, else None."""
    configured = get_settings().classifier_model_path
    if not configured:
        return None
    path = Path(configured)
    return path if path.is_file() else None


def is_active() -> bool:
    """True when a usable trained artifact is configured and on disk."""
    return _configured_path() is not None


def classify(content: str, *, threshold: float | None = None) -> ClassificationResult:
    """Classify ``content`` with the trained model and the keyword override.

    Args:
        content: Raw document text.
        threshold: Confidence threshold override. Defaults to
            ``Settings.classifier_confidence_threshold``.

    Returns:
        A :class:`ClassificationResult` whose ``model_version`` is the trained
        artifact's version.

    Raises:
        ModelArtifactError: if no artifact is configured/present (callers should
            route through :func:`app.classifier.classify`, which falls back to
            the keyword engine instead of raising).
        RuntimeError: if the final label would be less sensitive than the base,
            the same fail-safe invariant the keyword engine enforces.
    """
    path = _configured_path()
    if path is None:
        raise ModelArtifactError(
            "No classifier artifact is configured; call app.classifier.classify "
            "which falls back to the keyword engine."
        )
    loaded = _load_artifact(path)

    effective_threshold = (
        get_settings().classifier_confidence_threshold
        if threshold is None
        else threshold
    )

    proba = loaded.model.predict_proba([content])[0]
    best_index = max(range(len(proba)), key=lambda i: proba[i])
    model_label = SensitivityLabel(loaded.classes[best_index])
    confidence = round(float(proba[best_index]), 4)

    # Keyword rules can only escalate: if a hard rule fired more sensitive than
    # the model, act on the rule. The model never downgrades what the rules caught.
    keyword_scores, matched_keywords = _score(content)
    base_label = model_label
    keyword_override = False
    if keyword_scores:
        keyword_label = _select_base_label(keyword_scores)
        if rank(keyword_label) > rank(base_label):
            base_label = keyword_label
            keyword_override = True

    # High-precision content detectors (raw SSNs, Luhn-valid cards, PEM/API-key
    # material, classification banners, PHI) escalate the same way — structurally
    # validated so they fire on real identifiers, never on a bare keyword. Their
    # signal names are merged into ``matched_keywords`` (``detector:`` prefixed).
    label_before_detectors = base_label
    base_label, detector_signals = apply_detectors(base_label, content)
    detector_override = rank(base_label) > rank(label_before_detectors)
    if detector_signals:
        matched_keywords = matched_keywords + detector_signals

    is_defaulted = confidence < effective_threshold
    final_label = escalate(base_label) if is_defaulted else base_label

    if rank(final_label) < rank(base_label):
        raise RuntimeError(
            "Classifier fail-safe invariant violated: final label "
            f"{final_label.value} is less sensitive than base label "
            f"{base_label.value}. Escalation must never downgrade."
        )

    return ClassificationResult(
        sensitivity_label=final_label,
        confidence=confidence,
        model_version=loaded.model_version,
        is_defaulted=is_defaulted,
        base_label=base_label,
        confidence_threshold=effective_threshold,
        matched_keywords=matched_keywords,
        rationale=_rationale(
            model_label=model_label,
            base_label=base_label,
            final_label=final_label,
            confidence=confidence,
            threshold=effective_threshold,
            matched_keywords=matched_keywords,
            keyword_override=keyword_override,
            detector_override=detector_override,
            detector_signals=detector_signals,
            is_defaulted=is_defaulted,
        ),
    )


def _rationale(
    *,
    model_label: SensitivityLabel,
    base_label: SensitivityLabel,
    final_label: SensitivityLabel,
    confidence: float,
    threshold: float,
    matched_keywords: tuple[str, ...],
    keyword_override: bool,
    detector_override: bool,
    detector_signals: tuple[str, ...],
    is_defaulted: bool,
) -> str:
    """Build the human-readable explanation attached to a model result."""
    parts = [
        f"Trained model predicted {model_label.value} with calibrated "
        f"confidence {confidence:.4f}."
    ]
    keyword_hits = tuple(k for k in matched_keywords if not k.startswith("detector:"))
    if keyword_override:
        parts.append(
            f"Keyword rules ({', '.join(keyword_hits)}) fired more sensitive, "
            f"so the base label was escalated; keyword rules can only raise "
            "protection, never lower it."
        )
    elif keyword_hits:
        parts.append(
            f"Keyword rules ({', '.join(keyword_hits)}) matched but were not "
            "more sensitive than the model, so they did not override."
        )
    if detector_signals:
        readable = ", ".join(s.removeprefix("detector:") for s in detector_signals)
        if detector_override:
            parts.append(
                f"High-precision content detectors ({readable}) matched validated "
                f"identifiers and escalated the base label to {base_label.value}; "
                "detectors can only raise protection, never lower it."
            )
        else:
            parts.append(
                f"Content detectors ({readable}) matched but were not more "
                "sensitive than the model/keyword label, so they did not override."
            )
    if is_defaulted:
        parts.append(
            f"Confidence was below the threshold {threshold:.2f}, so the result "
            f"was escalated to {final_label.value} (low-confidence "
            "classifications resolve toward more protection)."
        )
    else:
        parts.append(
            f"Confidence was at or above the threshold {threshold:.2f}; no "
            "fail-safe escalation applied."
        )
    return " ".join(parts)

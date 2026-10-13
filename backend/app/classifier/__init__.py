"""Sensitivity classifier, ``SPEC.md`` 3.2, implements ``PRD.md`` FR-1.

Two engines produce the same :class:`~app.classifier.result.ClassificationResult`:

- :mod:`app.classifier.model_classifier` — the trained Scikit-learn model, used
  when ``Settings.classifier_model_path`` names an artifact that exists on disk.
- :mod:`app.classifier.stub_classifier` — the keyword-rule engine, the labelled
  fallback used when no trained artifact is configured or present.

:func:`classify` dispatches between them. Both preserve the load-bearing
fail-safe: a low-confidence judgement escalates toward more protection
(``PRD.md`` Risk R1). The trained model additionally treats the keyword rules as
an escalation-only override, so swapping in the model never loses a hard
identifier the rules would have caught.

Callers record :func:`active_model_version` (or the ``model_version`` on each
result) so every stored classification is attributable to the engine that
produced it.
"""

from app.classifier.labels import SensitivityLabel
from app.classifier.model_classifier import ModelArtifactError
from app.classifier.model_classifier import active_model_version as _model_version
from app.classifier.model_classifier import classify as _model_classify
from app.classifier.model_classifier import is_active as _model_is_active
from app.classifier.result import ClassificationResult
from app.classifier.stub_classifier import MODEL_VERSION as KEYWORD_MODEL_VERSION
from app.classifier.stub_classifier import classify as _keyword_classify

#: Back-compat alias. The version actually recorded on a result comes from that
#: result's ``model_version``; use :func:`active_model_version` for the engine
#: currently in force.
MODEL_VERSION = KEYWORD_MODEL_VERSION


def classify(content: str, *, threshold: float | None = None) -> ClassificationResult:
    """Classify ``content`` with the trained model if present, else keyword rules.

    The trained model is used only when a usable artifact is configured and on
    disk; otherwise the keyword engine runs. Either way the fail-safe escalation
    is applied, so a low-confidence result resolves toward more protection.
    """
    if _model_is_active():
        return _model_classify(content, threshold=threshold)
    return _keyword_classify(content, threshold=threshold)


def active_model_version() -> str:
    """Return the version string of the engine currently in force."""
    return _model_version() or KEYWORD_MODEL_VERSION


__all__ = [
    "MODEL_VERSION",
    "ClassificationResult",
    "ModelArtifactError",
    "SensitivityLabel",
    "active_model_version",
    "classify",
]

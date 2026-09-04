"""Sensitivity classifier, ``SPEC.md`` 3.2, implements ``PRD.md`` FR-1.

The current implementation is a keyword-rule STUB, see
:mod:`app.classifier.stub_classifier`. The real Scikit-learn model is blocked
on a labelled dataset, tracked as an open dependency in ``PRD.md`` Section 9.
"""

from app.classifier.labels import SensitivityLabel
from app.classifier.stub_classifier import (
    MODEL_VERSION,
    ClassificationResult,
    classify,
)

__all__ = [
    "MODEL_VERSION",
    "ClassificationResult",
    "SensitivityLabel",
    "classify",
]

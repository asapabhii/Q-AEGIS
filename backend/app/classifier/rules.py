"""Keyword rules for the sensitivity classifier stub.

THIS IS STUB DATA. These keyword lists are hand-written heuristics, not a
trained model and not a validated taxonomy. They exist so the surrounding
pipeline (API contract, confidence heuristic, fail-safe escalation, audit
record) can be built and tested before a labelled dataset exists.

``PRD.md`` Section 9 records the labelled dataset as an unmet dependency, and
``PRD.md`` Section 8 explicitly excludes this stub from the classification
accuracy metric. Do not tune these keywords and present the result as accuracy
improvement; the replacement path is the real model in ``SPEC.md`` 3.2, not a
longer keyword list.
"""

from dataclasses import dataclass

from app.classifier.labels import SensitivityLabel


@dataclass(frozen=True)
class KeywordRule:
    """A single keyword-to-label rule.

    Attributes:
        label: The sensitivity label this keyword is evidence for.
        keyword: Lowercase match term. Matched on word boundaries, so "ssn"
            does not match inside "lesson".
        weight: Relative strength of this keyword as evidence. A term that is
            almost always genuinely sensitive (``"ssn"``) outweighs a term that
            is frequently incidental (``"internal"``).
    """

    label: SensitivityLabel
    keyword: str
    weight: float


def _rules_for(
    label: SensitivityLabel, weight: float, keywords: tuple[str, ...]
) -> tuple[KeywordRule, ...]:
    """Build a tuple of rules sharing one label and weight."""
    return tuple(
        KeywordRule(label=label, keyword=keyword, weight=weight) for keyword in keywords
    )


#: Terms that indicate deliberately published, non-sensitive material.
_PUBLIC_KEYWORDS = (
    "press release",
    "public announcement",
    "marketing brochure",
    "published openly",
    "for public distribution",
)

#: Terms that indicate internal-only but not confidential material.
_INTERNAL_KEYWORDS = (
    "internal use only",
    "internal memo",
    "staff handbook",
    "team offsite",
    "onboarding guide",
    "meeting notes",
)

#: Terms that indicate commercially or personally confidential material.
_CONFIDENTIAL_KEYWORDS = (
    "confidential",
    "salary",
    "payroll",
    "performance review",
    "acquisition target",
    "unreleased financials",
    "customer list",
    "contract terms",
    "non-disclosure",
)

#: Terms that indicate regulated, credential, or authentication material, the
#: categories where a misclassification has the most serious consequence.
_RESTRICTED_KEYWORDS = (
    "ssn",
    "social security number",
    "aadhaar",
    "passport number",
    "credit card number",
    "cvv",
    "private key",
    "secret key",
    "api key",
    "password",
    "medical record",
    "patient diagnosis",
    "biometric",
    "protected health information",
)

#: All keyword rules, ordered least to most sensitive.
#:
#: Weights rise with sensitivity so that a single strong restricted-tier term
#: is not outvoted by several weak internal-tier terms in the same document.
KEYWORD_RULES: tuple[KeywordRule, ...] = (
    *_rules_for(SensitivityLabel.PUBLIC, 1.0, _PUBLIC_KEYWORDS),
    *_rules_for(SensitivityLabel.INTERNAL, 1.5, _INTERNAL_KEYWORDS),
    *_rules_for(SensitivityLabel.CONFIDENTIAL, 2.5, _CONFIDENTIAL_KEYWORDS),
    *_rules_for(SensitivityLabel.RESTRICTED, 4.0, _RESTRICTED_KEYWORDS),
)

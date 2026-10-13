"""High-precision content detectors for the sensitivity classifier, FR-1.

The trained model (:mod:`app.classifier.model_classifier`) and the keyword
fallback (:mod:`app.classifier.stub_classifier`) both learn *distributional*
signals — the words a genre tends to use. That leaves a gap the owner hit in
practice: a document whose sensitivity lives in a *hard identifier* (a raw
Social-Security number, an AWS secret key, a PEM private-key block, a
Luhn-valid card number, a classification banner) can still read as ordinary
prose to a bag-of-words model and be scored PUBLIC.

This module closes that gap with deterministic, high-precision detectors that
run alongside either engine and can only **escalate** a label, never lower it
(the same escalate-only contract the keyword rules already honor —
``model_classifier`` docstring, ``PRD.md`` Risk R1). Each detector is tuned for
precision over recall: a false RESTRICTED erodes operator trust, so a signal
fires only when it is structurally validated (Luhn for cards, mod-97 for IBANs,
area/group/serial rules for SSNs, entropy + secret-context for opaque tokens),
not on a bare keyword.

The public surface is :func:`detect`, which returns the single most-sensitive
tier any detector fired plus the signal names that fired, and
:func:`apply_detectors`, the escalate-only helper the engines call.
"""

from __future__ import annotations

import math
import re

from app.classifier.labels import SensitivityLabel, most_sensitive_of, rank

#: A detector hit: the tier it argues for, and a short stable signal name that
#: is surfaced in ``matched_keywords`` (prefixed ``detector:``) for audit.
_Hit = tuple[SensitivityLabel, str]

_R = SensitivityLabel.RESTRICTED
_C = SensitivityLabel.CONFIDENTIAL


def _luhn_valid(digits: str) -> bool:
    """Return True if ``digits`` (a bare digit string) passes the Luhn checksum.

    Payment-card numbers (and many account numbers) carry a Luhn check digit, so
    validating it turns "13-19 digits in a row" from a noisy pattern into a
    high-precision signal: random or example numbers rarely pass.
    """
    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _iban_valid(candidate: str) -> bool:
    """Return True if ``candidate`` is a structurally valid IBAN (mod-97 == 1)."""
    compact = candidate.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    try:
        return int(numeric) % 97 == 1
    except ValueError:  # pragma: no cover - guarded by the fullmatch above
        return False


def _shannon_entropy(text: str) -> float:
    """Shannon entropy in bits per character; 0.0 for empty input."""
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for char in text:
        counts[char] = counts.get(char, 0) + 1
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


# --- Compiled patterns -------------------------------------------------------
# Each is anchored on word boundaries and, where a bare pattern would be noisy,
# paired with a structural validator (Luhn/mod-97) or a context gate below.

# SSN: dashed form only (raw 9-digit runs are too noisy to be high-precision).
# Reject the government-reserved invalid ranges (area 000/666/900-999, group 00,
# serial 0000) so example/placeholder numbers do not fire.
_SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")

# Card candidate: 13-19 digits, optionally separated by single spaces/dashes.
# Validated with Luhn AND a known issuer-identification-number (IIN/BIN) prefix
# in the detector, so a random Luhn-passing order number does not read as a card.
# The suffix rejects a following digit (embedded in a longer run) and a decimal
# point that begins a fraction ("...16.00"), but allows a trailing sentence period
# so a card ending a sentence still fires.
_CARD_CANDIDATE = re.compile(r"(?<![\d.])\d(?:[ -]?\d){12,18}(?!\d)(?!\.\d)")
_CARD_IIN = re.compile(
    r"(?:4\d{12}(?:\d{3})?(?:\d{3})?"  # Visa (13/16/19)
    r"|(?:5[1-5]\d{2}|222[1-9]|22[3-9]\d|2[3-6]\d{2}|27[01]\d|2720)\d{12}"  # MC
    r"|3[47]\d{13}"  # Amex (15)
    r"|(?:6011|65\d{2}|64[4-9]\d)\d{12,15}"  # Discover
    r"|3(?:0[0-5]|[68]\d)\d{11}"  # Diners
    r"|35(?:2[89]|[3-8]\d)\d{12,15})$"  # JCB
)

# IBAN candidate: two-letter country + 2 check digits + up to 30 alnum, allowing
# the conventional 4-char grouping. Validated with mod-97 in the detector.
_IBAN_CANDIDATE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{1,4}){2,8}\b")

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?!\d)"
)

_PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
)
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")

# Named provider secrets whose prefix makes them unambiguous.
_PROVIDER_TOKENS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b"), "openai_key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "github_token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "slack_token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "google_api_key"),
    (re.compile(r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{16,}\b"), "stripe_key"),
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}\b"
        ),
        "jwt",
    ),
)

# Generic ``secret = value`` assignment. The value must be long and must not be
# an obvious placeholder, so committed real secrets fire but examples do not.
# The keyword boundary excludes only alphanumerics (not ``_``) so a secret named
# in SCREAMING_SNAKE_CASE (``AWS_SECRET_ACCESS_KEY``, ``DB_PASSWORD``) still fires.
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|secret(?:[_-]?key)?|token|password"
    r"|passwd|pwd|access[_-]?key|client[_-]?secret|auth[_-]?token|bearer)"
    r"(?![A-Za-z0-9])\s*[:=]\s*['\"]?([^\s'\"]{12,})['\"]?"
)
_PLACEHOLDER_SECRET = re.compile(
    r"(?i)^(?:x{3,}|\.{3,}|-{3,}|change[_-]?me|your[_-]?|paste[_-]?|todo|none|null"
    r"|example|placeholder|redacted|dummy|test[_-]?key|secret|password)"
)

# Opaque high-entropy token, gated by nearby secret context (see detector).
_OPAQUE_TOKEN = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")
_SECRET_CONTEXT = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|secret|token|password|passwd|credential"
    r"|access[_-]?key|client[_-]?secret|bearer|authorization|private[_-]?key"
    r"|passphrase)(?![A-Za-z0-9])"
)

# Government/enterprise classification banners. RESTRICTED markings are matched
# CASE-SENSITIVELY (uppercase banner style) so ordinary prose ("keep it secret",
# "the Secretary") does not fire; CONFIDENTIAL markings are looser because that
# tier is a softer escalation. ``TOP SECRET`` and any ``//`` caveat, or a
# standalone all-caps ``SECRET`` token, argue RESTRICTED.
_MARKING_RESTRICTED = re.compile(
    r"TOP SECRET|COSMIC TOP SECRET|\bTS//[A-Z]|\bSECRET//|//NOFORN\b|\bNOFORN\b"
    r"|//SCI\b|//SI\b|//TK\b|//REL TO\b"
    r"|(?<![A-Za-z_])SECRET(?![A-Za-z_])"
)
_MARKING_CONFIDENTIAL = re.compile(
    r"(?i)\bconfidential\b|(?-i:\bCUI\b|\bFOUO\b|\bLES\b)"
)

# PHI lexicon. A medical context plus a personal identifier is RESTRICTED (a real
# patient record); two or more medical terms alone is CONFIDENTIAL.
_MEDICAL_TERM = re.compile(
    r"(?i)\b(?:patient|diagnosis|diagnos(?:ed|es)|prescription|prescribed"
    r"|medical record|mrn|physician|clinician|symptom[s]?|treatment plan"
    r"|blood pressure|hba1c|icd-?10|dosage|mg/dl|prognosis|comorbid"
    r"|protected health information|phi\b)\b"
)
_MRN = re.compile(r"(?i)\b(?:mrn|medical record (?:number|no\.?))\b")


def _find_ssn(content: str) -> list[_Hit]:
    return [(_R, "ssn")] if _SSN.search(content) else []


def _find_card(content: str) -> list[_Hit]:
    for match in _CARD_CANDIDATE.finditer(content):
        digits = re.sub(r"[ -]", "", match.group())
        if _luhn_valid(digits) and _CARD_IIN.match(digits):
            return [(_R, "credit_card_luhn")]
    return []


def _find_iban(content: str) -> list[_Hit]:
    for match in _IBAN_CANDIDATE.finditer(content):
        if _iban_valid(match.group()):
            return [(_C, "iban_mod97")]
    return []


def _find_keys_and_secrets(content: str) -> list[_Hit]:
    hits: list[_Hit] = []
    if _PEM_PRIVATE_KEY.search(content):
        hits.append((_R, "private_key_pem"))
    if _AWS_ACCESS_KEY.search(content):
        hits.append((_R, "aws_access_key"))
    for pattern, name in _PROVIDER_TOKENS:
        if pattern.search(content):
            hits.append((_R, name))
    for match in _SECRET_ASSIGNMENT.finditer(content):
        value = match.group(1)
        if not _PLACEHOLDER_SECRET.match(value):
            hits.append((_R, "secret_assignment"))
            break
    return hits


def _find_high_entropy_secret(content: str) -> list[_Hit]:
    """A long opaque token near a secret keyword — the AWS-secret-key case that
    has no distinctive prefix. Gated hard on both entropy and context so ordinary
    hashes/URLs/base64 payloads in benign text do not trip it."""
    for match in _OPAQUE_TOKEN.finditer(content):
        token = match.group()
        if _shannon_entropy(token) < 4.0:
            continue
        window = content[max(0, match.start() - 40) : match.start()]
        if _SECRET_CONTEXT.search(window):
            return [(_R, "high_entropy_secret")]
    return []


def _find_markings(content: str) -> list[_Hit]:
    hits: list[_Hit] = []
    if _MARKING_RESTRICTED.search(content):
        hits.append((_R, "classification_marking"))
    if _MARKING_CONFIDENTIAL.search(content):
        hits.append((_C, "confidential_marking"))
    return hits


def _find_pii_cluster(content: str) -> list[_Hit]:
    """Email plus phone in the same document is personal data → CONFIDENTIAL.
    A lone email (contact page) is intentionally not enough."""
    if _EMAIL.search(content) and _PHONE.search(content):
        return [(_C, "pii_cluster")]
    return []


def _find_phi(content: str) -> list[_Hit]:
    terms = {m.group().lower() for m in _MEDICAL_TERM.finditer(content)}
    if not terms:
        return []
    has_identifier = bool(
        _SSN.search(content)
        or _MRN.search(content)
        or _EMAIL.search(content)
        or _PHONE.search(content)
    )
    if has_identifier:
        return [(_R, "phi_with_identifier")]
    if len(terms) >= 2:
        return [(_C, "phi_medical_context")]
    return []


_DETECTORS = (
    _find_ssn,
    _find_card,
    _find_iban,
    _find_keys_and_secrets,
    _find_high_entropy_secret,
    _find_markings,
    _find_pii_cluster,
    _find_phi,
)


def detect(content: str) -> tuple[SensitivityLabel | None, tuple[str, ...]]:
    """Run every detector over ``content``.

    Returns the single most-sensitive tier any detector argued for and the sorted
    set of signal names that fired, or ``(None, ())`` when nothing fired. The
    caller escalates to at most this tier — detectors never lower a label.
    """
    if not content:
        return None, ()
    hits: list[_Hit] = []
    for detector in _DETECTORS:
        hits.extend(detector(content))
    if not hits:
        return None, ()
    label = most_sensitive_of([tier for tier, _ in hits])
    signals = tuple(sorted({name for _, name in hits}))
    return label, signals


def apply_detectors(
    base_label: SensitivityLabel, content: str
) -> tuple[SensitivityLabel, tuple[str, ...]]:
    """Escalate ``base_label`` to the detector tier when a detector argues higher.

    This is the escalate-only contract the engines share: the returned label is
    ``max(base_label, detector_label)`` by sensitivity rank, never lower, plus the
    ``detector:``-prefixed signal names to merge into ``matched_keywords`` for
    audit. When no detector fires the label is returned unchanged with no signals.
    """
    detector_label, signals = detect(content)
    if detector_label is not None and rank(detector_label) > rank(base_label):
        base_label = detector_label
    prefixed = tuple(f"detector:{name}" for name in signals)
    return base_label, prefixed

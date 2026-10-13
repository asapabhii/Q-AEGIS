"""Network-free synthetic document generator for classifier weak supervision, FR-1.

The trained model must stop scoring arbitrary out-of-domain documents PUBLIC just
because they do not resemble the diplomatic-cable corpus it was first trained on.
Real breadth comes from 20 Newsgroups, the cables, and local source files (see
:mod:`app.classifier.build_corpus`). This module supplies the piece those miss:
documents drawn from ordinary business, clinical, engineering, and legal genres
that genuinely CARRY sensitive content -- an HR memo quoting an SSN, an ops runbook
with an API key, a wire instruction with an IBAN -- so the model learns the
*lexical context* around sensitive data across many genres, not only the cable
register, while the deterministic detectors remain the exact-identifier backstop.

Every document is generated deterministically from a seed, so a corpus rebuild is
byte-for-byte reproducible. Identifiers are real in FORMAT (Luhn-valid cards,
mod-97-valid IBANs, reserved-range-free SSNs, correctly prefixed provider tokens),
so the detector layer validates them exactly as it would in production -- these are
synthetic *documents*, not fake *signals*. The intended tier each document carries
is only a genre prior: :mod:`app.classifier.build_corpus` recomputes the final
label as ``max_rank(genre_prior, detector_label)``, so a benign template that
happens to read as public stays public and a sensitive one is confirmed by the
detector rather than trusted on the generator's say-so.
"""

from __future__ import annotations

import random
import string
from typing import Iterator

from app.classifier.labels import SensitivityLabel

_R = SensitivityLabel.RESTRICTED
_C = SensitivityLabel.CONFIDENTIAL
_P = SensitivityLabel.PUBLIC

#: A generated document: its text, the genre-prior tier, and a stable source id.
Document = tuple[str, SensitivityLabel, str]

_FIRST_NAMES = (
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Priya",
    "Wei",
    "Fatima",
    "Diego",
    "Aisha",
    "Chen",
    "Omar",
    "Ingrid",
    "Kwame",
)
_LAST_NAMES = (
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Nguyen",
    "Patel",
    "Kim",
    "Okafor",
    "Rossi",
    "Haddad",
    "Novak",
    "Andersson",
    "Mensah",
)
_COMPANIES = (
    "Northwind Trading",
    "Acme Logistics",
    "Blue Harbor Health",
    "Vertex Labs",
    "Meridian Bank",
    "Cascade Systems",
    "Ironwood Legal",
    "Solaris Energy",
    "Redpine Software",
    "Harborview Clinic",
    "Atlas Freight",
    "Quill & Vane",
)


# --- Real-format identifier synthesis ----------------------------------------
# Each returns a value the production detectors will VALIDATE (Luhn, mod-97,
# reserved-range rules), so a synthetic document carrying one escalates for the
# same structural reason a real one would -- never on a bare keyword.


def _name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _ssn(rng: random.Random) -> str:
    """A syntactically valid US SSN (area, group, serial all in legal ranges)."""
    area = rng.randint(1, 899)
    while area in (666,) or 900 <= area <= 999:
        area = rng.randint(1, 899)
    return f"{area:03d}-{rng.randint(1, 99):02d}-{rng.randint(1, 9999):04d}"


def _luhn_complete(prefix_digits: str, length: int, rng: random.Random) -> str:
    """Extend ``prefix_digits`` to ``length`` digits with a valid Luhn checksum."""
    body = prefix_digits + "".join(
        str(rng.randint(0, 9)) for _ in range(length - 1 - len(prefix_digits))
    )
    for check in range(10):
        candidate = body + str(check)
        if _luhn_ok(candidate):
            return candidate
    return body + "0"


def _luhn_ok(digits: str) -> bool:
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


def _card(rng: random.Random) -> str:
    """A Luhn-valid card number with a real issuer prefix (Visa/MC/Amex)."""
    kind = rng.choice(("visa", "mc", "amex"))
    if kind == "visa":
        number = _luhn_complete("4", 16, rng)
    elif kind == "mc":
        number = _luhn_complete(str(rng.randint(51, 55)), 16, rng)
    else:
        number = _luhn_complete(rng.choice(("34", "37")), 15, rng)
    return " ".join(number[i : i + 4] for i in range(0, len(number), 4))


def _iban(rng: random.Random) -> str:
    """A mod-97-valid GB IBAN (country + check digits + bank/account)."""
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    account = "".join(str(rng.randint(0, 9)) for _ in range(14))
    body = bank + account + "GB00"
    numeric = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in body)
    check = 98 - (int(numeric) % 97)
    compact = f"GB{check:02d}{bank}{account}"
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def _token(rng: random.Random, alphabet: str, length: int) -> str:
    return "".join(rng.choice(alphabet) for _ in range(length))


def _api_key(rng: random.Random) -> str:
    """A provider-prefixed secret the detector recognises unambiguously."""
    kind = rng.choice(("aws", "openai", "github", "stripe"))
    if kind == "aws":
        return "AKIA" + _token(rng, string.ascii_uppercase + string.digits, 16)
    if kind == "openai":
        return "sk-" + _token(rng, string.ascii_letters + string.digits, 32)
    if kind == "github":
        return "ghp_" + _token(rng, string.ascii_letters + string.digits, 36)
    return "sk_live_" + _token(rng, string.ascii_letters + string.digits, 24)


def _mrn(rng: random.Random) -> str:
    return f"MRN {rng.randint(10000, 999999)}"


def _phone(rng: random.Random) -> str:
    return f"({rng.randint(200, 989)}) 555-{rng.randint(0, 9999):04d}"


def _email(rng: random.Random, name: str) -> str:
    user = name.lower().replace(" ", ".")
    return f"{user}@{rng.choice(('acme.com', 'northwind.co', 'vertexlabs.io'))}"


# --- Genre templates ---------------------------------------------------------
# Each builder returns a short, realistic document body. Sensitive builders embed
# a validated identifier so the detector confirms the intended tier; benign
# builders are kept scrupulously clean (no Luhn-valid runs, no all-caps SECRET)
# so they stay PUBLIC after weak-supervision relabelling.


def _restricted_doc(rng: random.Random) -> str:
    company = rng.choice(_COMPANIES)
    person = _name(rng)
    kind = rng.randint(0, 4)
    if kind == 0:
        return (
            f"{company} Payroll Adjustment\nEmployee: {person}\n"
            f"SSN: {_ssn(rng)}\nEffective next cycle, the correction to gross pay "
            "will be applied and back-dated. Route questions to HR only; do not "
            "forward this record outside the payroll team."
        )
    if kind == 1:
        return (
            f"Chargeback dispute for order #{rng.randint(10000, 99999)}. The "
            f"cardholder {person} was billed twice on card {_card(rng)}. Issue a "
            "refund to the original method and note the case in the ledger."
        )
    if kind == 2:
        return (
            f"# {company} production runbook\nRotate the worker credentials before "
            f"deploy. Current key: {_api_key(rng)}\nExport it to the environment, "
            "restart the pods, then invalidate the previous value in the vault."
        )
    if kind == 3:
        return (
            "TOP SECRET//NOFORN\nOperational summary follows. Sourcing and methods "
            "are compartmented; handling caveats apply. Distribution is limited to "
            "cleared personnel with a demonstrated need to know."
        )
    return (
        f"Clinical encounter note. Patient {person}, {_mrn(rng)}. Diagnosis: "
        f"type 2 diabetes; HbA1c elevated. Prescribed metformin, dosage 500mg "
        "twice daily. Follow-up in six weeks to review the treatment plan."
    )


def _confidential_doc(rng: random.Random) -> str:
    company = rng.choice(_COMPANIES)
    person = _name(rng)
    kind = rng.randint(0, 4)
    if kind == 0:
        return (
            f"CONFIDENTIAL -- {company} wire instruction. Remit the retainer to "
            f"IBAN {_iban(rng)} by end of week and confirm the reference with "
            "accounts payable once the transfer settles."
        )
    if kind == 1:
        return (
            f"This memorandum is Confidential and subject to legal privilege. It "
            f"summarises {company}'s negotiating position ahead of the merger and "
            "must not be shared beyond the deal team and outside counsel."
        )
    if kind == 2:
        return (
            f"Escalation contact sheet. Primary: {person}, {_email(rng, person)}, "
            f"{_phone(rng)}. Secondary on-call rotates weekly; keep this list "
            "internal to the response team."
        )
    if kind == 3:
        return (
            "CUI//FOUO cover sheet. The attached assessment contains controlled "
            "unclassified information. Store on approved systems only and shred "
            "printed copies after the review meeting."
        )
    return (
        f"{company} board pre-read (Confidential). Quarterly margin compressed on "
        "input costs; the restructuring provision and the prognosis for the "
        "affected division are discussed in the appendix. Do not circulate."
    )


def _public_doc(rng: random.Random) -> str:
    company = rng.choice(_COMPANIES)
    kind = rng.randint(0, 4)
    if kind == 0:
        return (
            f"FOR IMMEDIATE RELEASE\n{company} today announced a new regional hub "
            "to shorten delivery times for customers. The expansion adds local "
            "jobs and reflects steady demand across the product line."
        )
    if kind == 1:
        return (
            f"Introducing the latest release from {company}. Faster search, a "
            "cleaner dashboard, and one-click exports help teams get to insight "
            "sooner. Available today on all supported plans at no extra cost."
        )
    if kind == 2:
        return (
            "Community meetup notes. We covered the roadmap, took questions on "
            "accessibility, and agreed to publish the slides on the public wiki. "
            "Thanks to everyone who attended and shared feedback."
        )
    if kind == 3:
        return (
            "## Changelog\n- Fixed a layout glitch on small screens\n- Improved "
            "load time for the reports page\n- Updated the getting-started guide\n"
            "See the docs for full upgrade notes."
        )
    return (
        f"Frequently asked questions about {company} support. Our help center is "
        "open to everyone, hours are listed online, and most common issues are "
        "answered in the public knowledge base."
    )


_BUILDERS: tuple[tuple[SensitivityLabel, object], ...] = (
    (_R, _restricted_doc),
    (_C, _confidential_doc),
    (_P, _public_doc),
)


def iter_documents(*, per_tier: int = 1500, seed: int = 1729) -> Iterator[Document]:
    """Yield ``per_tier`` synthetic documents for each genre-prior tier.

    Deterministic in ``seed``: the same arguments always yield the same corpus.
    The tier attached here is a prior only; :mod:`app.classifier.build_corpus`
    recomputes the final label via the detectors so the label authority is one
    place, not this generator.
    """
    rng = random.Random(seed)
    for tier, builder in _BUILDERS:
        for index in range(per_tier):
            content = builder(rng)
            source_id = f"synth-{tier.value.lower()}-{index}"
            yield content, tier, source_id

"""WikiLeaks cables preparation tests, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

The load-bearing property here is *no label leakage*: a cable prints its own
classification in the body, and the cleaner must remove that marking so a model
cannot read the label off the page — while leaving genuine prose (``Secretary``,
``SECSTATE``) untouched.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.classifier.prep_wikileaks_cables import convert, strip_cable_markings


def test_strip_removes_plain_and_letter_spaced_markings() -> None:
    assert "secret" not in strip_cable_markings("SECRET the talks continue").lower()
    assert "secret" not in strip_cable_markings("S E C R E T SECTION 01 OF 02").lower()
    conf = strip_cable_markings("C O N F I D E N T I A L BEIRUT 01640 body")
    assert "confidential" not in conf.replace(" ", "").lower()
    assert "unclas" not in strip_cable_markings("UNCLAS STATE 12345").lower()
    assert "unclas" not in strip_cable_markings("UNCLASSIFIED notice").lower()
    top = strip_cable_markings("T O P S E C R E T dossier")
    assert "secret" not in top.replace(" ", "").lower()
    assert "top" not in top.replace(" ", "").lower()


def test_strip_removes_handling_caveats() -> None:
    cleaned = strip_cable_markings("report NOFORN and NODIS and SIPDIS here")
    low = cleaned.lower()
    assert "noforn" not in low
    assert "nodis" not in low
    assert "sipdis" not in low
    assert (
        "for official use only"
        not in strip_cable_markings("marked FOR OFFICIAL USE ONLY today").lower()
    )


def test_strip_preserves_legitimate_words() -> None:
    # "Secretary" and "SECSTATE" embed marking substrings but are real content.
    cleaned = strip_cable_markings("The Secretary cabled SECSTATE WASHDC today")
    assert "Secretary" in cleaned
    assert "SECSTATE" in cleaned


def test_strip_removes_section_pagination_and_csv_seams() -> None:
    cleaned = strip_cable_markings('body one","body two SECTION 02 OF 03 tail')
    assert "SECTION" not in cleaned
    assert '","' not in cleaned
    assert "body one" in cleaned
    assert "body two" in cleaned


def test_strip_handles_empty() -> None:
    assert strip_cable_markings("") == ""
    assert strip_cable_markings(None) == ""  # type: ignore[arg-type]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_convert_applies_cleaner_so_the_label_is_not_in_the_text(
    tmp_path: Path,
) -> None:
    records = [
        {
            "body": "S E C R E T SECTION 01 OF 02 CAIRO 001 " + ("substantive " * 40),
            "classification": "SECRET",
            "cable_id": "85CAIRO001",
        },
        {
            "body": "UNCLAS " + ("public bulletin text " * 30),
            "classification": "UNCLASSIFIED",
            "cable_id": "85CAIRO002",
        },
    ]
    out = tmp_path / "cables.csv"

    stats = convert(
        records,
        out,
        content_field="body",
        label_field="classification",
        id_field="cable_id",
        min_chars=50,
        max_chars=20000,
        test_fraction=0.0,
        seed=7,
        content_cleaner=strip_cable_markings,
    )

    assert stats.written == 2
    for row in _read_csv(out):
        # No standalone marking may survive into the training text.
        flat = row["content"].replace(" ", "").lower()
        assert "secret" not in flat
        assert "unclas" not in flat

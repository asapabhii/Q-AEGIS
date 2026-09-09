"""Capabilities allowlist, SPEC.md 3.6.

``opa check --capabilities`` is the compile-time gate. This file must list
only the builtins ``policy.rego`` uses. A fat dump of OPA ``--current``
would let a later edit of the interpreter use ``http.send`` or ``io.jwt.*``
and still pass CI.
"""

import json
from pathlib import Path

REGO_DIR = Path(__file__).resolve().parents[1] / "app" / "policy" / "rego"

#: The builtins ``policy.rego`` actually references. Keep this in lockstep
#: with ``capabilities.json``. Adding a name here without using it in Rego
#: re-opens the gate Copilot flagged on PR #11.
ALLOWED_BUILTINS = {
    "assign",
    "count",
    "eq",
    "equal",
    "gt",
    "gte",
    "internal.member_2",
    "lt",
    "lte",
    "neq",
    "object.get",
}


def test_capabilities_are_an_allowlist_of_the_interpreter_builtins() -> None:
    data = json.loads((REGO_DIR / "capabilities.json").read_text(encoding="utf-8"))
    names = {entry["name"] for entry in data["builtins"]}
    assert names == ALLOWED_BUILTINS
    assert "rego_v1" in data["features"]


def test_capabilities_exclude_network_jwt_and_now() -> None:
    data = json.loads((REGO_DIR / "capabilities.json").read_text(encoding="utf-8"))
    names = {entry["name"] for entry in data["builtins"]}
    leaked = [
        name
        for name in names
        if name.startswith(("http.", "net.", "io.jwt", "providers.", "crypto."))
        or name in {"time.now_ns", "http.send"}
    ]
    assert leaked == []

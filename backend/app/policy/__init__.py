"""Deterministic policy engine, ``SPEC.md`` 3.6, implements ``PRD.md`` FR-5.

Evaluates a closed condition tree against caller-supplied document facts and
returns the first matching active rule's action, or the AI recommendation when
nothing matches. Evaluation is in-process WASM (``opa-wasmtime``) over one
reviewed Rego module. Rules are data on ``input``, never compiled into Rego.

``after_hours``-style derivation is not this module's job. ``trust_score`` and
``ai_recommendation`` are facts the caller sends until 3.5 and 3.7 exist.

Owner: Udhav (``WORK_DIVISION.md``). Required reviewer on any change here.
"""

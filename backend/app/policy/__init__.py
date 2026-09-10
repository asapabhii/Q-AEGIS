"""Deterministic policy engine, ``SPEC.md`` 3.6, implements ``PRD.md`` FR-5.

Evaluates a closed condition tree against persisted document facts and
returns the first matching active rule's action, or the AI recommendation when
nothing matches. Evaluation is in-process WASM (``opa-wasmtime``) over one
reviewed Rego module. Rules are data on ``input``, never compiled into Rego.

``POST /policy-decisions`` reads ``sensitivity_label``, ``risk_value``, and
``trust_score`` from stored rows via a ``trust_score_id``. The label is the
effective sensitivity: latest override ``new_label``, else latest
classification. ``ai_recommendation`` is still caller-asserted until 3.4
exists to produce it.

``POST /policy-rules/test`` dry-runs a candidate against the last 20
``policy_decision_recorded`` audit snapshots. It persists nothing.

Owner: Udhav (``WORK_DIVISION.md``). Required reviewer on any change here.
"""

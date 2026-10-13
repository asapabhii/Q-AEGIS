#!/usr/bin/env python3
"""Live end-to-end smoke for the Q-AEGIS bound pipeline.

Drives the running HTTPS backend (self-signed dev cert) through the entire
``SPEC.md`` Section 3 pipeline using the dev header-bypass auth, one role per
endpoint's real authorization matrix. Exercises the real trained classifier,
the real five-agent LangGraph assessment, the QAOA migration ranker, Neo4j
attack paths, fastembed RAG, and the ML-DSA-87 signed audit checkpoint.

Run against a freshly reset + seeded stack (from backend/):
    ./venv/Scripts/python.exe scripts/smoke_e2e.py

Exits non-zero if any check fails. This is a verification driver, not a test
fixture: it talks to the live stack, so nothing here is mocked.
"""

from __future__ import annotations

import sys
import uuid
import random
from datetime import datetime, timezone

import httpx

BASE = "https://127.0.0.1:8443/api/v1"
ACTOR_HEADER = "X-Q-AEGIS-Actor-Role"
EXPECTED_MODEL = "multigenre-hashing-svm-1.0.0"

# Seeded dev users carry server-generated UUIDs -- ``python -m app.db.seed``
# assigns a fresh id per row on each run -- so we resolve the id for a role at
# request time from GET /auth/me (the dev role-header path) rather than pinning
# an id that the next re-seed would silently invalidate.
_USER_ID_CACHE: dict[str, str] = {}


def user_id(role: str) -> str:
    """Return the seeded user id for ``role``, resolved live via GET /auth/me."""
    if role not in _USER_ID_CACHE:
        resp = req("GET", "/auth/me", role=role)
        resp.raise_for_status()
        _USER_ID_CACHE[role] = resp.json()["id"]
    return _USER_ID_CACHE[role]


CABLE = (
    "CONFIDENTIAL EMBASSY CABLE. Subject: bilateral negotiations on trade "
    "tariffs and sanctions policy. The ambassador met privately with the "
    "foreign minister to discuss sensitive diplomatic deliberations regarding "
    "intelligence sharing, arms control, and covert cooperation. This cable "
    "records internal government positions and is not for public release."
)

client = httpx.Client(base_url=BASE, verify=False, timeout=90.0)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail:
        line += f" -- {detail}"
    print(line, flush=True)
    return bool(ok)


def req(method: str, path: str, role: str | None = None, **kw) -> httpx.Response:
    headers = dict(kw.pop("headers", {}))
    if role:
        headers[ACTOR_HEADER] = role
    return client.request(method, path, headers=headers, **kw)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def after_hours_iso() -> str:
    # 02:00 UTC == 07:30 IST (before 09:00) -> derived after_hours == True.
    return datetime(2026, 9, 23, 2, 0, 0, tzinfo=timezone.utc).isoformat()


# populated as the walk proceeds
ctx: dict[str, object] = {}


def step_health() -> None:
    r = req("GET", "/health")
    ok = r.status_code == 200 and r.json().get("status") == "ok"
    check("health", ok, f"{r.status_code} {r.json() if ok else r.text[:200]}")


def step_register(kind: str, role: str) -> None:
    fn = f"smoke-{kind}-{uuid.uuid4().hex[:8]}.txt"
    r = req("POST", "/documents", role=role, json={"filename": fn})
    ok = r.status_code == 201
    doc_id = r.json().get("id") if ok else None
    ctx[f"doc_{kind}"] = doc_id
    check(f"register doc {kind}", ok, f"{r.status_code} id={doc_id}")


def step_upload() -> None:
    doc_id = ctx.get("doc_a")
    if not doc_id:
        return check("upload doc a", False, "no document_id")
    files = {"file": ("cable.txt", CABLE.encode("utf-8"), "text/plain")}
    r = req("POST", f"/documents/{doc_id}/upload", role="data_owner", files=files)
    ok = r.status_code == 201
    detail = ""
    if ok:
        body = r.json()
        detail = f"stored, extracted {len(body.get('extracted_text',''))} chars"
    else:
        detail = f"{r.status_code} {r.text[:200]}"
    check("upload doc a", ok, detail)


def step_classify(kind: str) -> None:
    doc_id = ctx.get(f"doc_{kind}")
    if not doc_id:
        return check(f"classify doc {kind}", False, "no document_id")
    r = req(
        "POST",
        "/classify",
        role="security_analyst",
        json={"document_id": doc_id, "content": CABLE},
    )
    ok = r.status_code == 200
    if not ok:
        return check(f"classify doc {kind}", False, f"{r.status_code} {r.text[:200]}")
    body = r.json()
    ctx[f"label_{kind}"] = body.get("sensitivity_label")
    mv = body.get("model_version")
    real = mv == EXPECTED_MODEL
    check(
        f"classify doc {kind}",
        ok,
        f"label={body.get('sensitivity_label')} conf={body.get('confidence')} "
        f"model_version={mv}",
    )
    check(
        f"classify doc {kind} uses REAL trained model",
        real,
        f"got {mv!r}, expected {EXPECTED_MODEL!r}",
    )


def step_risk() -> None:
    doc_id = ctx.get("doc_a")
    if not doc_id:
        return check("risk score", False, "no document_id")
    r = req(
        "POST",
        "/risk-scores",
        role="security_analyst",
        json={
            "document_id": doc_id,
            "actor_user_id": user_id("security_analyst"),
            "device_id": "workstation-smoke-01",
            "device_is_new": True,
            "accessed_at": after_hours_iso(),
        },
    )
    ok = r.status_code == 201
    if not ok:
        return check("risk score", False, f"{r.status_code} {r.text[:200]}")
    body = r.json()
    ctx["risk_score_id"] = body.get("id")
    derived = body.get("context_snapshot", {}).get("after_hours")
    check(
        "risk score",
        ok,
        f"risk_value={body.get('risk_value')} after_hours(derived)={derived}",
    )
    check(
        "after_hours derived server-side",
        derived is True,
        f"expected True from 02:00Z / Asia/Kolkata, got {derived}",
    )


AGENTS = ("security", "compliance", "contextual", "quantum", "sustainability")


def step_trust() -> None:
    rsid = ctx.get("risk_score_id")
    if not rsid:
        return check("trust score", False, "no risk_score_id")
    outputs = [
        {
            "agent_type": a,
            "score": s,
            "rationale": f"{a} agent assessed the closed context snapshot.",
        }
        for a, s in zip(AGENTS, ("0.82", "0.77", "0.68", "0.91", "0.55"))
    ]
    r = req(
        "POST",
        "/trust-scores",
        role="security_analyst",
        json={"risk_score_id": rsid, "outputs": outputs},
    )
    ok = r.status_code == 201
    if not ok:
        return check("trust score", False, f"{r.status_code} {r.text[:200]}")
    body = r.json()
    ctx["trust_score_id"] = body.get("id")
    check(
        "trust score",
        ok,
        f"consensus={body.get('consensus_value')} v={body.get('consensus_version')}",
    )


def step_policy_rule() -> None:
    name = f"restricted-forces-pqc-{uuid.uuid4().hex[:8]}"
    r = req(
        "POST",
        "/policy-rules",
        role="compliance_officer",
        json={
            "rule_name": name,
            "condition_expr": {
                "all": [
                    {
                        "field": "sensitivity_label",
                        "op": "in",
                        "value": ["CONFIDENTIAL", "RESTRICTED"],
                    }
                ]
            },
            "action": "force_pqc",
            "priority": random.randint(1000, 9_000_000),
        },
    )
    ok = r.status_code == 201
    if ok:
        ctx["rule_id"] = r.json().get("id")
    check(
        "policy rule create", ok, f"{r.status_code} {r.text[:160] if not ok else name}"
    )


def step_policy_decision() -> None:
    tsid = ctx.get("trust_score_id")
    if not tsid:
        return check("policy decision", False, "no trust_score_id")
    r = req(
        "POST",
        "/policy-decisions",
        role="security_admin",
        json={"trust_score_id": tsid},
    )
    ok = r.status_code == 201
    if not ok:
        return check("policy decision", False, f"{r.status_code} {r.text[:200]}")
    body = r.json()
    ctx["policy_decision_id"] = body.get("id")
    matched = body.get("rule_id")
    check(
        "policy decision",
        ok,
        f"ai_rec={body.get('ai_recommendation')} final={body.get('final_decision')} "
        f"rule={'<none: AI stands>' if matched is None else body.get('rule_name')} "
        f"overridden={body.get('overridden')}",
    )


def step_crypto() -> None:
    tsid = ctx.get("trust_score_id")
    if not tsid:
        return check("crypto profile", False, "no trust_score_id")
    r = req(
        "POST",
        "/crypto-profiles",
        role="security_analyst",
        json={"trust_score_id": tsid},
    )
    ok = r.status_code == 201
    if not ok:
        return check("crypto profile", False, f"{r.status_code} {r.text[:200]}")
    body = r.json()
    check(
        "crypto profile",
        ok,
        "profile_type="
        f"{body.get('profile_type')} consensus={body.get('consensus_value')}",
    )


def step_override() -> None:
    doc_id = ctx.get("doc_a")
    if not doc_id:
        return check("manual override", False, "no document_id")
    current = ctx.get("label_a")
    order = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
    new_label = "PUBLIC" if current != "PUBLIC" else "RESTRICTED"
    # pick any label that differs from the current effective label
    for cand in order:
        if cand != current:
            new_label = cand
            break
    r = req(
        "POST",
        "/manual-overrides",
        role="security_analyst",
        json={
            "document_id": doc_id,
            "new_label": new_label,
            "justification": (
                "Analyst reviewed the full cable text and the surrounding "
                "case file before relabeling."
            ),
        },
    )
    ok = r.status_code == 201
    detail = f"{current} -> {new_label}" if ok else f"{r.status_code} {r.text[:200]}"
    check("manual override", ok, detail)


def step_migration(tag: str) -> None:
    r = req(
        "POST",
        "/migration-schedule/rank",
        role="security_admin",
        json={"budget": 100.0, "window_days": 30, "seed": 42},
    )
    ok = r.status_code in (200, 201)
    if not ok:
        return check(f"migration rank {tag}", False, f"{r.status_code} {r.text[:200]}")
    body = r.json()
    primary = body.get("primary") or body.get("primary_method") or {}
    method = primary.get("method") if isinstance(primary, dict) else primary
    check(
        f"migration rank {tag}",
        ok,
        f"primary={method} scheduled={len(body.get('schedule', []) or [])} "
        f"baselines={len(body.get('baselines', []) or [])}",
    )


def step_graph() -> None:
    r = req("GET", "/graph/status", role="security_analyst")
    configured = r.status_code == 200 and r.json().get("configured")
    check("graph status", r.status_code == 200, f"configured={configured}")

    doc_id = ctx.get("doc_a")
    r = req(
        "POST", "/graph/seed", role="security_analyst", json={"document_id": doc_id}
    )
    ok = r.status_code == 201
    detail = (
        f"nodes={r.json().get('nodes_upserted')} "
        f"rels={r.json().get('relationships_upserted')}"
        if ok
        else f"{r.status_code} {r.text[:200]}"
    )
    check("graph seed", ok, detail)

    r = req(
        "GET",
        f"/graph/documents/{doc_id}/paths",
        role="security_analyst",
        params={"max_hops": 4},
    )
    check(
        "graph document paths",
        r.status_code == 200,
        f"{r.status_code} "
        f"paths={len(r.json()) if r.status_code == 200 else r.text[:120]}",
    )


def step_rag() -> None:
    doc_id = ctx.get("doc_a")
    if not doc_id:
        return check("rag ingest", False, "no document_id")
    r = req("POST", f"/rag/ingest/{doc_id}", role="security_analyst")
    ok = r.status_code == 201
    model = r.json().get("embedding_model") if ok else None
    check(
        "rag ingest",
        ok,
        (
            f"chunks={r.json().get('chunks_written')} model={model}"
            if ok
            else f"{r.status_code} {r.text[:200]}"
        ),
    )

    # grounded question -- answerable from the ingested cable
    r = req(
        "POST",
        "/rag/ask",
        role="security_analyst",
        json={
            "question": "What sensitive topics does this diplomatic cable discuss?",
            "document_id": doc_id,
        },
    )
    ok = r.status_code == 200
    if ok:
        b = r.json()
        check(
            "rag ask (grounded)",
            ok,
            f"verified={b.get('verified')} citations={len(b.get('citations', []))} "
            f"refusal={b.get('refusal_reason')}",
        )
    else:
        check("rag ask (grounded)", False, f"{r.status_code} {r.text[:200]}")

    # ungrounded question -- verifier should refuse rather than hallucinate
    r = req(
        "POST",
        "/rag/ask",
        role="security_analyst",
        json={
            "question": "What is the boiling point of liquid helium at 3 atm?",
            "document_id": doc_id,
        },
    )
    if r.status_code == 200:
        b = r.json()
        refused = (b.get("verified") is False) or bool(b.get("refusal_reason"))
        check(
            "rag ask (ungrounded -> refusal)",
            refused,
            f"verified={b.get('verified')} refusal={b.get('refusal_reason')}",
        )
    else:
        check(
            "rag ask (ungrounded -> refusal)", False, f"{r.status_code} {r.text[:160]}"
        )


def step_audit() -> None:
    doc_id = ctx.get("doc_a")

    r = req("GET", "/audit/entries", role="auditor", params={"document_id": doc_id})
    body = r.json() if r.status_code == 200 else {}
    # /audit/entries returns AuditChainResponse{document_id, count, entries[]},
    # not a bare list -- read the count field, not len() of the object.
    ctx["doc_a_entry_count"] = (
        int(body.get("count", 0)) if isinstance(body, dict) else 0
    )
    check(
        "audit entries (doc a)",
        r.status_code == 200,
        f"{r.status_code} count={ctx['doc_a_entry_count']}",
    )

    r = req("GET", "/audit/verify", role="auditor", params={"document_id": doc_id})
    ok = r.status_code == 200 and r.json().get("is_valid") is True
    check(
        "audit verify (doc a chain)",
        ok,
        f"{r.status_code} "
        f"valid={r.json().get('is_valid') if r.status_code == 200 else r.text[:120]}",
    )

    # system chain (document_id omitted) -- the chain the migration-rank +
    # graph/rag events append to; the duplicate-payload bug corrupted this one.
    r = req("GET", "/audit/verify", role="auditor")
    ok = r.status_code == 200 and r.json().get("is_valid") is True
    check(
        "audit verify (system chain)",
        ok,
        f"{r.status_code} "
        f"valid={r.json().get('is_valid') if r.status_code == 200 else r.text[:160]} "
        f"entries={r.json().get('entry_count') if r.status_code == 200 else '?'}",
    )

    # ML-DSA-87 signed checkpoint over the doc-a chain (real liboqs in container)
    r = req(
        "POST",
        "/audit/checkpoint",
        role="auditor",
        json={"document_id": doc_id},
    )
    ok = r.status_code == 201
    if not ok:
        check(
            "audit checkpoint (ML-DSA-87 sign)",
            False,
            f"{r.status_code} {r.text[:200]}",
        )
    else:
        b = r.json()
        ctx["checkpoint_id"] = b.get("checkpoint_id")
        check(
            "audit checkpoint (ML-DSA-87 sign)",
            ok,
            f"alg={b.get('algorithm')} tree_size={b.get('tree_size')} "
            f"sig_len={len(b.get('signature',''))} key={b.get('signing_key_id')}",
        )

    cp = ctx.get("checkpoint_id")
    if cp:
        r = req("GET", f"/audit/checkpoint/{cp}/verify", role="auditor")
        b = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and b.get("is_valid") is True
            and b.get("signature_valid") is True
            and b.get("root_matches") is True
        )
        check(
            "audit checkpoint verify",
            ok,
            f"valid={b.get('is_valid')} sig={b.get('signature_valid')} "
            f"root={b.get('root_matches')}",
        )

    r = req("GET", "/audit/signing-key", role="auditor")
    ok = r.status_code == 200 and bool(r.json().get("public_key"))
    check(
        "audit signing-key",
        ok,
        f"{r.status_code} alg={r.json().get('algorithm') if ok else r.text[:120]}",
    )

    r = req(
        "GET",
        "/audit/inclusion-proof",
        role="auditor",
        params={"leaf_index": 0, "document_id": doc_id},
    )
    check(
        "audit inclusion-proof",
        r.status_code == 200,
        f"{r.status_code} {r.text[:120] if r.status_code!=200 else 'ok'}",
    )

    n = ctx.get("doc_a_entry_count") or 1
    if isinstance(n, int) and n >= 2:
        r = req(
            "GET",
            "/audit/consistency-proof",
            role="auditor",
            params={"old_size": 1, "new_size": n, "document_id": doc_id},
        )
        check(
            "audit consistency-proof", r.status_code == 200, f"{r.status_code} 1->{n}"
        )
    else:
        check("audit consistency-proof", True, f"skipped (only {n} entry)")


def step_assessment() -> None:
    """The crown jewel: real five-agent LangGraph pipeline in one call."""
    doc_id = ctx.get("doc_b")
    if not doc_id:
        return check("assessment (real 5 agents)", False, "no doc_b")
    r = req(
        "POST",
        "/assessments",
        role="security_admin",
        json={
            "document_id": doc_id,
            "device_id": "workstation-smoke-assess",
            "device_is_new": False,
            "accessed_at": now_iso(),
            "content": CABLE,
        },
    )
    ok = r.status_code == 201
    if not ok:
        return check(
            "assessment (real 5 agents)", False, f"{r.status_code} {r.text[:300]}"
        )
    b = r.json()
    check(
        "assessment (real 5 agents)",
        ok,
        f"consensus={b.get('consensus_value')} ai_rec={b.get('ai_recommendation')} "
        f"final={b.get('final_decision')} profile={b.get('profile_type')} "
        f"encrypted={b.get('encrypted')} reselected={b.get('reselected')}",
    )


def main() -> int:
    print(f"=== Q-AEGIS live end-to-end smoke @ {now_iso()} ===", flush=True)
    print(f"target: {BASE}\n", flush=True)

    step_health()

    # Document A: granular walk through every stage of the bound pipeline.
    step_register("a", "data_owner")
    step_upload()
    step_classify("a")
    step_risk()
    step_trust()
    step_policy_rule()
    step_policy_decision()
    step_crypto()
    step_override()

    # Migration ranking, run twice: the second call proves the audit-chain
    # duplicate-payload fix (identical system-chain writes no longer 500).
    step_migration("#1")
    step_migration("#2")

    step_graph()
    step_rag()
    step_audit()

    # Document B: the combined endpoint that runs the REAL five-agent LangGraph.
    step_register("b", "data_owner")
    step_classify("b")
    step_assessment()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n=== {passed}/{total} checks passed ===", flush=True)
    if passed != total:
        print("FAILURES:", flush=True)
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}", flush=True)
    return 0 if passed == total else 1


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        client.close()
    sys.exit(rc)

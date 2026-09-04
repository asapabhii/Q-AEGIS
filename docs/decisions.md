# Decisions

A running log of implementation decisions made where `SPEC.md` deliberately left a choice open, plus any other significant technical decision worth recording so the reasoning survives past whoever made the call. Newest at the top. Each entry: date, decision, who made it, why, what was rejected and why.

---

## Pending

- **Policy engine: Cedar vs OPA** (`SPEC.md` 2.2, `SPEC.md` 3.6). Not yet decided.
- **Event bus: Redis Streams vs Kafka** (`SPEC.md` 2.3, `SPEC.md` 3.1). Default assumption is Redis Streams until a concrete scale need appears.
- **Vector store: pgvector vs Qdrant** (`SPEC.md` 2.4, `SPEC.md` 3.12). Default assumption is pgvector until a measured latency or filtered-search problem appears.

---

## Log

<!-- Add entries above this line, most recent first. Example format:

### 2026-08-20: Policy engine, chose Cedar

Decided by: Udhav.
Why: formal determinism guarantee matched PRD FR-5's requirement directly; team had no existing OPA/Rego experience to lose by switching.
Rejected: OPA, larger ecosystem but Rego's documented non-determinism issues were a direct conflict with FR-5.

-->

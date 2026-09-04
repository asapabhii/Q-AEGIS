# Decisions

A running log of implementation decisions made where `SPEC.md` deliberately left a choice open, plus any other significant technical decision worth recording so the reasoning survives past whoever made the call. Newest at the top. Each entry: date, decision, who made it, why, what was rejected and why.

---

## Pending

- **Policy engine: Cedar vs OPA** (`SPEC.md` 2.2, `SPEC.md` 3.6). Not yet decided.
- **Event bus: Redis Streams vs Kafka** (`SPEC.md` 2.3, `SPEC.md` 3.1). Default assumption is Redis Streams until a concrete scale need appears.
- **Vector store: pgvector vs Qdrant** (`SPEC.md` 2.4, `SPEC.md` 3.12). Default assumption is pgvector until a measured latency or filtered-search problem appears.

---

## Log

### 2026-09-04: Branching model, trunk-based with no long-lived branches

Decided by: Abhinav.

`main` is the only long-lived branch. There is no `develop` branch, no `release/*`
branches, and no per-person branches.

All work happens on short-lived branches:

- Named `feature/<module>-<short-description>`, for example
  `feature/5-2-classifier-stub` or `feature/phase-1-bootstrap`.
- Branched from an up-to-date `main`.
- Merged back into `main` via pull request only, never by direct push.
- Deleted immediately after merge.

Why: with three contributors and a module ownership split already enforced by
review (`WORK_DIVISION.md`), a long-lived integration branch adds a second merge
surface and a second place for CI to diverge from what actually ships, while
solving a coordination problem this team size does not have. Trunk-based keeps
one branch protected, one CI target, and one definition of "current".

Consequence to keep in mind: because `main` is the integration point, a feature
branch that lives longer than a few days starts accumulating drift and the
"require branches to be up to date before merging" rule will force repeated
rebases. That is the intended pressure, it is a signal to split the change into
smaller pull requests, not a reason to introduce a long-lived branch.

Rejected: Git Flow, its `develop` and `release/*` branches are designed around
versioned, batched releases to external consumers, which this phase explicitly
does not have (`PRD.md` Non-Goal NG4).

### 2026-09-04: CODEOWNERS added, but Code Owner review enforcement deferred

Decided by: Abhinav.

`.github/CODEOWNERS` now exists and maps the three highest-consequence backend
modules (`backend/app/crypto/`, `backend/app/policy/`, `backend/app/audit/`) to
`@UdhavFr` and `frontend/` to `@sukhideas`, matching the required-reviewer rule
already stated in `AGENTS.md` and `WORK_DIVISION.md`.

The usernames are real GitHub accounts, not placeholders. Despite that,
**"Require review from Code Owners" is deliberately NOT enabled in branch
protection yet**, and neither is a minimum approval count.

Why: a CODEOWNERS entry naming an account that lacks write access to the
repository does not block a merge, GitHub ignores the entry and the pull request
merges as if no owner were assigned. The failure mode is silent, there is no
error surfaced on the pull request, which makes it strictly worse than not
configuring the rule at all, an unenforced rule that is believed to be enforced.
At the time of writing, `@UdhavFr` has write access and would resolve correctly,
but `@sukhideas` is not yet a collaborator, so the `frontend/` line would be one
of these silent no-ops. A minimum approval count is also deferred because with
effectively one active reviewer, requiring approvals blocks all merges rather
than improving them.

Revisit when: `@sukhideas` has been added as a collaborator with write access.
At that point verify both owners resolve (GitHub shows unresolvable owners in the
repository's CODEOWNERS settings view, and a pull request touching an owned path
should auto-request the owner as a reviewer, that auto-request is the observable
proof the entry works), then enable "Require review from Code Owners" and set a
minimum approval count of 1 in the same change.

Until then, the reviewer requirement is enforced by convention and review
discipline as documented in `AGENTS.md`, not by the platform. Treat it as such.

<!-- Add entries above this line, most recent first. Example format:

### 2026-08-20: Policy engine, chose Cedar

Decided by: Udhav.
Why: formal determinism guarantee matched PRD FR-5's requirement directly; team had no existing OPA/Rego experience to lose by switching.
Rejected: OPA, larger ecosystem but Rego's documented non-determinism issues were a direct conflict with FR-5.

-->

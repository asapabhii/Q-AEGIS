# Local development setup

Everything needed to get Q-AEGIS Shield running on your machine and to open your
first pull request. Follow it top to bottom the first time. If a command here
disagrees with what you remember, this file is the one that was verified against
the repository.

Read `AGENTS.md` before writing any code, it is the standing instruction set and
it applies to you whether or not you use an AI agent. Read the specific numbered
section of `SPEC.md` for the module you own; `WORK_DIVISION.md` says which module
that is.

---

## 1. What you need installed

| Tool | Version | Why |
|---|---|---|
| Git | any recent | — |
| Python | **3.13** | Pinned in `.github/workflows/ci.yml` and `backend/Dockerfile`. A different minor version can pass locally and fail CI. |
| Docker Desktop | recent, WSL2 backend on Windows | Runs Postgres, Redis, and Neo4j. |
| Node.js | 20 LTS or newer | Frontend only. Not needed for backend work. |
| GitHub CLI (`gh`) | optional | Convenient for opening pull requests. |

Windows note: enable Docker Desktop's WSL2 backend, and give it at least 4 GB of
memory. All three datastores run at once and Neo4j alone reserves a 512 MB heap.

---

## 2. Clone

```bash
git clone https://github.com/asapabhii/Q-AEGIS.git
cd Q-AEGIS
```

You need write access to push a branch. Ask Abhinav if `git push` is rejected.

---

## 3. Create your `.env`

This is the step people skip, and the containers fail in confusing ways without
it. `.env` is gitignored and must never be committed (`AGENTS.md` security
rules). `.env.example` holds dummy values only.

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Then open `.env` and replace every `SET_LOCALLY`. Local throwaway
values are fine, they only ever reach containers on your own machine, but three
things have to stay internally consistent or a service will not start:

1. `DATABASE_URL` embeds `POSTGRES_USER` and `POSTGRES_PASSWORD`. Change the
   password and you must change it in the URL too.
2. `REDIS_URL` embeds `REDIS_PASSWORD`. Same rule.
3. `NEO4J_AUTH` is `neo4j/<password>` and its password half must match
   `QAEGIS_NEO4J_PASSWORD`. The container's initial password comes from
   `NEO4J_AUTH`; the healthcheck and the application read
   `QAEGIS_NEO4J_PASSWORD`. If they diverge, Neo4j starts but never reports
   healthy.

**Use `127.0.0.1`, not `localhost`, in all three URLs.** `.env.example` already
does. On Windows `localhost` resolves to the IPv6 address `::1` first, while the
containers publish on IPv4 only, so a connection does not fail, it hangs until it
times out. That is a much more confusing symptom than a refused connection, which
is why the example file spells the address out.

**Do not add any variable starting with `NEO4J_` to `.env`.** The official Neo4j
image treats that prefix as its server-config namespace, maps each such variable
to a config setting, strict-validates the result, and crash-loops with
`Failed to read config: Unrecognized setting` when it does not recognize one.
Because `infra/docker-compose.yml` passes the whole `.env` to the container, a
well-meaning `NEO4J_URI` here takes the database down. Application-side Neo4j
settings are deliberately `QAEGIS_`-prefixed for exactly this reason. The only
`NEO4J_`-prefixed name in use is `NEO4J_AUTH`, which the image's entrypoint
genuinely defines. The full warning is in `.env.example`.

Variables and what reads them:

| Variable | Read by |
|---|---|
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | the Postgres container, and its healthcheck |
| `DATABASE_URL` | the application and Alembic (`backend/app/config.py`). Required; there is no default, and the app refuses to guess one |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | the Redis container and its healthcheck |
| `REDIS_URL` | the application, once the event bus lands (`SPEC.md` 3.1) |
| `NEO4J_AUTH` | the Neo4j container's entrypoint, sets the initial password |
| `QAEGIS_NEO4J_URI`, `QAEGIS_NEO4J_USER`, `QAEGIS_NEO4J_PASSWORD` | the application, and the Neo4j healthcheck |
| `APP_ENV`, `LOG_LEVEL` | the application (`backend/app/config.py`) |
| `CLASSIFIER_CONFIDENCE_THRESHOLD` | the classifier, confidence below it defaults to the **more** sensitive label (`SPEC.md` 3.2) |

---

## 4. Start the datastores

```bash
cd infra
docker compose up -d
docker compose ps
```

No `--env-file` flag is needed, and no particular working directory beyond
`infra/`; each service declares `env_file: ../.env` itself.

Wait for all three to read `healthy` in `docker compose ps`. Neo4j takes the
longest, roughly 30 to 60 seconds on a first run, because its healthcheck runs a
real Cypher query rather than just checking that the port is open.

Published ports, all bound to `127.0.0.1` only:

| Service | Port |
|---|---|
| Postgres | 5432 |
| Redis | 6379 |
| Neo4j HTTP (browser at <http://127.0.0.1:7474>) | 7474 |
| Neo4j Bolt | 7687 |

Useful commands:

```bash
docker compose logs -f neo4j   # follow one service's logs
docker compose down            # stop, keeps data volumes
docker compose down -v         # stop and delete data, use when a container is wedged
```

The backend is deliberately **not** a service in this compose file. It connects
to Postgres now, but you run it from your shell with `--reload` while working, so
containerizing it would mean rebuilding an image to see a code change. Redis and
Neo4j are still unused by any module.

Known gap, stated rather than hidden: these three services speak plaintext on
loopback, while `AGENTS.md` requires TLS in transit everywhere. Binding to
`127.0.0.1` reduces exposure, it does not satisfy the requirement. See the
comment block at the top of `infra/docker-compose.yml`.

---

## 5. Backend

```bash
cd backend

# create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
.\venv\Scripts\Activate.ps1       # Windows PowerShell

pip install --upgrade pip
pip install -r requirements-dev.txt   # includes requirements.txt
```

Install `requirements-dev.txt`, not `requirements.txt`. The dev file pulls in the
runtime file plus pytest, black, and flake8, which you need before you can pass
CI. If you only ever install the runtime file you will not be able to run the
tests you are required to write.

`requirements.txt` intentionally omits most of `SPEC.md` Section 8's dependency
list. redis, langgraph, neo4j, pgvector, qiskit, and liboqs-python are each added
by the pull request that first imports them. Add yours there, pinned exactly,
when you need it.

### Build the schema

From `backend/`, with the containers healthy and `DATABASE_URL` set:

```bash
alembic upgrade head
python -m app.db.seed
```

The first builds all twelve tables from empty and installs the append-only
triggers. The second creates one development user per role, and is idempotent, so
running it again is harmless.

The seed is a **stub** and is labelled one in its own module. It exists because
`documents.uploaded_by`, `audit_log.actor_id`, `manual_overrides.overridden_by`
and `policy_rules.created_by` are real foreign keys to `users.id`, while the API's
identity source is still a header-trusting stub that knows a caller's role and
nothing else. Without a row per role, every write fails its foreign key. Skip this
step and requests come back `503` telling you to run it.

Both commands are also what the test suite runs, so if `pytest` passes, your
schema is current. Re-run `alembic upgrade head` after every `git pull` that
touches `backend/alembic/versions/`.

### Run it

```bash
uvicorn app.main:app --reload
```

From `backend/`, with the virtual environment active. Then:

- <http://127.0.0.1:8000/api/v1/health>
- <http://127.0.0.1:8000/docs> for interactive API docs

### Call the classifier

Every endpoint checks the caller's role server-side. At Phase 1 the identity
source is a **stub** that trusts a request header, which a client can trivially
forge, so it is authorization plumbing, not authentication. Read the docstring in
`backend/app/api/deps.py` before you build anything on top of it. The header is
required; without it you get a 401.

It takes two calls, not one. `document_id` is a real foreign key, so register the
document first and classify the id you get back. An arbitrary UUID returns a 404.

```bash
# 1. register, and keep the "id" from the response
curl -X POST http://127.0.0.1:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: data_owner" \
  -d '{"filename": "payroll-q3.pdf"}'

# 2. classify it
curl -X POST http://127.0.0.1:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: data_owner" \
  -d '{"document_id": "<the id from step 1>",
       "content": "Employee SSN 123-45-6789 and salary details"}'
```

`/documents` registers metadata only, there is no file upload yet, which is why
`storage_path` comes back null and the status is `registered` rather than
`uploaded`.

Roles accepted on `/classify`: `data_owner`, `security_analyst`,
`security_admin`. `compliance_officer` and `auditor` are refused with a 403 on
purpose, neither persona's stated need involves submitting documents.
`/documents` accepts `data_owner` and `security_admin`.

Each classify call writes one `classification_metadata` row and one `audit_log`
entry in the same transaction as the document's status change, so a failure
anywhere leaves none of it behind. Reclassifying appends rows rather than
replacing them; the history tables are append-only and a trigger enforces it.

There is no read endpoint for that history yet. If you need one, say so rather
than querying the tables directly from the frontend.

### Compute contextual risk

`POST /api/v1/risk-scores` scores a closed snapshot. The server computes
`risk_value`; the client cannot supply it. Roles: `security_analyst` and
`security_admin` only. All five snapshot fields are required; extra keys are
rejected. An unknown `document_id` is a 404.

There is no scheduler and no event bus on this endpoint. Each call writes one
`risk_scores` row and one `audit_log` entry in the same transaction. It does
not change `documents.current_status`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/risk-scores \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: security_analyst" \
  -d '{
    "document_id": "<the id from step 1>",
    "actor_user_id": "<a users.id from python -m app.db.seed>",
    "device_id": "laptop-12",
    "device_is_new": true,
    "accessed_at": "2026-09-09T22:15:00+00:00",
    "after_hours": true
  }'
```

`after_hours` is whatever the caller asserts, not something the server derives
from `accessed_at`. Re-scoring appends a new row; prior scores stay.

### Compute a trust score

`POST /api/v1/trust-scores` combines exactly five agent outputs into one
`consensus_value`. The server computes that number; the client cannot supply it.
Roles: `security_analyst` and `security_admin`. The five scores are
caller-asserted until 3.4 exists to produce them. A missing or duplicate agent
type is 422. An unknown `risk_score_id` is a 404. A second call on the same
risk score is 409 — score a new contextual risk row first.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/trust-scores \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: security_analyst" \
  -d '{
    "risk_score_id": "<the id from the risk-score call>",
    "outputs": [
      {"agent_type": "security", "score": 0.50, "rationale": "No malware indicators."},
      {"agent_type": "compliance", "score": 0.50, "rationale": "Retention policy holds."},
      {"agent_type": "contextual", "score": 0.50, "rationale": "Known device, business hours."},
      {"agent_type": "quantum", "score": 0.50, "rationale": "Hybrid already sufficient."},
      {"agent_type": "sustainability", "score": 0.50, "rationale": "No extra PQC cost needed."}
    ]
  }'
```

Each call writes five `agent_outputs` rows, one `trust_scores` row, and one
`audit_log` entry in the same transaction. It does not change
`documents.current_status` and it does not select a crypto profile (FR-6 is
after the policy gate).

### Policy gate

`POST /api/v1/policy-rules` authors a rule. Role: `compliance_officer` only.
`POST /api/v1/policy-decisions` evaluates active rules in priority order. Roles:
`compliance_officer` and `security_admin`. The server computes `final_decision`;
the client cannot supply it. Body is a `trust_score_id` and an
`ai_recommendation`. The label, risk value, and trust score are read from
stored rows. Classify, score risk, and compute trust first. An unknown
`trust_score_id` is a 404. No classification for that document is 422.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/policy-rules \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: compliance_officer" \
  -d '{
    "rule_name": "Deny restricted",
    "condition_expr": {
      "field": "sensitivity_label",
      "op": "eq",
      "value": "RESTRICTED"
    },
    "action": "deny",
    "priority": 10
  }'

curl -X POST http://127.0.0.1:8000/api/v1/policy-decisions \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: compliance_officer" \
  -d '{
    "trust_score_id": "<the id from the trust-score call>",
    "ai_recommendation": "allow"
  }'
```

Each call writes the decision (or the rule) and one `audit_log` entry in the
same transaction. An unknown `trust_score_id` is a 404. Evaluation does not
change `documents.current_status`.

The API loads the committed `backend/app/policy/rego/policy.wasm`. You do not
need the OPA CLI to run it. Rebuild the WASM only after editing `policy.rego`,
with OPA 1.8.0, and extract `/policy.wasm` from the bundle — not `/policy.rego`,
which the bundle rewrites:

```bash
opa build -t wasm -e q_aegis/policy/first_match \
  -o bundle.tar.gz backend/app/policy/rego/policy.rego
```

### Select a crypto profile

`POST /api/v1/crypto-profiles` maps a persisted trust score onto AES-256,
hybrid (`X25519MLKEM768`), or full post-quantum. The server computes
`profile_type`; the client cannot supply it. Roles: `security_analyst` and
`security_admin`. An unknown `trust_score_id` is a 404. If this document has
no `policy_decisions` row yet, the call is 422 — run the policy gate first
(FR-6). A `deny` still counts. Thresholds are placeholders (`<= 0.4`
post-quantum, `<= 0.8` hybrid, else AES-256). This does not encrypt bytes.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/crypto-profiles \
  -H "Content-Type: application/json" \
  -H "X-Q-AEGIS-Actor-Role: security_analyst" \
  -d '{"trust_score_id": "<the id from the trust-score call>"}'
```

Each call writes one `crypto_profiles` row and one `audit_log` entry in the
same transaction. It does not change `documents.current_status`. Reselection
is a new row.

### Test and lint

Run all three before every pull request. CI runs exactly these and the coverage
number is a gate, not a report.

```bash
pytest --cov=app --cov-fail-under=70
black --check .
flake8 .
```

`black .` without `--check` applies the formatting. The floor is 70% on new code
per `AGENTS.md`; the suite currently sits at 100%, so a drop is a signal you left
something untested, not headroom to spend.

Warnings are errors in this suite (`backend/pyproject.toml`). If a dependency
bump starts emitting a `DeprecationWarning`, the suite fails at that commit
rather than at the version that removes the feature. That is intended. Fix the
cause; only add an ignore for a warning raised inside third-party code you cannot
change, and explain it inline.

### Build the image the way CI does

Only needed if you are touching the Dockerfile or debugging the `build` job.

```bash
cd backend
docker build --tag q-aegis-backend:local .
docker run --rm -p 127.0.0.1:8000:8000 q-aegis-backend:local
```

---

## 6. Frontend

The frontend application (`SPEC.md` 3.13) is scaffolded as a Next.js (App Router)
project using TypeScript and Tailwind CSS in `frontend/`. It includes:

- A centralized, strictly typed API client in `frontend/src/lib/api/client.ts`
  that models backend Pydantic schemas and DB enums (`types.ts`), handling the
  `X-Q-AEGIS-Actor-Role` header plumbing and formatting FastAPI error details.
- The interactive classification workbench in `frontend/src/app/page.tsx`
  demonstrating the two-step register-then-classify flow (`POST /api/v1/documents`
  followed by `POST /api/v1/classify`).
- A Vitest unit and component test suite (`src/**/*.test.{ts,tsx}`) using `jsdom`,
  Testing Library (`@testing-library/react`, `@testing-library/user-event`,
  `@testing-library/jest-dom`), and
  `@vitejs/plugin-react`. Validates API client request construction, FastAPI error
  formatting, and component workbench rendering.
- A 70% coverage floor matching the backend requirement (`AGENTS.md`), enforced locally
  via `npm test` (`@vitest/coverage-v8`) and in CI.
- A `frontend` job in `.github/workflows/ci.yml` running `npm ci`, `npm run lint`,
  `npm test` (with coverage gate), and `npm run build` on pull requests targeting
  `main` and pushes to `main`. (Note: this job is not yet wired as a required branch
  protection check; Abhinav is adding it separately once runs are established).

### Development commands

```bash
cd frontend
npm install
npm run dev        # start Next.js dev server at http://127.0.0.1:3000
npm run lint       # run ESLint
npm test           # run Vitest suite
npm run build      # production build
```

### Environment variables

The frontend reads a single environment variable:

- `NEXT_PUBLIC_API_URL`: Base URL for the backend API.
  - **Default**: `http://127.0.0.1:8000`
  - **Why `127.0.0.1` rather than `localhost`**: On Windows, `localhost` resolves
    to IPv6 (`::1`) first while local services and containers publish on IPv4 only.
    This leads to connection hangs rather than clean, fast connections. Always use
    explicit `127.0.0.1`.
  - To override for custom configurations, set `NEXT_PUBLIC_API_URL` in
    `frontend/.env.local` or your shell. Next.js only reads environment files
    from `frontend/`, so the root `.env` used by Docker Compose and the backend
    will not be picked up. `frontend/.env.local` is gitignored by `frontend/.gitignore`
    (`.env*`) and must never be committed (`AGENTS.md`).

Constraints from `AGENTS.md`: TypeScript only, no plain `.js` files; Tailwind for
styling; every API call goes through `frontend/src/lib/api/`, no inline `fetch()`
scattered through components. UI that hides a control is never access control, the
server decides.

---

## 7. How a change reaches `main`

`main` is protected. You cannot push to it, and that is deliberate.

```bash
git checkout main
git pull
git checkout -b feature/<module>-<short-description>   # e.g. feature/3-6-policy-rule-eval

# work, then
pytest --cov=app --cov-fail-under=70 && black --check . && flake8 .

git add <specific files, not -A>
git commit -m "feat(3.6): add rule evaluation for policy engine"
git push -u origin HEAD
gh pr create --fill --base main    # or open it in the GitHub UI
```

Rules that will actually block your merge:

- **Branch naming**: `feature/<module>-<short-description>`, branched from an
  up-to-date `main`, deleted after merge. `main` is the only long-lived branch,
  no `develop`, no `release/*`, no per-person branches (`docs/decisions.md`).
- **Commit messages** reference the `SPEC.md` section being implemented, for
  example `feat(3.6): ...`, `fix(3.8): ...`.
- **Both status checks must pass**: `lint-test` and `build`. Those exact job IDs
  are wired into branch protection, so renaming a job in `ci.yml` makes the
  protection rule wait forever on a check that no longer reports.
- **One approval is required**, and GitHub does not let you approve your own
  pull request. Nobody lands work solo, including Abhinav.
- **Code Owner review** is enforced. `backend/app/crypto/`, `backend/app/policy/`,
  and `backend/app/audit/` require Udhav regardless of author; `frontend/`
  requires Sukhmani. See `.github/CODEOWNERS`.
- **A pull request without a test update is incomplete.** Not a follow-up pull
  request, the same one.
- Your branch must be up to date with `main` before merging. Keep branches short;
  a long-lived one will force repeated rebases, which is the intended pressure to
  split the change.

Never commit `.env`, a key, or any real credential. Never write an `UPDATE` or
`DELETE` against `audit_log`, in application code or in a migration; it is
append-only and a database trigger enforces it. Do not work around the trigger.

---

## 8. When something breaks

**A container will not start, or `docker compose ps` shows it restarting.**
Read its logs first, `docker compose logs <service>`. For Neo4j specifically,
`Failed to read config: Unrecognized setting` means a stray `NEO4J_`-prefixed
variable reached it from `.env`, see section 3.

**Neo4j starts but never turns healthy.** The password halves of `NEO4J_AUTH` and
`QAEGIS_NEO4J_PASSWORD` disagree. Fix `.env`, then `docker compose down -v` for
that service, the initial password is only set on first initialization of the
data volume, so a plain restart keeps the old one.

**Redis exits immediately with `REDIS_PASSWORD is not set in .env`.** Exactly
what it says. That guard exists so an unset password fails loudly instead of
starting Redis with authentication silently disabled.

**`required variable ... is missing a value`.** You are running `docker compose`
from somewhere other than `infra/`, or `.env` does not exist at the repository
root.

**`DatabaseNotConfiguredError`, or pytest skipping every database test.**
`DATABASE_URL` is unset or blank. There is deliberately no fallback: a default
would embed a credential in source and let a misconfigured process connect
somewhere unintended and appear to work.

**A connection to Postgres hangs instead of failing.** Your URL says `localhost`.
Use `127.0.0.1`, see section 3.

**`503` with "No user exists with role ...".** You have not run
`python -m app.db.seed`, see section 5.

**`404` from `/classify` on a `document_id` you made up.** Expected. Register the
document through `POST /api/v1/documents` first.

**A test fails on `RestrictViolation` with "Table ... is append-only".** The
trigger is doing its job. A new decision is a new row; do not reach for an
`UPDATE`.

**A port is already in use.** Ports are hardcoded in
`infra/docker-compose.yml`, edit the mapping there.

**Tests fail on a `DeprecationWarning` you did not introduce.** Warnings are
errors here by design. See section 5.

**`black --check` fails in CI but not locally.** Version mismatch. Reinstall from
`requirements-dev.txt`, versions are pinned exactly so local, CI, and the Docker
image agree.

**Docker misbehaves broadly after your disk filled up** (500 errors from the
engine, `invalid ELF header` during a build). Layers are corrupt. Shut Docker
Desktop down, run `wsl --shutdown` on Windows, restart it, then
`docker builder prune -af` and re-pull the base image.

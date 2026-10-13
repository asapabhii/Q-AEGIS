Q-AEGIS SHIELD  -  HOW TO RUN AND TEST THE WHOLE PROJECT END TO END
===================================================================

Plain-text runbook. Follow it top to bottom. Every command is PowerShell on
Windows unless it says otherwise. Nothing here commits, pushes, or merges git.

What this gets you: the full stack up (Postgres, Redis, Neo4j, the API), the
schema built and seeded, the 1,040-test automated backend suite green, the
32-check live end-to-end smoke green, the post-quantum crypto path exercised,
and the frontend built and tested. Budget about 20-30 minutes the first time
(most of it the one image rebuild and the Neo4j first-start).

Read this first - the one thing that just bit you
-------------------------------------------------
Your last run failed because docker compose was invoked WITHOUT the env file.
When you run it as "docker compose -f infra/docker-compose.yml ..." from
C:\Q-AEGIS, compose looks for its variables in infra\.env (the compose file's
own folder), and that file does NOT exist. So JWT_SECRET, POSTGRES_USER and the
rest came back empty and every command aborted before touching anything - which
also means NO data was lost, the DROP DATABASE never ran.

The real secrets live in the repository-root file C:\Q-AEGIS\.env. The correct
way to run compose on this branch, every time, is: change into the infra folder
and pass --env-file ..\.env . That is the form the compose file's own header
documents. Use it for up, build, exec, down - all of them.


QUICK PATH  (from the current state: stack has been up ~15h on stale code)
==========================================================================
Run these in order for a full green pass. Details and the why are in the
numbered sections below.

    cd C:\Q-AEGIS\infra
    docker compose --env-file ..\.env build backend
    docker compose --env-file ..\.env up -d backend
    docker compose --env-file ..\.env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);" -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"'
    cd C:\Q-AEGIS\backend
    $env:PYTHONPATH = "."
    venv\Scripts\python.exe -m alembic upgrade head
    venv\Scripts\python.exe -m app.db.seed
    cd C:\Q-AEGIS\backend; $env:PYTHONPATH="."; venv\Scripts\python.exe scripts\smoke_e2e.py

Expected end result: 32/32 checks passed. Then run the automated suite
(Section 4) and the frontend (Section 8). The DROP line wipes only the dev demo
data; the automated suite uses a separate throwaway database and is untouched.

SECTION 0  -  WHAT YOU NEED (all already installed on this machine)
===================================================================
- Docker Desktop with the WSL2 backend, running.
- The Python 3.10 host virtualenv already at C:\Q-AEGIS\backend\venv .
- Node.js 20+ and npm (for the frontend).
- Git (only for staging later; this runbook never commits).

You do not install anything new except, once, four Python packages the host
venv is missing (Section 4) and the frontend node_modules (Section 8).


SECTION 1  -  ONE-TIME CHECKS (env and certificates)
====================================================
1. The root env file C:\Q-AEGIS\.env exists and holds the real local values
   (Postgres user/password/db, JWT_SECRET, Redis password, the dev seed
   password, the Neo4j password, the agent LLM key). This is already in place.
   Never print its contents and never commit it.

2. TLS certificates exist in C:\Q-AEGIS\infra\certs\ : ca.crt, server.crt,
   server.key, redis.dh, and sophos-inspection-ca.crt . They are already there.
   If they were ever missing, regenerate them from the repo root with:

    powershell -ExecutionPolicy Bypass -File scripts\generate-local-certs.ps1

3. CLASSIFIER_MODEL_PATH is set at line 70 of C:\Q-AEGIS\.env (you added it).
   That line only matters when you run the API on the bare host; the container
   bakes its own copy of the trained classifier at
   /srv/artifacts/classifier/multigenre-hashing-svm-1.0.0.joblib and ignores
   the host value.


SECTION 2  -  BRING UP THE FULL STACK
=====================================
Always run compose from the infra folder and always pass --env-file ..\.env .
That single habit is what makes JWT_SECRET and the Postgres variables resolve.

    cd C:\Q-AEGIS\infra
    docker compose --env-file ..\.env up -d
    docker compose --env-file ..\.env ps

Wait until all four services report healthy. Neo4j is the slowest to come up
on a cold start (30-60 seconds); re-run the ps command until it settles.

Published ports on the host (what you connect to from Windows):
    Postgres    127.0.0.1:15432   (inside the Docker network it is 5432)
    Redis       127.0.0.1:6379
    Neo4j       127.0.0.1:7474 (browser)  and  7687 (Bolt)
    Backend API https://127.0.0.1:8443

The compose file auto-merges docker-compose.override.yml when you run it from
the infra folder, which is what feeds the backend the Sophos corporate TLS CA
so the five real scoring agents can reach the LLM endpoint. If you ever run
compose from somewhere else you lose that merge; don't.


SECTION 3  -  BUILD THE SCHEMA AND SEED USERS
=============================================
The backend image is runtime-only - it ships app code + artifacts but NOT the
alembic tooling or the migrations directory - so migrations and the seed run
from the HOST venv, not inside the container. The host reads DATABASE_URL from
C:\Q-AEGIS\.env, which must point at the published port 127.0.0.1:15432 (see
Section 10); the seed reads QAEGIS_DEV_SEED_PASSWORD from the same .env. Run it
once per fresh database:

    cd C:\Q-AEGIS\backend
    $env:PYTHONPATH = "."
    venv\Scripts\python.exe -m alembic upgrade head
    venv\Scripts\python.exe -m app.db.seed

alembic upgrade head builds the twelve core tables and installs the
database-level append-only triggers on the audit tables. The seed inserts one
user per role so you can authenticate. If you are starting from the ~15h-old
stack that already has a schema, you still want the fresh-database reset in
Section 6 before the live smoke - skip ahead there.


SECTION 4  -  RUN THE AUTOMATED BACKEND SUITE (1,040 tests, on the host)
=======================================================================
This is the authoritative proof that the code is correct. It runs on the host
venv against a THROWAWAY database named qaegis_ci, never the live qaegis
database, so it can never pollute the demo data or the live audit chain.

Step 4a - create the throwaway database once (no password needed; this runs
through the container's local socket):

    cd C:\Q-AEGIS\infra
    docker compose --env-file ..\.env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='\''qaegis_ci'\''" | grep -q 1 || psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE qaegis_ci OWNER \"$POSTGRES_USER\";"'

Step 4b - install the four packages the host venv is missing (real pinned
dependencies, just absent from the bare host; without joblib and scikit-learn
the suite dies at collection):

    cd C:\Q-AEGIS\backend
    venv\Scripts\python.exe -m pip install pgvector==0.4.1 neo4j==5.28.1 scikit-learn==1.7.2 joblib==1.5.2

Step 4c - point the test run at qaegis_ci without ever typing a password. This
reads your existing DATABASE_URL out of .env and only swaps the database name,
so every other connection detail (port 15432, sslmode, the CA path) is
preserved exactly:

    cd C:\Q-AEGIS\backend
    $u = (Select-String -Path C:\Q-AEGIS\.env -Pattern '^DATABASE_URL=' | Select-Object -First 1).Line -replace '^DATABASE_URL=',''
    $env:DATABASE_URL = $u -replace '/qaegis(\?|$)', '/qaegis_ci$1'
    $env:PYTHONPATH = "."

Step 4d - run the suite. The one ignored test file is the sensitive-corpus
synthesis test that must not be exercised here; the ddtrace import-warning is
already neutralised in pyproject, so do not add -p no:ddtrace .

    venv\Scripts\python.exe -m pytest --ignore=tests/test_classifier_synth.py --cov=app --cov-fail-under=70 -q

Expected: about 1,040 passed, 19 skipped, 0 failed, total coverage around 79%
(the served-runtime slice is ~85%; the offline data-prep command-line tools
drag the whole-tree number down). The 19 skips are the real ML-DSA-87 tests
that need liboqs, which is not on the host - they run in Docker instead
(Section 7). This run takes roughly 7-12 minutes; run it and read the output,
don't cancel it early.

If pytest complains that tables are missing, the fixtures did not build the
schema for you - migrate qaegis_ci once and re-run:

    venv\Scripts\python.exe -m alembic upgrade head


SECTION 5  -  RUN THE LIVE END-TO-END SMOKE (32 checks)
=======================================================
This drives the entire bound pipeline against the running container: classify,
contextual risk, the five agents, the consensus trust score, the OPA policy
gate, crypto selection, the Merkle audit append, the PQ-signed checkpoint, the
knowledge-graph paths, the RAG answer, and the QAOA migration ranking.

    cd C:\Q-AEGIS\backend
    $env:PYTHONPATH = "."
    venv\Scripts\python.exe scripts\smoke_e2e.py

On a stack freshly built from the current code you get 32/32. On the stale
~15h container you will see exactly four failures, and they are NOT code
defects - they are the old container running code from before two fixes landed:
    - assessment returns 422 about after_hours: the running code now derives
      after_hours on the server, the old image still demanded it in the body.
    - migration rank #1 and #2 return 500: the running code stamps each ranking
      run with a unique id so two identical-seed runs cannot collide on the
      audit chain; the old image did not.
    - policy rule create returns 500: a downstream symptom - the migration 500
      wedges the one shared system audit chain, and the next append onto that
      chain then collides.
The automated suite in Section 4 exercises every one of these paths on a fresh
database and they pass, which is the proof the code is correct. Section 6
rebuilds the live stack so the smoke also shows 32/32.


SECTION 6  -  REBUILD THE IMAGE AND RESET THE AUDIT CHAIN (get to 32/32)
========================================================================
Step 6a - rebuild the backend on the current code and recreate the container.
The liboqs build layer is cached, so this is only a few minutes:

    cd C:\Q-AEGIS\infra
    docker compose --env-file ..\.env build backend
    docker compose --env-file ..\.env up -d backend

Re-run the smoke (Section 5) now if you want: the assessment 422 flips to PASS
immediately, which proves the new image shipped. The migration and policy
checks may still fail, because the live qaegis database's system audit chain is
already wedged by the old code's duplicate payloads, and a broken audit chain
is deliberately never auto-healed - a self-healing audit log would defeat the
point. Clear it with the reset below.

Step 6b - DESTRUCTIVE, and the only destructive step in this runbook. This
recreates the qaegis database so the audit chain starts clean. It wipes the dev
demo data only; the automated suite's qaegis_ci database is a different database
and is untouched. Run the DROP/CREATE from the infra folder; the migrate + seed
then run from the host venv (the container has no alembic tooling):

    docker compose --env-file ..\.env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);" -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"'
    cd C:\Q-AEGIS\backend
    $env:PYTHONPATH = "."
    venv\Scripts\python.exe -m alembic upgrade head
    venv\Scripts\python.exe -m app.db.seed

Step 6c - re-run the smoke:

    cd C:\Q-AEGIS\backend; $env:PYTHONPATH="."; venv\Scripts\python.exe scripts\smoke_e2e.py

Expected now: 32/32 checks passed.


SECTION 7  -  POST-QUANTUM CRYPTO (real ML-DSA-87)
==================================================
You do not need a separate step for this. The prod/container image builds
liboqs 0.16.0 into itself, so the running backend already does real
post-quantum work, and the smoke's audit-checkpoint checks sign a Signed Tree
Head with ML-DSA-87 and verify it inside that container. When those smoke
checks pass you have exercised the real PQ path end to end: a valid signature
verifies, and tampering with the root, the signature, or the key is rejected.
The confirmed ML-DSA-87 sizes are 2592-byte public key, 4896-byte secret key,
4627-byte signature.

The 19 skipped tests in Section 4 are skipped only because the bare host has no
liboqs; they are not a gap in coverage, just a host limitation. If you want to
run PQ code directly against liboqs in Docker, use the pqtest image and the
exact incantation below - the MSYS_NO_PATHCONV=1 prefix is required or Git-Bash
rewrites /opt/liboqs into a Windows path and the library fails to load (this is
a Bash command, not PowerShell):

    MSYS_NO_PATHCONV=1 docker run --rm -v "C:\Q-AEGIS\backend:/mnt/backend" -w /mnt/backend qaegis-backend:pqtest sh -lc 'export OQS_INSTALL_PATH=/opt/liboqs; export LD_LIBRARY_PATH=/opt/liboqs/lib; export PYTHONPATH=/mnt/backend; /opt/venv/bin/python <your-script.py>'


SECTION 8  -  FRONTEND (unit tests, build, and the live UI)
===========================================================
Step 8a - install and verify:

    cd C:\Q-AEGIS\frontend
    npm install
    npm run lint
    npm test
    npm run build

npm test runs vitest with a 70% coverage gate. npm run build must complete with
no type or build errors.

Step 8b - run the UI against the live API. The backend is now HTTPS on 8443, so
create C:\Q-AEGIS\frontend\.env.local with one line:

    NEXT_PUBLIC_API_URL=https://127.0.0.1:8443

Then:

    npm run dev

and open http://127.0.0.1:3000 . Because the API uses a private local CA, the
browser will refuse the first API call until you trust it. Two options:
    - Import C:\Q-AEGIS\infra\certs\ca.crt into your OS or browser trust store, or
    - Run the API on the host over plain HTTP for UI work instead of the
      container: from C:\Q-AEGIS\backend run
          venv\Scripts\python.exe -m uvicorn app.main:app --reload
      which serves http://127.0.0.1:8000, and set NEXT_PUBLIC_API_URL to
      http://127.0.0.1:8000 . (Note: the committed default in the repo is still
      http://127.0.0.1:8000, which is stale for the containerised 8443 stack -
      that is a known documentation-sync item, not a bug in your setup.)

Step 8c - optional manual click-through of the six screens: the dashboard, the
override/decision screen, the policy rules screen, the audit viewer, the
summary/export screen, and the ask/graph screen. Dev-header role bypass is on
in local mode, so you can move between operator and auditor roles.


SECTION 9  -  WHAT "ALL GREEN" LOOKS LIKE
=========================================
    Stack:     four containers healthy (postgres, redis, neo4j, backend).
    Suite:     ~1,040 passed, 19 skipped, 0 failed; coverage >= 70% (about 79%
               whole-tree, ~85% served runtime).
    Smoke:     32/32 checks passed (after the Section 6 rebuild and reset).
    PQ:        smoke checkpoint sign and verify pass; ML-DSA-87 sizes
               2592/4896/4627.
    Frontend:  vitest green, build succeeds, the six screens load against the
               API.


SECTION 10  -  TROUBLESHOOTING (traps already paid for in debugging time)
=========================================================================
- "required variable JWT_SECRET is missing a value" (or POSTGRES_USER / DB /
  PASSWORD / REDIS_PASSWORD / the seed password): you ran compose without
  --env-file ..\.env, or not from the infra folder. Nothing was changed when
  this happens - compose aborts before acting. Fix: cd C:\Q-AEGIS\infra and add
  --env-file ..\.env to the command.

- Host pytest, alembic, or seed hangs or times out connecting to Postgres: the
  host-side DATABASE_URL must use the published port 15432, not 5432. Nothing
  listens on 5432 from the host; the container maps 15432 to its internal 5432.

- The suite dies at collection complaining about joblib or scikit-learn: you
  skipped Step 4b. Install the four pinned packages into the host venv.

- ImportWarning about _ImportHookChainedLoader.exec_module during collection:
  this is the ddtrace watchdog and it is already suppressed by one narrow
  ignore in pyproject.toml. Do not try to fix it with -p no:ddtrace or
  DD_TRACE_ENABLED=false; the watchdog is global and those do not help.

- A TRUNCATE or UPDATE or DELETE against an audit table errors: that is the
  append-only guard doing its job, not a fault. Never mutate audit_log,
  audit_checkpoints, or audit_signing_keys. To start clean, recreate the
  database (Section 6b). A bare TRUNCATE of a signing/checkpoint table fails on
  the foreign key before the trigger even runs; the real erase path is
  recreating the database.

- Neo4j never goes healthy, or the container crashes on boot about a config
  variable: do not add extra NEO4J_-prefixed variables to .env, and make sure
  the Neo4j password in NEO4J_AUTH matches the one the app uses. Give it up to a
  minute on a cold start before deciding it failed.

- A connection just hangs with no error: use 127.0.0.1 everywhere, never
  localhost - the localhost name resolution path stalls in this setup.

- The MSYS_NO_PATHCONV=1 prefix (Section 7) is mandatory for any docker run
  launched from Git-Bash that passes an absolute /opt/... path, or the path is
  rewritten and liboqs fails to load.

- Docker acting strange after a disk fills up: run "wsl --shutdown", restart
  Docker Desktop, and if needed "docker builder prune -af".


SECTION 11  -  STOP AND CLEAN UP
================================
Stop the stack but keep the data (fastest restart next time):

    cd C:\Q-AEGIS\infra
    docker compose --env-file ..\.env down

Stop the stack and wipe all volumes (Postgres, Redis, Neo4j start empty next
time - you would redo Section 3):

    docker compose --env-file ..\.env down -v

Stop the frontend dev server with Ctrl+C in its terminal.

SECTION 12  -  A NOTE ON THE OLDER LOCAL_DEV GUIDE
==================================================
The file docs\LOCAL_DEV.md predates this branch and is partially stale: it says
the backend is not a compose service and that Postgres is on 5432. On this
branch the backend IS a compose service on HTTPS 8443 and Postgres is published
on 15432. Where the two disagree, this runbook is the current one. Bringing
LOCAL_DEV.md and the frontend's default API URL back in line is a pending
documentation task, not something you need to fix to run or test the project.

This runbook file itself (HOW-TO-RUN-AND-TEST-EVERYTHING.md) is scratch and is
not part of the pull request; leave it out of any staging.


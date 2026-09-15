# Q-AEGIS Shield

A data governance platform that classifies document sensitivity, continuously scores risk from multiple independent signals, and selects matching cryptographic protection in real time, with every decision recorded in a tamper-evident, independently verifiable log.

## Documentation map

This repository's documentation is deliberately split by purpose, read the one that matches what you're trying to do rather than searching all of them:

- **`PRD.md`**, what is being built and why, with acceptance criteria per requirement. Start here if you're trying to understand the product.
- **`SPEC.md`**, how it's built: architecture, algorithms, encryption parameters, data model, build order. Start here if you're implementing something.
- **`WORK_DIVISION.md`**, who owns which module.
- **`AGENTS.md`**, standing instructions read automatically by AI coding agents (Antigravity, OpenCode, GitHub Copilot's coding agent, and Cursor all support this format). Read it if you're an agent, or if you want to know what an agent working on this repo already knows.
- **`docs/decisions.md`**, a running log of implementation decisions made where `SPEC.md` deliberately left a choice open.

## Quick Start (Windows)

To start the application locally, open three separate terminals and run the following commands:

### 1. Infrastructure
```powershell
cd infra
docker compose --env-file ../.env up -d
```

### 2. Backend
```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload
```

### 3. Frontend
```powershell
cd frontend
npm run dev
```
Full environment setup detail: `SPEC.md` Section 8.

## Current phase

See `SPEC.md` Section 7 for the full build order. All six frontend screens (FR-12 through FR-16) are built and the API client covers every backend endpoint. The classifier (3.2) remains a keyword stub due to missing data dependencies; the fail-safe escalation logic is active. Current blockers: a labelled training dataset for the Scikit-learn classifier upgrade, and the multi-agent orchestration layer (3.4) to supply real agent scores instead of caller-supplied values.

Running this locally for the first time: `docs/LOCAL_DEV.md`.

## Contributing

Read `WORK_DIVISION.md` before opening a pull request against a module you don't own. Every pull request needs a passing CI run (lint, tests, 70% coverage floor on new code) and, for anything touching `backend/app/crypto/`, `backend/app/policy/`, or `backend/app/audit/`, review from the module's listed reviewer regardless of who authored the change.

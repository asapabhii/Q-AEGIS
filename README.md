# Q-AEGIS Shield

A data governance platform that classifies document sensitivity, continuously scores risk from multiple independent signals, and selects matching cryptographic protection in real time, with every decision recorded in a tamper-evident, independently verifiable log.

## Documentation map

This repository's documentation is deliberately split by purpose, read the one that matches what you're trying to do rather than searching all of them:

- **`PRD.md`**, what is being built and why, with acceptance criteria per requirement. Start here if you're trying to understand the product.
- **`SPEC.md`**, how it's built: architecture, algorithms, encryption parameters, data model, build order. Start here if you're implementing something.
- **`WORK_DIVISION.md`**, who owns which module.
- **`AGENTS.md`**, standing instructions read automatically by AI coding agents (Antigravity, OpenCode, GitHub Copilot's coding agent, and Cursor all support this format). Read it if you're an agent, or if you want to know what an agent working on this repo already knows.
- **`docs/decisions.md`**, a running log of implementation decisions made where `SPEC.md` deliberately left a choice open.

## Getting started

```bash
# clone and enter
git clone <repo-url> && cd qaegis-shield

# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend, separate terminal
cd frontend
npm install && npm run dev

# full local stack
cd infra && docker-compose up
```

Full environment setup detail: `SPEC.md` Section 8.

## Current phase

See `SPEC.md` Section 7 for the full build order. Phase 1 is complete: repository scaffolding, the classifier stub, the core audit log functions, and CI with branch protection and a coverage gate. Current phase: Phase 2, the data model (`SPEC.md` Section 5) and the crypto-selector stub.

Running this locally for the first time: `docs/LOCAL_DEV.md`.

## Contributing

Read `WORK_DIVISION.md` before opening a pull request against a module you don't own. Every pull request needs a passing CI run (lint, tests, 70% coverage floor on new code) and, for anything touching `backend/app/crypto/`, `backend/app/policy/`, or `backend/app/audit/`, review from the module's listed reviewer regardless of who authored the change.

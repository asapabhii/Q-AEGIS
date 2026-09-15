---
name: qaegis-design-documentation
description: Transform approved Q-AEGIS Shield requirements from PRD.md into comprehensive technical designs aligned with SPEC.md. Define system architecture, deterministic component interactions, strict data models, and auditable interfaces.
license: MIT
compatibility: Claude Code, Cursor, VS Code, Windsurf
metadata:
  category: methodology
  complexity: advanced
  author: Q-AEGIS Team
  version: "2.0.0"
---

# Q-AEGIS Design Documentation

Create technical blueprints that bridge the `PRD.md` functional requirements and the `SPEC.md` implementation plan. This skill ensures that every design choice respects the project's strict modularity, security constraints, and deterministic policies.

## When to Use This Skill

Use this design documentation skill when:
- You need to plan the implementation of a specific `SPEC.md` Section 3 module[cite: 13].
- Architecture decisions (e.g., Redis Streams vs. Kafka for the Event Bus, or pgvector vs. Qdrant for RAG) need to be evaluated and logged to `docs/decisions.md`[cite: 11, 13].
- You are designing API boundaries using Pydantic models.
- You are designing frontend workflows requiring strict TypeScript and Next.js compliance.

## Design Document Structure

### Standard Template

```markdown
# Design Document: [Feature / SPEC.md Module Name]

## Overview
[Mapping to PRD.md requirement and SPEC.md architecture]

## Architecture & Boundaries
[System architecture, ensuring no structural merging of SPEC.md modules]

## Components and Interfaces
[Pydantic models for API boundaries, Next.js components for frontend]

## Data Models
[SQLAlchemy structure mapping exactly to docs/data-dictionary.md]

## Security & Error Handling
[Deterministic fail-safes, role-based access, auditability]

## Testing Strategy
[70% coverage floor verification and module-specific test cases]
---
applyTo: "frontend/**/*.ts,frontend/**/*.tsx"
---

Read `SPEC.md` 3.13 and `PRD.md` FR-12 through FR-16 before editing any screen.

- Next.js, TypeScript only, no plain JavaScript files. Tailwind for styling.
- The six screens (classification request, manual override, policy rule builder, risk dashboard, audit viewer, summary report) have field-level specs and validation rules already documented in the system design reference. Implement against those specs, do not redesign layout without checking with the module owner in `WORK_DIVISION.md` first.
- Every mandatory field's validation rule is enforced client-side for UX and, separately and always, server-side. The client-side check is never sufficient alone.
- The manual override screen's confirmation checkbox must gate the submit button (disabled until checked), this is a specified requirement, not optional polish.
- Centralize API calls in `frontend/src/lib/api/`, no inline `fetch()` calls scattered through components.

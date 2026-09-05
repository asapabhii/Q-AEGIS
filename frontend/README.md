# Q-AEGIS Shield — Frontend

Frontend application for Q-AEGIS Shield (`SPEC.md` 3.13), built with Next.js (App Router), TypeScript, and Tailwind CSS.

## Getting Started

Install dependencies and start the development server:

```bash
npm install
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000) in your browser.

## Available Scripts

- `npm run dev`: Starts the local Next.js development server.
- `npm run lint`: Runs ESLint over all source files.
- `npm test`: Runs the Vitest test suite (`src/**/*.test.ts`).
- `npm run build`: Compiles the production build.

## Environment Variables

The frontend reads one environment variable:

- `NEXT_PUBLIC_API_URL`: The base URL of the backend API.
  - **Default**: `http://127.0.0.1:8000`
  - **Why `127.0.0.1` rather than `localhost`**: Always use `127.0.0.1`. On Windows, `localhost` resolves to IPv6 (`::1`) first while local services and containers bind on IPv4, resulting in timeouts or connection hangs rather than clean, fast connections.
  - **Security & Overrides**: Do not commit real endpoints, credentials, or keys. Local overrides belong in `frontend/.env.local` (covered by `frontend/.gitignore` via `.env*`), as Next.js only reads environment files from `frontend/` and ignores the root `.env` (see `docs/LOCAL_DEV.md`).

## Architecture Constraints (AGENTS.md)

- **TypeScript only**: No plain `.js` files.
- **Centralized API**: All backend requests are routed through `src/lib/api/client.ts` with models defined in `src/lib/api/types.ts`. No inline `fetch()` calls in UI components.
- **Authorization plumbing**: The `X-Q-AEGIS-Actor-Role` header is a development stub for role-based testing, not authentication. The server always decides authorization.

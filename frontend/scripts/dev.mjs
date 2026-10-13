// Dev-server launcher.
//
// The Next dev server reverse-proxies /api/* to the backend, which runs over
// HTTPS with a self-signed local CA (see next.config.ts). Node verifies that
// server-side hop against its CA store, so we point NODE_EXTRA_CA_CERTS at the
// repo's local CA *before* Node initializes TLS. This must be set at process
// start (Next's proxy ignores NODE_TLS_REJECT_UNAUTHORIZED), so it lives here
// in a launcher that sets it and then spawns `next dev` as a child that
// inherits it — rather than in .env.local, which Next loads too late.
//
// Result: `npm run dev` just works; the browser only ever speaks plain HTTP to
// the same origin, and no CA import into any browser/OS trust store is needed.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const caPath = path.resolve(here, "..", "..", "infra", "certs", "ca.crt");

if (!process.env.NODE_EXTRA_CA_CERTS) {
  if (existsSync(caPath)) {
    process.env.NODE_EXTRA_CA_CERTS = caPath;
    console.log(`[dev] trusting local dev CA for the API proxy: ${caPath}`);
  } else {
    console.warn(
      `[dev] local dev CA not found at ${caPath}. The /api proxy to an HTTPS ` +
        `backend will fail cert verification. Set NEXT_PUBLIC_API_URL to a ` +
        `direct backend URL, or generate certs (infra/certs).`
    );
  }
}

const child = spawn("next", ["dev"], {
  stdio: "inherit",
  shell: true,
  env: process.env,
});
child.on("exit", (code) => process.exit(code ?? 0));

/**
 * Single source of truth for the frontend role model.
 *
 * The backend is the real authority: every gate here MIRRORS a
 * `require_role(...)` dependency in backend/app/api/deps.py (and audit.py for
 * the evidence routes). The UI uses these lists only to shape navigation and
 * render honest "not permitted" states — it never grants access the server
 * would refuse. When a backend gate changes, update the matching entry here in
 * the same change.
 *
 * Authoritative backend matrix (transcribed from deps.py / audit.py):
 *   RegisterDocumentCaller  POST /documents ............ data_owner, security_admin
 *   ClassifyCaller          POST /classify ............. data_owner, security_analyst, security_admin
 *   OverrideCaller          POST /manual-overrides ..... security_analyst, security_admin
 *   PolicyRuleCaller        POST /policy-rules[/test] .. compliance_officer
 *   DocumentInventoryCaller GET /documents[/{id}][/agents] .. security_admin, security_analyst, auditor, ciso, engineer
 *   ShredCaller             POST /shred ................ data_owner, compliance_officer, security_admin
 *   SummaryCaller           export ..................... data_owner, security_admin
 *   MigrationCaller         migration .................. security_admin
 *   GraphCaller             graph ...................... security_analyst, security_admin, ciso, engineer
 *   RagCaller               POST /ask .................. security_analyst, security_admin, auditor, ciso
 *   VerifyChainCaller       GET /audit/* (reads) ....... auditor, security_admin, security_analyst
 *   CheckpointCreator       POST /audit/checkpoint ..... auditor, security_admin
 */

import type { UserRole } from "@/lib/api/types";

// ---------------------------------------------------------------------------
// Roles — labels and options
// ---------------------------------------------------------------------------

/** Every role the backend recognizes, in a sensible presentation order. */
export const ALL_ROLES: UserRole[] = [
  "data_owner",
  "security_analyst",
  "security_admin",
  "compliance_officer",
  "auditor",
  "ciso",
  "engineer",
];

/** Human-readable role names for chips, selects, and identity display. */
export const ROLE_LABELS: Record<UserRole, string> = {
  data_owner: "Data Owner",
  security_analyst: "Security Analyst",
  security_admin: "Security Admin",
  compliance_officer: "Compliance Officer",
  auditor: "Auditor",
  ciso: "CISO",
  engineer: "Engineer",
};

/** One-line description of what each role does, for the role switcher. */
export const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  data_owner: "Registers and classifies documents; requests export or shred.",
  security_analyst: "Triages risk, overrides labels, investigates the fleet.",
  security_admin: "Full operator: classify, override, migrate, protect.",
  compliance_officer: "Authors policy rules and authorizes shredding.",
  auditor: "Reads the audit chain and issues signed checkpoints.",
  ciso: "Executive fleet posture and risk overview.",
  engineer: "System health and pipeline diagnostics.",
};

/** `<select>` option list, ordered as {@link ALL_ROLES}. */
export const ROLE_OPTIONS: Array<{ value: UserRole; label: string }> =
  ALL_ROLES.map((value) => ({ value, label: ROLE_LABELS[value] }));

/**
 * Default caller role when there is no JWT session and no stored dev role.
 * security_admin sees the widest set of surfaces without immediately tripping
 * a backend gate, so a fresh dev session lands somewhere useful rather than on
 * a wall of 403s (data_owner, the old default, fails the inventory gate).
 */
export const DEFAULT_ROLE: UserRole = "security_admin";

// ---------------------------------------------------------------------------
// Access lists — each mirrors one backend require_role(...) gate
// ---------------------------------------------------------------------------

/**
 * Canonical access lists, referenced by both the nav filter here and by
 * individual pages so a page's allow-list can never drift from the sidebar.
 * Import the specific list you need (e.g. `ACCESS.override`) instead of
 * re-declaring role arrays inside a page.
 */
export const ACCESS = {
  /** POST /documents + POST /classify — the register→classify entry page. */
  classify: ["data_owner", "security_admin"] as UserRole[],
  /** POST /manual-overrides. */
  override: ["security_analyst", "security_admin"] as UserRole[],
  /** POST /policy-rules and /policy-rules/test. */
  rules: ["compliance_officer"] as UserRole[],
  /** GET /documents[/{id}][/agents] — the FR-14 inventory gate. */
  inventory: [
    "security_admin",
    "security_analyst",
    "auditor",
    "ciso",
    "engineer",
  ] as UserRole[],
  /** Executive fleet posture — a UI subset of the inventory readers. */
  ciso: ["ciso", "security_admin"] as UserRole[],
  /** System health — a UI subset of the inventory readers. */
  engineer: ["engineer", "security_admin"] as UserRole[],
  /** GET /graph. */
  graph: ["security_analyst", "security_admin", "ciso", "engineer"] as UserRole[],
  /** POST /ask (agentic RAG). */
  ask: ["security_analyst", "security_admin", "auditor", "ciso"] as UserRole[],
  /** GET /audit/* reads (entries, verify, proofs, checkpoint reads). */
  audit: ["auditor", "security_admin", "security_analyst"] as UserRole[],
  /** POST /audit/checkpoint — issuing a Signed Tree Head. */
  checkpointIssue: ["auditor", "security_admin"] as UserRole[],
  /** POST /migration-schedule/rank. */
  migration: ["security_admin"] as UserRole[],
  /** Export (PDF summary) — SummaryCaller. */
  export: ["data_owner", "security_admin"] as UserRole[],
  /** POST /shred — ShredCaller. */
  shred: ["data_owner", "compliance_officer", "security_admin"] as UserRole[],
  /** Export & Shred page visibility = union of export + shred callers. */
  summaryPage: ["data_owner", "security_admin", "compliance_officer"] as UserRole[],
} as const;

// ---------------------------------------------------------------------------
// Route → access resolution
// ---------------------------------------------------------------------------

/**
 * Exact route → allowed roles. Dynamic and nested routes are resolved by the
 * prefix rules in {@link canAccess}; this map covers the canonical top-level
 * destinations that appear in navigation.
 */
const ROUTE_ACCESS: Record<string, UserRole[]> = {
  "/": ACCESS.classify,
  "/override": ACCESS.override,
  "/rules": ACCESS.rules,
  "/dashboard": ACCESS.inventory,
  "/ciso": ACCESS.ciso,
  "/engineer": ACCESS.engineer,
  "/agents": ACCESS.inventory,
  "/graph": ACCESS.graph,
  "/ask": ACCESS.ask,
  "/audit": ACCESS.audit,
  "/audit/checkpoints": ACCESS.audit,
  "/migration": ACCESS.migration,
  "/summary": ACCESS.summaryPage,
};

/**
 * Resolve the effective allow-list for any pathname, including dynamic and
 * nested routes. Returns null when the route is not gated at the UI level
 * (e.g. /login, or a future page) — callers should treat null as "no UI gate"
 * and defer to the server.
 *
 * Order matters: the most specific prefix must be tested first.
 */
export function accessForPath(pathname: string): UserRole[] | null {
  // Normalize trailing slash (but keep the root "/").
  const path =
    pathname.length > 1 && pathname.endsWith("/")
      ? pathname.slice(0, -1)
      : pathname;

  // Exact canonical routes.
  if (path in ROUTE_ACCESS) return ROUTE_ACCESS[path];

  // Nested / dynamic routes, most specific first.
  if (path.startsWith("/audit/checkpoints")) return ACCESS.audit;
  if (path.startsWith("/audit/")) return ACCESS.audit; // /audit/{document_id}
  if (path.startsWith("/documents/") && path.endsWith("/summary")) {
    return ACCESS.summaryPage;
  }
  if (path.startsWith("/documents/")) return ACCESS.inventory;

  return null;
}

/**
 * Whether {@link role} may see {@link pathname} in the UI. Ungated routes
 * (accessForPath === null) return true — the UI filter is UX, not the security
 * boundary; the backend enforces every gate regardless.
 */
export function canAccess(pathname: string, role: UserRole): boolean {
  const allowed = accessForPath(pathname);
  return allowed === null || allowed.includes(role);
}

/** Whether {@link role} is in an explicit allow-list. */
export function roleAllowed(allowed: UserRole[], role: UserRole): boolean {
  return allowed.includes(role);
}

// ---------------------------------------------------------------------------
// Post-login landing
// ---------------------------------------------------------------------------

/**
 * Where each role lands after signing in. The old fixed `router.push("/dashboard")`
 * was gated to {@link ACCESS.inventory}, so `data_owner` and `compliance_officer`
 * hit a "not permitted" wall on their very first screen despite a successful
 * login. Each destination below is the role's most useful surface AND one the
 * role can actually see; {@link landingPathForRole} re-checks that with
 * {@link canAccess} so this map can never silently drift into a 403.
 */
export const ROLE_LANDING: Record<UserRole, string> = {
  data_owner: "/",
  security_analyst: "/dashboard",
  security_admin: "/dashboard",
  compliance_officer: "/rules",
  auditor: "/audit",
  ciso: "/ciso",
  engineer: "/engineer",
};

/** The post-login route for {@link role}, guaranteed visible to that role. */
export function landingPathForRole(role: UserRole): string {
  const target = ROLE_LANDING[role] ?? "/";
  return canAccess(target, role) ? target : "/";
}

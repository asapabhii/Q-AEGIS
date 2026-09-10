"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { SiteNav } from "@/components/SiteNav";
import {
  ApiError,
  createPolicyRule,
  testPolicyRule,
} from "@/lib/api/client";
import type {
  PolicyAction,
  PolicyRuleResponse,
  PolicyRuleTestResponse,
  UserRole,
} from "@/lib/api/types";
import {
  CONDITION_FIELDS,
  MAX_RULE_NAME_CHARS,
  POLICY_ACTIONS,
  SENSITIVITY_LABELS,
  canAuthorRule,
  emptyConditionDraft,
  operatorsForField,
  toRuleRequest,
  type ConditionDraft,
  type ConditionField,
  type LeafOperator,
} from "@/lib/rules";

const RULE_ROLES: { value: UserRole; label: string }[] = [
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "security_admin", label: "Security Admin" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "data_owner", label: "Data Owner" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

type DraftRow = ConditionDraft & { id: number };

function valueChoices(field: ConditionField): readonly string[] | null {
  if (field === "sensitivity_label") return SENSITIVITY_LABELS;
  if (field === "ai_recommendation") return POLICY_ACTIONS;
  return null;
}

export function RuleBuilderScreen() {
  const [role, setRole] = useState<UserRole>("compliance_officer");
  const [ruleName, setRuleName] = useState("");
  const [action, setAction] = useState<PolicyAction>("deny");
  const [priority, setPriority] = useState("10");
  const [nextRowId, setNextRowId] = useState(1);
  const [drafts, setDrafts] = useState<DraftRow[]>([
    { id: 0, ...emptyConditionDraft() },
  ]);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<PolicyRuleTestResponse | null>(
    null
  );
  const [saved, setSaved] = useState<PolicyRuleResponse | null>(null);

  const loading = testing || saving;
  const canSubmit = canAuthorRule({
    ruleName,
    action,
    priority,
    drafts,
    loading,
  });

  function updateDraft(id: number, patch: Partial<ConditionDraft>) {
    setDrafts((rows) =>
      rows.map((row) => {
        if (row.id !== id) return row;
        const next = { ...row, ...patch };
        if (patch.field && !operatorsForField(patch.field).includes(next.op)) {
          next.op = "eq";
          next.value = "";
        }
        return next;
      })
    );
  }

  function addCondition() {
    setDrafts((rows) => [...rows, { id: nextRowId, ...emptyConditionDraft() }]);
    setNextRowId((value) => value + 1);
  }

  function removeCondition(id: number) {
    setDrafts((rows) => (rows.length <= 1 ? rows : rows.filter((row) => row.id !== id)));
  }

  async function handleTest() {
    const body = toRuleRequest({ ruleName, action, priority, drafts });
    if (!body) return;
    setTesting(true);
    setTestError(null);
    setSaveError(null);
    setSaved(null);
    try {
      setTestResult(await testPolicyRule(body, role));
    } catch (err) {
      setTestResult(null);
      setTestError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setTesting(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = toRuleRequest({ ruleName, action, priority, drafts });
    if (!body) return;
    setSaving(true);
    setSaveError(null);
    setTestError(null);
    setTestResult(null);
    try {
      setSaved(await createPolicyRule(body, role));
    } catch (err) {
      setSaved(null);
      setSaveError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold"
            >
              Q
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Policy Rule Builder
              </h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                PRD.md FR-13 · test before it goes live
              </p>
            </div>
          </div>
          <SiteNav active="/rules" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8 space-y-8">
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6">
          <h2 className="text-base font-semibold mb-1">Author an override rule</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">
            Compliance Officers can save a named rule with at least one
            condition. Test evaluates the last 20 gate snapshots and writes
            nothing. Multiple conditions are sent as a flat <code>all</code>.
          </p>

          <form onSubmit={handleSave} className="grid gap-5 md:grid-cols-2">
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="rule-role"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Caller Role
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    (authorization plumbing, not authentication)
                  </span>
                </label>
                <select
                  id="rule-role"
                  value={role}
                  onChange={(event) => setRole(event.target.value as UserRole)}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                >
                  {RULE_ROLES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="rule-name"
                  className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                >
                  Rule name
                  <span className="ml-1 text-[var(--color-text-muted)]">
                    ({ruleName.trim().length}/{MAX_RULE_NAME_CHARS} after trim)
                  </span>
                </label>
                <input
                  id="rule-name"
                  type="text"
                  value={ruleName}
                  onChange={(event) => setRuleName(event.target.value)}
                  maxLength={MAX_RULE_NAME_CHARS}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                  placeholder="Deny restricted"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="rule-action"
                    className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                  >
                    Action
                  </label>
                  <select
                    id="rule-action"
                    value={action}
                    onChange={(event) =>
                      setAction(event.target.value as PolicyAction)
                    }
                    className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                  >
                    {POLICY_ACTIONS.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="rule-priority"
                    className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1.5"
                  >
                    Priority
                  </label>
                  <input
                    id="rule-priority"
                    type="number"
                    min={1}
                    step={1}
                    value={priority}
                    onChange={(event) => setPriority(event.target.value)}
                    className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-xs font-medium text-[var(--color-text-secondary)]">
                  Conditions
                </p>
                {drafts.map((row, index) => {
                  const choices = valueChoices(row.field);
                  const useSelect = choices !== null && row.op !== "in";
                  return (
                    <div
                      key={row.id}
                      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-[var(--color-text-muted)]">
                          Condition {index + 1}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeCondition(row.id)}
                          disabled={drafts.length <= 1}
                          className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="grid gap-2 sm:grid-cols-3">
                        <div>
                          <label
                            htmlFor={`rule-field-${row.id}`}
                            className="block text-xs text-[var(--color-text-muted)] mb-1"
                          >
                            Field
                          </label>
                          <select
                            id={`rule-field-${row.id}`}
                            value={row.field}
                            onChange={(event) =>
                              updateDraft(row.id, {
                                field: event.target.value as ConditionField,
                              })
                            }
                            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-2 py-1.5 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                          >
                            {CONDITION_FIELDS.map((field) => (
                              <option key={field} value={field}>
                                {field}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label
                            htmlFor={`rule-op-${row.id}`}
                            className="block text-xs text-[var(--color-text-muted)] mb-1"
                          >
                            Operator
                          </label>
                          <select
                            id={`rule-op-${row.id}`}
                            value={row.op}
                            onChange={(event) =>
                              updateDraft(row.id, {
                                op: event.target.value as LeafOperator,
                              })
                            }
                            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-2 py-1.5 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                          >
                            {operatorsForField(row.field).map((op) => (
                              <option key={op} value={op}>
                                {op}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label
                            htmlFor={`rule-value-${row.id}`}
                            className="block text-xs text-[var(--color-text-muted)] mb-1"
                          >
                            Value
                          </label>
                          {useSelect ? (
                            <select
                              id={`rule-value-${row.id}`}
                              value={row.value}
                              onChange={(event) =>
                                updateDraft(row.id, { value: event.target.value })
                              }
                              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-2 py-1.5 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                            >
                              <option value="">Select</option>
                              {choices.map((item) => (
                                <option key={item} value={item}>
                                  {item}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              id={`rule-value-${row.id}`}
                              type="text"
                              value={row.value}
                              onChange={(event) =>
                                updateDraft(row.id, { value: event.target.value })
                              }
                              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] px-2 py-1.5 text-sm focus:border-[var(--color-border-focus)] focus:outline-none"
                              placeholder={
                                row.op === "in" ? "a, b" : "0.0 – 1.0"
                              }
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <button
                  type="button"
                  onClick={addCondition}
                  className="text-sm text-cyan-400 hover:underline"
                >
                  Add condition
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  id="rule-test-btn"
                  onClick={() => void handleTest()}
                  disabled={!canSubmit}
                  className="rounded-lg border border-[var(--color-border)] px-4 py-2.5 text-sm font-semibold hover:bg-[var(--color-bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {testing ? "Testing…" : "Test rule"}
                </button>
                <button
                  type="submit"
                  id="rule-save-btn"
                  disabled={!canSubmit}
                  className="rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? "Saving…" : "Save rule"}
                </button>
              </div>

              {testError && <p className="text-sm text-red-400">{testError}</p>}
              {saveError && <p className="text-sm text-red-400">{saveError}</p>}
            </div>

            <div className="space-y-4">
              {saved && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Rule saved
                  </h3>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">Name</dt>
                      <dd>{saved.rule_name}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">ID</dt>
                      <dd className="font-mono text-xs">{saved.id}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">Active</dt>
                      <dd>{saved.active ? "yes" : "no"}</dd>
                    </div>
                  </dl>
                </div>
              )}

              {testResult && (
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
                    Dry-run result
                  </h3>
                  <dl className="space-y-2 text-sm mb-4">
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">Window</dt>
                      <dd>{testResult.window}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">
                        Considered
                      </dt>
                      <dd>{testResult.considered}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[var(--color-text-secondary)]">Skipped</dt>
                      <dd>{testResult.skipped}</dd>
                    </div>
                  </dl>
                  {testResult.replays.length === 0 ? (
                    <p className="text-sm text-[var(--color-text-muted)]">
                      No historical decisions in the window
                    </p>
                  ) : (
                    <ul className="space-y-2 text-xs">
                      {testResult.replays.map((replay) => (
                        <li
                          key={replay.decision_id}
                          className="rounded-md border border-[var(--color-border)] px-2 py-2"
                        >
                          <div className="font-mono">{replay.document_id}</div>
                          <div className="text-[var(--color-text-muted)]">
                            {replay.would_match ? "would match" : "no match"}
                            {replay.would_change_outcome
                              ? " · would change outcome"
                              : ""}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {!saved && !testResult && !testError && !saveError && (
                <div className="flex items-center justify-center h-48 rounded-lg border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] text-sm">
                  Test against recent decisions, then save
                </div>
              )}
            </div>
          </form>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-3 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
          <span>Q-AEGIS Shield · SPEC.md 3.13 · Input Screen 3</span>
          <span>Test writes nothing — save persists the rule</span>
        </div>
      </footer>
    </div>
  );
}

export default function RulesPage() {
  return <RuleBuilderScreen />;
}

"use client";

import { FormEvent, useState } from "react";
import {
  Plus,
  X,
  FlaskConical,
  Save,
  CheckCircle2,
  AlertTriangle,
  Code2,
} from "lucide-react";
import { useGsapReveal } from "@/lib/hooks/useGsapReveal";
import { useRole } from "@/lib/context/RoleContext";
import {
  ApiError,
  createPolicyRule,
  testPolicyRule,
} from "@/lib/api/client";
import type {
  PolicyAction,
  PolicyRuleResponse,
  PolicyRuleTestResponse,
} from "@/lib/api/types";
import {
  CONDITION_FIELDS,
  MAX_RULE_NAME_CHARS,
  POLICY_ACTIONS,
  SENSITIVITY_LABELS,
  canAuthorRule,
  clampRuleName,
  emptyConditionDraft,
  operatorsForField,
  strippedRuleNameLength,
  toRuleRequest,
  type ConditionDraft,
  type ConditionField,
  type LeafOperator,
} from "@/lib/rules";

type DraftRow = ConditionDraft & { id: number };

function valueChoices(field: ConditionField): readonly string[] | null {
  if (field === "sensitivity_label") return SENSITIVITY_LABELS;
  if (field === "ai_recommendation") return POLICY_ACTIONS;
  return null;
}

export function RuleBuilderScreen() {
  const containerRef = useGsapReveal<HTMLDivElement>();
  const { role } = useRole();
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
  const [testResult, setTestResult] = useState<PolicyRuleTestResponse | null>(null);
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
    <div
      ref={containerRef}
      className="mx-auto w-full max-w-screen-xl space-y-8 px-6 py-8"
    >
      {/* Hero Header */}
      <header data-reveal className="flex items-start justify-between">
        <div>
          <h1
            className="font-semibold mb-1"
            style={{
              fontSize: "var(--font-size-2xl)",
              color: "var(--color-text-primary)",
            }}
          >
            Rule Configuration Studio
          </h1>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-secondary)",
            }}
          >
            Build, test, and deploy policy override rules with visual query editor
          </p>
        </div>


      </header>

      {/* Success Banner */}
      {saved && (
        <div
          data-reveal
          className="card p-6 flex items-start gap-4"
          style={{ borderColor: "var(--status-pass)" }}
        >
          <div
            className="flex h-10 w-10 items-center justify-center rounded-full"
            style={{ backgroundColor: "rgba(16, 185, 129, 0.1)" }}
          >
            <CheckCircle2 className="h-5 w-5" style={{ color: "var(--status-pass)" }} />
          </div>
          <div className="flex-1">
            <h3
              className="text-base font-semibold mb-2"
              style={{ color: "var(--color-text-primary)" }}
            >
              Policy Rule Deployed
            </h3>
            <p className="text-sm mb-3" style={{ color: "var(--color-text-secondary)" }}>
              <span className="font-medium" style={{ color: "var(--color-text-primary)" }}>
                {saved.rule_name}
              </span>{" "}
              is now{" "}
              {saved.active ? (
                <span style={{ color: "var(--status-pass)" }}>active</span>
              ) : (
                <span style={{ color: "var(--status-override)" }}>inactive</span>
              )}{" "}
              in the policy engine
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
              Rule ID:{" "}
              <span className="mono-data" style={{ color: "var(--status-pass)" }}>
                {saved.id}
              </span>
            </p>
          </div>
          <button
            onClick={() => setSaved(null)}
            className="btn btn-ghost"
            style={{ padding: "var(--spacing-2)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Main Content */}
      <div data-reveal className="grid gap-6 lg:grid-cols-[1fr_420px]">
        {/* Left: Form */}
        <div className="card p-6">
          <form onSubmit={handleSave} className="space-y-6">
            <header className="mb-6 flex items-center gap-2">
              <Code2 className="h-5 w-5" style={{ color: "var(--color-text-secondary)" }} />
              <h2
                className="font-semibold"
                style={{
                  fontSize: "var(--font-size-lg)",
                  color: "var(--color-text-primary)",
                }}
              >
                Rule Configuration
              </h2>
            </header>

            {/* Rule name */}
            <div>
              <label
                className="block text-sm font-medium mb-2"
                style={{ color: "var(--color-text-secondary)" }}
              >
                Rule Name
                <span className="ml-2 text-xs mono-data" style={{ color: "var(--color-text-tertiary)" }}>
                  {strippedRuleNameLength(ruleName)}/{MAX_RULE_NAME_CHARS}
                </span>
              </label>
              <input
                id="rule-name"
                type="text"
                value={ruleName}
                onChange={(event) =>
                  setRuleName(clampRuleName(event.target.value))
                }
                className="input w-full"
                placeholder="e.g. Deny RESTRICTED without approval"
              />
            </div>

            {/* Action + Priority */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  className="block text-sm font-medium mb-2"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Action
                </label>
                <select
                  id="rule-action"
                  value={action}
                  onChange={(event) =>
                    setAction(event.target.value as PolicyAction)
                  }
                  className="input w-full"
                >
                  {POLICY_ACTIONS.map((item) => (
                    <option key={item} value={item}>
                      {item.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label
                  className="block text-sm font-medium mb-2"
                  style={{ color: "var(--color-text-secondary)" }}
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
                  className="input mono-data w-full"
                />
              </div>
            </div>

            {/* Conditions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label
                  className="block text-sm font-medium"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Conditions{" "}
                  <span className="text-xs ml-2" style={{ color: "var(--color-text-tertiary)" }}>
                    (combined with AND logic)
                  </span>
                </label>
                <div className="text-xs mono-data" style={{ color: "var(--color-text-tertiary)" }}>
                  {drafts.length} condition{drafts.length !== 1 ? "s" : ""}
                </div>
              </div>

              {/* Condition list without line connectors */}
              <div className="space-y-3">
                {drafts.map((row, index) => {
                  const choices = valueChoices(row.field);
                  const useSelect = choices !== null && row.op !== "in";
                  return (
                    <div
                      key={row.id}
                      className="rounded-lg p-4 border-hairline"
                      style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                    >
                      {/* Condition header */}
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div
                            className="flex h-6 w-6 items-center justify-center rounded font-mono text-xs font-medium"
                            style={{
                              backgroundColor: "var(--color-bg-secondary)",
                              color: "var(--color-text-primary)",
                              border: "var(--border-width-hairline) solid var(--color-border)",
                            }}
                          >
                            {index + 1}
                          </div>
                          <span
                            className="text-xs uppercase tracking-wider"
                            style={{ color: "var(--color-text-secondary)" }}
                          >
                            Condition
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeCondition(row.id)}
                          disabled={drafts.length <= 1}
                          className="btn btn-ghost"
                          style={{
                            padding: "var(--spacing-1)",
                            color: drafts.length <= 1 ? "var(--color-text-tertiary)" : "var(--status-fail)",
                          }}
                          aria-label="Remove condition"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>

                      {/* Condition inputs */}
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div>
                          <label
                            htmlFor={`rule-field-${row.id}`}
                            className="block text-xs mb-1.5 uppercase tracking-wider"
                            style={{ color: "var(--color-text-secondary)" }}
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
                            className="input w-full"
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
                            className="block text-xs mb-1.5 uppercase tracking-wider"
                            style={{ color: "var(--color-text-secondary)" }}
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
                            className="input mono-data w-full"
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
                            className="block text-xs mb-1.5 uppercase tracking-wider"
                            style={{ color: "var(--color-text-secondary)" }}
                          >
                            Value
                          </label>
                          {useSelect ? (
                            <select
                              id={`rule-value-${row.id}`}
                              value={row.value}
                              onChange={(event) =>
                                updateDraft(row.id, {
                                  value: event.target.value,
                                })
                              }
                              className="input w-full"
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
                                updateDraft(row.id, {
                                  value: event.target.value,
                                })
                              }
                              className="input mono-data w-full"
                              placeholder={
                                row.op === "in"
                                  ? "a, b, c"
                                  : row.field === "trust_score"
                                    ? "0.0 – 1.0"
                                    : "value"
                              }
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <button
                type="button"
                onClick={addCondition}
                className="btn btn-secondary w-full flex items-center justify-center gap-2"
                style={{
                  borderStyle: "dashed",
                  backgroundColor: "transparent",
                }}
              >
                <Plus className="h-4 w-4" />
                Add Condition
              </button>
            </div>

            {/* Info Banner */}
            <div className="card p-4">
              <p className="text-sm" style={{ color: "var(--color-text-secondary)", lineHeight: "var(--line-height-relaxed)" }}>
                Test mode evaluates against the last 20 policy decisions without writing to the database. Save mode deploys the rule to the live policy engine.
              </p>
            </div>

            {/* Action buttons */}
            <div className="grid grid-cols-2 gap-4 pt-2">
              <button
                type="button"
                id="rule-test-btn"
                onClick={() => void handleTest()}
                disabled={!canSubmit}
                className="btn btn-secondary flex items-center justify-center gap-2"
                style={{ padding: "var(--spacing-3)" }}
              >
                {testing ? "Testing..." : <><FlaskConical className="h-4 w-4" /> Test Rule</>}
              </button>
              <button
                type="submit"
                id="rule-save-btn"
                disabled={!canSubmit}
                className="btn btn-primary flex items-center justify-center gap-2"
                style={{ padding: "var(--spacing-3)" }}
              >
                {saving ? "Deploying..." : <><Save className="h-4 w-4" /> Deploy Rule</>}
              </button>
            </div>

            {testError && (
               <div
                className="p-4 rounded-lg flex items-center gap-3 border-hairline"
                style={{
                  backgroundColor: "rgba(239, 68, 68, 0.1)",
                  borderColor: "var(--status-fail)",
                }}
              >
                <AlertTriangle
                  className="h-5 w-5 flex-shrink-0"
                  style={{ color: "var(--status-fail)" }}
                />
                <p className="text-sm" style={{ color: "var(--status-fail)" }}>{testError}</p>
              </div>
            )}
            {saveError && (
              <div
                className="p-4 rounded-lg flex items-center gap-3 border-hairline"
                style={{
                  backgroundColor: "rgba(239, 68, 68, 0.1)",
                  borderColor: "var(--status-fail)",
                }}
              >
                <AlertTriangle
                  className="h-5 w-5 flex-shrink-0"
                  style={{ color: "var(--status-fail)" }}
                />
                <p className="text-sm" style={{ color: "var(--status-fail)" }}>{saveError}</p>
              </div>
            )}
          </form>
        </div>

        {/* Right: Results Panel */}
        <div className="space-y-4">
          {testResult ? (
            <div className="card p-6">
              <header className="mb-6">
                <h3
                  className="font-semibold mb-1"
                  style={{
                    fontSize: "var(--font-size-base)",
                    color: "var(--color-text-primary)",
                  }}
                >
                  Test Results
                </h3>
                <p
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  Dry-run simulation against recent decisions
                </p>
              </header>

              <div className="space-y-4">
                {/* Metrics */}
                <div className="grid grid-cols-3 gap-3">
                  <div
                    className="text-center p-3 rounded-lg border-hairline"
                    style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                  >
                    <p className="text-xl font-medium mono-data" style={{ color: "var(--color-text-primary)" }}>
                      {testResult.window}
                    </p>
                    <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                      Window
                    </p>
                  </div>
                  <div
                    className="text-center p-3 rounded-lg border-hairline"
                    style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                  >
                    <p className="text-xl font-medium mono-data" style={{ color: "var(--color-text-primary)" }}>
                      {testResult.considered}
                    </p>
                    <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                      Considered
                    </p>
                  </div>
                  <div
                    className="text-center p-3 rounded-lg border-hairline"
                    style={{ backgroundColor: "var(--color-bg-tertiary)" }}
                  >
                    <p className="text-xl font-medium mono-data" style={{ color: "var(--color-text-secondary)" }}>
                      {testResult.skipped}
                    </p>
                    <p className="text-xs mt-1 uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                      Skipped
                    </p>
                  </div>
                </div>

                {/* Replay results */}
                {testResult.replays.length === 0 ? (
                  <div
                    className="flex flex-col items-center justify-center py-8 rounded-lg border-hairline"
                    style={{ borderStyle: "dashed" }}
                  >
                    <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                      No historical decisions in window
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p
                      className="text-xs uppercase tracking-wider mb-3"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      Match Results ({testResult.replays.length})
                    </p>
                    <div className="space-y-2 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                      {testResult.replays.map((replay) => {
                        const wouldMatch = replay.would_match;
                        const wouldChange = replay.would_change_outcome;
                        return (
                          <div
                            key={replay.decision_id}
                            className="rounded-lg p-3 border-hairline transition-colors"
                            style={{
                              backgroundColor: wouldMatch
                                ? "var(--color-bg-hover)"
                                : "var(--color-bg-tertiary)",
                              borderColor: wouldMatch
                                ? "var(--color-border-hover)"
                                : "var(--color-border)",
                            }}
                          >
                            <div className="flex items-start gap-3">
                              <div
                                className="flex h-5 w-5 items-center justify-center rounded-full flex-shrink-0 mt-0.5"
                                style={{
                                  backgroundColor: wouldMatch
                                    ? "rgba(16, 185, 129, 0.1)"
                                    : "var(--color-bg-secondary)",
                                }}
                              >
                                {wouldMatch ? (
                                  <CheckCircle2 className="h-3 w-3" style={{ color: "var(--status-pass)" }} />
                                ) : (
                                  <X className="h-3 w-3" style={{ color: "var(--color-text-tertiary)" }} />
                                )}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-xs mono-data truncate" style={{ color: "var(--color-text-primary)" }}>
                                  {replay.document_id}
                                </p>
                                <div className="flex items-center gap-2 mt-1">
                                  <span
                                    className="text-xs"
                                    style={{
                                      color: wouldMatch
                                        ? "var(--status-pass)"
                                        : "var(--color-text-secondary)",
                                    }}
                                  >
                                    {wouldMatch ? "Match" : "No match"}
                                  </span>
                                  {wouldChange && (
                                    <span
                                      className="text-xs flex items-center gap-1"
                                      style={{ color: "var(--status-override)" }}
                                    >
                                      <AlertTriangle className="h-3 w-3" />
                                      Would change outcome
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div
              className="card flex flex-col items-center justify-center py-12"
              style={{ minHeight: "400px" }}
            >
              <Code2
                className="h-12 w-12 mb-4 opacity-40"
                style={{ color: "var(--color-text-tertiary)" }}
              />
              <p
                className="text-base font-medium mb-2"
                style={{ color: "var(--color-text-primary)" }}
              >
                Ready to Test
              </p>
              <p
                className="text-sm text-center max-w-xs"
                style={{ color: "var(--color-text-secondary)" }}
              >
                Configure your rule conditions and test against recent policy decisions
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function RulesPage() {
  return <RuleBuilderScreen />;
}

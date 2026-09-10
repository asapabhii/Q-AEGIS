import type { PolicyAction, PolicyRuleRequest } from "@/lib/api/types";

/** Matches ``policy_rules.rule_name`` and ``PolicyRuleCreateRequest``. */
export const MAX_RULE_NAME_CHARS = 150;

export const CONDITION_FIELDS = [
  "sensitivity_label",
  "risk_value",
  "trust_score",
  "ai_recommendation",
] as const;

export type ConditionField = (typeof CONDITION_FIELDS)[number];

export const LEAF_OPERATORS = [
  "eq",
  "neq",
  "gt",
  "gte",
  "lt",
  "lte",
  "in",
] as const;

export type LeafOperator = (typeof LEAF_OPERATORS)[number];

export const POLICY_ACTIONS: readonly PolicyAction[] = [
  "allow",
  "deny",
  "require_mfa",
  "force_pqc",
];

export const SENSITIVITY_LABELS = [
  "PUBLIC",
  "INTERNAL",
  "CONFIDENTIAL",
  "RESTRICTED",
] as const;

const NUMERIC_FIELDS: ReadonlySet<ConditionField> = new Set([
  "risk_value",
  "trust_score",
]);

export type ConditionDraft = {
  field: ConditionField;
  op: LeafOperator;
  value: string;
};

export type LeafCondition = {
  field: ConditionField;
  op: LeafOperator;
  value: string | number | Array<string | number>;
};

export function operatorsForField(field: ConditionField): readonly LeafOperator[] {
  if (NUMERIC_FIELDS.has(field)) {
    return LEAF_OPERATORS;
  }
  return ["eq", "neq", "in"];
}

function parseScalar(
  field: ConditionField,
  raw: string
): string | number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (NUMERIC_FIELDS.has(field)) {
    const number = Number(trimmed);
    if (!Number.isFinite(number) || number < 0 || number > 1) return null;
    return number;
  }
  if (field === "sensitivity_label") {
    return (SENSITIVITY_LABELS as readonly string[]).includes(trimmed)
      ? trimmed
      : null;
  }
  if (field === "ai_recommendation") {
    return (POLICY_ACTIONS as readonly string[]).includes(trimmed)
      ? trimmed
      : null;
  }
  return null;
}

export function parseLeafValue(
  field: ConditionField,
  op: LeafOperator,
  raw: string
): string | number | Array<string | number> | null {
  if (!operatorsForField(field).includes(op)) return null;
  if (op === "in") {
    const parts = raw
      .split(",")
      .map((part) => part.trim())
      .filter((part) => part.length > 0);
    if (parts.length < 1) return null;
    const parsed: Array<string | number> = [];
    for (const part of parts) {
      const item = parseScalar(field, part);
      if (item === null) return null;
      parsed.push(item);
    }
    return parsed;
  }
  return parseScalar(field, raw);
}

export function buildLeaf(draft: ConditionDraft): LeafCondition | null {
  const value = parseLeafValue(draft.field, draft.op, draft.value);
  if (value === null) return null;
  return { field: draft.field, op: draft.op, value };
}

export function buildConditionExpr(
  drafts: ConditionDraft[]
): Record<string, unknown> | null {
  if (drafts.length < 1) return null;
  const leaves: LeafCondition[] = [];
  for (const draft of drafts) {
    const leaf = buildLeaf(draft);
    if (leaf === null) return null;
    leaves.push(leaf);
  }
  if (leaves.length === 1) {
    return leaves[0];
  }
  return { all: leaves };
}

export function canAuthorRule(options: {
  ruleName: string;
  action: string;
  priority: string;
  drafts: ConditionDraft[];
  loading: boolean;
}): boolean {
  if (options.loading) return false;
  const name = options.ruleName.trim();
  if (!name || name.length > MAX_RULE_NAME_CHARS) return false;
  if (!(POLICY_ACTIONS as readonly string[]).includes(options.action)) {
    return false;
  }
  const priority = Number(options.priority);
  if (!Number.isInteger(priority) || priority <= 0) return false;
  return buildConditionExpr(options.drafts) !== null;
}

export function toRuleRequest(options: {
  ruleName: string;
  action: PolicyAction;
  priority: string;
  drafts: ConditionDraft[];
}): PolicyRuleRequest | null {
  if (
    !canAuthorRule({
      ruleName: options.ruleName,
      action: options.action,
      priority: options.priority,
      drafts: options.drafts,
      loading: false,
    })
  ) {
    return null;
  }
  const condition_expr = buildConditionExpr(options.drafts);
  if (!condition_expr) return null;
  return {
    rule_name: options.ruleName.trim(),
    condition_expr,
    action: options.action,
    priority: Number(options.priority),
  };
}

export function emptyConditionDraft(): ConditionDraft {
  return { field: "sensitivity_label", op: "eq", value: "" };
}

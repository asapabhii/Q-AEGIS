import { describe, expect, it } from "vitest";
import {
  MAX_RULE_NAME_CHARS,
  buildConditionExpr,
  canAuthorRule,
  parseLeafValue,
  toRuleRequest,
} from "./rules";

const readyDraft = {
  field: "sensitivity_label" as const,
  op: "eq" as const,
  value: "RESTRICTED",
};

const ready = {
  ruleName: "Deny restricted",
  action: "deny",
  priority: "10",
  drafts: [readyDraft],
  loading: false,
};

describe("canAuthorRule", () => {
  it("allows a named rule with one complete condition", () => {
    expect(canAuthorRule(ready)).toBe(true);
  });

  it("refuses a blank or whitespace-only name", () => {
    expect(canAuthorRule({ ...ready, ruleName: "" })).toBe(false);
    expect(canAuthorRule({ ...ready, ruleName: "   " })).toBe(false);
  });

  it("refuses a name longer than 150 characters after trim", () => {
    expect(
      canAuthorRule({ ...ready, ruleName: "x".repeat(MAX_RULE_NAME_CHARS + 1) })
    ).toBe(false);
  });

  it("refuses when there is no complete condition", () => {
    expect(
      canAuthorRule({
        ...ready,
        drafts: [{ field: "sensitivity_label", op: "eq", value: "" }],
      })
    ).toBe(false);
    expect(canAuthorRule({ ...ready, drafts: [] })).toBe(false);
  });

  it("refuses a non-positive or non-integer priority", () => {
    expect(canAuthorRule({ ...ready, priority: "0" })).toBe(false);
    expect(canAuthorRule({ ...ready, priority: "1.5" })).toBe(false);
    expect(canAuthorRule({ ...ready, priority: "" })).toBe(false);
  });
});

describe("buildConditionExpr", () => {
  it("emits a single leaf when there is one condition", () => {
    expect(buildConditionExpr([readyDraft])).toEqual({
      field: "sensitivity_label",
      op: "eq",
      value: "RESTRICTED",
    });
  });

  it("wraps two or more leaves in all", () => {
    expect(
      buildConditionExpr([
        readyDraft,
        { field: "trust_score", op: "lte", value: "0.4" },
      ])
    ).toEqual({
      all: [
        { field: "sensitivity_label", op: "eq", value: "RESTRICTED" },
        { field: "trust_score", op: "lte", value: 0.4 },
      ],
    });
  });

  it("refuses an incomplete extra row", () => {
    expect(
      buildConditionExpr([
        readyDraft,
        { field: "risk_value", op: "gt", value: "" },
      ])
    ).toBeNull();
  });
});

describe("parseLeafValue", () => {
  it("parses an in-list of labels", () => {
    expect(
      parseLeafValue("sensitivity_label", "in", "PUBLIC, INTERNAL")
    ).toEqual(["PUBLIC", "INTERNAL"]);
  });

  it("rejects inequality on a label field", () => {
    expect(parseLeafValue("sensitivity_label", "gt", "RESTRICTED")).toBeNull();
  });

  it("rejects a numeric value outside [0, 1]", () => {
    expect(parseLeafValue("trust_score", "eq", "1.2")).toBeNull();
  });
});

describe("toRuleRequest", () => {
  it("strips the name and sends only the persist fields", () => {
    expect(
      toRuleRequest({
        ruleName: "  Deny restricted  ",
        action: "deny",
        priority: "10",
        drafts: [readyDraft],
      })
    ).toEqual({
      rule_name: "Deny restricted",
      condition_expr: {
        field: "sensitivity_label",
        op: "eq",
        value: "RESTRICTED",
      },
      action: "deny",
      priority: 10,
    });
  });
});

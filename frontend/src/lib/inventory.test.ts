import { describe, expect, it } from "vitest";
import type { DocumentSnapshot } from "@/lib/api/types";
import { countLabeled, displayStage } from "./inventory";

const blank: DocumentSnapshot = {
  id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  filename: "a.pdf",
  storage_path: null,
  current_status: "registered",
  uploaded_by: "11111111-2222-3333-4444-555555555555",
  uploaded_at: "2026-09-10T00:00:00Z",
  sensitivity_label: null,
  label_source: null,
  override_id: null,
  classification_id: null,
  risk_score_id: null,
  risk_value: null,
  risk_computed_at: null,
  trust_score_id: null,
  trust_score: null,
  trust_computed_at: null,
  policy_decision_id: null,
  final_decision: null,
  decided_at: null,
  crypto_profile_id: null,
  profile_type: null,
  selected_at: null,
};

describe("displayStage", () => {
  it("does not invent a value for a stage that has not run", () => {
    expect(displayStage(null)).toBe("—");
    expect(displayStage("RESTRICTED")).toBe("RESTRICTED");
  });
});

describe("countLabeled", () => {
  it("counts only rows that already have an effective label", () => {
    expect(countLabeled([blank])).toBe(0);
    expect(
      countLabeled([{ ...blank, sensitivity_label: "INTERNAL" }])
    ).toBe(1);
  });
});

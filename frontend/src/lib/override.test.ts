import { describe, expect, it } from "vitest";
import {
  MIN_JUSTIFICATION_CHARS,
  canSubmitOverride,
  strippedJustificationLength,
} from "./override";

const ready = {
  documentId: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  hasClassifiedSnapshot: true,
  newLabel: "INTERNAL" as const,
  currentLabel: "RESTRICTED" as const,
  justification: "Reviewed with the data owner and reclassified.",
  confirmed: true,
  loading: false,
};

describe("canSubmitOverride", () => {
  it("allows a complete, confirmed change", () => {
    expect(canSubmitOverride(ready)).toBe(true);
  });

  it("refuses until the confirmation checkbox is checked", () => {
    expect(canSubmitOverride({ ...ready, confirmed: false })).toBe(false);
  });

  it("refuses a justification shorter than 20 characters after trim", () => {
    expect(strippedJustificationLength("   short   ")).toBe(5);
    expect(
      canSubmitOverride({
        ...ready,
        justification: "   " + "x".repeat(MIN_JUSTIFICATION_CHARS - 1),
      })
    ).toBe(false);
  });

  it("counts trimmed length so padding does not unlock submit", () => {
    expect(
      canSubmitOverride({
        ...ready,
        justification: " ".repeat(MIN_JUSTIFICATION_CHARS),
      })
    ).toBe(false);
  });

  it("refuses the current effective label", () => {
    expect(
      canSubmitOverride({
        ...ready,
        newLabel: "RESTRICTED",
        currentLabel: "RESTRICTED",
      })
    ).toBe(false);
  });

  it("refuses an unclassified document", () => {
    expect(
      canSubmitOverride({
        ...ready,
        hasClassifiedSnapshot: false,
        currentLabel: null,
      })
    ).toBe(false);
  });
});

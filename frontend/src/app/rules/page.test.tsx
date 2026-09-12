import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RuleBuilderScreen } from "./page";
import {
  ApiError,
  createPolicyRule,
  testPolicyRule,
} from "@/lib/api/client";
import type { PolicyRuleResponse, PolicyRuleTestResponse } from "@/lib/api/types";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    createPolicyRule: vi.fn(),
    testPolicyRule: vi.fn(),
  };
});

const mockCreate = vi.mocked(createPolicyRule);
const mockTest = vi.mocked(testPolicyRule);

const sampleLeaf = {
  field: "sensitivity_label",
  op: "eq",
  value: "RESTRICTED",
};

const sampleSaved: PolicyRuleResponse = {
  id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  rule_name: "Deny restricted",
  condition_expr: sampleLeaf,
  action: "deny",
  priority: 10,
  active: true,
  created_at: "2026-09-10T12:00:00Z",
};

const sampleTest: PolicyRuleTestResponse = {
  rule_name: "Deny restricted",
  action: "deny",
  priority: 10,
  condition_expr: sampleLeaf,
  window: 20,
  considered: 1,
  skipped: 0,
  replays: [
    {
      decision_id: "11111111-1111-1111-1111-111111111111",
      document_id: "22222222-2222-2222-2222-222222222222",
      decided_at: "2026-09-10T11:00:00Z",
      sensitivity_label: "RESTRICTED",
      recorded_final_decision: "allow",
      would_match: true,
      hypothetical_final_decision: "deny",
      would_change_outcome: true,
    },
  ],
};

const expectedBody = {
  rule_name: "Deny restricted",
  condition_expr: sampleLeaf,
  action: "deny",
  priority: 10,
};

async function fillReadyForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByPlaceholderText(/e.g. Deny RESTRICTED/i),
    "Deny restricted"
  );
  await user.selectOptions(screen.getByLabelText(/^value$/i), "RESTRICTED");
}

describe("RuleBuilderScreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("keeps test and save disabled until name and one condition are filled", async () => {
    const user = userEvent.setup();
    render(<RuleBuilderScreen />);
    const testBtn = screen.getByRole("button", { name: /test rule/i });
    const saveBtn = screen.getByRole("button", { name: /deploy rule/i });
    expect(testBtn).toBeDisabled();
    expect(saveBtn).toBeDisabled();

    await user.type(
      screen.getByPlaceholderText(/e.g. Deny RESTRICTED/i),
      "Deny restricted"
    );
    expect(testBtn).toBeDisabled();

    await user.selectOptions(screen.getByLabelText(/^value$/i), "RESTRICTED");
    expect(testBtn).toBeEnabled();
    expect(saveBtn).toBeEnabled();
  });

  it("keeps both actions disabled for a whitespace-only name", async () => {
    const user = userEvent.setup();
    render(<RuleBuilderScreen />);
    await user.type(
      screen.getByPlaceholderText(/e.g. Deny RESTRICTED/i),
      "   "
    );
    await user.selectOptions(screen.getByLabelText(/^value$/i), "RESTRICTED");
    expect(screen.getByRole("button", { name: /test rule/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /deploy rule/i })).toBeDisabled();
  });

  it("tests without calling createPolicyRule", async () => {
    const user = userEvent.setup();
    mockTest.mockResolvedValueOnce(sampleTest);
    render(<RuleBuilderScreen />);
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /test rule/i }));

    expect(mockTest).toHaveBeenCalledTimes(1);
    expect(mockTest).toHaveBeenCalledWith(expectedBody, "compliance_officer");
    expect(mockCreate).not.toHaveBeenCalled();
    expect(await screen.findByText("Test Results")).toBeInTheDocument();
    expect(screen.getByText(/^Match$/i)).toBeInTheDocument();
    expect(JSON.stringify(mockTest.mock.calls[0][0])).not.toContain("window");
  });

  it("saves the rule without calling testPolicyRule", async () => {
    const user = userEvent.setup();
    mockCreate.mockResolvedValueOnce(sampleSaved);
    render(<RuleBuilderScreen />);
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /deploy rule/i }));

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate).toHaveBeenCalledWith(expectedBody, "compliance_officer");
    expect(mockTest).not.toHaveBeenCalled();
    expect(await screen.findByText("Policy Rule Deployed")).toBeInTheDocument();
    expect(screen.getByText(sampleSaved.id)).toBeInTheDocument();
  });

  it("sends two conditions as a flat all tree", async () => {
    const user = userEvent.setup();
    mockCreate.mockResolvedValueOnce({
      ...sampleSaved,
      condition_expr: {
        all: [sampleLeaf, { field: "trust_score", op: "lte", value: 0.4 }],
      },
    });
    render(<RuleBuilderScreen />);
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /add condition/i }));
    await user.selectOptions(screen.getAllByLabelText(/^field$/i)[1], "trust_score");
    await user.selectOptions(screen.getAllByLabelText(/^operator$/i)[1], "lte");
    await user.type(screen.getAllByLabelText(/^value$/i)[1], "0.4");
    await user.click(screen.getByRole("button", { name: /deploy rule/i }));

    expect(mockCreate).toHaveBeenCalledWith(
      {
        rule_name: "Deny restricted",
        condition_expr: {
          all: [
            sampleLeaf,
            { field: "trust_score", op: "lte", value: 0.4 },
          ],
        },
        action: "deny",
        priority: 10,
      },
      "compliance_officer"
    );
  });

  it("renders a unique-name conflict on save", async () => {
    const user = userEvent.setup();
    mockCreate.mockRejectedValueOnce(
      new ApiError(409, "Conflict", {
        detail:
          "A rule with this name already exists, or another active rule already has this priority.",
      })
    );
    render(<RuleBuilderScreen />);
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /deploy rule/i }));
    expect(
      await screen.findByText(/API 409: A rule with this name already exists/i)
    ).toBeInTheDocument();
    expect(screen.queryByText("Policy Rule Deployed")).not.toBeInTheDocument();
  });

  it("passes the selected role to test and save", async () => {
    const user = userEvent.setup();
    mockTest.mockResolvedValueOnce(sampleTest);
    mockCreate.mockResolvedValueOnce(sampleSaved);
    render(<RuleBuilderScreen />);
    await user.selectOptions(
      screen.getByDisplayValue("Compliance Officer"),
      "security_admin"
    );
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /test rule/i }));
    expect(mockTest).toHaveBeenCalledWith(expectedBody, "security_admin");
    await user.click(screen.getByRole("button", { name: /deploy rule/i }));
    expect(mockCreate).toHaveBeenCalledWith(expectedBody, "security_admin");
  });
});


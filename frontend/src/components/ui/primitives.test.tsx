import { describe, expect, it } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Badge from "./Badge";
import Card from "./Card";
import DataTable from "./DataTable";
import HashDisplay from "./HashDisplay";

describe("shared UI primitives", () => {
  it("renders a badge with the clinical tone variable", () => {
    render(<Badge label="RESTRICTED" tone="restricted" />);

    const badge = screen.getByText("RESTRICTED");
    expect(badge).toHaveClass("badge-restricted");
    cleanup();
  });

  it("renders tabular data and an explicit empty state", () => {
    const columns = [
      { key: "document", header: "Document" },
      { key: "value", header: "Value", align: "right" as const, mono: true },
    ];
    const { unmount } = render(
      <DataTable
        label="Risk values"
        columns={columns}
        rows={[{ document: "roadmap.pdf", value: "0.222" }]}
      />,
    );

    expect(screen.getByText("Document")).toBeInTheDocument();
    expect(screen.getByText("0.222")).toBeInTheDocument();
    unmount();

    render(
      <DataTable label="Risk values" columns={columns} rows={[]} />,
    );
    expect(
      screen.getByText("No rows match the current filters."),
    ).toBeInTheDocument();
    cleanup();
  });

  it("renders card structure without decorative behavior", () => {
    render(
      <Card
        title="Policy gate"
        description="Deterministic override."
        actions={<button type="button">Test rule</button>}
      >
        <p>Rule outcome</p>
      </Card>,
    );

    const card = screen.getByRole("heading", { name: "Policy gate" }).closest("section");
    expect(card).toBeInTheDocument();
    expect(screen.getByText("Deterministic override.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test rule" })).toBeInTheDocument();
    cleanup();
  });

  it("abbreviates a hash and reveals it on selection", async () => {
    const user = userEvent.setup();
    const hash = "9".repeat(64);
    render(<HashDisplay hash={hash} />);

    const button = screen.getByRole("button", {
      name: `Show full hash ${hash}`,
    });
    expect(within(button).getByText("99999999…")).toBeInTheDocument();

    await user.click(button);
    expect(
      screen.getByRole("button", { name: "Show abbreviated hash" }),
    ).toHaveTextContent(hash);
    cleanup();
  });
});

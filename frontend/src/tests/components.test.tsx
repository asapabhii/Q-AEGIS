import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import HashDisplay from "@/components/ui/HashDisplay";
import MetricCard from "@/components/ui/MetricCard";
import RiskGauge from "@/components/ui/RiskGauge";
import StatusDot from "@/components/ui/StatusDot";
import Badge from "@/components/ui/Badge";

describe("UI Components", () => {
  it("renders Card", () => {
    render(
      <Card>
        Test Content Body
      </Card>
    );
    expect(screen.getByText("Test Content Body")).toBeInTheDocument();
  });

  it("renders DataTable with data", () => {
    const rows = [{ id: 1, name: "Alice" }, { id: 2, name: "Bob" }];
    const columns = [
      { key: "id", header: "ID" },
      { key: "name", header: "Name" },
    ];
    render(<DataTable label="Test Table" rows={rows} columns={columns} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("renders HashDisplay", () => {
    render(<HashDisplay hash="abc123def456ghi789jkl012mno345pqr" visibleChars={10} />);
    expect(screen.getByTitle("abc123def456ghi789jkl012mno345pqr")).toBeInTheDocument();
  });

  it("renders MetricCard with all props", () => {
    render(
      <MetricCard
        label="Total Users"
        value="1,234"
        trend="up"
        trendValue="vs last month"
        tone="teal"
      />
    );
    expect(screen.getByText("Total Users")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });

  it("renders RiskGauge with score", () => {
    render(<RiskGauge value={0.8} />);
  });

  it("renders StatusDot", () => {
    const { container } = render(<StatusDot variant="online" label="Test" />);
    expect(container).toBeInTheDocument();
  });

  it("renders Badge", () => {
    render(<Badge tone="restricted" label="RESTRICTED" />);
    expect(screen.getByText("RESTRICTED")).toBeInTheDocument();
  });
});

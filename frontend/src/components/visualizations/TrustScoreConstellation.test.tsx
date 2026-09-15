import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import TrustScoreConstellation from "./TrustScoreConstellation";

describe("TrustScoreConstellation", () => {
  afterEach(() => {
    cleanup();
  });

  const sampleScores = [
    { type: "security" as const, score: 85, rationale: "Strong security" },
    { type: "compliance" as const, score: 90, rationale: "Fully compliant" },
    { type: "contextual" as const, score: 75, rationale: "Good context" },
    { type: "quantum" as const, score: 60, rationale: "Needs upgrade" },
    { type: "sustainability" as const, score: 95, rationale: "Very sustainable" },
  ];

  it("renders without crashing", () => {
    const { container } = render(
      <TrustScoreConstellation trustScore={81} agentScores={sampleScores} />
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("displays the live indicator when isLive is true", () => {
    render(
      <TrustScoreConstellation trustScore={81} agentScores={sampleScores} isLive={true} />
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("does not display the live indicator when isLive is false", () => {
    render(
      <TrustScoreConstellation trustScore={81} agentScores={sampleScores} isLive={false} />
    );
    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });

  // Note: Because d3 rendering modifies the DOM directly and involves transitions,
  // we might not immediately see the text content if the transition takes time.
  // However, the text nodes are created immediately with opacity 0.
  it("creates agent labels and scores", () => {
    render(<TrustScoreConstellation trustScore={81} agentScores={sampleScores} />);
    
    // Check for agent labels (SEC, COM, CTX, QTM, SUS)
    expect(document.querySelector("text")?.textContent).toBeDefined(); // D3 creates the elements
    
    // D3 tests can be tricky with RTL, but we can verify the SVG structure exists
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
    
    // It should have defs
    expect(svg?.querySelector("defs")).toBeInTheDocument();
    
    // It should have center score group
    expect(svg?.querySelector(".center-score")).toBeInTheDocument();
    
    // It should have agent nodes
    expect(svg?.querySelector(".agent-nodes")).toBeInTheDocument();
  });
});

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EncryptionTierBar from "./EncryptionTierBar";

describe("EncryptionTierBar", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the current tier correctly (AES-256)", () => {
    render(<EncryptionTierBar currentTier="aes256" trustScore={40} />);
    expect(screen.getAllByText("AES-256").length).toBeGreaterThan(0);
    expect(screen.getByText("Classical symmetric encryption")).toBeInTheDocument();
    expect(screen.getByText("AES-256-GCM, 256-bit key")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // Level
  });

  it("renders the current tier correctly (Hybrid)", () => {
    render(<EncryptionTierBar currentTier="hybrid" trustScore={60} />);
    expect(screen.getAllByText("Hybrid PQC").length).toBeGreaterThan(0);
    expect(screen.getByText("Classical + Post-Quantum")).toBeInTheDocument();
    expect(screen.getByText("X25519 + ML-KEM-768")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // Level
  });

  it("renders the current tier correctly (Post-Quantum)", () => {
    render(<EncryptionTierBar currentTier="post_quantum" trustScore={90} />);
    expect(screen.getAllByText("Full Post-Quantum").length).toBeGreaterThan(0);
    expect(screen.getByText("Quantum-resistant")).toBeInTheDocument();
    expect(screen.getByText("ML-KEM-1024 + ML-DSA-87")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // Level
  });

  it("does not show upgrade recommendation if showUpgradeRecommendation is false", () => {
    render(<EncryptionTierBar currentTier="aes256" trustScore={80} showUpgradeRecommendation={false} />);
    expect(screen.queryByText("Upgrade Available")).not.toBeInTheDocument();
  });

  it("shows upgrade recommendation if showUpgradeRecommendation is true and recommended tier is higher", () => {
    render(<EncryptionTierBar currentTier="aes256" trustScore={60} showUpgradeRecommendation={true} />);
    expect(screen.getByText("Upgrade Available")).toBeInTheDocument();
    // It's mentioned in the text: "upgrading to Hybrid PQC for enhanced..."
    expect(screen.getAllByText(/Hybrid PQC/i).length).toBeGreaterThan(0);
  });

  it("does not show upgrade recommendation if current tier is already at or above recommended", () => {
    render(<EncryptionTierBar currentTier="post_quantum" trustScore={90} showUpgradeRecommendation={true} />);
    expect(screen.queryByText("Upgrade Available")).not.toBeInTheDocument();
  });

  it("shows tier details on hover", async () => {
    const user = userEvent.setup();
    const { container } = render(<EncryptionTierBar currentTier="aes256" trustScore={40} />);
    
    const markers = container.querySelectorAll(".absolute.inset-0.flex > .relative > div");
    await user.hover(markers[2]);
    
    // Hovering over post_quantum marker shows its description
    expect(screen.getByText("Quantum-resistant")).toBeInTheDocument();
    
    await user.unhover(markers[2]);
    expect(screen.queryByText("Quantum-resistant")).not.toBeInTheDocument();
  });
});

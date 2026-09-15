import { describe, expect, it } from "vitest";
import {
  MOCK_AGENT_OUTPUTS,
  MOCK_AUDIT_DOCUMENT_ID,
  MOCK_AUDIT_LOG,
  MOCK_CLASSIFICATIONS,
  MOCK_CRYPTO_PROFILES,
  MOCK_DOCUMENTS,
  MOCK_MIGRATION_SCHEDULE,
  MOCK_OVERRIDES,
  MOCK_POLICY_DECISIONS,
  MOCK_POLICY_RULES,
  MOCK_RISK_SCORES,
  MOCK_TRUST_SCORES,
} from "./mock-data";

const HEX_64 = /^[0-9a-f]{64}$/;

describe("mock data fixtures", () => {
  it("exports the expected fixture counts", () => {
    expect(MOCK_DOCUMENTS).toHaveLength(8);
    expect(MOCK_CLASSIFICATIONS).toHaveLength(8);
    expect(MOCK_RISK_SCORES).toHaveLength(6);
    expect(MOCK_AGENT_OUTPUTS).toHaveLength(30);
    expect(MOCK_TRUST_SCORES).toHaveLength(6);
    expect(MOCK_POLICY_RULES).toHaveLength(4);
    expect(MOCK_POLICY_DECISIONS).toHaveLength(6);
    expect(MOCK_CRYPTO_PROFILES).toHaveLength(6);
    expect(MOCK_AUDIT_LOG).toHaveLength(15);
    expect(MOCK_OVERRIDES).toHaveLength(2);
    expect(MOCK_MIGRATION_SCHEDULE).toHaveLength(6);
  });

  it("contains five ordered agent outputs for every risk assessment", () => {
    const expectedTypes = [
      "security",
      "compliance",
      "contextual",
      "quantum",
      "sustainability",
    ];

    MOCK_RISK_SCORES.forEach((_, index) => {
      const outputs = MOCK_AGENT_OUTPUTS.slice(index * 5, index * 5 + 5);
      expect(outputs.map((output) => output.agent_type)).toEqual(expectedTypes);
      outputs.forEach((output) => {
        expect(output.score).toBeGreaterThanOrEqual(0);
        expect(output.score).toBeLessThanOrEqual(1);
        expect(output.rationale.trim().length).toBeGreaterThan(0);
      });
    });
  });

  it("covers all crypto profiles and fail-safe classifications", () => {
    expect(MOCK_CRYPTO_PROFILES.map(({ profile_type }) => profile_type).sort()).toEqual([
      "aes256",
      "hybrid",
      "hybrid",
      "hybrid",
      "post_quantum",
      "post_quantum",
    ]);
    expect(
      MOCK_CLASSIFICATIONS.some((classification) => classification.is_defaulted),
    ).toBe(true);
  });

  it("uses valid manual-override justifications and changed labels", () => {
    MOCK_OVERRIDES.forEach((override) => {
      expect(override.justification.length).toBeGreaterThan(20);
      expect(override.new_label).not.toBe(override.original_label);
    });
  });

  it("forms one contiguous audit chain with valid hashes", () => {
    expect(MOCK_AUDIT_DOCUMENT_ID).toBe(MOCK_DOCUMENTS[0]?.id);
    expect(MOCK_AUDIT_LOG[0]?.prev_hash).toBeNull();

    MOCK_AUDIT_LOG.forEach((entry, index) => {
      expect(entry.index).toBe(index);
      expect(entry.payload_hash).toMatch(HEX_64);
      expect(entry.merkle_root_at_time).toMatch(HEX_64);
      if (entry.prev_hash !== null) {
        expect(entry.prev_hash).toMatch(HEX_64);
      }
      if (index > 0) {
        expect(entry.prev_hash).toBe(MOCK_AUDIT_LOG[index - 1]?.payload_hash);
      }
    });
  });

  it("orders the migration queue with positive ranks", () => {
    expect(
      MOCK_MIGRATION_SCHEDULE.map((entry) => entry.priority_rank),
    ).toEqual([1, 2, 3, 4, 5, 6]);
  });
});

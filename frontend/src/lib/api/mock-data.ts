/**
 * Deterministic mock data for Q-AEGIS Shield frontend development.
 *
 * These fixtures let UI work proceed before backend integration. They use
 * realistic cybersecurity terminology, cryptographic parameters, and precise
 * scores. They are not production data and must not be mistaken for live
 * audit records.
 */

import type {
  AgentOutputResponse,
  AuditEntry,
  ClassificationResponse,
  CryptoProfileResponse,
  DocumentResponse,
  ManualOverrideResponse,
  MigrationScheduleEntry,
  PolicyDecisionResponse,
  PolicyRuleResponse,
  RiskScoreResponse,
  TrustScoreResponse,
} from "./types";

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export const MOCK_DOCUMENTS: DocumentResponse[] = [
  {
    id: "123e4567-e89b-12d3-a456-426614174001",
    filename: "quantum-migration-roadmap.pdf",
    storage_path: null,
    current_status: "protected",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174001",
    uploaded_at: "2026-09-01T08:12:44Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174002",
    filename: "vendor-risk-assessment-q3.xlsx",
    storage_path: null,
    current_status: "classified",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174002",
    uploaded_at: "2026-09-02T10:04:19Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174003",
    filename: "employee-access-review-august.docx",
    storage_path: null,
    current_status: "classified",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174003",
    uploaded_at: "2026-09-03T14:27:51Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174004",
    filename: "public-security-whitepaper.pdf",
    storage_path: null,
    current_status: "registered",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174004",
    uploaded_at: "2026-09-04T09:41:07Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174005",
    filename: "merkle-audit-export-september.txt",
    storage_path: null,
    current_status: "protected",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174005",
    uploaded_at: "2026-09-05T11:18:33Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174006",
    filename: "incident-response-playbook.docx",
    storage_path: null,
    current_status: "classified",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174006",
    uploaded_at: "2026-09-06T13:52:20Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174007",
    filename: "internal-network-inventory.xlsx",
    storage_path: null,
    current_status: "registered",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174007",
    uploaded_at: "2026-09-07T15:09:48Z",
  },
  {
    id: "123e4567-e89b-12d3-a456-426614174008",
    filename: "board-meeting-minutes-september.pdf",
    storage_path: null,
    current_status: "registered",
    uploaded_by: "223e4567-e89b-12d3-a456-426614174008",
    uploaded_at: "2026-09-08T09:25:12Z",
  },
];

// ---------------------------------------------------------------------------
// Classifications
// ---------------------------------------------------------------------------

export const MOCK_CLASSIFICATIONS: ClassificationResponse[] = [
  {
    document_id: "123e4567-e89b-12d3-a456-426614174001",
    sensitivity_label: "RESTRICTED",
    confidence: 0.9147,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: false,
    base_label: "RESTRICTED",
    confidence_threshold: 0.75,
    matched_keywords: ["restricted", "private key", "quantum migration"],
    rationale:
      "Keyword rules identified restricted migration and private-key material.",
    classified_at: "2026-09-01T08:13:02Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174002",
    sensitivity_label: "CONFIDENTIAL",
    confidence: 0.8542,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: false,
    base_label: "CONFIDENTIAL",
    confidence_threshold: 0.75,
    matched_keywords: ["confidential", "vendor assessment", "risk score"],
    rationale:
      "Keyword rules identified confidential third-party risk assessment content.",
    classified_at: "2026-09-02T10:05:11Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174003",
    sensitivity_label: "INTERNAL",
    confidence: 0.4128,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: true,
    base_label: "PUBLIC",
    confidence_threshold: 0.75,
    matched_keywords: ["employee", "access review"],
    rationale:
      "Confidence fell below the threshold, so the fail-safe applied the more sensitive label.",
    classified_at: "2026-09-03T14:28:37Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174004",
    sensitivity_label: "PUBLIC",
    confidence: 0.9231,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: false,
    base_label: "PUBLIC",
    confidence_threshold: 0.75,
    matched_keywords: ["public", "whitepaper"],
    rationale: "Keyword rules identified intentionally published security material.",
    classified_at: "2026-09-04T09:42:01Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174005",
    sensitivity_label: "RESTRICTED",
    confidence: 0.6812,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: true,
    base_label: "CONFIDENTIAL",
    confidence_threshold: 0.75,
    matched_keywords: ["audit export", "merkle root", "restricted"],
    rationale:
      "Confidence fell below the threshold, so the fail-safe applied the more sensitive label.",
    classified_at: "2026-09-05T11:19:24Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174006",
    sensitivity_label: "CONFIDENTIAL",
    confidence: 0.7894,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: false,
    base_label: "CONFIDENTIAL",
    confidence_threshold: 0.75,
    matched_keywords: ["incident response", "containment", "confidential"],
    rationale:
      "Keyword rules identified confidential incident-response procedures.",
    classified_at: "2026-09-06T13:53:12Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174007",
    sensitivity_label: "INTERNAL",
    confidence: 0.8073,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: false,
    base_label: "INTERNAL",
    confidence_threshold: 0.75,
    matched_keywords: ["internal", "network inventory"],
    rationale: "Keyword rules identified internal infrastructure inventory data.",
    classified_at: "2026-09-07T15:10:39Z",
  },
  {
    document_id: "123e4567-e89b-12d3-a456-426614174008",
    sensitivity_label: "PUBLIC",
    confidence: 0.9577,
    model_version: "stub-keyword-rules-0.1.0",
    is_defaulted: false,
    base_label: "PUBLIC",
    confidence_threshold: 0.75,
    matched_keywords: ["board minutes", "published"],
    rationale: "Keyword rules identified non-sensitive published meeting material.",
    classified_at: "2026-09-08T09:26:04Z",
  },
];

// ---------------------------------------------------------------------------
// Contextual risk scores
// ---------------------------------------------------------------------------

export const MOCK_RISK_SCORES: RiskScoreResponse[] = [
  {
    id: "323e4567-e89b-12d3-a456-426614174001",
    document_id: "123e4567-e89b-12d3-a456-426614174001",
    risk_value: "0.8",
    model_version: "contextual-risk-additive-0.1.0",
    context_snapshot: {
      actor_user_id: "223e4567-e89b-12d3-a456-426614174001",
      device_id: "SEC-LAPTOP-0142",
      device_is_new: true,
      accessed_at: "2026-09-09T02:14:00Z",
      after_hours: true,
    },
    computed_at: "2026-09-09T02:14:31Z",
  },
  {
    id: "323e4567-e89b-12d3-a456-426614174002",
    document_id: "123e4567-e89b-12d3-a456-426614174002",
    risk_value: "0.55",
    model_version: "contextual-risk-additive-0.1.0",
    context_snapshot: {
      actor_user_id: "223e4567-e89b-12d3-a456-426614174002",
      device_id: "SEC-WORKSTATION-007",
      device_is_new: true,
      accessed_at: "2026-09-09T10:42:00Z",
      after_hours: false,
    },
    computed_at: "2026-09-09T10:42:18Z",
  },
  {
    id: "323e4567-e89b-12d3-a456-426614174003",
    document_id: "123e4567-e89b-12d3-a456-426614174003",
    risk_value: "0.2",
    model_version: "contextual-risk-additive-0.1.0",
    context_snapshot: {
      actor_user_id: "223e4567-e89b-12d3-a456-426614174003",
      device_id: "HR-WORKSTATION-112",
      device_is_new: false,
      accessed_at: "2026-09-09T15:03:00Z",
      after_hours: false,
    },
    computed_at: "2026-09-09T15:03:49Z",
  },
  {
    id: "323e4567-e89b-12d3-a456-426614174004",
    document_id: "123e4567-e89b-12d3-a456-426614174004",
    risk_value: "0.725",
    model_version: "contextual-risk-additive-0.1.0",
    context_snapshot: {
      actor_user_id: "223e4567-e89b-12d3-a456-426614174004",
      device_id: "COMPLIANCE-LAPTOP-033",
      device_is_new: true,
      accessed_at: "2026-09-09T23:18:00Z",
      after_hours: true,
    },
    computed_at: "2026-09-09T23:18:55Z",
  },
  {
    id: "323e4567-e89b-12d3-a456-426614174005",
    document_id: "123e4567-e89b-12d3-a456-426614174005",
    risk_value: "0.475",
    model_version: "contextual-risk-additive-0.1.0",
    context_snapshot: {
      actor_user_id: "223e4567-e89b-12d3-a456-426614174005",
      device_id: "AUDIT-WORKSTATION-021",
      device_is_new: false,
      accessed_at: "2026-09-10T01:47:00Z",
      after_hours: true,
    },
    computed_at: "2026-09-10T01:47:26Z",
  },
  {
    id: "323e4567-e89b-12d3-a456-426614174006",
    document_id: "123e4567-e89b-12d3-a456-426614174006",
    risk_value: "0.275",
    model_version: "contextual-risk-additive-0.1.0",
    context_snapshot: {
      actor_user_id: "223e4567-e89b-12d3-a456-426614174006",
      device_id: "SOC-WORKSTATION-009",
      device_is_new: false,
      accessed_at: "2026-09-10T09:12:00Z",
      after_hours: false,
    },
    computed_at: "2026-09-10T09:12:43Z",
  },
];

// ---------------------------------------------------------------------------
// Agent outputs
// ---------------------------------------------------------------------------

const RISK_1_AGENT_OUTPUTS: AgentOutputResponse[] = [
  {
    id: "423e4567-e89b-12d3-a456-426614174011",
    agent_type: "security",
    score: "0.185",
    rationale: "After-hours access from an unrecognized device elevated compromise risk.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174012",
    agent_type: "compliance",
    score: "0.245",
    rationale: "Restricted migration material requires heightened handling controls.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174013",
    agent_type: "contextual",
    score: "0.23",
    rationale: "New device and overnight access increased contextual exposure.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174014",
    agent_type: "quantum",
    score: "0.21",
    rationale: "Long-lived restricted data is exposed to harvest-now-decrypt-later collection.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174015",
    agent_type: "sustainability",
    score: "0.24",
    rationale: "Frequent re-encryption would impose unnecessary operational overhead.",
  },
];

const RISK_2_AGENT_OUTPUTS: AgentOutputResponse[] = [
  {
    id: "423e4567-e89b-12d3-a456-426614174021",
    agent_type: "security",
    score: "0.72",
    rationale: "Known workstation and business-hours access indicate normal handling.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174022",
    agent_type: "compliance",
    score: "0.61",
    rationale: "Vendor assessment contains contractual obligations but no key material.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174023",
    agent_type: "contextual",
    score: "0.68",
    rationale: "A new endpoint was observed, although access timing remains routine.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174024",
    agent_type: "quantum",
    score: "0.59",
    rationale: "Three-year retention creates moderate quantum-archive exposure.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174025",
    agent_type: "sustainability",
    score: "0.665",
    rationale: "Hybrid protection would balance longevity against operational cost.",
  },
];

const RISK_3_AGENT_OUTPUTS: AgentOutputResponse[] = [
  {
    id: "423e4567-e89b-12d3-a456-426614174031",
    agent_type: "security",
    score: "0.86",
    rationale: "Known HR workstation and routine access indicate low compromise risk.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174032",
    agent_type: "compliance",
    score: "0.83",
    rationale: "Internal review data has limited regulatory handling requirements.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174033",
    agent_type: "contextual",
    score: "0.845",
    rationale: "No anomalous device, location, or timing signals were observed.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174034",
    agent_type: "quantum",
    score: "0.835",
    rationale: "Short retention and low secrecy reduce archive-decryption exposure.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174035",
    agent_type: "sustainability",
    score: "0.84",
    rationale: "Classical protection remains proportionate to operational impact.",
  },
];

const RISK_4_AGENT_OUTPUTS: AgentOutputResponse[] = [
  {
    id: "423e4567-e89b-12d3-a456-426614174041",
    agent_type: "security",
    score: "0.42",
    rationale: "Overnight access from a new compliance endpoint warrants caution.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174042",
    agent_type: "compliance",
    score: "0.39",
    rationale: "Audit material may support regulatory review and must remain intact.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174043",
    agent_type: "contextual",
    score: "0.405",
    rationale: "The device is new, although the authenticated role is authorized.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174044",
    agent_type: "quantum",
    score: "0.385",
    rationale: "Long audit retention increases exposure to future decryption.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174045",
    agent_type: "sustainability",
    score: "0.39",
    rationale: "Stronger protection is justified despite higher migration effort.",
  },
];

const RISK_5_AGENT_OUTPUTS: AgentOutputResponse[] = [
  {
    id: "423e4567-e89b-12d3-a456-426614174051",
    agent_type: "security",
    score: "0.76",
    rationale: "Known audit workstation reduces endpoint-compromise likelihood.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174052",
    agent_type: "compliance",
    score: "0.755",
    rationale: "Overnight handling is documented, though outside routine review hours.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174053",
    agent_type: "contextual",
    score: "0.745",
    rationale: "After-hours access is the only elevated contextual signal.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174054",
    agent_type: "quantum",
    score: "0.765",
    rationale: "Export has a limited operational lifetime and modest secrecy needs.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174055",
    agent_type: "sustainability",
    score: "0.755",
    rationale: "Hybrid controls provide adequate durability without excess cost.",
  },
];

const RISK_6_AGENT_OUTPUTS: AgentOutputResponse[] = [
  {
    id: "423e4567-e89b-12d3-a456-426614174061",
    agent_type: "security",
    score: "0.53",
    rationale: "SOC workstation and normal hours indicate controlled handling.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174062",
    agent_type: "compliance",
    score: "0.51",
    rationale: "Playbook data has operational sensitivity but limited external exposure.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174063",
    agent_type: "contextual",
    score: "0.495",
    rationale: "Context is routine, with no new device or timing anomaly.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174064",
    agent_type: "quantum",
    score: "0.525",
    rationale: "Response procedures may remain useful beyond current algorithms.",
  },
  {
    id: "423e4567-e89b-12d3-a456-426614174065",
    agent_type: "sustainability",
    score: "0.5",
    rationale: "Hybrid protection aligns with periodic playbook updates.",
  },
];

export const MOCK_AGENT_OUTPUTS: AgentOutputResponse[] = [
  ...RISK_1_AGENT_OUTPUTS,
  ...RISK_2_AGENT_OUTPUTS,
  ...RISK_3_AGENT_OUTPUTS,
  ...RISK_4_AGENT_OUTPUTS,
  ...RISK_5_AGENT_OUTPUTS,
  ...RISK_6_AGENT_OUTPUTS,
];

// ---------------------------------------------------------------------------
// Trust scores
// ---------------------------------------------------------------------------

export const MOCK_TRUST_SCORES: TrustScoreResponse[] = [
  {
    id: "523e4567-e89b-12d3-a456-426614174001",
    document_id: "123e4567-e89b-12d3-a456-426614174001",
    risk_score_id: "323e4567-e89b-12d3-a456-426614174001",
    consensus_value: "0.222",
    consensus_version: "trust-weighted-mean-0.1.0",
    outputs: RISK_1_AGENT_OUTPUTS,
    computed_at: "2026-09-09T02:15:02Z",
  },
  {
    id: "523e4567-e89b-12d3-a456-426614174002",
    document_id: "123e4567-e89b-12d3-a456-426614174002",
    risk_score_id: "323e4567-e89b-12d3-a456-426614174002",
    consensus_value: "0.653",
    consensus_version: "trust-weighted-mean-0.1.0",
    outputs: RISK_2_AGENT_OUTPUTS,
    computed_at: "2026-09-09T10:43:11Z",
  },
  {
    id: "523e4567-e89b-12d3-a456-426614174003",
    document_id: "123e4567-e89b-12d3-a456-426614174003",
    risk_score_id: "323e4567-e89b-12d3-a456-426614174003",
    consensus_value: "0.842",
    consensus_version: "trust-weighted-mean-0.1.0",
    outputs: RISK_3_AGENT_OUTPUTS,
    computed_at: "2026-09-09T15:04:27Z",
  },
  {
    id: "523e4567-e89b-12d3-a456-426614174004",
    document_id: "123e4567-e89b-12d3-a456-426614174004",
    risk_score_id: "323e4567-e89b-12d3-a456-426614174004",
    consensus_value: "0.398",
    consensus_version: "trust-weighted-mean-0.1.0",
    outputs: RISK_4_AGENT_OUTPUTS,
    computed_at: "2026-09-09T23:19:41Z",
  },
  {
    id: "523e4567-e89b-12d3-a456-426614174005",
    document_id: "123e4567-e89b-12d3-a456-426614174005",
    risk_score_id: "323e4567-e89b-12d3-a456-426614174005",
    consensus_value: "0.756",
    consensus_version: "trust-weighted-mean-0.1.0",
    outputs: RISK_5_AGENT_OUTPUTS,
    computed_at: "2026-09-10T01:48:03Z",
  },
  {
    id: "523e4567-e89b-12d3-a456-426614174006",
    document_id: "123e4567-e89b-12d3-a456-426614174006",
    risk_score_id: "323e4567-e89b-12d3-a456-426614174006",
    consensus_value: "0.512",
    consensus_version: "trust-weighted-mean-0.1.0",
    outputs: RISK_6_AGENT_OUTPUTS,
    computed_at: "2026-09-10T09:13:29Z",
  },
];

// ---------------------------------------------------------------------------
// Policy rules and decisions
// ---------------------------------------------------------------------------

export const MOCK_POLICY_RULES: PolicyRuleResponse[] = [
  {
    id: "623e4567-e89b-12d3-a456-426614174001",
    rule_name: "Force PQC for confidential material",
    condition_expr: {
      all: [
        { field: "sensitivity_label", op: "eq", value: "CONFIDENTIAL" },
        { field: "trust_score", op: "lt", value: 0.45 },
      ],
    },
    action: "force_pqc",
    priority: 1,
    active: true,
    created_at: "2026-09-05T12:00:00Z",
  },
  {
    id: "623e4567-e89b-12d3-a456-426614174002",
    rule_name: "Deny elevated after-hours risk",
    condition_expr: {
      all: [
        { field: "risk_value", op: "gte", value: 0.75 },
        { field: "trust_score", op: "lt", value: 0.4 },
      ],
    },
    action: "deny",
    priority: 2,
    active: true,
    created_at: "2026-09-05T12:15:00Z",
  },
  {
    id: "623e4567-e89b-12d3-a456-426614174003",
    rule_name: "Require MFA for restricted documents",
    condition_expr: {
      field: "sensitivity_label",
      op: "eq",
      value: "RESTRICTED",
    },
    action: "require_mfa",
    priority: 3,
    active: true,
    created_at: "2026-09-05T12:30:00Z",
  },
  {
    id: "623e4567-e89b-12d3-a456-426614174004",
    rule_name: "Allow low-risk public or internal handling",
    condition_expr: {
      all: [
        {
          field: "sensitivity_label",
          op: "in",
          value: ["PUBLIC", "INTERNAL"],
        },
        { field: "risk_value", op: "lte", value: 0.3 },
      ],
    },
    action: "allow",
    priority: 10,
    active: true,
    created_at: "2026-09-05T12:45:00Z",
  },
];

export const MOCK_POLICY_DECISIONS: PolicyDecisionResponse[] = [
  {
    id: "723e4567-e89b-12d3-a456-426614174001",
    document_id: "123e4567-e89b-12d3-a456-426614174001",
     trust_score_id: "523e4567-e89b-12d3-a456-426614174001",
     risk_score_id: "323e4567-e89b-12d3-a456-426614174001",
     classification_id: "133e4567-e89b-12d3-a456-426614174001",
     override_id: null,
     label_source: "classification",
     sensitivity_label: "RESTRICTED",
     risk_value: "0.8",
     trust_score: "0.222",
    rule_id: "623e4567-e89b-12d3-a456-426614174003",
    rule_name: "Require MFA for restricted documents",
    ai_recommendation: "allow",
    final_decision: "require_mfa",
    overridden: true,
    policy_version: "policy-first-match-0.1.0",
    decided_at: "2026-09-09T02:15:48Z",
  },
  {
    id: "723e4567-e89b-12d3-a456-426614174002",
    document_id: "123e4567-e89b-12d3-a456-426614174002",
     trust_score_id: "523e4567-e89b-12d3-a456-426614174002",
     risk_score_id: "323e4567-e89b-12d3-a456-426614174002",
     classification_id: "133e4567-e89b-12d3-a456-426614174002",
     override_id: null,
     label_source: "classification",
     sensitivity_label: "CONFIDENTIAL",
     risk_value: "0.55",
     trust_score: "0.653",
    rule_id: null,
    rule_name: null,
    ai_recommendation: "allow",
    final_decision: "allow",
    overridden: false,
    policy_version: "policy-first-match-0.1.0",
    decided_at: "2026-09-09T10:43:57Z",
  },
  {
    id: "723e4567-e89b-12d3-a456-426614174003",
    document_id: "123e4567-e89b-12d3-a456-426614174003",
     trust_score_id: "523e4567-e89b-12d3-a456-426614174003",
     risk_score_id: "323e4567-e89b-12d3-a456-426614174003",
     classification_id: "133e4567-e89b-12d3-a456-426614174003",
     override_id: null,
     label_source: "classification",
     sensitivity_label: "INTERNAL",
     risk_value: "0.2",
     trust_score: "0.842",
    rule_id: "623e4567-e89b-12d3-a456-426614174004",
    rule_name: "Allow low-risk public or internal handling",
    ai_recommendation: "allow",
    final_decision: "allow",
    overridden: false,
    policy_version: "policy-first-match-0.1.0",
    decided_at: "2026-09-09T15:05:13Z",
  },
  {
    id: "723e4567-e89b-12d3-a456-426614174004",
    document_id: "123e4567-e89b-12d3-a456-426614174004",
     trust_score_id: "523e4567-e89b-12d3-a456-426614174004",
     risk_score_id: "323e4567-e89b-12d3-a456-426614174004",
     classification_id: "133e4567-e89b-12d3-a456-426614174004",
     override_id: null,
     label_source: "classification",
     sensitivity_label: "PUBLIC",
     risk_value: "0.725",
     trust_score: "0.398",
    rule_id: null,
    rule_name: null,
    ai_recommendation: "allow",
    final_decision: "allow",
    overridden: false,
    policy_version: "policy-first-match-0.1.0",
    decided_at: "2026-09-09T23:20:29Z",
  },
  {
    id: "723e4567-e89b-12d3-a456-426614174005",
    document_id: "123e4567-e89b-12d3-a456-426614174005",
     trust_score_id: "523e4567-e89b-12d3-a456-426614174005",
     risk_score_id: "323e4567-e89b-12d3-a456-426614174005",
     classification_id: "133e4567-e89b-12d3-a456-426614174005",
     override_id: null,
     label_source: "classification",
     sensitivity_label: "RESTRICTED",
     risk_value: "0.475",
     trust_score: "0.756",
    rule_id: "623e4567-e89b-12d3-a456-426614174001",
    rule_name: "Force PQC for confidential material",
    ai_recommendation: "require_mfa",
    final_decision: "force_pqc",
    overridden: true,
    policy_version: "policy-first-match-0.1.0",
    decided_at: "2026-09-10T01:48:51Z",
  },
  {
    id: "723e4567-e89b-12d3-a456-426614174006",
    document_id: "123e4567-e89b-12d3-a456-426614174006",
     trust_score_id: "523e4567-e89b-12d3-a456-426614174006",
     risk_score_id: "323e4567-e89b-12d3-a456-426614174006",
     classification_id: "133e4567-e89b-12d3-a456-426614174006",
     override_id: null,
     label_source: "classification",
     sensitivity_label: "CONFIDENTIAL",
     risk_value: "0.275",
     trust_score: "0.512",
    rule_id: null,
    rule_name: null,
    ai_recommendation: "allow",
    final_decision: "allow",
    overridden: false,
    policy_version: "policy-first-match-0.1.0",
    decided_at: "2026-09-10T09:14:17Z",
  },
];

// ---------------------------------------------------------------------------
// Crypto profiles
// ---------------------------------------------------------------------------

export const MOCK_CRYPTO_PROFILES: CryptoProfileResponse[] = [
  {
    id: "823e4567-e89b-12d3-a456-426614174001",
    document_id: "123e4567-e89b-12d3-a456-426614174001",
    trust_score_id: "523e4567-e89b-12d3-a456-426614174001",
    profile_type: "post_quantum",
    consensus_value: "0.222",
    selected_at: "2026-09-09T02:16:34Z",
  },
  {
    id: "823e4567-e89b-12d3-a456-426614174002",
    document_id: "123e4567-e89b-12d3-a456-426614174002",
    trust_score_id: "523e4567-e89b-12d3-a456-426614174002",
    profile_type: "hybrid",
    consensus_value: "0.653",
    selected_at: "2026-09-09T10:44:42Z",
  },
  {
    id: "823e4567-e89b-12d3-a456-426614174003",
    document_id: "123e4567-e89b-12d3-a456-426614174003",
    trust_score_id: "523e4567-e89b-12d3-a456-426614174003",
    profile_type: "aes256",
    consensus_value: "0.842",
    selected_at: "2026-09-09T15:06:08Z",
  },
  {
    id: "823e4567-e89b-12d3-a456-426614174004",
    document_id: "123e4567-e89b-12d3-a456-426614174004",
    trust_score_id: "523e4567-e89b-12d3-a456-426614174004",
    profile_type: "post_quantum",
    consensus_value: "0.398",
    selected_at: "2026-09-09T23:21:15Z",
  },
  {
    id: "823e4567-e89b-12d3-a456-426614174005",
    document_id: "123e4567-e89b-12d3-a456-426614174005",
    trust_score_id: "523e4567-e89b-12d3-a456-426614174005",
    profile_type: "hybrid",
    consensus_value: "0.756",
    selected_at: "2026-09-10T01:49:37Z",
  },
  {
    id: "823e4567-e89b-12d3-a456-426614174006",
    document_id: "123e4567-e89b-12d3-a456-426614174006",
    trust_score_id: "523e4567-e89b-12d3-a456-426614174006",
    profile_type: "hybrid",
    consensus_value: "0.512",
    selected_at: "2026-09-10T09:15:03Z",
  },
];

// ---------------------------------------------------------------------------
// Manual overrides
// ---------------------------------------------------------------------------

export const MOCK_OVERRIDES: ManualOverrideResponse[] = [
  {
    id: "923e4567-e89b-12d3-a456-426614174001",
    document_id: "123e4567-e89b-12d3-a456-426614174003",
    overridden_by: "223e4567-e89b-12d3-a456-426614174003",
    original_label: "PUBLIC",
    new_label: "INTERNAL",
    justification:
      "Access review contains employee identifiers that require internal handling and audit retention.",
    overridden_at: "2026-09-06T16:24:10Z",
  },
  {
    id: "923e4567-e89b-12d3-a456-426614174002",
    document_id: "123e4567-e89b-12d3-a456-426614174005",
    overridden_by: "223e4567-e89b-12d3-a456-426614174005",
    original_label: "CONFIDENTIAL",
    new_label: "RESTRICTED",
    justification:
      "Exported Merkle evidence exposes chain metadata covered by restricted audit-handling controls.",
    overridden_at: "2026-09-07T10:08:52Z",
  },
];

// ---------------------------------------------------------------------------
// Audit log chain for the quantum-migration roadmap
//
// Mirrors GET /api/v1/audit/entries: entries carry their chain index, not
// the document id (the chain is fetched per document) and no frontier (the
// backend omits write-path Merkle state from the read surface).
// ---------------------------------------------------------------------------

export const MOCK_AUDIT_DOCUMENT_ID = "123e4567-e89b-12d3-a456-426614174001";

const MOCK_AUDIT_CHAIN: Array<Omit<AuditEntry, "index">> = [
  {
    id: "a23e4567-e89b-12d3-a456-426614174001",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "document_registered",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      filename: "quantum-migration-roadmap.pdf",
      current_status: "registered",
    },
    payload_hash:
      "297393270da84eab002c85ac1cc8aa11e0448736f4766aaad799345de664b5cc",
    prev_hash: null,
    merkle_root_at_time:
      "c19ec7a7a17a5a28ae024ca56987ae089ee6592531749aa23ddcf991ef4a3614",
    created_at: "2026-09-01T08:12:44Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174002",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "classification_completed",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      sensitivity_label: "RESTRICTED",
      confidence: 0.9147,
      model_version: "stub-keyword-rules-0.1.0",
      is_defaulted: false,
    },
    payload_hash:
      "dd689f4dbe2e9401a2ee4dab1dcfc0ee7b98a007c333272a806e4a687951c004",
    prev_hash:
      "297393270da84eab002c85ac1cc8aa11e0448736f4766aaad799345de664b5cc",
    merkle_root_at_time:
      "01864f65d6faeb524a16f2f6b7de259d9484818f69b8f5f376fbb4995a14d37f",
    created_at: "2026-09-01T08:13:02Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174003",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "risk_score_computed",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      risk_score_id: "323e4567-e89b-12d3-a456-426614174001",
      risk_value: 0.8,
      device_id: "SEC-LAPTOP-0142",
      device_is_new: true,
      after_hours: true,
    },
    payload_hash:
      "2f1a15603b9bd058b4e2ba29084e3360584f9f03386c6583e3e097812815901d",
    prev_hash:
      "dd689f4dbe2e9401a2ee4dab1dcfc0ee7b98a007c333272a806e4a687951c004",
    merkle_root_at_time:
      "b5d34751dde4334191049721318ba0e74c53d103b506e3d7eed38c8803235e1e",
    created_at: "2026-09-09T02:14:31Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174004",
    actor_id: null,
    event_type: "trust_score_updated",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      trust_score_id: "523e4567-e89b-12d3-a456-426614174001",
      consensus_value: 0.222,
      consensus_version: "trust-weighted-mean-0.1.0",
    },
    payload_hash:
      "129e464002175dadfd3602a042d57579647ada37133fcb122c20333f15ca00e8",
    prev_hash:
      "2f1a15603b9bd058b4e2ba29084e3360584f9f03386c6583e3e097812815901d",
    merkle_root_at_time:
      "a4d6fd7bfd8f09c7eabb94c8f5e4af192a55121a3bb6f5d3ea197825e1c67b90",
    created_at: "2026-09-09T02:15:02Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174005",
    actor_id: null,
    event_type: "policy_decision_recorded",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      decision_id: "723e4567-e89b-12d3-a456-426614174001",
      rule_id: "623e4567-e89b-12d3-a456-426614174003",
      ai_recommendation: "allow",
      final_decision: "require_mfa",
      overridden: true,
    },
    payload_hash:
      "453754e777c0ca9154ad70f054e5d00d2e562133ccadb157ca8f6d5a44deb80f",
    prev_hash:
      "129e464002175dadfd3602a042d57579647ada37133fcb122c20333f15ca00e8",
    merkle_root_at_time:
      "5d313a472044c80f6926d45228da78b05fd217cd4e2befd78d3d9890eddc513e",
    created_at: "2026-09-09T02:15:48Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174006",
    actor_id: null,
    event_type: "crypto_profile_selected",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      crypto_profile_id: "823e4567-e89b-12d3-a456-426614174001",
      trust_score_id: "523e4567-e89b-12d3-a456-426614174001",
      profile_type: "post_quantum",
      consensus_value: 0.222,
    },
    payload_hash:
      "f9fac51b43f14175512ec96eec82a63878c1a245a31ba7326bb5e959a1a527ab",
    prev_hash:
      "453754e777c0ca9154ad70f054e5d00d2e562133ccadb157ca8f6d5a44deb80f",
    merkle_root_at_time:
      "8a92b39247bb7c1f89f17a18f94d8c950ec98d3db194c439a18bf93f32da0603",
    created_at: "2026-09-09T02:16:34Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174007",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "risk_score_computed",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      risk_score_id: "323e4567-e89b-12d3-a456-426614174007",
      risk_value: 0.725,
      device_id: "SEC-LAPTOP-0142",
      device_is_new: false,
      after_hours: true,
    },
    payload_hash:
      "e6258045121c1bcd1392524a84ed01454f7641aec0dbcb059f73560b9a3f6d5f",
    prev_hash:
      "f9fac51b43f14175512ec96eec82a63878c1a245a31ba7326bb5e959a1a527ab",
    merkle_root_at_time:
      "03f21803b749e8119deec27de297a13680c79ba8ef4b988223ec2db11277fd6a",
    created_at: "2026-09-09T23:18:55Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174008",
    actor_id: null,
    event_type: "trust_score_updated",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      trust_score_id: "523e4567-e89b-12d3-a456-426614174007",
      consensus_value: 0.398,
      consensus_version: "trust-weighted-mean-0.1.0",
    },
    payload_hash:
      "8d9c25a8399394ecf9cb8522d552770f24a983149f5fab55fb12a20403881e66",
    prev_hash:
      "e6258045121c1bcd1392524a84ed01454f7641aec0dbcb059f73560b9a3f6d5f",
    merkle_root_at_time:
      "4f77de8e00ff4f47e10b9cc136409ad7b123cb9feb696f0be060011bbf8fb3cc",
    created_at: "2026-09-09T23:19:41Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174009",
    actor_id: null,
    event_type: "policy_decision_recorded",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      decision_id: "723e4567-e89b-12d3-a456-426614174007",
      rule_id: "623e4567-e89b-12d3-a456-426614174002",
      ai_recommendation: "allow",
      final_decision: "deny",
      overridden: true,
    },
    payload_hash:
      "03560904c0844c68ad5fd8fff35f336bea0d350efef55ff4f76e706cdf248aee",
    prev_hash:
      "8d9c25a8399394ecf9cb8522d552770f24a983149f5fab55fb12a20403881e66",
    merkle_root_at_time:
      "3e1c460348ed05cb1059cc94b5ac9bdf9e7898f869b0f09f60aed04f93bfc85d",
    created_at: "2026-09-09T23:20:29Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174010",
    actor_id: null,
    event_type: "crypto_profile_selected",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      crypto_profile_id: "823e4567-e89b-12d3-a456-426614174007",
      trust_score_id: "523e4567-e89b-12d3-a456-426614174007",
      profile_type: "post_quantum",
      consensus_value: 0.398,
    },
    payload_hash:
      "138f29d7013cb33046004ab34d01216ba1bb871ae5ae63721fc802a8b3d27e2c",
    prev_hash:
      "03560904c0844c68ad5fd8fff35f336bea0d350efef55ff4f76e706cdf248aee",
    merkle_root_at_time:
      "4cfce035dd4f7c4c09287780207c9dc8d69848b17a4a43ee9d1d41bd643f4cc6",
    created_at: "2026-09-09T23:21:15Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174011",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "manual_override",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      override_id: "923e4567-e89b-12d3-a456-426614174007",
      original_label: "CONFIDENTIAL",
      new_label: "RESTRICTED",
      justification:
        "Migration appendix contains long-lived private-key rotation procedures.",
    },
    payload_hash:
      "d358b9089d3384738dd2b744b916b515d81041b98bbb0b0c02c49363e8d1bdea",
    prev_hash:
      "138f29d7013cb33046004ab34d01216ba1bb871ae5ae63721fc802a8b3d27e2c",
    merkle_root_at_time:
      "63786a58dd5cf9cec6922c7e88be1f79c5d17c964cc74ff5287078aa8ea32083",
    created_at: "2026-09-10T07:34:19Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174012",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "classification_completed",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      sensitivity_label: "RESTRICTED",
      confidence: 0.9284,
      model_version: "stub-keyword-rules-0.1.0",
      is_defaulted: false,
    },
    payload_hash:
      "565b1aae5f43b4c5a8af7646f01af2fd155dbb797040f58990deeeb66b60e844",
    prev_hash:
      "d358b9089d3384738dd2b744b916b515d81041b98bbb0b0c02c49363e8d1bdea",
    merkle_root_at_time:
      "e0ad17d320f2c63d78c9e4c351662a5f0dae7660382e954422f1812af4a195d8",
    created_at: "2026-09-10T07:35:08Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174013",
    actor_id: "223e4567-e89b-12d3-a456-426614174001",
    event_type: "risk_score_computed",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      risk_score_id: "323e4567-e89b-12d3-a456-426614174008",
      risk_value: 0.475,
      device_id: "SEC-WORKSTATION-007",
      device_is_new: false,
      after_hours: true,
    },
    payload_hash:
      "387a7f07b4574be6a97d39f9af3f3fdff213f915690e1ff5c7897dd51ac91421",
    prev_hash:
      "565b1aae5f43b4c5a8af7646f01af2fd155dbb797040f58990deeeb66b60e844",
    merkle_root_at_time:
      "e2c0c280e4c85f583e7a7444529d82c4fbc5d5bbefe7dd884eeca17065c3053c",
    created_at: "2026-09-10T08:02:44Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174014",
    actor_id: null,
    event_type: "trust_score_updated",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      trust_score_id: "523e4567-e89b-12d3-a456-426614174008",
      consensus_value: 0.512,
      consensus_version: "trust-weighted-mean-0.1.0",
    },
    payload_hash:
      "a66c1dcd13035a259e870e58747902680ccd061004c321be342a61585d6034d6",
    prev_hash:
      "387a7f07b4574be6a97d39f9af3f3fdff213f915690e1ff5c7897dd51ac91421",
    merkle_root_at_time:
      "0b41fcdd0ce22c05d8c484e6436df972194d684722336488ae38450233ba76c8",
    created_at: "2026-09-10T08:03:31Z",
  },
  {
    id: "a23e4567-e89b-12d3-a456-426614174015",
    actor_id: null,
    event_type: "migration_scheduled",
    payload: {
      document_id: "123e4567-e89b-12d3-a456-426614174001",
      schedule_id: "b23e4567-e89b-12d3-a456-426614174001",
      priority_rank: 1,
      required_profile: "post_quantum",
      status: "pending",
    },
    payload_hash:
      "b2583c56755fd278dce40dc10522038bfd207898fc8af8498a2c650a38fb00bf",
    prev_hash:
      "a66c1dcd13035a259e870e58747902680ccd061004c321be342a61585d6034d6",
    merkle_root_at_time:
      "ec81cfe59179e66e520f8e2c5498e21db7afb9eac19cc9d0a545a5150edeb0c1",
    created_at: "2026-09-10T08:04:17Z",
  },
];

/** The chain with genesis-first positions attached, as the API returns them. */
export const MOCK_AUDIT_LOG: AuditEntry[] = MOCK_AUDIT_CHAIN.map(
  (entry, index) => ({ ...entry, index }),
);

// ---------------------------------------------------------------------------
// Migration schedule
// ---------------------------------------------------------------------------

export const MOCK_MIGRATION_SCHEDULE: MigrationScheduleEntry[] = [
  {
    id: "b23e4567-e89b-12d3-a456-426614174001",
    document_id: "123e4567-e89b-12d3-a456-426614174001",
    priority_rank: 1,
    scheduled_upgrade_date: "2026-10-06",
    status: "pending",
    constraint_snapshot: {
      budget_documents: 50,
      available_engineering_days: 20,
      required_profile: "post_quantum",
    },
  },
  {
    id: "b23e4567-e89b-12d3-a456-426614174002",
    document_id: "123e4567-e89b-12d3-a456-426614174002",
    priority_rank: 2,
    scheduled_upgrade_date: "2026-10-13",
    status: "pending",
    constraint_snapshot: {
      budget_documents: 50,
      available_engineering_days: 20,
      required_profile: "post_quantum",
    },
  },
  {
    id: "b23e4567-e89b-12d3-a456-426614174003",
    document_id: "123e4567-e89b-12d3-a456-426614174005",
    priority_rank: 3,
    scheduled_upgrade_date: null,
    status: "pending",
    constraint_snapshot: {
      budget_documents: 50,
      available_engineering_days: 20,
      required_profile: "post_quantum",
    },
  },
  {
    id: "b23e4567-e89b-12d3-a456-426614174004",
    document_id: "123e4567-e89b-12d3-a456-426614174006",
    priority_rank: 4,
    scheduled_upgrade_date: null,
    status: "pending",
    constraint_snapshot: {
      budget_documents: 50,
      available_engineering_days: 20,
      required_profile: "hybrid",
    },
  },
  {
    id: "b23e4567-e89b-12d3-a456-426614174005",
    document_id: "123e4567-e89b-12d3-a456-426614174003",
    priority_rank: 5,
    scheduled_upgrade_date: null,
    status: "pending",
    constraint_snapshot: {
      budget_documents: 50,
      available_engineering_days: 20,
      required_profile: "hybrid",
    },
  },
  {
    id: "b23e4567-e89b-12d3-a456-426614174006",
    document_id: "123e4567-e89b-12d3-a456-426614174004",
    priority_rank: 6,
    scheduled_upgrade_date: null,
    status: "pending",
    constraint_snapshot: {
      budget_documents: 50,
      available_engineering_days: 20,
      required_profile: "aes256",
    },
  },
];

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuditScreen } from "./page";
import { ApiError, listAuditEntries, verifyAudit } from "@/lib/api/client";
import type { AuditChainResponse, AuditVerifyResponse } from "@/lib/api/types";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    listAuditEntries: vi.fn(),
    verifyAudit: vi.fn(),
  };
});

const mockList = vi.mocked(listAuditEntries);
const mockVerify = vi.mocked(verifyAudit);

const documentId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const emptyChain: AuditChainResponse = {
  document_id: documentId,
  count: 0,
  entries: [],
};

const sampleChain: AuditChainResponse = {
  document_id: documentId,
  count: 1,
  entries: [
    {
      id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      index: 0,
      actor_id: "11111111-1111-1111-1111-111111111111",
      event_type: "document_registered",
      payload: { filename: "payroll.pdf" },
      payload_hash: "abc123",
      prev_hash: null,
      merkle_root_at_time: "root1",
      created_at: "2026-09-10T00:00:00Z",
    },
  ],
};

const sampleVerdict: AuditVerifyResponse = {
  is_valid: true,
  computed_root: "root1",
  stored_root: "root1",
  end_index: 0,
  entry_count: 1,
  document_id: documentId,
};

describe("AuditScreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("keeps load and verify disabled until a document id is entered", () => {
    render(<AuditScreen />);
    expect(screen.getByRole("button", { name: /load chain/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /verify chain/i })).toBeDisabled();
  });

  it("loads the chain without calling verify", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValueOnce(sampleChain);
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /load chain/i }));
    expect(await screen.findByText("document_registered")).toBeInTheDocument();
    expect(screen.getByText("abc123")).toBeInTheDocument();
    expect(screen.getByText("11111111-1111-1111-1111-111111111111")).toBeInTheDocument();
    expect(screen.getByText("root1")).toBeInTheDocument();
    expect(screen.getByText("2026-09-10T00:00:00Z")).toBeInTheDocument();
    expect(screen.getByText("Prev hash").parentElement).toHaveTextContent("—");
    await user.click(screen.getByText("Payload"));
    expect(screen.getByText(/payroll\.pdf/)).toBeInTheDocument();
    expect(screen.queryByText("Independent verification")).not.toBeInTheDocument();
    expect(mockList).toHaveBeenCalledWith(documentId, "auditor");
    expect(mockVerify).not.toHaveBeenCalled();
  });

  it("verifies in a separate call and can run without loading first", async () => {
    const user = userEvent.setup();
    mockVerify.mockResolvedValueOnce(sampleVerdict);
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /verify chain/i }));
    expect(await screen.findByText("Independent verification")).toBeInTheDocument();
    expect(screen.getByText("yes")).toBeInTheDocument();
    expect(mockVerify).toHaveBeenCalledWith(documentId, "auditor");
    expect(mockList).not.toHaveBeenCalled();
  });

  it("shows an empty chain without inventing entries", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValueOnce(emptyChain);
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /load chain/i }));
    expect(
      await screen.findByText(/no entries for this document/i)
    ).toBeInTheDocument();
  });

  it("renders a load error", async () => {
    const user = userEvent.setup();
    mockList.mockRejectedValueOnce(
      new ApiError(404, "Not Found", { detail: "Document was not found." })
    );
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /load chain/i }));
    expect(
      await screen.findByText(/API 404: Document was not found/i)
    ).toBeInTheDocument();
  });

  it("loads the initial document id", async () => {
    mockList.mockResolvedValue(sampleChain);
    render(<AuditScreen initialDocumentId={documentId} />);
    expect(await screen.findByText("document_registered")).toBeInTheDocument();
    expect(mockList).toHaveBeenCalledWith(documentId, "auditor");
  });

  it("clears verification when the document id changes", async () => {
    const user = userEvent.setup();
    mockVerify.mockResolvedValueOnce(sampleVerdict);
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /verify chain/i }));
    expect(await screen.findByText("Independent verification")).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/^document id/i));
    await user.type(
      screen.getByLabelText(/^document id/i),
      "ffffffff-ffff-ffff-ffff-ffffffffffff"
    );
    expect(screen.queryByText("Independent verification")).not.toBeInTheDocument();
    expect(screen.getByText(/verify is a separate request/i)).toBeInTheDocument();
  });

  it("clears a verify error when the document id changes", async () => {
    const user = userEvent.setup();
    mockVerify.mockRejectedValueOnce(
      new ApiError(409, "Conflict", { detail: "Broken chain." })
    );
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /verify chain/i }));
    expect(await screen.findByText(/API 409: Broken chain/i)).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/^document id/i));
    await user.type(
      screen.getByLabelText(/^document id/i),
      "ffffffff-ffff-ffff-ffff-ffffffffffff"
    );
    expect(screen.queryByText(/API 409: Broken chain/i)).not.toBeInTheDocument();
  });

  it("hides a stale chain when the document id changes", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValueOnce(sampleChain);
    render(<AuditScreen />);
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /load chain/i }));
    expect(await screen.findByText("document_registered")).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/^document id/i));
    await user.type(
      screen.getByLabelText(/^document id/i),
      "ffffffff-ffff-ffff-ffff-ffffffffffff"
    );
    expect(screen.queryByText("document_registered")).not.toBeInTheDocument();
    expect(screen.getByText(/document id changed — load again/i)).toBeInTheDocument();
  });

  it("passes the selected role to load and verify", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValueOnce(sampleChain);
    mockVerify.mockResolvedValueOnce(sampleVerdict);
    render(<AuditScreen />);
    await user.selectOptions(
      screen.getByLabelText(/^caller role/i),
      "security_admin"
    );
    await user.type(screen.getByLabelText(/^document id/i), documentId);
    await user.click(screen.getByRole("button", { name: /load chain/i }));
    expect(mockList).toHaveBeenCalledWith(documentId, "security_admin");
    await user.click(screen.getByRole("button", { name: /verify chain/i }));
    expect(mockVerify).toHaveBeenCalledWith(documentId, "security_admin");
  });
});

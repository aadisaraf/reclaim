// Typed client for the Reclaim app API.
// Field shapes follow specs/001-denial-recovery/contracts/app-api.openapi.yaml and
// specs/001-denial-recovery/data-model.md. The backend (main.py/api.py) is not wired yet
// (tasks T043/T053/T064/T071/T084/T094/T100/T110/T113), so several nested shapes below
// (Policy.requirements, MatrixRow.requirementText) are reasonable extrapolations from
// data-model.md rather than confirmed wire shapes — they degrade to optional so the UI
// doesn't crash once the real api.py lands with a slightly different key.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { persona?: string }
): Promise<T> {
  const { persona, ...rest } = init ?? {};
  const headers = new Headers(rest.headers);
  if (persona) headers.set("X-Persona", persona);
  if (rest.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, { ...rest, headers });
  if (res.status === 204) {
    return undefined as T;
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (!res.ok) {
    if (contentType.includes("application/json")) {
      const body = (await res.json()) as { error?: { code: string; message: string } };
      if (body.error) {
        throw new ApiError(res.status, body.error.code, body.error.message);
      }
    }
    throw new ApiError(res.status, "unknown_error", `Request to ${path} failed with ${res.status}`);
  }
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as T;
}

export function apiBaseUrl(): string {
  return API_BASE;
}

// ---- Shared types --------------------------------------------------------

export type CaseStatus =
  | "new"
  | "claim-matched"
  | "needs-review"
  | "evidence-gathered"
  | "needs-evidence"
  | "ready-for-review"
  | "approved"
  | "submitted"
  | "in-review"
  | "paid"
  | "other-denial";

export interface Config {
  synthetic: true;
  demoDate: string;
  aiMode: "live" | "replay";
  model: string;
  missingEvidence: boolean;
  baseUrls: {
    clearinghouse: string;
    ehr: string;
    payer: string;
  };
}

export interface Persona {
  userId: string;
  role: string;
  canApprove: boolean;
}

export interface QueueCase {
  caseId: string;
  headline: string;
  status: CaseStatus;
  running: boolean;
}

export interface OtherLaneItem {
  caseId: string;
  hospitalClaimId: string;
  denialCode: string;
  amount: number;
  label: string;
}

export interface RemitFile {
  fileName: string;
  status: "processed" | "rejected";
  claimCount: number;
}

export interface Queue {
  cases: QueueCase[];
  summary: {
    paidClaims: number;
    otherDenials: number;
    lines: string[];
  };
  otherLane: OtherLaneItem[];
  remitFiles: RemitFile[];
}

// ---- Case detail ----------------------------------------------------------

export interface IdentityCheck {
  field: string;
  sourceA: string;
  valueA: string | null;
  sourceB: string;
  valueB: string | null;
  passed: boolean;
}

export interface Identity {
  chain: string[];
  checks: IdentityCheck[];
}

export interface EvidenceItem {
  resource: string;
  resourceType: string;
  date: string | null;
  sourceUrl: string;
  included: boolean;
  exclusionReason: string | null;
  summary: string;
  document: string | null;
  text: string | null;
}

export interface Evidence {
  items: EvidenceItem[];
  excludedLine: string;
  searchCounts: Record<string, number>;
}

export interface PayerDecision {
  payerClaimId: string;
  claimId: string;
  decision: string;
  decisionDate: string;
  reasonCode: string;
  reasonText: string;
  appealDeadline: string;
  allowedSubmissionChannels: string[];
  letter: { documentId: string; url: string };
}

export interface Policy {
  label: string;
  title: string;
  // Extrapolated from data-model.md §2 ("Policy mirrors the A7 JSON"); not confirmed on the wire.
  requirements?: { requirementId: string; text: string; evidenceTypes?: string[] }[];
}

export interface Deadline {
  line: string;
  warning: string | null;
}

export interface Citation {
  citationId: string;
  resource: string;
  document: string | null;
  date: string | null;
  excerpt: string;
  verified: boolean;
  rejectionReason: string | null;
}

export interface MatrixRow {
  requirementId: string;
  status: "satisfied" | "missing";
  reason: string | null;
  evidence: Citation[];
  // Extrapolated: data-model.md keeps requirement text on Policy, not MatrixRow. Kept optional
  // here and looked up from policy.requirements as a fallback (see MatrixTab.tsx).
  requirementText?: string;
}

export interface EvidenceMatrix {
  caseId: string;
  policyId: string;
  policyVersion: string;
  summary: { satisfied: number; total: number };
  requirements: MatrixRow[];
}

export interface HeaderField {
  label: string;
  value: string;
  source: "remit" | "claim837" | "payerDecision" | "claimMap" | "policy";
}

export interface LetterStatement {
  statementId: string;
  text: string;
  requirementIds: string[];
  citationIds: string[];
}

export interface Packet {
  version: number;
  status: "blocked" | "ready-for-review" | "approved" | "submitted";
  letter: {
    header: HeaderField[];
    body: LetterStatement[];
    requestedAction: string;
    attachments: string[];
    requiredApprover: string;
    version: number;
    footer: string;
  } | null;
  pdfUrl: string | null;
  blockedReason: string | null;
}

export interface Submission {
  idempotencyKey: string;
  status: "pending" | "confirmed" | "refused";
  appealId: string | null;
  expectedResolutionDays: number | null;
  payerStatus: "received" | "in-review" | null;
  errorCode: string | null;
  errorMessage: string | null;
  display: string | null;
}

export interface AiCost {
  inputTokens: number;
  cachedTokens: number;
  outputTokens: number;
  reasoningTokens: number;
  usd: number;
  line: string;
}

export interface TaskItem {
  taskId: string;
  taskType: string;
  requirementId: string;
  assigneeRole: string;
  question: string;
  status: "open" | "closed";
  closeNote: string | null;
}

export interface TimelineEvent {
  step: string;
  summary: string;
  ehrRequests: string[];
  llmUsage: AiCost | null;
  createdAt: string;
}

export interface CaseRow {
  caseId: string;
  lane: string;
  status: CaseStatus;
  headline: string;
  hospitalClaimId: string;
  payerClaimId: string | null;
  amount: number | null;
  needsReviewField: string | null;
  lastError: string | null;
}

export interface CaseDetail {
  case: CaseRow;
  running: boolean;
  statusLine: string;
  identity: Identity | null;
  evidence: Evidence | null;
  payerDecision: PayerDecision | null;
  policy: Policy | null;
  deadline: Deadline | null;
  matrix: EvidenceMatrix | null;
  completenessLine: string | null;
  needsLine: string | null;
  recoveryLine: string | null;
  tasks: TaskItem[];
  packet: Packet | null;
  submission: Submission | null;
  aiCost: AiCost | null;
  actions: {
    canRerun: boolean;
    rerunUnavailableReason: string | null;
    canApprove: boolean;
  };
  timeline: TimelineEvent[];
}

// ---- Requests --------------------------------------------------------------

export function getConfig(): Promise<Config> {
  return request<Config>("/api/config");
}

export function listPersonas(): Promise<Persona[]> {
  return request<Persona[]>("/api/personas");
}

export function getQueue(): Promise<Queue> {
  return request<Queue>("/api/queue");
}

export function getCase(caseId: string): Promise<CaseDetail> {
  return request<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`);
}

export function getPacketPdfUrl(caseId: string, version: number): string {
  return `${API_BASE}/api/cases/${encodeURIComponent(caseId)}/packets/${version}/pdf`;
}

export function getCaseDocumentUrl(caseId: string, documentId: string): string {
  return `${API_BASE}/api/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(documentId)}`;
}

export function rerunCase(caseId: string): Promise<{ caseId: string; running: boolean }> {
  return request(`/api/cases/${encodeURIComponent(caseId)}/rerun`, { method: "POST" });
}

export function approveAndSubmit(
  caseId: string,
  version: number,
  persona: string
): Promise<Submission> {
  return request<Submission>(
    `/api/cases/${encodeURIComponent(caseId)}/packets/${version}/approve-and-submit`,
    { method: "POST", persona }
  );
}

export function simulateRemit(): Promise<{ delivered: string }> {
  return request("/api/demo/simulate-remit", { method: "POST" });
}

export function setMissingEvidence(enabled: boolean): Promise<{ enabled: boolean }> {
  return request("/api/demo/missing-evidence", {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
}

export function resetDemo(): Promise<void> {
  return request("/api/demo/reset", { method: "POST" });
}

// ---- Persona persistence (localStorage; per-viewer convenience only) -------

const PERSONA_STORAGE_KEY = "reclaim.persona";

export function loadStoredPersona(): string | null {
  try {
    return window.localStorage.getItem(PERSONA_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storePersona(userId: string): void {
  try {
    window.localStorage.setItem(PERSONA_STORAGE_KEY, userId);
  } catch {
    // localStorage unavailable (private browsing, blocked); persona picker still works in-memory.
  }
}

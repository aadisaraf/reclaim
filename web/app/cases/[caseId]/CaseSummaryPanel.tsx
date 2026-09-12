"use client";

import { useState } from "react";
import { CaseRow, Deadline, Policy, PayerDecision, TimelineEvent, getCaseDocumentUrl } from "@/lib/api";
import { CopyIcon, MailIcon } from "../../components/icons";

const BUCKET_BY_STATUS: Record<string, "progress" | "attention" | "success" | "muted"> = {
  new: "progress",
  "claim-matched": "progress",
  "evidence-gathered": "progress",
  approved: "progress",
  "needs-review": "attention",
  "needs-evidence": "attention",
  "ready-for-review": "success",
  submitted: "success",
  "in-review": "success",
  paid: "success",
  "other-denial": "muted",
};

function initialsFor(hospitalClaimId: string): string {
  const digits = hospitalClaimId.match(/\d+/)?.[0] ?? hospitalClaimId;
  return digits.slice(-2);
}

export default function CaseSummaryPanel({
  caseId,
  caseRow,
  payerDecision,
  policy,
  deadline,
  timeline,
  actions,
  onRerun,
  rerunning,
  rerunMessage,
}: {
  caseId: string;
  caseRow: CaseRow;
  payerDecision: PayerDecision | null;
  policy: Policy | null;
  deadline: Deadline | null;
  timeline: TimelineEvent[];
  actions: { canRerun: boolean; rerunUnavailableReason: string | null };
  onRerun: () => void;
  rerunning: boolean;
  rerunMessage: string | null;
}) {
  const [copied, setCopied] = useState(false);
  const bucket = BUCKET_BY_STATUS[caseRow.status] ?? "progress";
  const lastEvent = timeline[timeline.length - 1] ?? null;

  async function onCopyClaimId() {
    try {
      await navigator.clipboard.writeText(caseRow.hospitalClaimId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable (permissions, insecure context) — nothing to show for it.
    }
  }

  const facts: { label: string; value: string }[] = [];
  if (caseRow.payerClaimId) facts.push({ label: "Payer claim ID", value: caseRow.payerClaimId });
  if (caseRow.amount !== null) facts.push({ label: "Billed amount", value: `$${caseRow.amount.toLocaleString()}` });
  if (payerDecision) facts.push({ label: "Denial reason", value: `${payerDecision.reasonCode} · ${payerDecision.reasonText}` });
  if (deadline?.line) facts.push({ label: "Deadline", value: deadline.line });
  if (policy?.label) facts.push({ label: "Policy", value: policy.label });

  return (
    <div className="summary-panel">
      <div style={{ display: "flex", gap: "var(--space-md)", alignItems: "center" }}>
        <div className={`avatar-circle bucket-${bucket}`}>{initialsFor(caseRow.hospitalClaimId)}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, overflowWrap: "anywhere" }}>{caseRow.hospitalClaimId}</div>
          <div className="code-value" style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)" }}>
            {caseId}
          </div>
        </div>
      </div>

      <div className="icon-action-row">
        <button className="icon-action-btn" onClick={onCopyClaimId} type="button">
          <CopyIcon />
          {copied ? "Copied" : "Copy ID"}
        </button>
        {payerDecision ? (
          <a
            className="icon-action-btn"
            href={getCaseDocumentUrl(caseId, payerDecision.letter.documentId)}
            target="_blank"
            rel="noreferrer"
          >
            <MailIcon />
            Denial letter
          </a>
        ) : (
          <button className="icon-action-btn" disabled type="button" title="No denial letter fetched yet">
            <MailIcon />
            Denial letter
          </button>
        )}
      </div>

      {lastEvent && (
        <div>
          <div className="summary-fact-label">Last activity</div>
          <div className="summary-fact-value">
            {lastEvent.summary}
            <div className="code-value" style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)" }}>
              {lastEvent.createdAt}
            </div>
          </div>
        </div>
      )}

      {facts.length > 0 && (
        <div className="summary-facts">
          {facts.map((f) => (
            <div key={f.label}>
              <div className="summary-fact-label">{f.label}</div>
              <div className="summary-fact-value">{f.value}</div>
            </div>
          ))}
        </div>
      )}

      <div>
        {actions.canRerun ? (
          <button className="btn-secondary" onClick={onRerun} disabled={rerunning} style={{ width: "100%" }}>
            {rerunning ? "Re-running…" : "Re-run pipeline"}
          </button>
        ) : (
          actions.rerunUnavailableReason && (
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)", margin: 0 }}>
              {actions.rerunUnavailableReason}
            </p>
          )
        )}
        {rerunMessage && (
          <p style={{ fontSize: "var(--text-xs)", color: "var(--color-destructive)", margin: "var(--space-xs) 0 0" }}>
            {rerunMessage}
          </p>
        )}
      </div>
    </div>
  );
}

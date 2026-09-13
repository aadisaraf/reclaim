"use client";

import { useEffect, useRef, useState } from "react";
import { CaseRow, Deadline, Policy, PayerDecision, TimelineEvent, getCaseDocumentUrl } from "@/lib/api";
import {
  CopyIcon,
  DocumentStackIcon,
  MailIcon,
  MoreIcon,
} from "../../components/icons";

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

function humanizeStep(step: string): string {
  const words = step.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function activityBubbleTone(summary: string): "" | "success" | "attention" {
  const s = summary.toLowerCase();
  if (
    s.includes("needs-review") ||
    s.includes("needs review") ||
    s.includes("excluded") ||
    s.includes("missing") ||
    s.includes("rejected")
  ) {
    return "attention";
  }
  if (s.includes("satisfied") || s.includes("passed") || s.includes("confirmed") || s.includes("ready")) {
    return "success";
  }
  return "";
}

type PanelTab = "facts" | "activity";

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
  const [moreOpen, setMoreOpen] = useState(false);
  const [panelTab, setPanelTab] = useState<PanelTab>("facts");
  const moreRef = useRef<HTMLDivElement>(null);
  const bucket = BUCKET_BY_STATUS[caseRow.status] ?? "progress";
  const lastEvent = timeline[timeline.length - 1] ?? null;
  const recentEvents = [...timeline].reverse().slice(0, 6);

  useEffect(() => {
    function onClickAway(e: MouseEvent) {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  async function onCopyClaimId() {
    try {
      await navigator.clipboard.writeText(caseRow.hospitalClaimId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable (permissions, insecure context) — nothing to show for it.
    }
  }

  function onRerunClick() {
    setMoreOpen(false);
    onRerun();
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

      <div className="icon-square-btn-row">
        <button className="icon-square-btn-wrap" onClick={onCopyClaimId} type="button">
          <span className="icon-square-btn green">
            <CopyIcon />
          </span>
          <span>{copied ? "Copied" : "Copy ID"}</span>
        </button>
        {payerDecision ? (
          <a
            className="icon-square-btn-wrap"
            href={getCaseDocumentUrl(caseId, payerDecision.letter.documentId)}
            target="_blank"
            rel="noreferrer"
          >
            <span className="icon-square-btn blue">
              <MailIcon />
            </span>
            <span>Denial letter</span>
          </a>
        ) : (
          <button className="icon-square-btn-wrap" disabled type="button" title="No denial letter fetched yet">
            <span className="icon-square-btn blue">
              <MailIcon />
            </span>
            <span>Denial letter</span>
          </button>
        )}
        <div className="dropdown-wrapper" ref={moreRef} style={{ flex: "0 0 auto" }}>
          <button
            className="icon-square-btn-wrap"
            onClick={() => setMoreOpen((v) => !v)}
            type="button"
            aria-label="More actions"
          >
            <span className="icon-square-btn neutral">
              <MoreIcon />
            </span>
            <span>More</span>
          </button>
          {moreOpen && (
            <div className="dropdown-menu" style={{ right: 0, left: "auto" }}>
              <button
                className="dropdown-item"
                onClick={onRerunClick}
                disabled={!actions.canRerun || rerunning}
                title={actions.rerunUnavailableReason ?? undefined}
              >
                {rerunning ? "Re-running…" : "Re-run pipeline"}
              </button>
            </div>
          )}
        </div>
      </div>
      {!actions.canRerun && actions.rerunUnavailableReason && (
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)", margin: 0 }}>
          {actions.rerunUnavailableReason}
        </p>
      )}
      {rerunMessage && (
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-destructive)", margin: 0 }}>{rerunMessage}</p>
      )}

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

      <div className="subtabs" role="tablist">
        <button
          className="subtab"
          role="tab"
          aria-selected={panelTab === "facts"}
          onClick={() => setPanelTab("facts")}
          type="button"
        >
          Facts
        </button>
        <button
          className="subtab"
          role="tab"
          aria-selected={panelTab === "activity"}
          onClick={() => setPanelTab("activity")}
          type="button"
        >
          Activities
        </button>
      </div>

      {panelTab === "facts" ? (
        facts.length > 0 ? (
          <div className="summary-facts">
            {facts.map((f) => (
              <div key={f.label}>
                <div className="summary-fact-label">{f.label}</div>
                <div className="summary-fact-value">{f.value}</div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)", margin: 0 }}>
            No facts available yet.
          </p>
        )
      ) : recentEvents.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)", maxHeight: 260, overflowY: "auto" }}>
          {recentEvents.map((e, i) => {
            const tone = activityBubbleTone(e.summary);
            return (
              <div key={i} className="activity-item">
                <span className={`activity-icon-bubble${tone ? ` ${tone}` : ""}`}>
                  <DocumentStackIcon size={14} />
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{humanizeStep(e.step)}</div>
                  <div style={{ fontSize: "var(--text-sm)" }}>{e.summary}</div>
                  <div className="code-value" style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)" }}>
                    {e.createdAt}
                  </div>
                  {(e.llmUsage || e.ehrRequests.length > 0) && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                      {e.llmUsage && (
                        <span
                          className="activity-transition-pill"
                          style={{ background: "var(--status-success-bg)", color: "var(--status-success-fg)" }}
                        >
                          {e.llmUsage.line}
                        </span>
                      )}
                      {e.ehrRequests.length > 0 && (
                        <span
                          className="activity-transition-pill"
                          style={{ background: "var(--status-muted-bg)", color: "var(--status-muted-fg)" }}
                        >
                          {e.ehrRequests.length} EHR request{e.ehrRequests.length === 1 ? "" : "s"}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)", margin: 0 }}>
          No activity yet.
        </p>
      )}
    </div>
  );
}

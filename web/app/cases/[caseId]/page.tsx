"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { CaseDetail, getCase, rerunCase } from "@/lib/api";
import StatusBadge from "../../components/StatusBadge";
import { BankIcon, ChevronLeftIcon, HospitalIcon, TruckIcon } from "../../components/icons";
import CaseSummaryPanel from "./CaseSummaryPanel";
import IdentityTab from "./IdentityTab";
import EvidenceTab from "./EvidenceTab";
import MatrixTab from "./MatrixTab";
import PacketTab from "./PacketTab";
import TimelineTab from "./TimelineTab";

type TabId = "identity" | "evidence" | "matrix" | "packet" | "timeline";

const TABS: { id: TabId; label: string }[] = [
  { id: "identity", label: "Identity" },
  { id: "evidence", label: "Evidence" },
  { id: "matrix", label: "Matrix" },
  { id: "packet", label: "Packet" },
  { id: "timeline", label: "Timeline" },
];

export default function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = params.caseId;

  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<TabId>("identity");
  const [rerunning, setRerunning] = useState(false);
  const [rerunMessage, setRerunMessage] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    getCase(caseId)
      .then((d) => {
        setDetail(d);
        setNotFound(false);
      })
      .catch((err) => {
        if (err && typeof err === "object" && "status" in err && (err as { status: number }).status === 404) {
          setNotFound(true);
        }
      });
  }, [caseId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (detail?.running) {
      pollRef.current = setInterval(refresh, 1000);
      return () => {
        if (pollRef.current) clearInterval(pollRef.current);
      };
    }
    return undefined;
  }, [detail?.running, refresh]);

  async function onRerun() {
    setRerunning(true);
    setRerunMessage(null);
    try {
      await rerunCase(caseId);
      refresh();
    } catch (err) {
      setRerunMessage(err instanceof Error ? err.message : "Rerun failed");
    } finally {
      setRerunning(false);
    }
  }

  if (notFound) {
    return <p>Case {caseId} was not found.</p>;
  }

  if (!detail) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>Loading case {caseId}…</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      <nav className="breadcrumb">
        <Link href="/" style={{ display: "flex", alignItems: "center" }} aria-label="Back to case queue">
          <ChevronLeftIcon size={16} />
        </Link>
        <Link href="/">Case queue</Link>
        <span>/</span>
        <span className="breadcrumb-current">{detail.case.hospitalClaimId}</span>
      </nav>

      <div className="case-shell">
        <CaseSummaryPanel
          caseId={caseId}
          caseRow={detail.case}
          payerDecision={detail.payerDecision}
          policy={detail.policy}
          deadline={detail.deadline}
          timeline={detail.timeline}
          actions={detail.actions}
          onRerun={onRerun}
          rerunning={rerunning}
          rerunMessage={rerunMessage}
        />

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)", minWidth: 0 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", flexWrap: "wrap" }}>
              <h1 style={{ fontSize: "var(--text-lg)", margin: 0 }}>{detail.case.headline}</h1>
              <StatusBadge status={detail.case.status} />
              {detail.running && (
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)" }}>
                  Updating…
                </span>
              )}
            </div>
            {detail.statusLine && (
              <p style={{ color: "var(--color-muted-foreground)", margin: "var(--space-xs) 0 0" }}>
                {detail.statusLine}
              </p>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", marginTop: "var(--space-sm)" }}>
              {(detail.case.createdAt ?? detail.timeline[0]?.createdAt) && (
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>
                  Created:{" "}
                  <span className="code-value">{detail.case.createdAt ?? detail.timeline[0]?.createdAt}</span>
                </span>
              )}
              <div className="system-chip-row">
                <span className="system-chip" title="Clearinghouse (SFTP inbox)">
                  <TruckIcon size={14} />
                </span>
                {detail.evidence && (
                  <span className="system-chip" title="Mock hospital FHIR EHR">
                    <HospitalIcon size={14} />
                  </span>
                )}
                {detail.payerDecision && (
                  <span className="system-chip" title="Northstar Health mock payer">
                    <BankIcon size={14} />
                  </span>
                )}
              </div>
            </div>
            {detail.needsLine && (
              <p style={{ color: "var(--status-attention-fg)", fontWeight: 600, margin: "var(--space-xs) 0 0" }}>
                {detail.needsLine}
              </p>
            )}
            {detail.case.lastError && (
              <p style={{ color: "var(--color-destructive)", margin: "var(--space-xs) 0 0" }}>
                Error: {detail.case.lastError}
              </p>
            )}
          </div>

          {detail.tasks.length > 0 && (
            <div>
              <h3 style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)", margin: "0 0 var(--space-xs)" }}>
                Clinician requests
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
                {detail.tasks.map((t) => (
                  <div key={t.taskId} className="card" style={{ padding: "var(--space-sm) var(--space-md)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-md)" }}>
                      <span className="code-value" style={{ fontSize: "var(--text-xs)" }}>
                        {t.taskId} · {t.assigneeRole}
                      </span>
                      <span className={`badge ${t.status === "open" ? "badge-attention" : "badge-success"}`}>
                        {t.status}
                      </span>
                    </div>
                    <p style={{ margin: "var(--space-xs) 0 0", fontSize: "var(--text-sm)" }}>{t.question}</p>
                    {t.closeNote && (
                      <p style={{ margin: "var(--space-xs) 0 0", fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>
                        {t.closeNote}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                className="tab"
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="card">
            {tab === "identity" && <IdentityTab identity={detail.identity} timeline={detail.timeline} />}
            {tab === "evidence" && <EvidenceTab evidence={detail.evidence} policy={detail.policy} />}
            {tab === "matrix" && (
              <MatrixTab
                caseId={caseId}
                matrix={detail.matrix}
                policy={detail.policy}
                payerDecision={detail.payerDecision}
                deadline={detail.deadline}
                completenessLine={detail.completenessLine}
              />
            )}
            {tab === "packet" && (
              <PacketTab
                caseId={caseId}
                packet={detail.packet}
                matrix={detail.matrix}
                deadline={detail.deadline}
                completenessLine={detail.completenessLine}
                recoveryLine={detail.recoveryLine}
                submission={detail.submission}
                canApprove={detail.actions.canApprove}
                onChanged={refresh}
              />
            )}
            {tab === "timeline" && <TimelineTab timeline={detail.timeline} aiCost={detail.aiCost} />}
          </div>
        </div>
      </div>
    </div>
  );
}

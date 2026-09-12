"use client";

import { useState } from "react";
import {
  Citation,
  Deadline,
  EvidenceMatrix,
  Packet,
  Submission,
  approveAndSubmit,
  getPacketPdfUrl,
} from "@/lib/api";
import { currentPersona } from "../../components/Header";
import { AlertCircleIcon, CheckCircleIcon } from "../../components/icons";

function citationsFor(matrix: EvidenceMatrix | null, requirementIds: string[], citationIds: string[]): Citation[] {
  if (!matrix) return [];
  const wanted = new Set(citationIds);
  return matrix.requirements
    .filter((r) => requirementIds.includes(r.requirementId))
    .flatMap((r) => r.evidence)
    .filter((c) => wanted.has(c.citationId));
}

export default function PacketTab({
  caseId,
  packet,
  matrix,
  deadline,
  completenessLine,
  recoveryLine,
  submission,
  canApprove,
  onChanged,
}: {
  caseId: string;
  packet: Packet | null;
  matrix: EvidenceMatrix | null;
  deadline: Deadline | null;
  completenessLine: string | null;
  recoveryLine: string | null;
  submission: Submission | null;
  canApprove: boolean;
  onChanged: () => void;
}) {
  const [expandedStatement, setExpandedStatement] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  if (!packet) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>No packet has been drafted yet.</p>;
  }

  async function onApprove() {
    if (!packet) return;
    setApproving(true);
    setApproveError(null);
    try {
      const result = await approveAndSubmit(caseId, packet.version, currentPersona());
      if (result.status === "refused") {
        setApproveError(result.errorMessage ?? "The payer refused the submission.");
      }
      onChanged();
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setApproving(false);
    }
  }

  const statusLines = [
    packet.status === "ready-for-review" ? "Ready for review" : null,
    completenessLine,
    deadline?.line ?? null,
    recoveryLine,
  ].filter((line): line is string => Boolean(line));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      <div>
        {statusLines.map((line, i) => (
          <p
            key={i}
            style={{
              margin: "2px 0",
              fontWeight: i === 0 ? 600 : 400,
              display: "flex",
              alignItems: "center",
              gap: "var(--space-xs)",
            }}
          >
            {i === 0 &&
              (packet.status === "ready-for-review" ? (
                <CheckCircleIcon size={16} />
              ) : (
                <AlertCircleIcon size={16} />
              ))}
            {line}
          </p>
        ))}
      </div>

      {packet.status === "blocked" && (
        <div
          className="badge badge-attention"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-xs)",
            padding: "var(--space-sm) var(--space-md)",
          }}
        >
          <AlertCircleIcon size={16} />
          Blocked: {packet.blockedReason}
        </div>
      )}

      {packet.letter && (
        <>
          <div>
            <h3 style={{ fontSize: "var(--text-base)", marginBottom: "var(--space-sm)" }}>Header</h3>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
              <tbody>
                {packet.letter.header.map((field) => (
                  <tr key={field.label} style={{ borderBottom: "1px solid var(--color-border)" }} title={`Source: ${field.source}`}>
                    <td style={{ padding: "var(--space-xs) 0", color: "var(--color-muted-foreground)" }}>{field.label}</td>
                    <td className="code-value">{field.value}</td>
                    <td style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-xs)" }}>{field.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h3 style={{ fontSize: "var(--text-base)", marginBottom: "var(--space-sm)" }}>Letter body</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {packet.letter.body.map((statement) => {
                const isOpen = expandedStatement === statement.statementId;
                return (
                  <div key={statement.statementId} className="card" style={{ cursor: "pointer" }}>
                    <p
                      onClick={() => setExpandedStatement(isOpen ? null : statement.statementId)}
                      style={{ margin: 0 }}
                    >
                      {statement.text}
                    </p>
                    {isOpen && (() => {
                      const verifiedCitations = citationsFor(matrix, statement.requirementIds, statement.citationIds);
                      return (
                        <div style={{ marginTop: "var(--space-sm)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-sm)" }}>
                          <p
                            style={{
                              fontSize: "var(--text-xs)",
                              color: "var(--color-muted-foreground)",
                              display: "flex",
                              alignItems: "center",
                              gap: "var(--space-xs)",
                            }}
                          >
                            {verifiedCitations.length > 0 && <CheckCircleIcon size={14} />}
                            Requirements: {statement.requirementIds.join(", ")}
                          </p>
                          {verifiedCitations.map((c) => (
                            <p key={c.citationId} style={{ fontSize: "var(--text-sm)", fontStyle: "italic", margin: "var(--space-xs) 0" }}>
                              <span className="code-value" style={{ fontStyle: "normal" }}>
                                {c.resource}:
                              </span>{" "}
                              &ldquo;{c.excerpt}&rdquo;
                            </p>
                          ))}
                        </div>
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          </div>

          <div>
            <h3 style={{ fontSize: "var(--text-base)", marginBottom: "var(--space-sm)" }}>Attachments</h3>
            <ul style={{ margin: 0, paddingLeft: "var(--space-lg)" }}>
              {packet.letter.attachments.map((a) => (
                <li key={a} className="code-value" style={{ fontSize: "var(--text-sm)" }}>
                  {a}
                </li>
              ))}
            </ul>
          </div>

          <a
            href={packet.pdfUrl ?? getPacketPdfUrl(caseId, packet.version)}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: "var(--text-sm)" }}
          >
            View packet PDF
          </a>
        </>
      )}

      <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-lg)" }}>
        {submission?.appealId ? (
          <p style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "var(--space-xs)" }}>
            <CheckCircleIcon size={16} />
            {submission.display}
            {submission.payerStatus === "in-review" && " · In review"}
          </p>
        ) : (
          <>
            <button className="btn-primary" onClick={onApprove} disabled={!canApprove || approving}>
              {approving ? "Submitting…" : "Approve and submit"}
            </button>
            {!canApprove && (
              <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)", marginTop: "var(--space-sm)" }}>
                The current persona cannot approve this packet.
              </p>
            )}
          </>
        )}
        {(approveError || submission?.errorMessage) && (
          <p style={{ color: "var(--color-destructive)", marginTop: "var(--space-sm)" }}>
            {approveError ?? submission?.errorMessage}
          </p>
        )}
      </div>
    </div>
  );
}

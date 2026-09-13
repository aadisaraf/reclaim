import { Deadline, EvidenceMatrix, PayerDecision, Policy, getCaseDocumentUrl } from "@/lib/api";
import { AlertCircleIcon, CheckCircleIcon } from "../../components/icons";
import StatCards from "../../components/StatCards";

function requirementText(row: { requirementId: string; requirementText?: string }, policy: Policy | null): string {
  if (row.requirementText) return row.requirementText;
  const fromPolicy = policy?.requirements?.find((r) => r.requirementId === row.requirementId)?.text;
  return fromPolicy ?? row.requirementId;
}

export default function MatrixTab({
  caseId,
  matrix,
  policy,
  payerDecision,
  deadline,
  completenessLine,
}: {
  caseId: string;
  matrix: EvidenceMatrix | null;
  policy: Policy | null;
  payerDecision: PayerDecision | null;
  deadline: Deadline | null;
  completenessLine: string | null;
}) {
  if (!matrix) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>The evidence matrix has not been built yet.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      <StatCards
        stats={[
          {
            key: "completeness",
            icon: <CheckCircleIcon size={16} />,
            label: "Policy criteria satisfied",
            value: matrix.summary.satisfied,
            ofValue: matrix.summary.total,
            iconTone: matrix.summary.satisfied === matrix.summary.total ? "success" : "attention",
          },
        ]}
      />

      <div>
        {policy && (
          <>
            <p style={{ fontWeight: 600 }}>{policy.label}</p>
            <p style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>{policy.title}</p>
          </>
        )}
        {completenessLine && <p style={{ fontSize: "var(--text-sm)", marginTop: "var(--space-sm)" }}>{completenessLine}</p>}
      </div>

      {deadline?.warning && (
        <div
          className="badge badge-attention"
          style={{ display: "block", padding: "var(--space-sm) var(--space-md)", borderRadius: "6px" }}
        >
          {deadline.warning}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
        {matrix.requirements.map((row) => (
          <div
            key={row.requirementId}
            className={row.status === "satisfied" ? "card matrix-row-satisfied" : "card"}
            style={{
              borderColor: row.status === "satisfied" ? "var(--status-success-fg)" : "var(--color-destructive)",
              background: row.status === "satisfied" ? "var(--status-success-bg)" : "var(--status-attention-bg)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-md)" }}>
              <span style={{ fontWeight: 600 }}>
                {row.requirementId}: {requirementText(row, policy)}
              </span>
              <span className={`badge ${row.status === "satisfied" ? "badge-success" : "badge-attention"}`}>
                {row.status === "satisfied" ? <CheckCircleIcon size={16} /> : <AlertCircleIcon size={16} />}
                {row.status === "satisfied" ? "Satisfied" : "Missing"}
              </span>
            </div>
            {row.status === "missing" && row.reason && (
              <p style={{ color: "var(--status-attention-fg)", margin: "var(--space-sm) 0 0" }}>{row.reason}</p>
            )}
            {row.evidence.length > 0 && (
              <ul style={{ margin: "var(--space-sm) 0 0", paddingLeft: "var(--space-lg)" }}>
                {row.evidence.map((c) => (
                  <li key={c.citationId} style={{ marginBottom: "var(--space-xs)" }}>
                    <span className="code-value">{c.resource}</span>
                    {c.date && (
                      <span className="code-value" style={{ color: "var(--color-muted-foreground)" }}>
                        {" "}
                        ({c.date})
                      </span>
                    )}
                    <p style={{ margin: "2px 0 0", fontStyle: "italic" }}>&ldquo;{c.excerpt}&rdquo;</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {payerDecision && (
        <div className="card">
          <p style={{ fontWeight: 600 }}>Payer decision</p>
          <p style={{ margin: "var(--space-xs) 0" }}>
            {payerDecision.reasonCode} · {payerDecision.reasonText}
          </p>
          <p className="code-value" style={{ color: "var(--color-muted-foreground)" }}>
            Decided {payerDecision.decisionDate} · deadline {payerDecision.appealDeadline}
          </p>
          {deadline && <p style={{ margin: "var(--space-xs) 0" }}>{deadline.line}</p>}
          <a
            href={getCaseDocumentUrl(caseId, payerDecision.letter.documentId)}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: "var(--text-sm)" }}
          >
            View denial letter
          </a>
        </div>
      )}
    </div>
  );
}

import { Identity, TimelineEvent } from "@/lib/api";
import { CheckCircleIcon, XCircleIcon, DocumentStackIcon } from "../../components/icons";

export default function IdentityTab({
  identity,
  timeline,
}: {
  identity: Identity | null;
  timeline: TimelineEvent[];
}) {
  if (!identity) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>Identity resolution has not run yet.</p>;
  }

  const noClinicalRequests = !timeline.some((e) => e.ehrRequests.length > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      <div>
        <h3 style={{ fontSize: "var(--text-base)", marginBottom: "var(--space-sm)" }}>Identity chain</h3>
        <div className="code-value" style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-sm)", alignItems: "center" }}>
          <span style={{ display: "flex", alignItems: "center", color: "var(--color-muted-foreground)" }}>
            <DocumentStackIcon size={16} />
          </span>
          {identity.chain.map((link, i) => (
            <span key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
              <span className="badge badge-progress">{link}</span>
              {i < identity.chain.length - 1 && <span style={{ color: "var(--color-muted-foreground)" }}>→</span>}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: "var(--text-base)", marginBottom: "var(--space-sm)" }}>Identity checks</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--color-border)" }}>
              <th style={{ padding: "var(--space-sm) 0" }}>Field</th>
              <th>Source A</th>
              <th>Value A</th>
              <th>Source B</th>
              <th>Value B</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {identity.checks.map((check) => (
              <tr
                key={check.field}
                style={{
                  borderBottom: "1px solid var(--color-border)",
                  background: check.passed ? "transparent" : "var(--status-attention-bg)",
                }}
              >
                <td style={{ padding: "var(--space-sm) 0", fontWeight: check.passed ? 400 : 600 }}>
                  {check.field}
                </td>
                <td style={{ color: "var(--color-muted-foreground)" }}>{check.sourceA}</td>
                <td className="code-value">{check.valueA ?? "—"}</td>
                <td style={{ color: "var(--color-muted-foreground)" }}>{check.sourceB}</td>
                <td className="code-value">{check.valueB ?? "—"}</td>
                <td>
                  <span className={`badge ${check.passed ? "badge-success" : "badge-attention"}`}>
                    {check.passed ? <CheckCircleIcon size={16} /> : <XCircleIcon size={16} />}
                    {check.passed ? "Passed" : "Failed"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {noClinicalRequests && (
        <p style={{ color: "var(--color-muted-foreground)", fontStyle: "italic" }}>
          No clinical records were requested.
        </p>
      )}
    </div>
  );
}

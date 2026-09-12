import { Evidence, Policy } from "@/lib/api";

const TYPE_LABELS: Record<string, string> = {
  Coverage: "Coverage",
  Condition: "Condition",
  ServiceRequest: "Order",
  Procedure: "Procedure",
  DiagnosticReport: "X-ray report",
  Observation: "Pain score",
  DocumentReference: "Note",
  MedicationRequest: "Medication",
};

export default function EvidenceTab({ evidence, policy }: { evidence: Evidence | null; policy: Policy | null }) {
  if (!evidence) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>Evidence has not been gathered yet.</p>;
  }

  const included = evidence.items.filter((i) => i.included);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      {policy && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>{policy.label}</p>
      )}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid var(--color-border)" }}>
            <th style={{ padding: "var(--space-sm) 0" }}>Type</th>
            <th>Record</th>
            <th>Source</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {included.map((item) => (
            <tr key={item.resource} style={{ borderBottom: "1px solid var(--color-border)" }}>
              <td style={{ padding: "var(--space-sm) 0" }}>{TYPE_LABELS[item.resourceType] ?? item.resourceType}</td>
              <td className="code-value">{item.resource}</td>
              <td style={{ color: "var(--color-muted-foreground)" }}>{item.summary}</td>
              <td className="code-value">{item.date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>
        <p style={{ margin: "2px 0" }}>{evidence.excludedLine}</p>
        <p style={{ margin: "2px 0" }}>MedicationRequest: {evidence.searchCounts["MedicationRequest"] ?? 0} found</p>
      </div>
    </div>
  );
}

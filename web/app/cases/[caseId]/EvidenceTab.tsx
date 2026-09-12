import { Evidence, EvidenceItem, Policy } from "@/lib/api";
import StatCards, { StatCardSpec } from "../../components/StatCards";
import { CheckCircleIcon, XCircleIcon, DocumentStackIcon } from "../../components/icons";

// Short abbreviation + a distinct neutral/blue/purple/teal color per FHIR resourceType, for the
// small doc-icon square. Deliberately not reusing green/amber/red — those are the status-badge
// palette (see design-system/reclaim/MASTER.md) and already mean something else in this app.
const TYPE_ICON: Record<string, { abbr: string; bg: string }> = {
  Coverage: { abbr: "COV", bg: "#0369A1" },
  Condition: { abbr: "CND", bg: "#7C3AED" },
  ServiceRequest: { abbr: "ORD", bg: "#0891B2" },
  Procedure: { abbr: "PROC", bg: "#4F46E5" },
  DiagnosticReport: { abbr: "DX", bg: "#1D4ED8" },
  Observation: { abbr: "OBS", bg: "#0D9488" },
  DocumentReference: { abbr: "DOC", bg: "#475569" },
  MedicationRequest: { abbr: "RX", bg: "#6D28D9" },
};

function docIconFor(resourceType: string): { abbr: string; bg: string } {
  return TYPE_ICON[resourceType] ?? { abbr: resourceType.slice(0, 4).toUpperCase(), bg: "#475569" };
}

// .doc-sub combines the human summary with the record date, e.g. "Condition · 2026-05-28".
function docSubLine(item: EvidenceItem): string {
  return item.date ? `${item.summary} · ${item.date}` : item.summary;
}

export default function EvidenceTab({ evidence, policy }: { evidence: Evidence | null; policy: Policy | null }) {
  if (!evidence) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>Evidence has not been gathered yet.</p>;
  }

  const includedCount = evidence.items.filter((i) => i.included).length;
  const excludedCount = evidence.items.filter((i) => !i.included).length;
  const medicationCount = evidence.searchCounts["MedicationRequest"] ?? 0;

  const stats: StatCardSpec[] = [
    { key: "included", icon: <CheckCircleIcon size={16} />, label: "Included", value: includedCount },
    { key: "excluded", icon: <XCircleIcon size={16} />, label: "Excluded", value: excludedCount },
    { key: "medications", icon: <DocumentStackIcon size={16} />, label: "Medications found", value: medicationCount },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      {policy && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>{policy.label}</p>
      )}

      <StatCards stats={stats} />

      <div>
        {evidence.items.map((item) => {
          const { abbr, bg } = docIconFor(item.resourceType);
          return (
            <div
              key={item.resource}
              className="doc-row"
              style={item.included ? undefined : { opacity: 0.6 }}
              title={!item.included ? item.exclusionReason ?? undefined : undefined}
            >
              <div className="doc-icon" style={{ background: bg }}>
                {abbr}
              </div>
              <div className="doc-meta">
                <div className="doc-name code-value">{item.resource}</div>
                <div className="doc-sub">{docSubLine(item)}</div>
              </div>
              <span className="doc-status-icon">
                {item.included ? <CheckCircleIcon size={20} /> : <XCircleIcon size={20} />}
              </span>
            </div>
          );
        })}
      </div>

      <div style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>
        <p style={{ margin: "2px 0" }}>{evidence.excludedLine}</p>
        <p style={{ margin: "2px 0" }}>MedicationRequest: {medicationCount} found</p>
      </div>
    </div>
  );
}

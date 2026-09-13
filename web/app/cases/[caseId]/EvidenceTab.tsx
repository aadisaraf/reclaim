import { useState } from "react";
import { Evidence, EvidenceItem, Policy } from "@/lib/api";
import StatCards, { StatCardSpec } from "../../components/StatCards";
import { CheckCircleIcon, XCircleIcon, DocumentStackIcon, MoreIcon } from "../../components/icons";

// Short abbreviation + a distinct neutral/blue/purple/teal color per FHIR resourceType, for the
// small doc-icon square. Deliberately not reusing green/amber/red — those are the status-badge
// palette (see the CSS custom properties in globals.css) and already mean something else in this app.
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
  const [activeSubtab, setActiveSubtab] = useState<"all" | "excluded">("all");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (!evidence) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>Evidence has not been gathered yet.</p>;
  }

  const includedCount = evidence.items.filter((i) => i.included).length;
  const excludedCount = evidence.items.filter((i) => !i.included).length;
  const medicationCount = evidence.searchCounts["MedicationRequest"] ?? 0;

  const stats: StatCardSpec[] = [
    { key: "included", icon: <CheckCircleIcon size={16} />, label: "Included", value: includedCount, iconTone: "success" },
    { key: "excluded", icon: <XCircleIcon size={16} />, label: "Excluded", value: excludedCount, iconTone: "attention" },
    { key: "medications", icon: <DocumentStackIcon size={16} />, label: "Medications found", value: medicationCount },
  ];

  const visibleItems = activeSubtab === "all" ? evidence.items : evidence.items.filter((i) => !i.included);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      {policy && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>{policy.label}</p>
      )}

      <StatCards stats={stats} />

      <div className="subtabs" role="tablist">
        <button
          type="button"
          className="subtab"
          role="tab"
          aria-selected={activeSubtab === "all"}
          onClick={() => setActiveSubtab("all")}
        >
          All
        </button>
        <button
          type="button"
          className="subtab"
          role="tab"
          aria-selected={activeSubtab === "excluded"}
          onClick={() => setActiveSubtab("excluded")}
        >
          Excluded
        </button>
      </div>

      {activeSubtab === "excluded" && excludedCount === 0 ? (
        <p style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>Nothing was excluded.</p>
      ) : (
        <div>
          {visibleItems.map((item) => {
            const { abbr, bg } = docIconFor(item.resourceType);
            const isExpanded = expandedRow === item.resource;
            const hasDetail = Boolean(item.sourceUrl || item.document || item.text);
            return (
              <div key={item.resource}>
                <div
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
                  <button
                    type="button"
                    aria-label={isExpanded ? "Hide details" : "Show details"}
                    aria-expanded={isExpanded}
                    onClick={() => setExpandedRow(isExpanded ? null : item.resource)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "4px",
                      color: "var(--color-muted-foreground)",
                      flexShrink: 0,
                    }}
                  >
                    <MoreIcon size={16} />
                  </button>
                </div>
                {isExpanded && hasDetail && (
                  <div
                    style={{
                      marginTop: "calc(-1 * var(--space-sm))",
                      marginLeft: "calc(38px + var(--space-md))",
                      marginBottom: "var(--space-sm)",
                      borderTop: "1px solid var(--color-border)",
                      paddingTop: "var(--space-sm)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "var(--space-xs)",
                    }}
                  >
                    <p style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)", margin: 0 }}>
                      Source: <span className="code-value">{item.sourceUrl}</span>
                    </p>
                    {item.document && (
                      <p style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)", margin: 0 }}>
                        Document: <span className="code-value">{item.document}</span>
                      </p>
                    )}
                    {item.text && (
                      <p style={{ fontSize: "var(--text-sm)", fontStyle: "italic", margin: 0 }}>{item.text}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>
        <p style={{ margin: "2px 0" }}>{evidence.excludedLine}</p>
        <p style={{ margin: "2px 0" }}>MedicationRequest: {medicationCount} found</p>
      </div>
    </div>
  );
}

import { AiCost, TimelineEvent } from "@/lib/api";
import { DocumentStackIcon } from "../../components/icons";

export default function TimelineTab({
  timeline,
  aiCost,
}: {
  timeline: TimelineEvent[];
  aiCost: AiCost | null;
}) {
  if (timeline.length === 0) {
    return <p style={{ color: "var(--color-muted-foreground)" }}>No audit events yet.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      {aiCost && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>{aiCost.line}</p>
      )}
      <div>
        {timeline.map((event, i) => (
          <div key={i} className="timeline-row" style={{ alignItems: "flex-start" }}>
            <span
              style={{
                display: "flex",
                alignItems: "center",
                color: "var(--color-muted-foreground)",
                marginTop: "2px",
                flexShrink: 0,
              }}
            >
              <DocumentStackIcon size={16} />
            </span>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch", flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-md)" }}>
                <span style={{ fontWeight: 600 }}>{event.step}</span>
                <span className="code-value" style={{ color: "var(--color-muted-foreground)" }}>
                  {event.createdAt}
                </span>
              </div>
              <p style={{ margin: "var(--space-xs) 0 0" }}>{event.summary}</p>
              {event.ehrRequests.length > 0 && (
                <ul style={{ margin: "var(--space-xs) 0 0", paddingLeft: "var(--space-lg)" }}>
                  {event.ehrRequests.map((req, j) => (
                    <li key={j} className="code-value" style={{ fontSize: "var(--text-xs)" }}>
                      {req}
                    </li>
                  ))}
                </ul>
              )}
              {event.llmUsage && (
                <p
                  style={{
                    margin: "var(--space-xs) 0 0",
                    fontSize: "var(--text-xs)",
                    color: "var(--color-muted-foreground)",
                  }}
                >
                  {event.llmUsage.line}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

import { ReactNode } from "react";

export interface StatCardSpec {
  key: string;
  icon?: ReactNode;
  label: string;
  value: string | number;
  ofValue?: string | number;
  iconTone?: "neutral" | "success" | "attention";
}

// Generic stat-card row (cloned from the reference "Docs Owned / Pending Reviews / Accepted"
// row). Feed it whatever real counts a tab has — it renders nothing else.
export default function StatCards({ stats }: { stats: StatCardSpec[] }) {
  if (stats.length === 0) return null;
  return (
    <div className="stat-card-row">
      {stats.map((s) => {
        const tone = s.iconTone ?? "neutral";
        return (
        <div key={s.key} className="stat-card">
          <div className="stat-card-label">
            <span className={`stat-card-icon-circle ${tone !== "neutral" ? tone : ""}`}>{s.icon}</span>
            <span>{s.label}</span>
          </div>
          <div className="stat-card-value">
            {s.value}
            {s.ofValue !== undefined && <span className="stat-card-value-of">/{s.ofValue}</span>}
          </div>
        </div>
        );
      })}
    </div>
  );
}

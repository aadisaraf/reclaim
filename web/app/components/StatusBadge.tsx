import { CaseStatus } from "@/lib/api";

// Groups the 11 CaseStatus values into 4 semantic buckets (design-system/reclaim/MASTER.md
// "Status Badge Colors") so the queue is scannable without memorizing 11 distinct colors.
const BUCKETS: Record<CaseStatus, "progress" | "attention" | "success" | "muted"> = {
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

const LABELS: Record<CaseStatus, string> = {
  new: "New",
  "claim-matched": "Claim matched",
  "needs-review": "Needs review",
  "evidence-gathered": "Evidence gathered",
  "needs-evidence": "Needs evidence",
  "ready-for-review": "Ready for review",
  approved: "Approved",
  submitted: "Submitted",
  "in-review": "In review",
  paid: "Paid",
  "other-denial": "Other denial",
};

export default function StatusBadge({ status }: { status: CaseStatus }) {
  const bucket = BUCKETS[status] ?? "progress";
  return <span className={`badge badge-${bucket}`}>{LABELS[status] ?? status}</span>;
}

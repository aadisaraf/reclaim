"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Queue,
  QUEUE_FILTERS,
  QueueFilterKey,
  REFRESH_CONFIG_EVENT,
  getConfig,
  getQueue,
  matchesQueueFilter,
  resetDemo,
  setMissingEvidence,
  simulateRemit,
} from "@/lib/api";
import StatusBadge from "./components/StatusBadge";

export default function QueuePage() {
  return (
    <Suspense fallback={null}>
      <QueuePageInner />
    </Suspense>
  );
}

function QueuePageInner() {
  const searchParams = useSearchParams();
  const filter = (searchParams.get("filter") as QueueFilterKey | null) ?? "all";
  const [queue, setQueue] = useState<Queue | null>(null);
  const [missingEvidence, setMissingEvidenceState] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshQueue = useCallback(() => {
    getQueue()
      .then(setQueue)
      .catch(() => {
        /* queue poll failure is shown by the header's own API-reachability message */
      });
  }, []);

  useEffect(() => {
    refreshQueue();
    getConfig()
      .then((c) => setMissingEvidenceState(c.missingEvidence))
      .catch(() => {});
    pollRef.current = setInterval(refreshQueue, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refreshQueue]);

  async function onSimulateRemit() {
    setBusy("simulate");
    setMessage(null);
    try {
      const result = await simulateRemit();
      setMessage(`Delivered ${result.delivered}`);
      refreshQueue();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to deliver remit");
    } finally {
      setBusy(null);
    }
  }

  async function onToggleMissingEvidence() {
    setBusy("toggle");
    try {
      const next = !missingEvidence;
      const result = await setMissingEvidence(next);
      setMissingEvidenceState(result.enabled);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to toggle missing-evidence mode");
    } finally {
      setBusy(null);
    }
  }

  async function onResetDemo() {
    if (!window.confirm("Reset the demo? This clears every case, task, and submission.")) {
      return;
    }
    setBusy("reset");
    setMessage(null);
    try {
      await resetDemo();
      setMissingEvidenceState(false);
      setMessage("Demo reset.");
      refreshQueue();
      window.dispatchEvent(new Event(REFRESH_CONFIG_EVENT));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to reset demo");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>
      <div className="card" style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-md)", alignItems: "center" }}>
        <button className="btn-primary" onClick={onSimulateRemit} disabled={busy !== null}>
          {busy === "simulate" ? "Delivering…" : "Simulate incoming remit"}
        </button>
        <label style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={missingEvidence}
            onChange={onToggleMissingEvidence}
            disabled={busy !== null}
          />
          <span style={{ fontSize: "var(--text-sm)" }}>Missing-evidence toggle</span>
        </label>
        <button className="btn-danger-outline" onClick={onResetDemo} disabled={busy !== null}>
          {busy === "reset" ? "Resetting…" : "Reset demo"}
        </button>
        {message && (
          <span style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>
            {message}
          </span>
        )}
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-md)", marginBottom: "var(--space-md)" }}>
          <h2 style={{ fontSize: "var(--text-md)", margin: 0 }}>Case queue</h2>
          <div className="filter-pill-row">
            {QUEUE_FILTERS.map((f) => (
              <Link
                key={f.key}
                href={f.key === "all" ? "/" : `/?filter=${f.key}`}
                className={`filter-pill ${filter === f.key ? "active" : ""}`}
              >
                {f.label}
              </Link>
            ))}
          </div>
        </div>
        {!queue || queue.cases.length === 0 ? (
          <p style={{ color: "var(--color-muted-foreground)" }}>
            No worked cases yet. Click &ldquo;Simulate incoming remit&rdquo; to deliver the sample 835.
          </p>
        ) : queue.cases.filter((c) => matchesQueueFilter(c.status, filter)).length === 0 ? (
          <p style={{ color: "var(--color-muted-foreground)" }}>No cases match this filter.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {queue.cases.filter((c) => matchesQueueFilter(c.status, filter)).map((c) => (
              <Link
                key={c.caseId}
                href={`/cases/${encodeURIComponent(c.caseId)}`}
                className="card"
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  textDecoration: "none",
                  color: "inherit",
                }}
              >
                <span>{c.headline}</span>
                <span style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
                  {c.running && (
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-muted-foreground)" }}>
                      Updating…
                    </span>
                  )}
                  <StatusBadge status={c.status} />
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      {queue && queue.summary.lines.length > 0 && (
        <div style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>
          {queue.summary.lines.map((line, i) => (
            <p key={i} style={{ margin: "2px 0" }}>
              {line}
            </p>
          ))}
        </div>
      )}

      {queue && queue.otherLane.length > 0 && (
        <div>
          <h3 style={{ fontSize: "var(--text-base)", color: "var(--color-muted-foreground)", marginBottom: "var(--space-sm)" }}>
            Other lane
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
            {queue.otherLane.map((item) => (
              <div
                key={item.caseId}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "var(--text-sm)",
                  color: "var(--color-muted-foreground)",
                  padding: "var(--space-xs) 0",
                }}
              >
                <span className="code-value">
                  {item.hospitalClaimId} · {item.denialCode} · ${item.amount.toLocaleString()}
                </span>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {queue && queue.remitFiles.length > 0 && (
        <div>
          <h3 style={{ fontSize: "var(--text-base)", color: "var(--color-muted-foreground)", marginBottom: "var(--space-sm)" }}>
            Remit files
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
            {queue.remitFiles.map((f) => (
              <div key={f.fileName} className="code-value" style={{ fontSize: "var(--text-sm)" }}>
                {f.fileName} — {f.status} ({f.claimCount} claims)
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

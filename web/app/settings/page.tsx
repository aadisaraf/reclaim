"use client";

import { useEffect, useState } from "react";
import { Config, getConfig } from "@/lib/api";
import { SettingsIcon } from "../components/icons";

export default function SettingsPage() {
  const [config, setConfig] = useState<Config | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch(() => setError(true));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)", maxWidth: 640 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        <SettingsIcon size={20} />
        <h1 style={{ fontSize: "var(--text-lg)", margin: 0 }}>Settings</h1>
      </div>
      <p style={{ color: "var(--color-muted-foreground)" }}>
        Read-only demo configuration. There is no login and nothing here is editable — this is a
        single-laptop demo, and every value is loaded from <code className="code-value">.env</code>.
      </p>

      {error && (
        <p style={{ color: "var(--color-destructive)" }}>Could not reach the API to load configuration.</p>
      )}

      {config && (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          <Row label="Demo date" value={config.demoDate} />
          <Row label="AI mode" value={config.aiMode} />
          <Row label="Model" value={config.model} />
          <Row label="Missing-evidence toggle" value={config.missingEvidence ? "on" : "off"} />
          <Row label="Clearinghouse base URL" value={config.baseUrls.clearinghouse} />
          <Row label="EHR base URL" value={config.baseUrls.ehr} />
          <Row label="Payer base URL" value={config.baseUrls.payer} />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-md)", borderBottom: "1px solid var(--color-border)", paddingBottom: "var(--space-sm)" }}>
      <span style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-sm)" }}>{label}</span>
      <span className="code-value">{value}</span>
    </div>
  );
}

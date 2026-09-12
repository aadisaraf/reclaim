"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Config,
  Persona,
  getConfig,
  listPersonas,
  loadStoredPersona,
  storePersona,
} from "@/lib/api";

// Dispatched by page.tsx after a successful "Reset demo" so the header's base-URL /
// AI-mode display refreshes without a full page reload (T114).
export const REFRESH_CONFIG_EVENT = "reclaim:refresh-config";
// Dispatched whenever the persona picker changes, so other components (PacketTab's
// "Approve and submit") can react without a shared context.
export const PERSONA_CHANGED_EVENT = "reclaim:persona-changed";

export function currentPersona(): string {
  return loadStoredPersona() ?? "billing-approver-01";
}

export default function Header() {
  const [config, setConfig] = useState<Config | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<string>("billing-approver-01");
  const [loadError, setLoadError] = useState(false);

  const refreshConfig = useCallback(() => {
    getConfig()
      .then(setConfig)
      .catch(() => setLoadError(true));
  }, []);

  useEffect(() => {
    refreshConfig();
    listPersonas()
      .then(setPersonas)
      .catch(() => setLoadError(true));
    setPersona(currentPersona());

    window.addEventListener(REFRESH_CONFIG_EVENT, refreshConfig);
    return () => window.removeEventListener(REFRESH_CONFIG_EVENT, refreshConfig);
  }, [refreshConfig]);

  function onPersonaChange(userId: string) {
    setPersona(userId);
    storePersona(userId);
    window.dispatchEvent(new CustomEvent(PERSONA_CHANGED_EVENT, { detail: userId }));
  }

  return (
    <header>
      <div className="synthetic-banner">Synthetic demo data — no real patients or claims</div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "var(--space-md)",
          padding: "var(--space-md) var(--space-xl)",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-card)",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-lg)" }}>
          <a href="/" style={{ fontWeight: 700, fontSize: "var(--text-md)", textDecoration: "none" }}>
            Reclaim
          </a>
          {config && (
            <span className="code-value" style={{ color: "var(--color-muted-foreground)" }}>
              Demo date: {config.demoDate}
            </span>
          )}
          {config && (
            <span
              className="badge badge-progress"
              title={`Model: ${config.model}`}
            >
              AI: {config.aiMode}
            </span>
          )}
          {loadError && (
            <span style={{ color: "var(--color-destructive)", fontSize: "var(--text-sm)" }}>
              Could not reach the API at {process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-lg)" }}>
          {config && (
            <div
              className="code-value"
              style={{
                fontSize: "var(--text-xs)",
                color: "var(--color-muted-foreground)",
                textAlign: "right",
                maxWidth: 260,
              }}
            >
              {(
                [
                  ["clearinghouse", config.baseUrls.clearinghouse],
                  ["ehr", config.baseUrls.ehr],
                  ["payer", config.baseUrls.payer],
                ] as const
              ).map(([label, url]) => (
                <div
                  key={label}
                  title={`${label}: ${url}`}
                  style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                >
                  {label}: {url}
                </div>
              ))}
            </div>
          )}
          <label style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>
              Persona
            </span>
            <select
              className="select"
              value={persona}
              onChange={(e) => onPersonaChange(e.target.value)}
            >
              {(personas.length
                ? personas
                : [
                    { userId: "billing-approver-01", role: "authorized-billing-user", canApprove: true },
                    { userId: "viewer-01", role: "viewer", canApprove: false },
                  ]
              ).map((p) => (
                <option key={p.userId} value={p.userId}>
                  {p.userId} ({p.role})
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </header>
  );
}

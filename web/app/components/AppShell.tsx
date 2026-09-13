"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Config,
  Persona,
  QUEUE_FILTERS,
  currentPersona,
  getConfig,
  listPersonas,
  storePersona,
  REFRESH_CONFIG_EVENT,
  PERSONA_CHANGED_EVENT,
} from "@/lib/api";
import {
  BellIcon,
  ChevronDownIcon,
  FolderIcon,
  HelpIcon,
  QueueIcon,
  SearchIcon,
  SettingsIcon,
} from "./icons";

// The sidebar's "Cases" section links to /?filter=<key> on the queue page (real client-side
// filtering — see app/page.tsx), not to separate routes; there's exactly one queue.
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [config, setConfig] = useState<Config | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState<string>("billing-approver-01");
  const [loadError, setLoadError] = useState(false);
  const [casesOpen, setCasesOpen] = useState(true);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    function onClickAway(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  function onPersonaChange(userId: string) {
    setPersona(userId);
    storePersona(userId);
    setUserMenuOpen(false);
    window.dispatchEvent(new CustomEvent(PERSONA_CHANGED_EVENT, { detail: userId }));
  }

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = searchValue.trim();
    if (!trimmed) return;
    // Case IDs are always "case-<digits>"; a bare number or partial claim id both resolve.
    const caseId = trimmed.startsWith("case-") ? trimmed : `case-${trimmed.replace(/\D/g, "")}`;
    router.push(`/cases/${encodeURIComponent(caseId)}`);
    setSearchValue("");
  }

  const activeFilter = searchParams.get("filter") ?? "all";
  const isQueue = pathname === "/";
  const isSettings = pathname === "/settings";
  const isHelp = pathname === "/help";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="sidebar-logo">
          <QueueIcon size={20} />
          Reclaim
        </Link>

        <nav className="sidebar-nav">
          <Link href="/" className={`nav-item ${isQueue && activeFilter === "all" ? "active" : ""}`}>
            <QueueIcon size={16} />
            Overview
          </Link>

          <button className="nav-item" onClick={() => setCasesOpen((v) => !v)} type="button">
            <FolderIcon size={16} />
            Cases
            <span
              style={{
                marginLeft: "auto",
                display: "inline-flex",
                transform: casesOpen ? "rotate(0deg)" : "rotate(-90deg)",
                transition: "transform 150ms ease",
              }}
            >
              <ChevronDownIcon size={12} />
            </span>
          </button>
          {casesOpen &&
            QUEUE_FILTERS.map((f) => (
              <Link
                key={f.key}
                href={f.key === "all" ? "/" : `/?filter=${f.key}`}
                className={`nav-subitem ${isQueue && activeFilter === f.key ? "active" : ""}`}
              >
                {f.label}
              </Link>
            ))}

          <div style={{ marginTop: "auto" }} />
          <Link href="/settings" className={`nav-item ${isSettings ? "active" : ""}`}>
            <SettingsIcon size={16} />
            Settings
          </Link>
          <Link href="/help" className={`nav-item ${isHelp ? "active" : ""}`}>
            <HelpIcon size={16} />
            Help
          </Link>
        </nav>
      </aside>

      <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <div className="topbar">
          <form className="topbar-search" onSubmit={onSearchSubmit}>
            <SearchIcon size={16} />
            <input
              placeholder="Jump to a case (e.g. 100028 or case-100028)"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
            />
          </form>

          {config && (
            <span className="badge badge-progress" title={`Model: ${config.model} · Demo date: ${config.demoDate}`}>
              AI: {config.aiMode}
            </span>
          )}
          {loadError && (
            <span style={{ color: "var(--color-destructive)", fontSize: "var(--text-sm)" }}>
              Could not reach the API
            </span>
          )}

          <div style={{ position: "relative" }} ref={notifRef}>
            <button
              onClick={() => setNotifOpen((v) => !v)}
              type="button"
              aria-haspopup="menu"
              aria-expanded={notifOpen}
              aria-label="Notifications"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: 999,
                border: "1px solid transparent",
                background: "none",
                color: "var(--color-muted-foreground)",
                cursor: "pointer",
              }}
            >
              <BellIcon size={18} />
            </button>
            {notifOpen && (
              <div className="dropdown-menu" style={{ right: 0, left: "auto", minWidth: 220 }}>
                <p style={{ margin: "var(--space-sm)", fontSize: "var(--text-sm)", color: "var(--color-muted-foreground)" }}>
                  No notifications. This demo has no notification system — cases update live on the
                  queue and case pages instead.
                </p>
              </div>
            )}
          </div>

          <div style={{ position: "relative" }} ref={userMenuRef}>
            <button
              className="user-menu"
              onClick={() => setUserMenuOpen((v) => !v)}
              title={persona}
              type="button"
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
              aria-label={`Persona: ${persona}`}
            >
              <div className="avatar-circle bucket-progress" style={{ width: 32, height: 32, fontSize: "var(--text-xs)" }}>
                {persona
                  .split("-")
                  .map((w) => w[0])
                  .slice(0, 2)
                  .join("")
                  .toUpperCase()}
              </div>
              <ChevronDownIcon size={14} />
            </button>
            {userMenuOpen && (
              <div className="user-menu-dropdown" role="menu">
                <div className="user-menu-dropdown-label">Persona</div>
                {(personas.length
                  ? personas
                  : [
                      { userId: "billing-approver-01", role: "authorized-billing-user", canApprove: true },
                      { userId: "viewer-01", role: "viewer", canApprove: false },
                    ]
                ).map((p) => (
                  <button
                    key={p.userId}
                    className="user-menu-dropdown-item"
                    onClick={() => onPersonaChange(p.userId)}
                    style={{ fontWeight: p.userId === persona ? 600 : 400, width: "100%", border: "none", background: "none", cursor: "pointer" }}
                    type="button"
                    role="menuitemradio"
                    aria-checked={p.userId === persona}
                  >
                    <span>{p.userId}</span>
                    <span style={{ color: "var(--color-muted-foreground)", fontSize: "var(--text-xs)" }}>{p.role}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <main style={{ padding: "var(--space-xl)", flex: 1 }}>{children}</main>
      </div>
    </div>
  );
}

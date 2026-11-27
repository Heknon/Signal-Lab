import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronRight, ExternalLink, FlaskConical, Layers, Moon, PanelLeft, Search, Sun, Monitor } from "lucide-react";
import { stackStatus, useLab } from "../context";
import { modKey } from "../lib/hooks";
import { BackendLogo, useClickOutside } from "./ui";

export function Logo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden>
      <path d="M3 18h6l3-9 5 15 3-10 2 4h7" fill="none" stroke="var(--accent)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type Theme = "system" | "dark" | "light";
function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) || "system");
  const cycle = () => {
    const next: Theme = theme === "system" ? "dark" : theme === "dark" ? "light" : "system";
    setTheme(next);
    if (next === "system") { delete document.documentElement.dataset.theme; try { localStorage.removeItem("sl-theme"); } catch { /* ignore */ } }
    else { document.documentElement.dataset.theme = next; try { localStorage.setItem("sl-theme", next); } catch { /* ignore */ } }
  };
  return [theme, cycle];
}

export default function TopBar({ crumbs, onToggleSidebar }: { crumbs?: { label: string; to?: string; hideSm?: boolean }[]; onToggleSidebar?: () => void }) {
  const { meta, health, setPaletteOpen, setScenarioOpen } = useLab();
  const [theme, cycleTheme] = useTheme();
  const [stackOpen, setStackOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(stackOpen, () => setStackOpen(false));
  const items = stackStatus(meta, health);
  const loc = useLocation();
  const bad = items.filter((i) => i.ok === false).length;

  return (
    <header className="topbar">
      {onToggleSidebar && (
        <button className="icon-btn" onClick={onToggleSidebar} title="Toggle outline ([)" aria-label="Toggle course outline"><PanelLeft /></button>
      )}
      <Link to="/" className="brand" aria-label="Signal Lab home">
        <span className="brand-mark"><Logo /></span>
        <span>Signal Lab</span>
      </Link>
      {crumbs && crumbs.length > 0 && (
        <nav className="crumbs" aria-label="Breadcrumb">
          {crumbs.map((c, i) => (
            <span key={i} className={`row ${c.hideSm ? "hide-sm" : ""}`} style={{ gap: 6, minWidth: 0 }}>
              <ChevronRight />
              {c.to && i < crumbs.length - 1 ? <Link to={c.to}>{c.label}</Link> : <span className={i === crumbs.length - 1 ? "current" : ""}>{c.label}</span>}
            </span>
          ))}
        </nav>
      )}
      <div className="topbar-right">
        <button className="search-btn" onClick={() => setPaletteOpen(true)} aria-label="Search lessons">
          <Search /><span className="label">Jump to lesson…</span><span className="kbd">{modKey} K</span>
        </button>
        {meta?.scenario && (
          <button className="btn btn-ghost btn-sm scenario-btn" onClick={() => setScenarioOpen(true)} title="Scenario: services, traffic and chaos">
            <FlaskConical /><span>Scenario</span>
          </button>
        )}
        <div ref={ref} style={{ position: "relative" }}>
          <button className="stack-pill" onClick={() => setStackOpen((v) => !v)} aria-expanded={stackOpen} title="Your observability stack">
            <span className="dots">
              {items.map((i) => <span key={i.id} className={`dot ${i.ok == null ? "dot-idle" : i.ok ? "dot-ok" : "dot-err"}`} />)}
            </span>
            <span className="label">{bad ? `${bad} down` : "Stack"}</span>
          </button>
          {stackOpen && meta && (
            <div className="popover" style={{ width: 360 }}>
              <StackSummary onNavigate={() => setStackOpen(false)} />
            </div>
          )}
        </div>
        <button className="icon-btn" onClick={cycleTheme} title={`Theme: ${theme}`} aria-label={`Theme: ${theme}`}>
          {theme === "dark" ? <Moon /> : theme === "light" ? <Sun /> : <Monitor />}
        </button>
        {loc.pathname !== "/stack" && (
          <Link to="/stack" className="icon-btn hide-xs" title="Stack & plugins" aria-label="Stack and plugins"><Layers /></Link>
        )}
      </div>
    </header>
  );
}

function StackSummary({ onNavigate }: { onNavigate: () => void }) {
  const { meta, health } = useLab();
  if (!meta) return null;
  const items = stackStatus(meta, health);
  const groups = [...new Set(items.map((i) => i.group))];
  return (
    <div className="stack" style={{ gap: 2 }}>
      {groups.map((g) => {
        const backend = meta.backends.find((b) => b.title === g);
        return (
          <div key={g} style={{ padding: "6px 8px" }}>
            <div className="row" style={{ marginBottom: 6 }}>
              {backend && <BackendLogo backend={backend} size={18} />}
              <span className="eyebrow" style={{ fontSize: 10.5 }}>{g}</span>
            </div>
            {items.filter((i) => i.group === g).map((i) => (
              <div key={i.id} className="row" style={{ padding: "3px 0", fontSize: 12.5 }}>
                <span className={`dot ${i.ok == null ? "dot-idle" : i.ok ? "dot-ok" : "dot-err"}`} />
                <span>{i.label}</span>
                <span className="subtle" style={{ marginLeft: "auto", fontSize: 11.5 }}>{i.detail}</span>
              </div>
            ))}
            {backend && backend.links.length > 0 && (
              <div className="backend-links" style={{ marginTop: 6 }}>
                {backend.links.slice(0, 3).map((l) => <a key={l.id} href={l.url} target="_blank" rel="noreferrer">{l.label}<ExternalLink /></a>)}
              </div>
            )}
          </div>
        );
      })}
      <div style={{ borderTop: "1px solid var(--border)", marginTop: 4, padding: "8px 8px 2px" }}>
        <Link to="/stack" onClick={onNavigate} className="row muted" style={{ fontSize: 12.5 }}><Layers style={{ width: 14, height: 14 }} />Stack, Collector pipeline &amp; plugins</Link>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FlaskConical, Home, Layers, Moon } from "lucide-react";
import { useLab } from "../context";
import { useHotkey } from "../lib/hooks";
import { lessonState, useProgress } from "../lib/progress";
import { KindLabel, StateIcon } from "./ui";

interface Item { id: string; group: string; label: string; sub?: string; icon?: React.ReactNode; run: () => void; keywords: string }

export default function CommandPalette() {
  const { lessons, paletteOpen, setPaletteOpen, setScenarioOpen, meta } = useLab();
  const p = useProgress();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useHotkey("mod+k", (e) => { e.preventDefault(); setPaletteOpen(!paletteOpen); });
  useEffect(() => { if (paletteOpen) { setQ(""); setSel(0); setTimeout(() => input.current?.focus(), 0); } }, [paletteOpen]);

  const items = useMemo<Item[]>(() => {
    const close = (fn: () => void) => () => { setPaletteOpen(false); fn(); };
    const out: Item[] = lessons.map((l) => ({
      id: l.id,
      group: "Lessons",
      label: l.title,
      sub: `${l.pack.title} · ${l.module.title}`,
      icon: <StateIcon state={lessonState(p, l.id)} />,
      run: close(() => nav(`/learn/${l.id}`)),
      keywords: `${l.title} ${l.summary} ${l.module.title} ${l.pack.title} ${l.concepts.join(" ")}`.toLowerCase(),
    }));
    out.push({ id: "home", group: "Go to", label: "Course overview", icon: <Home />, run: close(() => nav("/")), keywords: "home course overview" });
    out.push({ id: "stack", group: "Go to", label: "Stack, pipeline & plugins", icon: <Layers />, run: close(() => nav("/stack")), keywords: "stack plugins collector pipeline backends" });
    if (meta?.scenario) out.push({ id: "scenario", group: "Actions", label: "Open scenario controls", sub: "traffic & chaos", icon: <FlaskConical />, run: close(() => setScenarioOpen(true)), keywords: "scenario chaos traffic load latency errors" });
    out.push({ id: "theme", group: "Actions", label: "Toggle dark / light", icon: <Moon />, run: close(() => {
      const el = document.documentElement;
      const next = el.dataset.theme === "light" ? "dark" : "light";
      el.dataset.theme = next;
      try { localStorage.setItem("sl-theme", next); } catch { /* ignore */ }
    }), keywords: "theme dark light mode" });
    return out;
  }, [lessons, p, nav, setPaletteOpen, setScenarioOpen, meta]);

  const filtered = useMemo(() => {
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return items;
    return items.filter((i) => terms.every((t) => i.keywords.includes(t) || i.label.toLowerCase().includes(t)));
  }, [items, q]);

  if (!paletteOpen) return null;
  const groups = [...new Set(filtered.map((i) => i.group))];
  const flat = groups.flatMap((g) => filtered.filter((i) => i.group === g));

  return (
    <>
      <div className="scrim" onClick={() => setPaletteOpen(false)} />
      <div className="palette" role="dialog" aria-label="Command palette">
        <input
          ref={input}
          value={q}
          placeholder="Search lessons, concepts, actions…"
          onChange={(e) => { setQ(e.target.value); setSel(0); }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setPaletteOpen(false);
            else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(flat.length - 1, s + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
            else if (e.key === "Enter") flat[sel]?.run();
          }}
          aria-activedescendant={flat[sel]?.id}
        />
        <div className="palette-list" role="listbox">
          {flat.length === 0 && <div className="empty" style={{ minHeight: 80 }}>No matches</div>}
          {groups.map((g) => (
            <div key={g}>
              <div className="palette-group">{g}</div>
              {filtered.filter((i) => i.group === g).map((i) => {
                const idx = flat.indexOf(i);
                const l = lessons.find((x) => x.id === i.id);
                return (
                  <div key={i.id} id={i.id} role="option" aria-selected={idx === sel} className="palette-item" onMouseMove={() => setSel(idx)} onClick={i.run}>
                    {i.icon}
                    <span>{i.label}</span>
                    {l && <KindLabel kind={l.kind} />}
                    {i.sub && <span className="sub">{i.sub}</span>}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="palette-foot"><span><span className="kbd">↑↓</span> navigate</span><span><span className="kbd">↵</span> open</span><span><span className="kbd">esc</span> close</span></div>
      </div>
    </>
  );
}

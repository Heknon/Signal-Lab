import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { CheckCircle2 } from "lucide-react";
import { api, type Health, type LessonOutline, type Meta, type Module, type Pack } from "./api";
import { useAsync } from "./lib/hooks";

export interface FlatLesson extends LessonOutline { pack: Pack; module: Module; index: number }

interface LabContextValue {
  meta?: Meta;
  health?: Health;
  course: Pack[];
  lessons: FlatLesson[];
  findLesson: (id: string) => FlatLesson | undefined;
  scenarioOpen: boolean;
  setScenarioOpen: (v: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  toast: (msg: string) => void;
  error?: Error;
}

const Ctx = createContext<LabContextValue | null>(null);

export function LabProvider({ children }: { children: ReactNode }) {
  const meta = useAsync(api.meta, []);
  const health = useAsync(api.health, [], 5000);
  const course = useAsync(api.course, []);
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [toasts, setToasts] = useState<{ id: number; msg: string }[]>([]);

  const toast = useCallback((msg: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  const lessons = useMemo(() => {
    const out: FlatLesson[] = [];
    for (const pack of course.data ?? []) for (const module of pack.modules) for (const l of module.lessons) out.push({ ...l, pack, module, index: out.length });
    return out;
  }, [course.data]);
  const byId = useMemo(() => new Map(lessons.map((l) => [l.id, l])), [lessons]);

  const value: LabContextValue = {
    meta: meta.data,
    health: health.data,
    course: course.data ?? [],
    lessons,
    findLesson: (id) => byId.get(id),
    scenarioOpen, setScenarioOpen,
    paletteOpen, setPaletteOpen,
    toast,
    error: meta.error ?? course.error,
  };
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className="toast"><CheckCircle2 />{t.msg}</div>)}
      </div>
    </Ctx.Provider>
  );
}

export function useLab() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLab outside LabProvider");
  return v;
}

/** Overall health of the stack, for status dots. */
export function stackStatus(meta?: Meta, health?: Health) {
  const items: { id: string; label: string; ok: boolean | null; detail: string; group: string }[] = [];
  if (!meta) return items;
  items.push({ id: "collector", label: health?.collector.mode === "direct" ? "Lab tap (direct)" : "OTel Collector", ok: health ? health.collector.ok : null, detail: health?.collector.detail ?? "checking…", group: "Pipeline" });
  for (const b of meta.backends.filter((x) => x.enabled)) {
    for (const c of b.components) {
      const h = health?.backends[b.id]?.[c.id];
      items.push({ id: `${b.id}:${c.id}`, label: c.title, ok: h ? h.ok : null, detail: h ? `${c.role} · ${h.detail}` : c.role, group: b.title });
    }
  }
  return items;
}

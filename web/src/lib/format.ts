export function fmtDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "–";
  if (ms < 1) return `${(ms * 1000).toFixed(0)} µs`;
  if (ms < 10) return `${ms.toFixed(2)} ms`;
  if (ms < 1000) return `${ms.toFixed(ms < 100 ? 1 : 0)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
  return `${(ms / 60_000).toFixed(1)} min`;
}

export function fmtNumber(v: unknown, digits = 3): string {
  if (typeof v !== "number") return String(v ?? "–");
  if (Number.isInteger(v)) return v.toLocaleString("en-US");
  const abs = Math.abs(v);
  if (abs >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 1 });
  if (abs === 0) return "0";
  if (abs < 0.001) return v.toExponential(2);
  return Number(v.toPrecision(digits + 1)).toString();
}

export function fmtTime(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleTimeString("en-GB", { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

export function shortId(id: string | null | undefined, n = 8): string {
  return id ? id.slice(0, n) : "–";
}

export function fmtValue(v: unknown): { text: string; kind: "str" | "num" | "bool" | "other" } {
  if (typeof v === "string") return { text: JSON.stringify(v), kind: "str" };
  if (typeof v === "number") return { text: String(v), kind: "num" };
  if (typeof v === "boolean") return { text: String(v), kind: "bool" };
  return { text: JSON.stringify(v), kind: "other" };
}

const PALETTE = ["#a78bfa", "#4cc2ff", "#f5b041", "#3ecf8e", "#f472b6", "#fb923c", "#2dd4bf", "#a3e635", "#f87171", "#818cf8"];
export function serviceColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}
export const chartColors = PALETTE;

export function plural(n: number, one: string, many = one + "s"): string {
  return `${n} ${n === 1 ? one : many}`;
}

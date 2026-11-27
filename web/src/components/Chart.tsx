import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { chartColors, fmtNumber } from "../lib/format";

export interface ChartSeries { name: string; points: [number, number][] }

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Time-series line chart (uPlot), themed from CSS variables. */
export default function Chart({ series, height = 220 }: { series: ChartSeries[]; height?: number }) {
  const host = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el || !series.length) return;
    const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p[0])))].sort((a, b) => a - b);
    const data: uPlot.AlignedData = [
      xs.map((x) => x / 1000),
      ...series.map((s) => {
        const m = new Map(s.points.map(([t, v]) => [t, typeof v === "number" ? v : Number(v)]));
        return xs.map((x) => (m.has(x) ? m.get(x)! : null));
      }),
    ];
    const grid = cssVar("--border"), text = cssVar("--text-3");
    const opts: uPlot.Options = {
      width: el.clientWidth,
      height,
      legend: { show: false },
      cursor: { points: { size: 6 }, drag: { x: false, y: false } },
      scales: { x: { time: true } },
      axes: [
        { stroke: text, grid: { stroke: grid, width: 1 }, ticks: { stroke: grid }, font: "11px Inter Variable, sans-serif" },
        { stroke: text, grid: { stroke: grid, width: 1 }, ticks: { show: false }, size: 52, font: "11px Inter Variable, sans-serif", values: (_u, v) => v.map((x) => fmtNumber(x, 2)) },
      ],
      series: [
        {},
        ...series.map((s, i) => ({ label: s.name, stroke: chartColors[i % chartColors.length], width: 1.6, points: { show: false }, spanGaps: true })),
      ],
    };
    plot.current?.destroy();
    plot.current = new uPlot(opts, data, el);
    const ro = new ResizeObserver(() => plot.current?.setSize({ width: el.clientWidth, height }));
    ro.observe(el);
    return () => { ro.disconnect(); plot.current?.destroy(); plot.current = null; };
  }, [series, height]);

  return <div ref={host} style={{ width: "100%" }} />;
}

import type { ReactNode } from "react";
import { classHighlighter, highlightTree } from "@lezer/highlight";
import { parserFor } from "./languages";

export function highlight(code: string, lang: string): ReactNode[] {
  const parser = parserFor(lang);
  if (!parser) return [code];
  const out: ReactNode[] = [];
  let pos = 0;
  const tree = parser.parse(code);
  highlightTree(tree, classHighlighter, (from, to, classes) => {
    if (from > pos) out.push(code.slice(pos, from));
    out.push(<span key={from} className={classes}>{code.slice(from, to)}</span>);
    pos = to;
  });
  if (pos < code.length) out.push(code.slice(pos));
  return out;
}

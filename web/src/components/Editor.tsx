import { useEffect, useRef } from "react";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, placeholder as placeholderExt } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { bracketMatching, indentOnInput, syntaxHighlighting } from "@codemirror/language";
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { classHighlighter } from "@lezer/highlight";
import { python } from "@codemirror/lang-python";
import { yaml } from "@codemirror/lang-yaml";
import { LanguageType, PromQLExtension } from "@prometheus-io/codemirror-promql";
import { esqlLanguage } from "../lib/languages";

const theme = EditorView.theme({
  "&": { height: "100%", fontSize: "13px", backgroundColor: "transparent", color: "var(--text)" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.65", overflow: "auto" },
  ".cm-content": { padding: "12px 0", caretColor: "var(--accent)" },
  ".cm-line": { padding: "0 16px 0 10px" },
  ".cm-gutters": { backgroundColor: "transparent", border: "none", color: "var(--text-3)", paddingLeft: "6px" },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 6px 0 8px", minWidth: "32px", fontSize: "12px" },
  ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--surface-3) 45%, transparent)" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--text-2)" },
  "&.cm-focused": { outline: "none" },
  "&.cm-focused .cm-cursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection": { backgroundColor: "color-mix(in srgb, var(--accent) 22%, transparent) !important" },
  ".cm-matchingBracket": { backgroundColor: "var(--surface-3)", outline: "1px solid var(--border-strong)" },
  ".cm-selectionMatch": { backgroundColor: "color-mix(in srgb, var(--info) 14%, transparent)" },
  ".cm-placeholder": { color: "var(--text-3)" },
  ".cm-tooltip": { backgroundColor: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "8px", boxShadow: "var(--shadow-pop)", overflow: "hidden" },
  ".cm-tooltip-autocomplete > ul": { fontFamily: "var(--font-mono)", fontSize: "12px", maxHeight: "260px" },
  ".cm-tooltip-autocomplete > ul > li": { padding: "3px 10px !important" },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: "var(--surface-3)", color: "var(--text)" },
  ".cm-completionDetail": { color: "var(--text-3)", fontStyle: "normal", marginLeft: "10px" },
  ".cm-panels": { backgroundColor: "var(--surface)", color: "var(--text)" },
  ".cm-panels.cm-panels-bottom": { borderTop: "1px solid var(--border)" },
  ".cm-searchMatch": { backgroundColor: "var(--warn-soft)" },
  ".cm-diagnostic-error": { borderLeftColor: "var(--err)" },
  ".cm-lintRange-error": { backgroundImage: "none", textDecoration: "underline wavy var(--err)" },
});

export type EditorLanguage = "python" | "metricsql" | "promql" | "esql" | "yaml" | "text";

interface Props {
  value: string;
  onChange?: (v: string) => void;
  language: EditorLanguage;
  onRun?: () => void;
  readOnly?: boolean;
  compact?: boolean;
  placeholder?: string;
  promqlUrl?: string;
  autoFocus?: boolean;
}

function languageExtension(lang: EditorLanguage, promqlUrl?: string): Extension {
  switch (lang) {
    case "python": return python();
    case "yaml": return yaml();
    case "esql": return esqlLanguage;
    case "metricsql":
    case "promql": {
      // MetricsQL is a superset of PromQL: keep PromQL highlighting and completion,
      // but turn the linter off so MetricsQL-only syntax isn't flagged.
      const ext = new PromQLExtension().activateLinter(false);
      if (promqlUrl) ext.setComplete({ remote: { url: promqlUrl, lookbackInterval: 3600_000 } });
      return ext.asExtension(LanguageType.PromQL);
    }
    default: return [];
  }
}

export default function Editor({ value, onChange, language, onRun, readOnly, compact, placeholder, promqlUrl, autoFocus }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const handlers = useRef({ onChange, onRun });
  handlers.current = { onChange, onRun };

  useEffect(() => {
    if (!host.current) return;
    const runKey = keymap.of([
      { key: "Mod-Enter", preventDefault: true, run: () => { handlers.current.onRun?.(); return true; } },
      { key: "Shift-Enter", preventDefault: true, run: () => { if (!compact) return false; handlers.current.onRun?.(); return true; } },
    ]);
    const extensions: Extension[] = [
      runKey,
      history(),
      drawSelection(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      autocompletion({ icons: false }),
      highlightSelectionMatches(),
      syntaxHighlighting(classHighlighter),
      keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...completionKeymap, indentWithTab]),
      languageExtension(language, promqlUrl),
      theme,
      EditorView.updateListener.of((u) => { if (u.docChanged) handlers.current.onChange?.(u.state.doc.toString()); }),
      EditorState.readOnly.of(!!readOnly),
      EditorView.contentAttributes.of({ "aria-label": `${language} editor`, spellcheck: "false" }),
    ];
    if (!compact) extensions.push(lineNumbers(), highlightActiveLine(), highlightActiveLineGutter());
    else extensions.push(EditorView.lineWrapping);
    if (placeholder) extensions.push(placeholderExt(placeholder));
    const v = new EditorView({ state: EditorState.create({ doc: value, extensions }), parent: host.current });
    view.current = v;
    if (autoFocus) v.focus();
    return () => { v.destroy(); view.current = null; };
    // Recreate only when the language or mode changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language, readOnly, compact, promqlUrl]);

  // Keep external value changes (reset, reveal solution) in sync.
  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [value]);

  return <div ref={host} className="editor-host" />;
}

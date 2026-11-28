import { useEffect, useRef } from "react";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView, tooltips, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, placeholder as placeholderExt } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { bracketMatching, indentOnInput, indentUnit, syntaxHighlighting } from "@codemirror/language";
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { classHighlighter } from "@lezer/highlight";
import { python } from "@codemirror/lang-python";
import { yaml } from "@codemirror/lang-yaml";
import { LanguageType, PromQLExtension } from "@prometheus-io/codemirror-promql";
import { esqlLanguage } from "../lib/languages";
import { pythonCompletions, pythonIntelligence } from "../lib/pythonIntel";

const theme = EditorView.theme({
  "&": { height: "100%", fontSize: "13px", backgroundColor: "var(--bg-sunken)", color: "var(--text)" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.65", overflow: "auto" },
  ".cm-content": { padding: "12px 0", caretColor: "var(--accent)" },
  ".cm-line": { padding: "0 16px 0 10px" },
  // Opaque, so code scrolled sideways passes under the line numbers instead of showing through.
  ".cm-gutters": { backgroundColor: "var(--bg-sunken)", border: "none", color: "var(--text-3)", paddingLeft: "6px" },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 6px 0 8px", minWidth: "32px", fontSize: "12px" },
  ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--surface-3) 45%, transparent)" },
  ".cm-activeLineGutter": { backgroundColor: "var(--bg-sunken)", color: "var(--text-2)" },
  "&.cm-focused": { outline: "none" },
  "&.cm-focused .cm-cursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection": { backgroundColor: "color-mix(in srgb, var(--accent) 22%, transparent) !important" },
  ".cm-matchingBracket": { backgroundColor: "var(--surface-3)", outline: "1px solid var(--border-strong)" },
  ".cm-selectionMatch": { backgroundColor: "color-mix(in srgb, var(--info) 14%, transparent)" },
  ".cm-placeholder": { color: "var(--text-3)" },
  // No overflow clipping on tooltips themselves: the completion docs panel is a child
  // of the completion list, drawn beside it, and would be clipped away.
  ".cm-tooltip": { backgroundColor: "var(--surface)", border: "1px solid var(--border-strong)", borderRadius: "8px", boxShadow: "var(--shadow-pop)" },
  ".cm-tooltip-autocomplete > ul": { fontFamily: "var(--font-mono)", fontSize: "12px", maxHeight: "260px", borderRadius: "7px" },
  ".cm-tooltip-autocomplete > ul > li": { padding: "3px 10px !important" },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: "var(--surface-3)", color: "var(--text)" },
  ".cm-completionDetail": { color: "var(--text-3)", fontStyle: "normal", marginLeft: "10px" },
  ".cm-tooltip.cm-completionInfo": { maxWidth: "440px" },
  ".sl-doc": { padding: "8px 11px", maxWidth: "460px", fontSize: "12px", lineHeight: "1.5" },
  ".sl-doc-title": { fontFamily: "var(--font-mono)", color: "var(--text)", whiteSpace: "pre-wrap", wordBreak: "break-word" },
  ".sl-doc-where": { fontFamily: "var(--font-mono)", color: "var(--text-3)", fontSize: "11px", marginTop: "2px" },
  ".sl-doc-body": { color: "var(--text-2)", whiteSpace: "pre-wrap", marginTop: "6px", maxHeight: "220px", overflow: "auto", fontFamily: "var(--font-sans)" },
  ".sl-sig-active": { color: "var(--accent)", fontWeight: "600", textDecoration: "underline", textUnderlineOffset: "3px" },
  ".cm-panels": { backgroundColor: "var(--surface)", color: "var(--text)" },
  ".cm-panels.cm-panels-bottom": { borderTop: "1px solid var(--border)" },
  ".cm-searchMatch": { backgroundColor: "var(--warn-soft)" },
  ".cm-diagnostic-error": { borderLeftColor: "var(--err)" },
  ".cm-lintRange-error": { backgroundImage: "none", textDecoration: "underline wavy var(--err)" },
});

export type EditorLanguage = "python" | "metricsql" | "promql" | "esql" | "logsql" | "yaml" | "text";

interface Props {
  value: string;
  onChange?: (v: string) => void;
  language: EditorLanguage;
  onRun?: () => void;
  /** Ctrl/Cmd+S out of habit: edits autosave anyway, so this just syncs now and
   *  keeps the browser's "save page" dialog away. */
  onSave?: () => void;
  readOnly?: boolean;
  compact?: boolean;
  placeholder?: string;
  promqlUrl?: string;
  autoFocus?: boolean;
  /** Python only: completions, signature help and hover docs from the lab server. */
  intellisense?: boolean;
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

export default function Editor({ value, onChange, language, onRun, onSave, readOnly, compact, placeholder, promqlUrl, autoFocus, intellisense }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const handlers = useRef({ onChange, onRun, onSave });
  handlers.current = { onChange, onRun, onSave };

  useEffect(() => {
    if (!host.current) return;
    const runKey = keymap.of([
      { key: "Mod-Enter", preventDefault: true, run: () => { handlers.current.onRun?.(); return true; } },
      { key: "Mod-s", preventDefault: true, run: () => { handlers.current.onSave?.(); return true; } },
      { key: "Shift-Enter", preventDefault: true, run: () => { if (!compact) return false; handlers.current.onRun?.(); return true; } },
    ]);
    const intel = !!intellisense && language === "python";
    const extensions: Extension[] = [
      runKey,
      history(),
      drawSelection(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      // Python with intellisense: the server's completions replace the language's
      // own (local names and keywords), which Jedi also covers, so nothing is listed twice.
      intel ? autocompletion({ icons: false, override: [pythonCompletions], activateOnTypingDelay: 60 }) : autocompletion({ icons: false }),
      ...(intel ? pythonIntelligence(!readOnly) : []),
      // Tooltips (completion docs, hover, signatures) live at page level so the
      // panes' overflow clipping can't hide them; the theme classes come along.
      tooltips({ parent: document.body }),
      highlightSelectionMatches(),
      syntaxHighlighting(classHighlighter),
      keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...completionKeymap, indentWithTab]),
      languageExtension(language, promqlUrl),
      // CodeMirror's default indent unit is 2 spaces; Python (PEP 8, and every
      // starter here) uses 4, so Enter and Tab must too. YAML keeps 2.
      indentUnit.of(language === "python" ? "    " : "  "),
      EditorState.tabSize.of(language === "python" ? 4 : 2),
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
  }, [language, readOnly, compact, promqlUrl, intellisense]);

  // Keep external value changes (reset, reveal solution) in sync.
  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [value]);

  return <div ref={host} className="editor-host" />;
}

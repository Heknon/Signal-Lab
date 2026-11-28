// Python editor intelligence backed by the lab server (Jedi, see
// server/signal_lab/intellisense.py): completions with signatures and docs,
// a signature hint while typing a call's arguments, and docs on hover.
import { type Completion, type CompletionContext, type CompletionResult } from "@codemirror/autocomplete";
import { StateEffect, StateField, type Extension } from "@codemirror/state";
import { EditorView, ViewPlugin, hoverTooltip, showTooltip, type Tooltip, type ViewUpdate } from "@codemirror/view";

async function ask<T>(path: string, code: string, offset: number, signal?: AbortSignal): Promise<T | null> {
  try {
    const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ code, offset }), signal });
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null; // aborted or offline: no suggestions, never an error in the editor
  }
}

function docNode(title: string, doc?: string, where?: string): HTMLElement {
  const box = document.createElement("div");
  box.className = "sl-doc";
  const head = document.createElement("div");
  head.className = "sl-doc-title";
  head.textContent = title;
  box.appendChild(head);
  if (where) {
    const w = document.createElement("div");
    w.className = "sl-doc-where";
    w.textContent = where;
    box.appendChild(w);
  }
  if (doc) {
    const body = document.createElement("div");
    body.className = "sl-doc-body";
    body.textContent = doc;
    box.appendChild(body);
  }
  return box;
}

// ------------------------------------------------------------- completions

interface CompleteResponse { from: number; items: { label: string; type: string; detail: string; doc: string }[] }

export async function pythonCompletions(ctx: CompletionContext): Promise<CompletionResult | null> {
  const word = ctx.matchBefore(/[A-Za-z_][A-Za-z0-9_]*/);
  const afterDot = ctx.state.sliceDoc(Math.max(0, ctx.pos - 1), ctx.pos) === ".";
  if (!ctx.explicit && !afterDot && !word) return null;
  // Not inside comments or plain strings (but keep import lines and attribute access).
  const line = ctx.state.doc.lineAt(ctx.pos);
  const upto = line.text.slice(0, ctx.pos - line.from);
  if (/#/.test(upto.replace(/(["']).*?\1/g, ""))) return null;
  const controller = new AbortController();
  ctx.addEventListener("abort", () => controller.abort());
  const res = await ask<CompleteResponse>("/api/code/complete", ctx.state.doc.toString(), ctx.pos, controller.signal);
  if (!res || ctx.aborted || !res.items.length) return null;
  const options: Completion[] = res.items.map((i, rank) => {
    // "set_attribute(key: str, …)" next to "set_attribute": show just the "(key: str, …)" part.
    const detail = i.detail.startsWith(i.label + "(") ? i.detail.slice(i.label.length) : i.detail;
    return {
    label: i.label,
    type: i.type,
    detail: detail.length > 56 ? detail.slice(0, 55) + "…" : detail,
    info: i.doc || (i.detail.length > 60) ? () => docNode(i.detail || i.label, i.doc) : undefined,
    boost: -rank / 1000, // keep Jedi's ranking
    };
  });
  return { from: res.from, options, validFor: /^[A-Za-z0-9_]*$/ };
}

// ---------------------------------------------------------------- hover

const hover = hoverTooltip(async (view, pos) => {
  const word = view.state.wordAt(pos);
  if (!word) return null;
  const res = await ask<{ hover: { title: string; where: string; doc: string } | null }>("/api/code/hover", view.state.doc.toString(), pos);
  if (!res?.hover) return null;
  const h = res.hover;
  return { pos: word.from, end: word.to, above: true, create: () => ({ dom: docNode(h.title, h.doc, h.where) }) };
}, { hoverTime: 350 });

// -------------------------------------------------------- signature help

interface Signature { name: string; params: string[]; index: number | null; returns: string; doc: string }
const setSignature = StateEffect.define<{ pos: number; sig: Signature } | null>();

function signatureDom(sig: Signature): HTMLElement {
  const box = document.createElement("div");
  box.className = "sl-doc sl-sig";
  const head = document.createElement("div");
  head.className = "sl-doc-title";
  head.append(`${sig.name}(`);
  sig.params.forEach((p, i) => {
    if (i) head.append(", ");
    const span = document.createElement("span");
    span.textContent = p;
    if (i === sig.index) span.className = "sl-sig-active";
    head.appendChild(span);
  });
  head.append(")" + (sig.returns ? ` -> ${sig.returns}` : ""));
  box.appendChild(head);
  if (sig.doc) {
    const body = document.createElement("div");
    body.className = "sl-doc-body";
    body.textContent = sig.doc.split("\n\n")[0];
    box.appendChild(body);
  }
  return box;
}

const signatureField = StateField.define<Tooltip | null>({
  create: () => null,
  update(value, tr) {
    for (const e of tr.effects) {
      if (e.is(setSignature)) {
        const v = e.value;
        return v ? { pos: v.pos, above: true, strictSide: true, create: () => ({ dom: signatureDom(v.sig) }) } : null;
      }
    }
    return value && tr.docChanged ? { ...value, pos: tr.changes.mapPos(value.pos) } : value;
  },
  provide: (f) => showTooltip.from(f),
});

const signaturePlugin = ViewPlugin.fromClass(class {
  timer: number | null = null;
  controller: AbortController | null = null;
  constructor(readonly view: EditorView) {}
  update(u: ViewUpdate) {
    if (!u.docChanged && !u.selectionSet) return;
    if (this.timer) window.clearTimeout(this.timer);
    const sel = u.state.selection.main;
    // Only worth asking inside an open call: a "(" before the cursor on this line.
    const line = u.state.doc.lineAt(sel.head);
    const before = line.text.slice(0, sel.head - line.from);
    const open = (before.match(/\(/g) || []).length > (before.match(/\)/g) || []).length;
    if (!sel.empty || !u.view.hasFocus || !open) {
      if (u.state.field(signatureField)) queueMicrotask(() => this.view.dispatch({ effects: setSignature.of(null) }));
      return;
    }
    this.timer = window.setTimeout(() => this.fetch(sel.head), 180);
  }
  async fetch(pos: number) {
    this.controller?.abort();
    this.controller = new AbortController();
    const res = await ask<{ signature: Signature | null }>("/api/code/signature", this.view.state.doc.toString(), pos, this.controller.signal);
    if (!res || this.view.state.selection.main.head !== pos) return;
    this.view.dispatch({ effects: setSignature.of(res.signature ? { pos, sig: res.signature } : null) });
  }
  destroy() {
    if (this.timer) window.clearTimeout(this.timer);
    this.controller?.abort();
  }
});

const closeOnEscape = EditorView.domEventHandlers({
  keydown(e, view) {
    if (e.key === "Escape" && view.state.field(signatureField)) {
      view.dispatch({ effects: setSignature.of(null) });
      return false;
    }
    return false;
  },
  blur(_e, view) {
    if (view.state.field(signatureField, false)) queueMicrotask(() => view.dispatch({ effects: setSignature.of(null) }));
    return false;
  },
});

/** Hover docs (also in read-only editors) plus signature help when editable. */
export function pythonIntelligence(editable: boolean): Extension[] {
  return editable ? [hover, signatureField, signaturePlugin, closeOnEscape] : [hover];
}

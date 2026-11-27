// Language support shared by the editor and the static highlighter.
import { StreamLanguage, type StreamParser } from "@codemirror/language";
import { pythonLanguage } from "@codemirror/lang-python";
import { yamlLanguage } from "@codemirror/lang-yaml";
import { LanguageType, promQLLanguage } from "@prometheus-io/codemirror-promql";
import type { Parser } from "@lezer/common";

const ESQL_KEYWORDS = new Set(
  "from where stats by eval sort limit keep drop rename dissect grok enrich mv_expand row show metrics and or not as asc desc like rlike in is null nulls first last on with".split(" "),
);

const esqlParser: StreamParser<unknown> = {
  name: "esql",
  token(stream) {
    if (stream.eatSpace()) return null;
    if (stream.match("//")) { stream.skipToEnd(); return "comment"; }
    if (stream.match(/^"(?:[^"\\]|\\.)*"?/)) return "string";
    if (stream.match(/^`[^`]*`?/)) return "variableName";
    if (stream.match(/^-?\d+(\.\d+)?(e[+-]?\d+)?/i)) return "number";
    if (stream.match(/^(true|false)\b/i)) return "bool";
    if (stream.match("|")) return "keyword";
    if (stream.match(/^[=!<>]=?|^[+\-*/%]/)) return "operator";
    if (stream.match(/^[a-z_][\w.@*]*/i)) {
      const word = stream.current().toLowerCase();
      if (ESQL_KEYWORDS.has(word)) return "keyword";
      if (stream.peek() === "(") return "function";
      return "propertyName";
    }
    stream.next();
    return null;
  },
};
export const esqlLanguage = StreamLanguage.define(esqlParser);

export const promqlLanguage = promQLLanguage(LanguageType.PromQL);

export function parserFor(lang: string): Parser | null {
  switch (lang) {
    case "python": case "py": return pythonLanguage.parser;
    case "yaml": case "yml": return yamlLanguage.parser;
    case "promql": case "metricsql": return promqlLanguage.parser;
    case "esql": return esqlLanguage.parser;
    default: return null;
  }
}

import { Children, isValidElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Info, Lightbulb } from "lucide-react";
import { highlight } from "../lib/highlight";

const CALLOUTS: Record<string, { cls: string; icon: ReactNode }> = {
  NOTE: { cls: "callout-note", icon: <Info /> },
  TIP: { cls: "callout-tip", icon: <Lightbulb /> },
  IMPORTANT: { cls: "callout-note", icon: <Info /> },
  WARNING: { cls: "callout-warning", icon: <AlertTriangle /> },
  CAUTION: { cls: "callout-warning", icon: <AlertTriangle /> },
};

function textOf(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

/** Lesson prose: GitHub-flavoured markdown with `> [!NOTE]` callouts and lezer highlighting. */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          blockquote({ children }) {
            const items = Children.toArray(children).filter((c) => !(typeof c === "string" && !c.trim()));
            const first = items[0];
            const firstText = textOf(first);
            const m = firstText.match(/^\s*\[!(\w+)\]\s*/);
            if (m && CALLOUTS[m[1].toUpperCase()]) {
              const c = CALLOUTS[m[1].toUpperCase()];
              // Strip the marker from the first paragraph.
              let rest = items;
              if (isValidElement<{ children?: ReactNode }>(first)) {
                const kids = Children.toArray(first.props.children);
                if (typeof kids[0] === "string") kids[0] = (kids[0] as string).replace(/^\s*\[!\w+\]\s*/, "");
                rest = [<p key="first">{kids}</p>, ...items.slice(1)];
              }
              return <div className={`callout ${c.cls}`}>{c.icon}<div>{rest}</div></div>;
            }
            return <div className="callout">{children}</div>;
          },
          code({ className, children, ...rest }) {
            const lang = /language-(\w+)/.exec(className ?? "")?.[1];
            const text = String(children).replace(/\n$/, "");
            if (!lang) return <code className={className} {...rest}>{children}</code>;
            return <code className={className}>{highlight(text, lang)}</code>;
          },
          a({ href, children }) {
            const external = href?.startsWith("http");
            return <a href={href} target={external ? "_blank" : undefined} rel={external ? "noreferrer" : undefined}>{children}</a>;
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

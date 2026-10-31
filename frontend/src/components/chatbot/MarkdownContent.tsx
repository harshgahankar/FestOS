import type { ReactNode } from "react";

function renderInline(text: string): ReactNode[] {
  // Parses **bold** and `code` inside a line
  const parts: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index));
    }
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={`b-${match.index}`} className="font-bold text-ink">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(
        <code
          key={`c-${match.index}`}
          className="rounded bg-crimson-dark/10 px-1 py-0.5 font-mono text-[11px] font-semibold text-crimson-deep"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIdx = regex.lastIndex;
  }

  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx));
  }

  return parts.length > 0 ? parts : [text];
}

export function MarkdownContent({ content }: { content: string }) {
  if (!content) return null;

  const lines = content.split("\n");
  const nodes: ReactNode[] = [];
  let inList: "ul" | "ol" | null = null;
  let listItems: ReactNode[] = [];

  const flushList = (key: string) => {
    if (inList === "ul") {
      nodes.push(
        <ul key={key} className="my-2 space-y-1 pl-4 list-disc marker:text-crimson-dark/60 text-[13px] leading-relaxed">
          {listItems}
        </ul>
      );
    } else if (inList === "ol") {
      nodes.push(
        <ol key={key} className="my-2 space-y-1 pl-4 list-decimal marker:text-crimson-dark/60 text-[13px] leading-relaxed">
          {listItems}
        </ol>
      );
    }
    inList = null;
    listItems = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    if (!line) {
      flushList(`flush-${i}`);
      continue;
    }

    // Headers
    if (line.startsWith("### ")) {
      flushList(`flush-${i}`);
      nodes.push(
        <h4 key={`h3-${i}`} className="mt-3 mb-1 font-display text-sm font-bold text-crimson-deep">
          {renderInline(line.slice(4))}
        </h4>
      );
      continue;
    }

    if (line.startsWith("## ")) {
      flushList(`flush-${i}`);
      nodes.push(
        <h3 key={`h2-${i}`} className="mt-3.5 mb-1.5 font-display text-base font-bold text-crimson-deep border-b border-crimson-dark/10 pb-0.5">
          {renderInline(line.slice(3))}
        </h3>
      );
      continue;
    }

    if (line.startsWith("# ")) {
      flushList(`flush-${i}`);
      nodes.push(
        <h2 key={`h1-${i}`} className="mt-4 mb-2 font-display text-lg font-bold text-crimson-deep border-b border-crimson-dark/15 pb-1">
          {renderInline(line.slice(2))}
        </h2>
      );
      continue;
    }

    // Unordered list items (- or * or •)
    if (/^[-*•]\s+/.test(line)) {
      if (inList !== "ul") {
        flushList(`flush-${i}`);
        inList = "ul";
      }
      const itemText = line.replace(/^[-*•]\s+/, "");
      listItems.push(
        <li key={`li-${i}`} className="text-ink/90">
          {renderInline(itemText)}
        </li>
      );
      continue;
    }

    // Ordered list items (1. 2. etc)
    if (/^\d+\.\s+/.test(line)) {
      if (inList !== "ol") {
        flushList(`flush-${i}`);
        inList = "ol";
      }
      const itemText = line.replace(/^\d+\.\s+/, "");
      listItems.push(
        <li key={`oli-${i}`} className="text-ink/90">
          {renderInline(itemText)}
        </li>
      );
      continue;
    }

    // Regular line / paragraph
    flushList(`flush-${i}`);
    nodes.push(
      <p key={`p-${i}`} className="my-1.5 text-[13px] leading-relaxed text-ink/90">
        {renderInline(line)}
      </p>
    );
  }

  flushList("flush-end");

  return <div className="space-y-0.5">{nodes}</div>;
}

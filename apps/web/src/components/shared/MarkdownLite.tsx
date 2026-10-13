import * as React from "react";

/** Minimal markdown rendering (bold, italic, links, line breaks). No external deps. */
export function MarkdownLite({ text }: { text: string }) {
  const html = React.useMemo(() => render(text), [text]);
  return <div className="whitespace-pre-line leading-relaxed" dangerouslySetInnerHTML={{ __html: html }} />;
}

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function render(md: string): string {
  let s = esc(md);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener" class="text-blue-600 underline">$1</a>',
  );
  s = s.replace(
    /(^|\s)(https?:\/\/[^\s<]+)/g,
    '$1<a href="$2" target="_blank" rel="noopener" class="text-blue-600 underline">$2</a>',
  );
  return s;
}

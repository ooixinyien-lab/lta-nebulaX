import React from 'react';

/**
 * Parses inline formatting:
 * - Bold: **text** or __text__
 * - Inline code: `text`
 * - Citations: [A001], [run-123], [PLAT:BET:S15:EB]
 * - Math symbols cleanup: ($P$) -> (P), $P$ -> P
 */
function parseInline(text) {
  if (!text) return null;

  // Clean up raw LaTeX math syntax like ($P$) -> (P) or $P$ -> P
  const clean = text.replace(/\$([A-Za-z0-9_]+)\$/g, '$1');

  // Match bold, inline code, and bracketed citations
  const regex = /(\*\*.*?\*\*|__.*?__|`.*?`|\[[A-Za-z0-9_:\-]+\])/g;
  const parts = clean.split(regex);

  return parts.filter(Boolean).map((part, i) => {
    if ((part.startsWith('**') && part.endsWith('**')) || (part.startsWith('__') && part.endsWith('__'))) {
      const inner = part.slice(2, -2);
      return (
        <strong key={i} className="font-semibold text-slate-100">
          {inner}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      const inner = part.slice(1, -1);
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 mx-0.5 rounded bg-slate-800/80 text-cyan-300 font-mono text-[11px] border border-slate-700/50"
        >
          {inner}
        </code>
      );
    }
    if (part.startsWith('[') && part.endsWith(']')) {
      const inner = part.slice(1, -1);
      return (
        <span
          key={i}
          className="inline-flex items-center px-1.5 py-0.2 mx-0.5 rounded bg-emerald-950/70 text-emerald-300 font-mono text-[11px] border border-emerald-800/50 font-medium"
        >
          {inner}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

/**
 * Parses block-level markdown:
 * - Bullet lists (*, -, •)
 * - Numbered lists (1., 2.)
 * - Headings (#, ##, ###)
 * - Paragraphs
 */
export default function MarkdownContent({ content }) {
  if (!content) return null;

  const lines = content.split(/\r?\n/);
  const blocks = [];
  let currentList = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (currentList) {
        blocks.push(currentList);
        currentList = null;
      }
      continue;
    }

    const bulletMatch = trimmed.match(/^[-*•]\s+(.*)/);
    const numMatch = trimmed.match(/^\d+\.\s+(.*)/);

    if (bulletMatch) {
      if (!currentList || currentList.type !== 'ul') {
        if (currentList) blocks.push(currentList);
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(bulletMatch[1]);
    } else if (numMatch) {
      if (!currentList || currentList.type !== 'ol') {
        if (currentList) blocks.push(currentList);
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(numMatch[1]);
    } else {
      if (currentList) {
        blocks.push(currentList);
        currentList = null;
      }
      if (trimmed.startsWith('### ')) {
        blocks.push({ type: 'h3', text: trimmed.slice(4) });
      } else if (trimmed.startsWith('## ')) {
        blocks.push({ type: 'h2', text: trimmed.slice(3) });
      } else if (trimmed.startsWith('# ')) {
        blocks.push({ type: 'h1', text: trimmed.slice(2) });
      } else {
        blocks.push({ type: 'p', text: trimmed });
      }
    }
  }
  if (currentList) blocks.push(currentList);

  return (
    <div className="space-y-2 text-sm text-slate-200 leading-relaxed">
      {blocks.map((block, idx) => {
        if (block.type === 'ul') {
          return (
            <ul key={idx} className="space-y-1.5 my-1.5 pl-4 list-disc marker:text-cyan-400/80">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx} className="leading-relaxed">
                  {parseInline(item)}
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={idx} className="space-y-1.5 my-1.5 pl-4 list-decimal marker:text-cyan-400/80">
              {block.items.map((item, itemIdx) => (
                <li key={itemIdx} className="leading-relaxed">
                  {parseInline(item)}
                </li>
              ))}
            </ol>
          );
        }
        if (block.type === 'h1') {
          return (
            <h1 key={idx} className="text-base font-bold text-slate-100 pt-1">
              {parseInline(block.text)}
            </h1>
          );
        }
        if (block.type === 'h2') {
          return (
            <h2 key={idx} className="text-sm font-bold text-slate-100 pt-1">
              {parseInline(block.text)}
            </h2>
          );
        }
        if (block.type === 'h3') {
          return (
            <h3 key={idx} className="text-xs font-semibold text-slate-200 uppercase tracking-wider pt-1">
              {parseInline(block.text)}
            </h3>
          );
        }
        return (
          <p key={idx} className="leading-relaxed">
            {parseInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}

import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MarkdownContent from '../components/chatbot/MarkdownContent';

describe('MarkdownContent component', () => {
  it('renders bold text and strips asterisks', () => {
    const { container } = render(<MarkdownContent content="The score is **36.4 points**." />);
    const strong = container.querySelector('strong');
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe('36.4 points');
    expect(container.textContent).not.toContain('**');
  });

  it('renders code badges and strips backticks', () => {
    const { container } = render(<MarkdownContent content="Occupying `PLAT:BET:S15:EB`." />);
    const code = container.querySelector('code');
    expect(code).not.toBeNull();
    expect(code?.textContent).toBe('PLAT:BET:S15:EB');
    expect(container.textContent).not.toContain('`');
  });

  it('cleans up raw LaTeX math syntax ($P$ -> P)', () => {
    const { container } = render(<MarkdownContent content="Weighted Lateness Penalty ($P$): **36.4**" />);
    expect(container.textContent).toContain('(P)');
    expect(container.textContent).not.toContain('$P$');
  });

  it('renders bullet lists as unordered lists with items', () => {
    const markdown = `
Key drivers:
* First item
* Second item
    `.trim();

    const { container } = render(<MarkdownContent content={markdown} />);
    const ul = container.querySelector('ul');
    expect(ul).not.toBeNull();
    const items = container.querySelectorAll('li');
    expect(items.length).toBe(2);
    expect(items[0].textContent).toBe('First item');
    expect(items[1].textContent).toBe('Second item');
  });

  it('renders bracketed citations as badges', () => {
    const { container } = render(<MarkdownContent content="Activity [A001] for contract [C001]." />);
    const citations = container.querySelectorAll('span.font-mono');
    expect(citations.length).toBeGreaterThanOrEqual(2);
    expect(container.textContent).toContain('A001');
    expect(container.textContent).toContain('C001');
  });
});

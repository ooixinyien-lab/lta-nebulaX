import { h, badge } from '../lib/format.js';
export function conflictPanel(issues) {
  return `<section class="panel conflict-panel"><div class="panel-head"><div><h2>Conflict checks</h2><p>Requested times + committed work</p></div>${badge(`${issues.length} issues`,issues.length?'warning':'success')}</div>${issues.length ? `<div class="issue-list">${issues.map((i)=>`<article class="issue"><div class="issue-top">${badge(i.code.replaceAll('_',' '),'warning')}<span>${i.request_ids.map(h).join(' / ')}</span></div><p>${h(i.message)}</p></article>`).join('')}</div>` : '<div class="empty"><strong>No conflicts found</strong><p>Under the encoded synthetic rules only.</p></div>'}</section>`;
}

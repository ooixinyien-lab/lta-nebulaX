// Never insert unescaped user-supplied text into an HTML template.
export const h = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[ch]));
export const time = (iso) => iso ? new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit'
}).format(new Date(iso)) : 'Any time';
export const dateLabel = (iso) => iso ? new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Singapore', day: '2-digit', month: 'short'
}).format(new Date(iso.length === 10 ? `${iso}T12:00:00+08:00` : iso)) : '';
export const duration = (r) => r.phases.reduce((sum, p) => sum + p.duration_minutes, 0);
export function endOf(start, minutes) { return start ? new Date(new Date(start).getTime() + minutes * 60000).toISOString() : null; }
export function nextDate(date) { return new Date(new Date(`${date}T00:00:00Z`).getTime() + 86400000).toISOString().slice(0, 10); }
export const badge = (label, type = '') => `<span class="badge ${h(type)}">${h(label)}</span>`;

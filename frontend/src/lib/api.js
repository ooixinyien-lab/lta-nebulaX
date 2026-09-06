// All HTTP goes through this module. No direct DB or solver calls from a page.
import { headers } from '../auth/session.js';
export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...await headers(), ...options.headers },
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  const result = await response.json();
  if (!response.ok) {
    let detail = result.detail;
    if (Array.isArray(detail)) detail = detail.map((x) => `${x.loc?.join('.') || 'Input'}: ${x.msg}`).join('; ');
    if (detail && typeof detail === 'object') detail = detail.message || JSON.stringify(detail);
    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return result;
}

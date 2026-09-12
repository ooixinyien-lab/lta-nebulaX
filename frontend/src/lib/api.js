// All HTTP goes through this module. No direct DB or solver calls from a page.
import { headers, isUiDemo } from '../auth/session.js?v=20260910-demo2';
export async function api(path, options = {}) {
  if (isUiDemo()) {
    const { demoApi } = await import('./demo-api.js?v=2');
    return demoApi(path, options, (await headers())['X-Demo-User']);
  }
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

/* Auth teammate's module. Public Supabase REST endpoints; no SDK dependency.
   Supabase access/refresh tokens are in memory only: refresh the page -> sign in again.
   The backend independently verifies every Supabase identity and assigns its role.
*/
let config;
let session = null;
let refreshing = null;
export function isUiDemo() { return config?.ui_demo === true; }
export async function loadConfig() {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error('Cannot reach the backend. Start the Python server first.');
  config = await response.json();
  return config;
}
async function exchange(grant, payload) {
  const response = await fetch(`${config.supabase_url.replace(/\/$/, '')}/auth/v1/token?grant_type=${grant}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', apikey: config.supabase_publishable_key },
    body: JSON.stringify(payload)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.msg || result.error_description || 'Sign-in failed');
  session = { access: result.access_token, refresh: result.refresh_token, expires: Date.now() + result.expires_in * 1000 };
}
export function chooseDemo(id) { sessionStorage.setItem('railplan-demo-user', id); }
export async function signIn(email, password) { await exchange('password', { email, password }); }
export async function headers() {
  if (config.auth_mode === 'demo') return { 'X-Demo-User': sessionStorage.getItem('railplan-demo-user') || '' };
  if (!session) return {};
  if (session.expires - Date.now() < 60000) {
    refreshing ??= exchange('refresh_token', { refresh_token: session.refresh }).finally(() => { refreshing = null; });
    await refreshing;
  }
  return { Authorization: `Bearer ${session.access}` };
}
export async function signOut() {
  if (session) {
    try {
      await fetch(`${config.supabase_url.replace(/\/$/, '')}/auth/v1/logout`, {
        method: 'POST', headers: { apikey: config.supabase_publishable_key, Authorization: `Bearer ${session.access}` }
      });
    } catch (_) { /* Still remove the local session even when offline. */ }
  }
  session = null;
  sessionStorage.removeItem('railplan-demo-user');
}
export function canRestoreDemo() { return config.auth_mode === 'demo' && !!sessionStorage.getItem('railplan-demo-user'); }

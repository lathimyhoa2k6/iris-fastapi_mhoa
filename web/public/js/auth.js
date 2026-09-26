// Login state: the JWT from the database API, kept in localStorage.
const KEY = "iris-auth";
const listeners = new Set();

function read() {
  try {
    const data = JSON.parse(localStorage.getItem(KEY) || "null");
    if (data && data.expiresAt && Date.now() > data.expiresAt) return null;
    return data;
  } catch (_) {
    return null;
  }
}

export function getAuth() {
  return read();
}

export function token() {
  return read()?.token || null;
}

export function setAuth(response) {
  const data = {
    token: response.access_token,
    user: response.user,
    expiresAt: Date.now() + (response.expires_in || 0) * 1000,
  };
  try { localStorage.setItem(KEY, JSON.stringify(data)); } catch (_) { /* storage blocked */ }
  listeners.forEach(fn => fn(data));
}

export function clearAuth() {
  try { localStorage.removeItem(KEY); } catch (_) { /* storage blocked */ }
  listeners.forEach(fn => fn(null));
}

export function onAuthChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

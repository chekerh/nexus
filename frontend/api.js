/* Shared API helper for Nexus-UGC v2 */
const API_BASE = '/api/v1';

function getToken() {
  return localStorage.getItem('nexus_token');
}

function isAuthenticated() {
  return !!getToken();
}

function setToken(token) {
  localStorage.setItem('nexus_token', token);
}

function clearToken() {
  localStorage.removeItem('nexus_token');
}

async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = { ...options.headers };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    if (!window.location.pathname.includes('login.html')) {
      window.location.href = '/login.html';
    }
  }
  return res;
}

async function apiJSON(path, options = {}) {
  const res = await api(path, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.error || 'Request failed');
  return data;
}

// Auth helpers
async function login(email, password) {
  const data = await apiJSON('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
  setToken(data.token);
  return data;
}

async function register(email, password, displayName = '') {
  const data = await apiJSON('/auth/register', {
    method: 'POST',
    body: { email, password, display_name: displayName },
  });
  setToken(data.token);
  return data;
}

async function getMe() {
  return apiJSON('/auth/me');
}

function logout() {
  clearToken();
  window.location.href = '/login.html';
}

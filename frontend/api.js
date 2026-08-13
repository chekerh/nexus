/* Shared API helper for Nexus-UGC v2 */
const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
function log(...args) { if (DEV) console.log(...args); }
const API_BASE = '/api/v1';

// In-memory token (not localStorage — more XSS-resistant)
let _token = null;
let _csrfToken = null;
let _csrfFetching = false;
let _csrfQueue = [];

function getToken() {
  return _token;
}

function isAuthenticated() {
  return !!_token;
}

function setToken(token) {
  _token = token;
  // Server also sets httpOnly cookie as secure fallback
}

function clearToken() {
  _token = null;
}

function mediaUrl(path) {
  return `${API_BASE}/media/${path}`;
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || 30000);
  try {
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
    const res = await fetch(url, { ...options, headers, signal: controller.signal });
    if (res.status === 401) {
      clearToken();
      if (!window.location.pathname.includes('login.html') && !window.location.pathname.includes('setup.html')) {
        window.location.href = '/login.html';
      }
    }
    return res;
  } finally {
    clearTimeout(timeout);
  }
}

async function apiJSON(path, options = {}) {
  const res = await api(path, options);
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error('Server returned invalid response');
  }
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

async function register(email, password, displayName = '', inviteKey = '') {
  const data = await apiJSON('/auth/register', {
    method: 'POST',
    body: { email, password, display_name: displayName, invite_key: inviteKey },
  });
  setToken(data.token);
  return data;
}

async function googleAuth(idToken) {
  const data = await apiJSON('/auth/google', {
    method: 'POST',
    body: { id_token: idToken },
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

// Thumbnail API
async function generateThumbnails(jobId, clipIndex, title = '') {
  return apiJSON(`/jobs/${jobId}/thumbnails`, {
    method: 'POST',
    body: { clip_index: clipIndex, title, count: 4 },
  });
}

async function listThumbnails(jobId, clipIndex = null) {
  let path = `/jobs/${jobId}/thumbnails`;
  if (clipIndex !== null) path += `?clip_index=${clipIndex}`;
  return apiJSON(path);
}

async function getThumbnailStats(thumbnailId) {
  return apiJSON(`/thumbnails/${thumbnailId}/stats`);
}

async function trackImpression(thumbnailId) {
  return apiJSON(`/thumbnails/${thumbnailId}/impression`, { method: 'POST' });
}

async function trackClick(thumbnailId) {
  return apiJSON(`/thumbnails/${thumbnailId}/click`, { method: 'POST' });
}

async function declareWinner(thumbnailId) {
  return apiJSON(`/thumbnails/${thumbnailId}/declare-winner`, { method: 'POST' });
}

function thumbnailUrl(thumbnailId) {
  return `${API_BASE}/thumbnails/${thumbnailId}/image`;
}

// Persona API
async function listPersonas() {
  return apiJSON('/personas');
}

async function createPersona(data) {
  return apiJSON('/personas', { method: 'POST', body: data });
}

async function getPersona(id) {
  return apiJSON(`/personas/${id}`);
}

async function updatePersona(id, data) {
  return apiJSON(`/personas/${id}`, { method: 'PUT', body: data });
}

async function deletePersona(id) {
  return apiJSON(`/personas/${id}`, { method: 'DELETE' });
}

async function repurposeContent(personaId, transcript, platforms) {
  return apiJSON(`/personas/${personaId}/repurpose`, {
    method: 'POST',
    body: { transcript, platforms, count_per_platform: 1 },
  });
}

async function listSchedules(personaId) {
  return apiJSON(`/personas/${personaId}/schedules`);
}

async function createSchedule(personaId, data) {
  return apiJSON(`/personas/${personaId}/schedules`, { method: 'POST', body: data });
}

async function deleteSchedule(personaId, scheduleId) {
  return apiJSON(`/personas/${personaId}/schedules/${scheduleId}`, { method: 'DELETE' });
}

// Post Queue API
async function listPosts(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return apiJSON(`/posts${qs ? '?' + qs : ''}`);
}

async function createPost(data) {
  return apiJSON('/posts', { method: 'POST', body: data });
}

async function getPost(id) {
  return apiJSON(`/posts/${id}`);
}

async function updatePost(id, data) {
  return apiJSON(`/posts/${id}`, { method: 'PUT', body: data });
}

async function approvePost(id) {
  return apiJSON(`/posts/${id}/approve`, { method: 'POST' });
}

async function schedulePost(id, scheduledAt) {
  return apiJSON(`/posts/${id}/schedule`, { method: 'POST', body: { scheduled_at: scheduledAt } });
}

async function cancelPost(id) {
  return apiJSON(`/posts/${id}/cancel`, { method: 'POST' });
}

async function deletePost(id) {
  return apiJSON(`/posts/${id}`, { method: 'DELETE' });
}

async function getCalendar(startDate, endDate, personaId) {
  let path = `/calendar?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
  if (personaId) path += `&persona_id=${personaId}`;
  return apiJSON(path);
}

// Publish API
async function publishClip(data) {
  return apiJSON('/publish', { method: 'POST', body: data });
}

// Accounts API
async function listAccounts() {
  return apiJSON('/accounts');
}

// CSRF token support — fetched once, cached in memory
const _origApi = api;
async function getCsrfToken() {
  const res = await _origApi('/auth/csrf-token');
  if (!res.ok) return null;
  const data = await res.json();
  return data.csrf_token;
}

// Override api to add CSRF header to mutating requests
api = async function(path, options = {}) {
  if (options.method && options.method !== 'GET' && options.method !== 'HEAD' && options.method !== 'OPTIONS') {
    if (!_csrfToken) {
      if (!_csrfFetching) {
        _csrfFetching = true;
        _csrfToken = await getCsrfToken();
        _csrfFetching = false;
        _csrfQueue.forEach(r => r());
        _csrfQueue = [];
      } else {
        await new Promise(resolve => _csrfQueue.push(resolve));
      }
    }
    if (_csrfToken) {
      options.headers = { ...options.headers, 'X-CSRF-Token': _csrfToken };
    }
  }
  return _origApi(path, options);
};

// Dashboard Analytics
async function getDashboard() {
  return apiJSON('/analytics/dashboard');
}

// Campaign API
async function listCampaigns() {
  return apiJSON('/campaigns');
}

async function createCampaign(data) {
  return apiJSON('/campaigns', { method: 'POST', body: data });
}

async function getCampaign(id) {
  return apiJSON(`/campaigns/${id}`);
}

async function updateCampaign(id, data) {
  return apiJSON(`/campaigns/${id}`, { method: 'PUT', body: data });
}

async function activateCampaign(id) {
  return apiJSON(`/campaigns/${id}/activate`, { method: 'POST' });
}

async function pauseCampaign(id) {
  return apiJSON(`/campaigns/${id}/pause`, { method: 'POST' });
}

async function deleteCampaign(id) {
  return apiJSON(`/campaigns/${id}`, { method: 'DELETE' });
}

// ── SSE Progress Stream ──
function connectProgressSSE(processId, callbacks = {}) {
  const url = `${API_BASE}/stream/${processId}`;
  const source = new EventSource(url);

  const { onThought, onStage, onProgress, onMessage, onDone, onError } = callbacks;

  source.addEventListener('thought', e => {
    try {
      const data = JSON.parse(e.data);
      onThought?.(data.thought);
    } catch { /* ignore parse errors */ }
  });

  source.addEventListener('stage', e => {
    try {
      const data = JSON.parse(e.data);
      onStage?.(data.stage);
    } catch { /* ignore */ }
  });

  source.addEventListener('progress', e => {
    try {
      const data = JSON.parse(e.data);
      onProgress?.(data.percent);
    } catch { /* ignore */ }
  });

  source.addEventListener('message', e => {
    try {
      const data = JSON.parse(e.data);
      onMessage?.(data.message);
    } catch { /* ignore */ }
  });

  source.addEventListener('done', e => {
    try {
      const data = JSON.parse(e.data);
      onDone?.(data);
    } catch { /* ignore */ }
    source.close();
  });

  source.addEventListener('error', e => {
    onError?.(e);
    source.close();
  });

  source.addEventListener('heartbeat', () => {
    // keepalive — noop
  });

  return source;
}

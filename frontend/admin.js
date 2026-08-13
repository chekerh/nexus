const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
function log(...args) { if (DEV) console.log(...args); }

const PAGES = [
  { hash: 'overview',    label: 'Overview',          icon: '📊' },
  { hash: 'analytics',   label: 'Analytics',         icon: '📈' },
  { hash: 'activity',    label: 'Activity',          icon: '📋' },
  { hash: 'health',      label: 'System Health',     icon: '❤️' },
  { hash: 'brainstorm',  label: 'Feature Brainstorm', icon: '🧠' },
  { hash: 'publishing',  label: 'Publishing',        icon: '📤' },
  { hash: 'users',       label: 'Users',             icon: '👥' },
  { hash: 'invite-keys', label: 'Invite Keys',       icon: '🎫' },
  { hash: 'accounts',    label: 'Accounts',          icon: '🔗' },
  { hash: 'licenses',    label: 'Licenses',          icon: '🔑' },
];

let state = {};

function $(id) { return document.getElementById(id); }

function renderSidebar() {
  $('sidebar-nav').innerHTML = PAGES.map(p => `
    <button class="admin-nav-item" data-hash="${p.hash}">
      <span class="admin-nav-icon">${p.icon}</span> <span class="nav-label">${p.label}</span>
    </button>
  `).join('');
  $('sidebar-nav').addEventListener('click', e => {
    const btn = e.target.closest('.admin-nav-item');
    if (btn && btn.dataset.hash) navigate(btn.dataset.hash);
  });
}

function navigate(hash) {
  window.location.hash = hash;
  renderPage(hash);
}

function getHash() {
  const h = window.location.hash.replace('#', '');
  return h && PAGES.find(p => p.hash === h) ? h : 'overview';
}

function renderPage(hash) {
  document.querySelectorAll('.admin-nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.hash === hash);
  });
  const handlers = { overview, analytics, activity, health, brainstorm, publishing, users, 'invite-keys': inviteKeys, accounts, licenses };
  showSkeleton();
  setTimeout(() => { (handlers[hash] || overview)(); }, 50);
}

function showSkeleton() {
  setContent(`
    <div class="admin-section">
      <div class="skeleton skeleton-text" style="width:200px;height:1.2rem;margin-bottom:1rem;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem;">
        ${Array(4).fill('<div class="skeleton skeleton-card"></div>').join('')}
      </div>
    </div>
  `);
}

// ── Overview ──
async function overview() {
  const data = await fetchData('/api/v1/admin/stats', 'stats');
  if (!data) return;

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Admin <span class="gradient-text">Dashboard</span></h1>
        <p>Overview of your Nexus-UGC instance</p>
      </div>
    </div>
    <div class="stats-grid" id="overview-stats"></div>
    <div class="quick-actions" id="quick-actions"></div>
    <div class="admin-section">
      <div class="admin-section-title">📈 Publishing Summary</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:0.75rem;" id="pub-summary"></div>
    </div>
  `);

  $('overview-stats').innerHTML = [
    { icon: '👤', bg: 'rgba(0,229,255,0.1)', label: 'Total Users',       v: data.total_users },
    { icon: '🎭', bg: 'rgba(139,92,246,0.1)', label: 'Personas',         v: data.total_personas },
    { icon: '📝', bg: 'rgba(251,191,36,0.1)', label: 'Total Posts',      v: data.total_posts },
    { icon: '📋', bg: 'rgba(74,222,128,0.1)', label: 'Campaigns',        v: data.total_campaigns },
    { icon: '🗂️', bg: 'rgba(139,92,246,0.1)', label: 'Templates',        v: data.total_templates },
    { icon: '🔗', bg: 'rgba(248,113,113,0.1)', label: 'Connected Accts',  v: data.total_accounts },
    { icon: '✅', bg: 'rgba(74,222,128,0.1)', label: 'Published OK',     v: data.publish_success },
    { icon: '❌', bg: 'rgba(248,113,113,0.1)', label: 'Published Fail',   v: data.publish_failed },
    { icon: '⏳', bg: 'rgba(251,191,36,0.1)', label: 'Scheduled',        v: data.publish_scheduled },
    { icon: '🔑', bg: 'rgba(139,92,246,0.1)', label: 'Pro Licenses',     v: data.pro_licenses },
    { icon: '💎', bg: 'rgba(251,191,36,0.1)', label: 'Enterprise',       v: data.enterprise_licenses },
    { icon: '📅', bg: 'rgba(74,222,128,0.1)', label: 'Scheduled Posts',  v: data.total_scheduled_posts || 0 },
  ].map(c => `
    <div class="stat-card">
      <div class="stat-card-header">
        <div class="stat-card-icon" style="background:${c.bg}">${c.icon}</div>
      </div>
      <div class="stat-card-label">${c.label}</div>
      <div class="stat-card-value">${c.v}</div>
    </div>
  `).join('');

  const qaItems = [
    ...PAGES.filter(p => p.hash !== 'overview').map(p => ({ ...p })),
    { hash: '_external', label: 'Templates', icon: '🗂️', url: 'templates.html' },
  ];
  $('quick-actions').innerHTML = qaItems.map(p => `
    <a class="quick-action-btn" href="${p.url || '#'}" ${p.url ? 'target="_blank"' : `data-navigate="${p.hash}"`}>
      <div class="quick-action-icon" style="background:rgba(148,163,184,0.08);">${p.icon}</div>
      <div>
        <div class="quick-action-label">${p.label}</div>
        <div class="quick-action-desc">${p.url ? 'Open page' : 'View details'}</div>
      </div>
    </a>
  `).join('');
  $('quick-actions').querySelectorAll('[data-navigate]').forEach(el => {
    el.addEventListener('click', e => { e.preventDefault(); navigate(el.dataset.navigate); });
  });

  $('pub-summary').innerHTML = [
    { icon: '📝', label: 'Total Posts',   v: data.total_posts },
    { icon: '✅', label: 'Published',     v: data.publish_success,    c: 'var(--green)' },
    { icon: '❌', label: 'Failed',        v: data.publish_failed,     c: 'var(--red)' },
    { icon: '⏳', label: 'Scheduled',     v: data.publish_scheduled,  c: 'var(--yellow)' },
  ].map(i => `
    <div class="stat-card" style="text-align:center;">
      <div style="font-size:1.5rem;margin-bottom:0.25rem;">${i.icon}</div>
      <div class="stat-card-value" ${i.c ? `style="color:${i.c}"` : ''}>${i.v}</div>
      <div class="stat-card-label">${i.label}</div>
    </div>
  `).join('');
}

// ── Analytics ──
async function analytics() {
  const data = await fetchData('/api/v1/admin/stats', 'stats');
  if (!data) return;

  const successRate = (data.publish_success + data.publish_failed) > 0
    ? Math.round((data.publish_success / (data.publish_success + data.publish_failed)) * 100) + '%'
    : '—';

  const tierData = data.tiers || { free: 0, pro: 0, enterprise: 0 };
  const maxTier = Math.max(tierData.free || 1, tierData.pro || 1, tierData.enterprise || 1);

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Deep <span class="gradient-text">Analytics</span></h1>
        <p>Aggregated platform metrics</p>
      </div>
      <button class="btn btn-sm btn-primary" id="analytics-refresh">🔄 Refresh</button>
    </div>
    <div class="analytics-grid">
      <div class="analytics-card">
        <div class="analytics-card-label">Success Rate</div>
        <div class="analytics-card-value" style="color:${data.publish_failed > data.publish_success ? 'var(--red)' : 'var(--green)'}">${successRate}</div>
        <div class="analytics-hint">${data.publish_success} posted / ${data.publish_failed} failed</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card-label">Total Content</div>
        <div class="analytics-card-value">${data.total_posts}</div>
        <div class="analytics-hint">across ${Object.keys(data.platforms || {}).length} platforms</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card-label">Active Users</div>
        <div class="analytics-card-value">${data.total_users}</div>
        <div class="analytics-hint">${tierData.pro + tierData.enterprise} paid</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card-label">Publish History</div>
        <div class="analytics-card-value">${data.publish_history_total || 0}</div>
        <div class="analytics-hint">${data.publish_history_success || 0} success / ${data.publish_history_failed || 0} failed</div>
      </div>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">Tier Distribution</div>
      <div class="analytics-bar-container">
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;">
          <div class="analytics-bar" style="height:${(tierData.free / maxTier) * 100}%;background:var(--text-dim);width:60%;min-height:4px;"></div>
          <div class="analytics-bar-label">Free (${tierData.free})</div>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;">
          <div class="analytics-bar" style="height:${(tierData.pro / maxTier) * 100}%;background:var(--cyan);width:60%;min-height:4px;"></div>
          <div class="analytics-bar-label">Pro (${tierData.pro})</div>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;">
          <div class="analytics-bar" style="height:${(tierData.enterprise / maxTier) * 100}%;background:var(--purple);width:60%;min-height:4px;"></div>
          <div class="analytics-bar-label">Enterprise (${tierData.enterprise})</div>
        </div>
      </div>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">Platform Breakdown</div>
      ${Object.keys(data.platforms || {}).length === 0 ? '<p class="text-dim text-sm">No platform data yet.</p>' : `
      <table class="admin-table">
        <thead><tr><th>Platform</th><th>Count</th></tr></thead>
        <tbody>${Object.entries(data.platforms).sort((a, b) => b[1] - a[1]).map(([p, c]) => `
          <tr><td>${platformIcon(p)} ${escHtml(p)}</td><td>${c}</td></tr>
        `).join('')}</tbody>
      </table>`}
    </div>
  `);

  $('analytics-refresh')?.addEventListener('click', () => {
    delete state.stats;
    analytics();
  });
}

// ── Activity ──
let _activityPage = 0;
const ACTIVITY_PAGE_SIZE = 20;

async function activity() {
  const data = await fetchData('/api/v1/admin/user-activity', 'activity');
  if (!data) return;
  const allItems = data.activities || [];
  const items = allItems.slice(0, (_activityPage + 1) * ACTIVITY_PAGE_SIZE);
  const hasMore = items.length < allItems.length;

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Friend <span class="gradient-text">Activity</span></h1>
        <p>Recent actions across all users — ${allItems.length} events (showing ${items.length})</p>
      </div>
      <button class="btn btn-sm btn-primary" id="activity-refresh">🔄 Refresh</button>
    </div>
    <div class="admin-section" style="overflow-x:auto;">
      ${items.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">📋</div><h3>No activity yet</h3></div>' : items.map(a => `
        <div class="activity-row ${a.status}">
          <div class="activity-icon">${a.type === 'pipeline' ? '🎬' : '📝'}</div>
          <div class="activity-body">
            <div class="activity-user">${escHtml(a.user_name)}</div>
            <div class="activity-detail">${escHtml(a.detail)}</div>
          </div>
          <div class="activity-status">
            <span class="tier-badge ${a.status === 'posted' || a.status === 'completed' ? 'pro' : a.status === 'failed' ? 'free' : ''}">${a.status}</span>
          </div>
          <div class="activity-time text-dim">${timeAgo(a.created_at)}</div>
        </div>
      `).join('')}
      ${hasMore ? '<div style="text-align:center;padding:0.75rem 0 0;"><button class="btn btn-sm btn-ghost" id="activity-show-more">+ Show More</button></div>' : ''}
    </div>
  `);

  $('activity-refresh')?.addEventListener('click', () => {
    _activityPage = 0;
    delete state.activity;
    activity();
  });
  $('activity-show-more')?.addEventListener('click', () => {
    _activityPage++;
    delete state.activity;
    activity();
  });
}

// ── Health ──
async function health() {
  const data = await fetchData('/api/v1/admin/health', 'health');
  if (!data) return;

  const services = [
    { label: 'Database',      ok: data.database?.status === 'ok', detail: `${data.database?.latency_ms || 0}ms` },
    { label: 'Job Queue',     ok: data.job_queue?.status === 'ok', detail: `${data.job_queue?.pending_jobs || 0} pending` },
    { label: 'Publish Worker', ok: data.publish_worker?.status === 'ok', detail: data.publish_worker?.store_ready ? 'store ready' : 'unknown' },
    { label: 'Scheduler', ok: data.scheduler?.status === 'ok', detail: data.scheduler?.running ? 'running' : 'stopped' },
  ];

  const cfg = data.config || {};
  const configItems = Object.entries(cfg).map(([k, v]) => ({ label: k.replace(/_/g, ' '), ok: !!v }));

  setContent(`
    <div class="admin-header">
      <div>
        <h1>System <span class="gradient-text">Health</span></h1>
        <p>Live probes and diagnostics</p>
      </div>
      <button class="btn btn-sm btn-primary" id="health-refresh">🔄 Refresh</button>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">🔌 Service Status</div>
      <div class="health-grid" id="service-probes"></div>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">⚙️ Configuration</div>
      <div class="config-grid" id="config-checks"></div>
    </div>
  `);

  $('service-probes').innerHTML = services.map(s => `
    <div class="health-card status-${s.ok ? 'ok' : 'error'}">
      <div class="health-label">
        <span class="health-status-dot ${s.ok ? 'ok' : 'error'}"></span>
        ${s.label}
      </div>
      <div class="health-value">${s.ok ? '✅ OK' : '❌ DOWN'}</div>
      <div class="health-sub">${escHtml(s.detail)}</div>
    </div>
  `).join('');

  $('config-checks').innerHTML = configItems.map(c => `
    <div class="config-item ${c.ok ? 'enabled' : 'disabled'}">
      <span>${c.ok ? '✅' : '⚠️'}</span> ${escHtml(c.label)}
    </div>
  `).join('');

  $('health-refresh')?.addEventListener('click', () => {
    delete state.health;
    health();
  });
}

// ── Feature Brainstorm (Self-Improvement) ──
let brainstormState = { 
  suggestions: [], 
  error: null, 
  loading: false, 
  voted: {},
  filterStatus: 'all',
  filterCategory: 'all',
  sortBy: 'created_desc',
  page: 1,
  pageSize: 20,
  total: 0
};

async function brainstorm() {
  // Load persisted suggestions on first visit
  if (brainstormState.suggestions.length === 0 && !brainstormState.error && !brainstormState._loaded) {
    brainstormState._loaded = true;
    await loadPersistedSuggestions();
  }

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Feature <span class="gradient-text">Brainstorm</span></h1>
        <p>Nexus-UGC self-improvement via Ollama-powered codebase analysis</p>
      </div>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">🧠 Generate New Ideas</div>
      <div class="brainstorm-controls">
        <button class="btn btn-primary" id="brainstorm-run" ${brainstormState.loading ? 'disabled' : ''}>
          ${brainstormState.loading ? '⏳ Analyzing...' : '🚀 Analyze & Suggest'}
        </button>
        <span class="text-dim text-xs">Uses Ollama to scan backend + frontend code and propose improvements</span>
      </div>
      <div id="brainstorm-stream"></div>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">
        📋 Suggestions 
        <span style="font-weight:normal;color:var(--text-dim);font-size:0.8rem;margin-left:0.5rem;">(${brainstormState.total} total)</span>
      </div>
      <div class="flex gap-2 flex-wrap mb-3" style="align-items:center;">
        <select id="filter-status" class="form-select" style="width:auto;min-width:140px;">
          <option value="all" ${brainstormState.filterStatus === 'all' ? 'selected' : ''}>All Status</option>
          <option value="new" ${brainstormState.filterStatus === 'new' ? 'selected' : ''}>🆕 New</option>
          <option value="in_review" ${brainstormState.filterStatus === 'in_review' ? 'selected' : ''}>👀 In Review</option>
          <option value="implemented" ${brainstormState.filterStatus === 'implemented' ? 'selected' : ''}>✅ Implemented</option>
          <option value="dismissed" ${brainstormState.filterStatus === 'dismissed' ? 'selected' : ''}>🗑️ Dismissed</option>
        </select>
        <select id="filter-category" class="form-select" style="width:auto;min-width:140px;">
          <option value="all" ${brainstormState.filterCategory === 'all' ? 'selected' : ''}>All Categories</option>
          <option value="feature" ${brainstormState.filterCategory === 'feature' ? 'selected' : ''}>✨ Feature</option>
          <option value="ui" ${brainstormState.filterCategory === 'ui' ? 'selected' : ''}>🎨 UI/UX</option>
          <option value="bugfix" ${brainstormState.filterCategory === 'bugfix' ? 'selected' : ''}>🐛 Bug Fix</option>
          <option value="optimization" ${brainstormState.filterCategory === 'optimization' ? 'selected' : ''}>⚡ Optimization</option>
          <option value="security" ${brainstormState.filterCategory === 'security' ? 'selected' : ''}>🔒 Security</option>
        </select>
        <select id="sort-by" class="form-select" style="width:auto;min-width:180px;">
          <option value="created_desc" ${brainstormState.sortBy === 'created_desc' ? 'selected' : ''}>Newest First</option>
          <option value="votes_desc" ${brainstormState.sortBy === 'votes_desc' ? 'selected' : ''}>Most Votes</option>
          <option value="effort_asc" ${brainstormState.sortBy === 'effort_asc' ? 'selected' : ''}>Easiest First</option>
        </select>
        <button class="btn btn-secondary btn-sm" id="load-more" style="margin-left:auto;">Load More</button>
      </div>
      <div id="brainstorm-results"></div>
    </div>
  `);

  $('brainstorm-run')?.addEventListener('click', runBrainstorm);
  $('filter-status')?.addEventListener('change', (e) => { brainstormState.filterStatus = e.target.value; brainstormState.page = 1; loadPersistedSuggestions(); });
  $('filter-category')?.addEventListener('change', (e) => { brainstormState.filterCategory = e.target.value; brainstormState.page = 1; loadPersistedSuggestions(); });
  $('sort-by')?.addEventListener('change', (e) => { brainstormState.sortBy = e.target.value; brainstormState.page = 1; loadPersistedSuggestions(); });
  $('load-more')?.addEventListener('click', () => { brainstormState.page++; loadPersistedSuggestions(true); });

  if (brainstormState.suggestions.length > 0) {
    renderBrainstormResults();
  } else if (brainstormState.error) {
    $('brainstorm-results').innerHTML = `<div class="admin-section" style="text-align:center;padding:2rem;color:var(--red);">⚠️ ${escHtml(brainstormState.error)}</div>`;
  } else {
    $('brainstorm-results').innerHTML = `<div class="admin-section" style="text-align:center;padding:2rem;color:var(--text-dim);font-size:0.85rem;">Click "Analyze & Suggest" to generate improvement ideas based on your codebase.</div>`;
  }
}

async function loadPersistedSuggestions(append = false) {
  const params = new URLSearchParams();
  if (brainstormState.filterStatus !== 'all') params.set('status', brainstormState.filterStatus);
  if (brainstormState.filterCategory !== 'all') params.set('category', brainstormState.filterCategory);
  params.set('limit', brainstormState.pageSize.toString());
  params.set('offset', ((brainstormState.page - 1) * brainstormState.pageSize).toString());
  
  try {
    const token = getToken();
    const res = await fetch(`/api/v1/admin/feature-suggestions?${params}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) throw new Error('Failed to load suggestions');
    const data = await res.json();
    brainstormState.total = data.total;
    
    if (append) {
      brainstormState.suggestions = [...brainstormState.suggestions, ...data.suggestions];
    } else {
      brainstormState.suggestions = data.suggestions;
    }
    
    // Apply client-side sorting
    brainstormState.suggestions.sort((a, b) => {
      if (brainstormState.sortBy === 'votes_desc') return (b.votes || 0) - (a.votes || 0);
      if (brainstormState.sortBy === 'effort_asc') {
        const effortOrder = { low: 0, medium: 1, high: 2 };
        return (effortOrder[a.effort] || 1) - (effortOrder[b.effort] || 1);
      }
      return new Date(b.created_at) - new Date(a.created_at);
    });
    
    renderBrainstormResults();
  } catch (err) {
    console.error('Failed to load suggestions:', err);
    showToast(err.message || 'An error occurred', 'error');
    brainstormState.error = 'Failed to load suggestions';
    renderBrainstormResults();
  }
}

async function runBrainstorm() {
  brainstormState.loading = true;
  brainstormState.error = null;
  const btn = $('brainstorm-run');
  if (btn) btn.disabled = true;

  const stream = $('brainstorm-stream');
  if (stream) {
    stream.innerHTML = '<div class="brainstorm-stream"><div class="brainstorm-stream-item"><span class="stream-dot"></span> Connecting to Ollama...</div></div>';
  }

  try {
    const res = await fetch('/api/v1/admin/suggest-features', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getToken()}`,
        'Content-Type': 'application/json',
      },
    });
    const data = await res.json();

    if (stream) {
      stream.innerHTML = '<div class="brainstorm-stream"><div class="brainstorm-stream-item done"><span class="stream-dot"></span> Analysis complete — suggestions saved</div></div>';
      setTimeout(() => { if (stream) stream.innerHTML = ''; }, 2000);
    }

    if (!res.ok) {
      brainstormState.error = data.detail || 'Request failed';
      brainstorm();
      return;
    }

    if (data.error) {
      brainstormState.error = data.error;
      brainstorm();
      return;
    }

    brainstormState.suggestions = data.suggestions || [];
    brainstormState.page = 1;
    brainstormState.total = data.count || brainstormState.suggestions.length;
    
    if (brainstormState.suggestions.length === 0) {
      brainstormState.error = 'No suggestions returned. Make sure Ollama is running and responsive.';
    }
  } catch (err) {
    brainstormState.error = `Network error: ${err.message}`;
  } finally {
    brainstormState.loading = false;
    brainstorm();
  }
}

function renderBrainstormResults() {
  const container = $('brainstorm-results');
  if (!container) return;

  const cats = {};
  brainstormState.suggestions.forEach(s => {
    const cat = s.category || 'feature';
    if (!cats[cat]) cats[cat] = [];
    cats[cat].push(s);
  });

  const catOrder = ['feature', 'ui', 'optimization', 'bugfix', 'security'];
  const catLabels = { feature: '✨ Features', ui: '🎨 UI/UX', optimization: '⚡ Optimizations', bugfix: '🐛 Bug Fixes', security: '🔒 Security' };
  const statusLabels = { new: '🆕 New', in_review: '👀 In Review', implemented: '✅ Implemented', dismissed: '🗑️ Dismissed' };
  const statusClasses = { new: 'status-pending', in_review: 'status-processing', implemented: 'status-completed', dismissed: 'status-cancelled' };

  container.innerHTML = Object.entries(cats)
    .sort(([a], [b]) => catOrder.indexOf(a) - catOrder.indexOf(b))
    .map(([cat, items]) => `
      <div class="admin-section">
        <div class="admin-section-title">${catLabels[cat] || cat} (${items.length})</div>
        <div class="brainstorm-container">
          ${items.map(s => `
            <div class="brainstorm-card" data-id="${s.id}">
              <div class="brainstorm-card-header">
                <div style="flex:1;">
                  <div style="display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap;margin-bottom:var(--space-1);">
                    <h4 style="margin:0;font-size:var(--text-base);">${escHtml(s.title)}</h4>
                    <span class="badge badge-sm ${statusClasses[s.status] || 'status-pending'}">${statusLabels[s.status] || s.status}</span>
                    <span class="brainstorm-tag ${s.category}">${s.category}</span>
                    <span class="brainstorm-tag" style="background:rgba(148,163,184,0.06);color:var(--text-dim);">${s.effort || 'medium'} effort</span>
                  </div>
                  <div style="font-size:var(--text-xs);color:var(--text-tertiary);">Source: ${s.source} ${s.ollama_model ? `(${s.ollama_model})` : ''} • ${fmtDate(s.created_at)}</div>
                </div>
                <div class="brainstorm-vote" style="display:flex;align-items:center;gap:var(--space-2);flex-shrink:0;">
                  <button class="btn btn-ghost btn-sm vote-down" data-id="${s.id}" data-dir="-1" title="Downvote" style="min-width:32px;">−</button>
                  <span class="vote-count" style="min-width:2rem;text-align:center;font-weight:var(--font-bold);">${s.votes || 0}</span>
                  <button class="btn btn-ghost btn-sm vote-up" data-id="${s.id}" data-dir="1" title="Upvote" style="min-width:32px;">+</button>
                  <button class="btn btn-ghost btn-sm status-btn" data-id="${s.id}" data-status="in_review" title="Mark In Review" style="min-width:32px;">👀</button>
                  <button class="btn btn-ghost btn-sm status-btn" data-id="${s.id}" data-status="implemented" title="Mark Implemented" style="min-width:32px;">✅</button>
                  <button class="btn btn-ghost btn-sm status-btn" data-id="${s.id}" data-status="dismissed" title="Dismiss" style="min-width:32px;">🗑️</button>
                </div>
              </div>
              <p style="margin:var(--space-3) 0;line-height:var(--leading-relaxed);">${escHtml(s.description)}</p>
              ${s.files && s.files.length ? `<div style="font-size:var(--text-xs);color:var(--text-dim);margin-top:var(--space-2);">📁 ${s.files.map(f => `<code style="background:rgba(148,163,184,0.06);padding:0.1rem 0.3rem;border-radius:4px;">${escHtml(f)}</code>`).join(' ')}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');

  // Vote buttons - call API
  container.querySelectorAll('.vote-up, .vote-down').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const dir = parseInt(btn.dataset.dir);
      btn.disabled = true;
      try {
        const token = getToken();
        const res = await fetch(`/api/v1/admin/feature-suggestions/${id}/vote`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ direction: dir }),
        });
        if (res.ok) {
          const data = await res.json();
          // Update local state
          const suggestion = brainstormState.suggestions.find(s => s.id === id);
          if (suggestion) suggestion.votes = data.votes;
          renderBrainstormResults();
        }
      } catch (err) {
        console.error('Vote failed:', err);
        showToast(err.message || 'An error occurred', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  });

  // Status buttons
  container.querySelectorAll('.status-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const status = btn.dataset.status;
      btn.disabled = true;
      try {
        const token = getToken();
        const res = await fetch(`/api/v1/admin/feature-suggestions/${id}`, {
          method: 'PUT',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ status }),
        });
        if (res.ok) {
          const data = await res.json();
          // Update local state
          const idx = brainstormState.suggestions.findIndex(s => s.id === id);
          if (idx >= 0) brainstormState.suggestions[idx] = data;
          renderBrainstormResults();
          showToast(`Status updated to ${statusLabels[status] || status}`, 'success');
        }
      } catch (err) {
        console.error('Status update failed:', err);
        showToast(err.message || 'An error occurred', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  });
}

// ── Publishing ──
async function publishing() {
  const data = await fetchData('/api/v1/admin/publishing', 'publishing');
  if (!data) return;

  const platforms = data.platforms || {};
  const names = Object.keys(platforms).length ? Object.keys(platforms) : ['youtube', 'tiktok', 'instagram', 'twitter', 'facebook', 'linkedin'];

  const totals = { posted: 0, failed: 0, scheduled: 0 };
  const cards = names.map(name => {
    const p = platforms[name] || { posted: 0, failed: 0, scheduled: 0, total: 0 };
    totals.posted += p.posted || 0;
    totals.failed += p.failed || 0;
    totals.scheduled += p.scheduled || 0;
    const rate = (p.posted + p.failed) > 0 ? Math.round((p.posted / (p.posted + p.failed)) * 100) : 0;
    return `
      <div class="platform-card">
        <div class="platform-card-header">
          <span style="font-size:1.2rem;">${platformIcon(name)}</span>
          <span class="platform-name">${escHtml(name)}</span>
          <span class="tier-badge free" style="margin-left:auto;">${rate}% OK</span>
        </div>
        <div class="platform-stat"><span class="platform-stat-label">✅ Posted</span><span class="platform-stat-value" style="color:var(--green)">${p.posted}</span></div>
        <div class="platform-stat"><span class="platform-stat-label">❌ Failed</span><span class="platform-stat-value" style="color:var(--red)">${p.failed}</span></div>
        <div class="platform-stat"><span class="platform-stat-label">⏳ Scheduled</span><span class="platform-stat-value" style="color:var(--yellow)">${p.scheduled}</span></div>
      </div>
    `;
  }).join('');

  const totalPub = totals.posted + totals.failed;
  const rate = totalPub > 0 ? Math.round((totals.posted / totalPub) * 100) + '%' : '—';

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Publishing <span class="gradient-text">Analytics</span></h1>
        <p>Per-platform publishing breakdown</p>
      </div>
      <button class="btn btn-sm btn-primary" id="pub-refresh">🔄 Refresh</button>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">🌐 By Platform</div>
      <div class="platform-grid" id="platform-cards"></div>
    </div>
    <div class="admin-section">
      <div class="admin-section-title">📊 Totals</div>
      <div class="stats-grid">${[
        { icon: '📤', label: 'Total Posted',   v: totals.posted,     c: 'var(--green)' },
        { icon: '❌', label: 'Total Failed',   v: totals.failed,     c: 'var(--red)' },
        { icon: '⏳', label: 'Total Scheduled', v: totals.scheduled,   c: 'var(--yellow)' },
        { icon: '📊', label: 'Success Rate',   v: rate },
      ].map(i => `
        <div class="stat-card" style="text-align:center;">
          <div style="font-size:1.5rem;margin-bottom:0.25rem;">${i.icon}</div>
          <div class="stat-card-value" style="color:${i.c || 'inherit'}">${i.v}</div>
          <div class="stat-card-label">${i.label}</div>
        </div>
      `).join('')}</div>
    </div>
  `);

  $('platform-cards').innerHTML = cards;

  $('pub-refresh')?.addEventListener('click', () => {
    delete state.publishing;
    publishing();
  });
}

function platformIcon(name) {
  const icons = { youtube: '▶️', tiktok: '🎵', instagram: '📸', twitter: '🐦', facebook: '👍', linkedin: '💼' };
  return icons[name] || '🌐';
}

// ── Users ──
async function users() {
  const data = await fetchData('/api/v1/admin/users', 'users');
  if (!data) return;
  const list = data.users || [];

  setContent(`
    <div class="admin-header">
      <div>
        <h1>User <span class="gradient-text">Management</span></h1>
        <p>${list.length} total users — click row to view details</p>
      </div>
      <button class="btn btn-sm btn-primary" id="users-refresh">🔄 Refresh</button>
    </div>
    <div class="admin-section" style="overflow-x:auto;">
      ${list.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">👥</div><h3>No users yet</h3></div>' : `
      <table class="admin-table" id="user-table">
        <thead><tr>
          <th>User</th><th>Tier</th><th>Credits</th><th>🧠 Brain Rot</th><th>✅ Pub'd</th><th>❌ Failed</th><th>Total Posts</th><th>Last Post</th><th>Joined</th>
        </tr></thead>
        <tbody>${list.map(u => `
          <tr class="user-row" data-user-id="${u.id}" style="cursor:pointer;">
            <td>
              <div style="font-weight:500;">${escHtml(u.display_name || u.email)}</div>
              <div class="text-dim" style="font-size:0.65rem;">${escHtml(u.email)}</div>
            </td>
            <td><span class="tier-badge ${u.tier}">${u.tier}</span>${u.is_active ? '' : ' 🔒'}</td>
            <td>${u.credits_used}/${u.credits_limit}</td>
            <td style="text-align:center;">${u.brainrot_posts || 0}</td>
            <td style="text-align:center;color:var(--green);">${u.published || 0}</td>
            <td style="text-align:center;color:var(--red);">${u.failed_publishes || 0}</td>
            <td style="text-align:center;">${u.posts || 0}</td>
            <td class="text-dim" style="font-size:0.7rem;">${u.last_post_at ? timeAgo(u.last_post_at) : '—'}</td>
            <td class="text-dim" style="font-size:0.7rem;">${fmtDate(u.created_at)}</td>
          </tr>
          <tr id="user-detail-${u.id}" class="user-detail-row" style="display:none;">
            <td colspan="9">
              <div class="user-detail-card">
                <div class="flex gap-2 items-center" style="flex-wrap:wrap;margin-bottom:0.5rem;">
                  <span class="tier-badge ${u.tier}">${u.tier}</span>
                  <span>👤 ${escHtml(u.display_name || u.email)}</span>
                  <span>📧 ${escHtml(u.email)}</span>
                  <span>💳 ${u.credits_used}/${u.credits_limit} credits</span>
                  <span>📝 ${u.posts} posts (${u.published} pub'd, ${u.failed_publishes} failed)</span>
                  <span>🎭 ${u.personas || 0} personas</span>
                  <span class="tier-badge ${u.is_active ? 'pro' : 'free'}">${u.is_active ? 'Active' : 'Disabled'}</span>
                </div>
                <div class="flex gap-1 items-center" style="flex-wrap:wrap;">
                  <button class="btn btn-xs ${u.is_active ? 'btn-ghost' : 'btn-primary'}" data-action="toggle-user" data-user-id="${u.id}" data-active="${u.is_active}">
                    ${u.is_active ? '🔒 Disable' : '🔓 Enable'}
                  </button>
                  <span class="text-dim text-xs" style="margin-left:0.5rem;">Set credit limit:</span>
                  <input type="number" id="credit-limit-${u.id}" class="form-input" style="width:70px;padding:0.25rem 0.5rem;font-size:0.75rem;" value="${u.credits_limit}">
                  <button class="btn btn-xs btn-ghost" data-action="set-credit" data-user-id="${u.id}">Update</button>
                </div>
              </div>
            </td>
          </tr>
        `).join('')}</tbody>
      </table>`}
    </div>
  `);

  document.querySelectorAll('.user-row').forEach(row => {
    row.addEventListener('click', () => toggleUserDetail(row.dataset.userId));
  });
  document.querySelectorAll('[data-action="toggle-user"]').forEach(btn => {
    btn.addEventListener('click', () => toggleUserActive(btn.dataset.userId, btn.dataset.active === 'true' ? false : true));
  });
  document.querySelectorAll('[data-action="set-credit"]').forEach(btn => {
    btn.addEventListener('click', () => setUserCreditLimit(btn.dataset.userId));
  });

  $('users-refresh')?.addEventListener('click', () => {
    delete state.users;
    users();
  });
}

function toggleUserDetail(id) {
  const row = document.getElementById(`user-detail-${id}`);
  if (row) row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
}

async function toggleUserActive(userId, makeActive) {
  try {
    const res = await fetch(`/api/v1/admin/users/${userId}`, {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: makeActive }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
    delete state.users;
    users();
    showToast(makeActive ? 'Account enabled' : 'Account disabled', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function setUserCreditLimit(userId) {
  const input = document.getElementById(`credit-limit-${userId}`);
  const limit = parseInt(input?.value);
  if (!limit || limit < 1) { showToast('Credit limit must be at least 1', 'error'); return; }
  try {
    const res = await fetch(`/api/v1/admin/users/${userId}`, {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ credits_limit: limit }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
    delete state.users;
    users();
    showToast(`Limit set to ${limit}`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Accounts ──
async function accounts() {
  const data = await fetchData('/api/v1/admin/accounts', 'accts');
  if (!data) return;
  const list = data.accounts || [];

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Connected <span class="gradient-text">Accounts</span></h1>
        <p>${list.length} social accounts</p>
      </div>
      <button class="btn btn-sm btn-primary" id="accts-refresh">🔄 Refresh</button>
    </div>
    <div class="admin-section" style="overflow-x:auto;">
      ${list.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">🔗</div><h3>No connected accounts</h3></div>' : `
      <table class="admin-table">
        <thead><tr><th>Platform</th><th>Handle</th><th>User</th><th>Tokens</th><th>Connected</th></tr></thead>
        <tbody>${list.map(a => `
          <tr>
            <td>${platformIcon(a.platform)} ${a.platform}</td>
            <td style="font-weight:500;">${escHtml(a.handle || '—')}</td>
            <td class="text-dim">${escHtml(a.user_email || '—')}</td>
            <td>${a.has_tokens ? '✅ Yes' : '❌ No'}</td>
            <td class="text-dim" style="font-size:0.7rem;">${fmtDate(a.created_at)}</td>
          </tr>
        `).join('')}</tbody>
      </table>`}
    </div>
  `);

  $('accts-refresh')?.addEventListener('click', () => {
    delete state.accts;
    accounts();
  });
}

// ── Invite Keys ──
async function inviteKeys() {
  const data = await fetchData('/api/v1/admin/invite-keys', 'invite_keys');
  if (!data) return;
  const keys = data.invite_keys || [];

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Invite <span class="gradient-text">Keys</span></h1>
        <p>${keys.length} keys — share these with friends so they can register</p>
      </div>
      <div class="flex gap-1">
        <button class="btn btn-sm btn-secondary" id="invite-1">+ 1 Key</button>
        <button class="btn btn-sm btn-secondary" id="invite-5">+ 5 Keys</button>
        <button class="btn btn-sm btn-ghost" id="invite-refresh">🔄 Refresh</button>
      </div>
    </div>
    <div class="admin-section" style="overflow-x:auto;">
      ${keys.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">🎫</div><h3>No invite keys yet</h3></div>' : `
      <table class="admin-table">
        <thead><tr><th>Code</th><th>Created By</th><th>Uses</th><th>Max Uses</th><th>Expires</th><th>Status</th><th>Action</th></tr></thead>
        <tbody>${keys.map(k => `
          <tr>
            <td style="font-family:monospace;font-size:0.7rem;font-weight:600;">${escHtml(k.code)}</td>
            <td class="text-dim" style="font-size:0.7rem;">${escHtml(k.created_by)}</td>
            <td>${k.used_count}/${k.max_uses}</td>
            <td>${k.max_uses}</td>
            <td class="text-dim" style="font-size:0.7rem;">${k.expires_at ? timeAgo(k.expires_at) : 'Never'}</td>
            <td>${k.is_active ? '✅ Active' : '🚫 Revoked'}</td>
            <td>${k.is_active ? `<button class="btn btn-xs btn-ghost" data-action="revoke-key" data-key-id="${k.id}">Revoke</button>` : '—'}</td>
          </tr>
        `).join('')}</tbody>
      </table>`}
    </div>
  `);

  $('invite-1')?.addEventListener('click', () => createInviteKey(1));
  $('invite-5')?.addEventListener('click', () => createInviteKey(5));
  $('invite-refresh')?.addEventListener('click', () => { delete state.invite_keys; inviteKeys(); });
  document.querySelectorAll('[data-action="revoke-key"]').forEach(btn => {
    btn.addEventListener('click', () => revokeInviteKey(btn.dataset.keyId));
  });
}

async function createInviteKey(count) {
  try {
    const res = await fetch('/api/v1/admin/invite-keys', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ count }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
    const data = await res.json();
    const codes = data.invite_keys.join('\n');
    navigator.clipboard.writeText(codes).then(() => {
      showToast('Invite keys copied to clipboard!', 'success');
    }).catch(() => {
      showToast('Failed to copy invite keys to clipboard. Please try again.', 'error');
    });
    delete state.invite_keys;
    inviteKeys();
  } catch (err) {
    showAdminError(err.message);
  }
}

async function revokeInviteKey(keyId) {
  if (!await confirmDialog('Revoke this invite key?')) return;
  try {
    const res = await fetch(`/api/v1/admin/invite-keys/${keyId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Failed');
    delete state.invite_keys;
    inviteKeys();
  } catch (err) {
    showAdminError(err.message);
  }
}

// ── Licenses ──
async function licenses() {
  const data = await fetchData('/api/v1/admin/licenses', 'lics');
  if (!data) return;
  const list = data.licenses || [];

  setContent(`
    <div class="admin-header">
      <div>
        <h1>Whop <span class="gradient-text">Licenses</span></h1>
        <p>${list.length} issued licenses</p>
      </div>
      <button class="btn btn-sm btn-primary" id="licenses-refresh">🔄 Refresh</button>
    </div>
    <div class="admin-section" style="overflow-x:auto;">
      ${list.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">🔑</div><h3>No licenses yet</h3></div>' : `
      <table class="admin-table">
        <thead><tr><th>ID</th><th>Tier</th><th>Status</th><th>Product</th><th>Created</th></tr></thead>
        <tbody>${list.map(l => `
          <tr>
            <td style="font-family:monospace;font-size:0.7rem;">${formatKey(l.id || l.license_key)}</td>
            <td><span class="tier-badge ${l.tier || 'free'}">${escHtml(l.tier) || 'free'}</span></td>
            <td>${l.status === 'active' ? '✅ Active' : '⏸️ ' + (escHtml(l.status) || 'inactive')}</td>
            <td style="font-size:0.7rem;color:var(--text-dim);">${formatKey(l.product_id || '—')}</td>
            <td class="text-dim" style="font-size:0.7rem;">${fmtDate(l.created_at)}</td>
          </tr>
        `).join('')}</tbody>
      </table>`}
    </div>
  `);

  $('licenses-refresh')?.addEventListener('click', () => { delete state.lics; licenses(); });
}

// ── Theme Toggle ──
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('nexus-theme', next);
  updateThemeUI(next);
}

function updateThemeUI(theme) {
  const icon = $('theme-icon');
  const label = $('theme-label');
  if (icon) icon.textContent = theme === 'dark' ? '🌙' : '☀️';
  if (label) label.textContent = theme === 'dark' ? 'Light' : 'Dark';
}

// ── Helpers ──
function setContent(html) { $('admin-content').innerHTML = html; }

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const now = Date.now();
  const d = new Date(dateStr).getTime();
  const diff = now - d;
  if (isNaN(diff)) return '—';
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(dateStr);
}

async function fetchData(url, cacheKey) {
  if (state[cacheKey]) return state[cacheKey];
  try {
    const token = getToken();
    if (!token) { window.location.href = 'admin-login.html'; return null; }
    const res = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    });
    if (res.status === 401 || res.status === 403) {
      clearToken();
      window.location.href = 'admin-login.html';
      return null;
    }
    if (!res.ok) { showAdminError(`Failed to load (${res.status}): ${url}`); return null; }
    const json = await res.json();
    state[cacheKey] = json;
    return json;
  } catch (err) {
    showAdminError(`Network error: ${err.message}`);
    return null;
  }
}

function formatKey(key) {
  if (!key) return '—';
  const s = String(key);
  if (s.length <= 12) return s;
  return s.slice(0, 6) + '…' + s.slice(-4);
}

function showAdminError(msg) {
  const el = $('admin-content');
  el.innerHTML = `
    <div class="admin-section" style="text-align:center;padding:3rem;">
      <div style="font-size:2rem;margin-bottom:0.75rem;">⚠️</div>
      <h3 style="margin-bottom:0.5rem;">Error</h3>
      <p class="text-secondary text-sm">${escHtml(msg)}</p>
      <button class="btn btn-sm btn-primary mt-2 retry-btn">Retry</button>
    </div>
  `;
  el.querySelector('.retry-btn')?.addEventListener('click', () => navigate(getHash()));
}

// ── Init ──
function init() {
  if (!getToken()) { window.location.href = 'admin-login.html'; return; }
  renderSidebar();

  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  updateThemeUI(theme);

  $('admin-theme-btn')?.addEventListener('click', toggleTheme);

  $('admin-logout-btn').addEventListener('click', () => {
    clearToken();
    window.location.href = 'admin-login.html';
  });

  $('admin-back-btn')?.addEventListener('click', () => window.location.href = 'index.html');

  $('admin-toggle-btn')?.addEventListener('click', () => {
    $('admin-sidebar')?.classList.toggle('open');
  });

  document.querySelectorAll('.admin-nav-item').forEach(item => {
    item.addEventListener('click', () => {
      $('admin-sidebar')?.classList.remove('open');
    });
  });

  window.addEventListener('hashchange', () => renderPage(getHash()));
  renderPage(getHash());
}

document.addEventListener('DOMContentLoaded', init);

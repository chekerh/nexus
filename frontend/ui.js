/* Shared UI utilities — toast, auth UI, HTML escaping, error handling */
const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
function log(...args) { if (DEV) console.log(...args); }

/* ── Interval registry (for cleanup on visibility change) ── */
const _intervals = [];
function registerInterval(id) { _intervals.push(id); }
function clearAllIntervals() { _intervals.forEach(clearInterval); _intervals.length = 0; }
document.addEventListener('visibilitychange', () => {
  if (document.hidden) clearAllIntervals();
});

/* ── Global error handler ── */
window.addEventListener('error', (e) => {
  console.error('Uncaught error:', e.error || e.message);
  const toast = document.getElementById('toast-container');
  if (toast) {
    const el = document.createElement('div');
    el.className = 'toast toast-error';
    el.textContent = typeof __ === 'function' ? __('common.error', 'Something went wrong. Check console for details.') : 'Something went wrong. Check console for details.';
    el.setAttribute('role', 'alert');
    toast.appendChild(el);
    void el.offsetWidth;
    el.classList.add('toast-visible');
    setTimeout(() => { el.classList.remove('toast-visible'); el.classList.add('toast-hiding'); setTimeout(() => el.remove(), 300); }, 5000);
  }
});
window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise rejection:', e.reason);
});

/* ── Toast Notification ── */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toast.setAttribute('role', 'alert');
  container.appendChild(toast);

  // Trigger reflow for animation
  void toast.offsetWidth;
  toast.classList.add('toast-visible');

  setTimeout(() => {
    toast.classList.remove('toast-visible');
    toast.classList.add('toast-hiding');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Auth UI update ── */
function updateAuthUI() {
  const loginBtn = document.getElementById('login-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const emailEl = document.getElementById('user-email');

  if (typeof isAuthenticated !== 'function') return;

  if (isAuthenticated()) {
    if (loginBtn) loginBtn.classList.add('hidden');
    if (logoutBtn) logoutBtn.classList.remove('hidden');
    if (typeof getMe === 'function') {
      getMe().then(u => {
        if (emailEl) emailEl.textContent = u.email;
      }).catch(() => {});
    }
  } else {
    if (loginBtn) loginBtn.classList.remove('hidden');
    if (logoutBtn) logoutBtn.classList.add('hidden');
  }
}

/* ── Navigation system ── */
function setupNavigation() {
  const isAuth = typeof isAuthenticated === 'function' && isAuthenticated();
  const isAppPage = !!document.querySelector('.app-layout');
  const isMinimal = document.body.classList.contains('page-minimal');

  if (isMinimal) return;

  const navbarNav = document.querySelector('.navbar-nav');
  const navbarActions = document.querySelector('.navbar-actions');

  if (isAppPage && isAuth) {
    if (navbarNav) navbarNav.style.display = 'none';

    const loginBtn = document.getElementById('login-btn');
    const logoutBtn = document.getElementById('logout-btn');

    if (loginBtn) loginBtn.classList.add('hidden');
    if (logoutBtn) logoutBtn.classList.remove('hidden');

    const emailEl = document.getElementById('user-email');
    if (emailEl && !emailEl.textContent) {
      if (typeof getMe === 'function') {
        getMe().then(u => {
          emailEl.textContent = u.email;
        }).catch(() => {});
      }
    }

    const existingDropdown = document.querySelector('.user-dropdown');
    if (logoutBtn && !existingDropdown && navbarActions) {
      logoutBtn.classList.add('hidden');
      const dropdown = document.createElement('div');
      dropdown.className = 'user-dropdown';
      dropdown.innerHTML = `
        <button class="user-dropdown-btn" data-dropdown-toggle>
          <span id="user-email-short" class="text-dim"></span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 5l3 3 3-3"/></svg>
        </button>
        <div class="user-dropdown-menu" data-dropdown-menu>
          <div class="dropdown-label">Account</div>
          <a href="settings.html">⚙️ Settings</a>
          <a href="billing.html">💳 Billing</a>
          <hr>
          <button id="logout-btn-dropdown">🚪 Sign Out</button>
        </div>`;
      navbarActions.appendChild(dropdown);

      if (typeof getMe === 'function') {
        getMe().then(u => {
          const short = document.getElementById('user-email-short');
          if (short) short.textContent = u.display_name || u.email.split('@')[0];
          const full = document.getElementById('user-email');
          if (full) full.textContent = u.email;
        }).catch(() => {});
      }

      const toggle = dropdown.querySelector('[data-dropdown-toggle]');
      const menu = dropdown.querySelector('[data-dropdown-menu]');
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.toggle('open');
      });
      document.addEventListener('click', () => menu.classList.remove('open'), { once: false });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') menu.classList.remove('open');
      });

      dropdown.querySelector('#logout-btn-dropdown').addEventListener('click', () => {
        if (typeof clearToken === 'function') clearToken();
        if (typeof logout === 'function') { logout(); }
        else { window.location.href = 'login.html'; }
      });
    }
  } else if (isAppPage && !isAuth) {
    if (navbarNav) navbarNav.style.display = 'none';

    const sidebar = document.querySelector('.sidebar');
    if (sidebar && !sidebar.querySelector('.sidebar-auth-prompt')) {
      const prompt = document.createElement('div');
      prompt.className = 'sidebar-auth-prompt';
      prompt.style.cssText = 'padding:1rem;text-align:center;';
      prompt.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem;margin-bottom:0.75rem;">Please sign in to access app features.</p><a href="login.html" class="btn btn-primary btn-sm">Sign In</a>';
      sidebar.querySelector('.sidebar-nav')?.after(prompt);
    }

    const loginBtn = document.getElementById('login-btn');
    if (loginBtn) loginBtn.classList.remove('hidden');
  }

  const isIndex = window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname === '';
  if (isIndex && !isAuth && navbarNav) {
    navbarNav.style.display = '';
    navbarNav.classList.add('public-nav');
  } else if (isIndex && isAuth) {
    if (navbarNav) navbarNav.style.display = 'none';
    const dashSection = document.getElementById('dashboard-section');
    if (dashSection) dashSection.style.removeProperty('display');
    const existingQuickNav = document.querySelector('.app-quick-nav');
    if (navbarActions && !existingQuickNav) {
      const quickNav = document.createElement('div');
      quickNav.className = 'app-quick-nav';
      quickNav.style.cssText = 'display:flex;align-items:center;gap:0.25rem;margin-right:1rem;';
      quickNav.innerHTML = `
        <a href="brainrot.html" class="btn btn-ghost btn-sm" style="font-size:0.8rem;">🧠 Create</a>
        <a href="queue.html" class="btn btn-ghost btn-sm" style="font-size:0.8rem;">📋 Queue</a>`;
      navbarActions.prepend(quickNav);
    }
  }
}

/* Close dropdown on any click outside */
document.addEventListener('click', () => {
  document.querySelectorAll('.user-dropdown-menu.open').forEach(m => m.classList.remove('open'));
});

/* ── HTML escaping ── */
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ── Date formatting ── */
function fmtDate(d) {
  if (!d) return '—';
  const date = new Date(d);
  if (isNaN(date.getTime())) return '—';
  const lang = (typeof __ === 'function' && document.documentElement.lang) || 'en';
  return date.toLocaleDateString(lang === 'ar' ? 'ar-TN' : lang === 'fr' ? 'fr-FR' : 'en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/* ── Loading / Empty / Error State Helpers ── */

/**
 * Fill a container with a loading placeholder.
 * @param {HTMLElement} container
 * @param {string} message - Loading text
 */
function showLoading(container, message = 'Loading...') {
  container.innerHTML = `<div class="loading-pulse" style="text-align:center;padding:2rem;color:var(--text-dim);font-size:0.875rem;">${escHtml(message)}</div>`;
}

/**
 * Fill a container with an empty-state message.
 * @param {HTMLElement} container
 * @param {string} icon - emoji or icon
 * @param {string} title
 * @param {string} message - optional description
 */
function showEmpty(container, icon = '📋', title = 'Nothing here', message = '') {
  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-state-icon">${icon}</div>
      <h3>${escHtml(title)}</h3>
      ${message ? `<p>${escHtml(message)}</p>` : ''}
    </div>`;
}

/**
 * Fill a container with an error message and optional retry button.
 * @param {HTMLElement} container
 * @param {string} message
 * @param {string} retryFnName - name of global function to call on retry (e.g. 'loadPersonas')
 */
function showError(container, message = 'Something went wrong', retryFnName = null) {
  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-state-icon" style="color:var(--red)">⚠️</div>
      <h3>Error</h3>
      <p style="color:var(--red);font-size:0.85rem;">${escHtml(message)}</p>
      ${retryFnName ? '<button class="btn btn-sm btn-primary retry-btn" style="margin-top:0.5rem;">Try Again</button>' : ''}
    </div>`;
  const retryBtn = container.querySelector('.retry-btn');
  if (retryBtn && retryFnName && typeof window[retryFnName] === 'function') {
    retryBtn.addEventListener('click', window[retryFnName]);
  }
}

/* ── Form Validation ── */
/**
 * Validate a form against a set of field rules.
 * @param {object} rules - { fieldId: { required?, pattern?, minLength?, message } }
 * @returns {boolean} true if all fields pass validation
 * Shows inline errors on .field-error elements near each field.
 */
function validateForm(rules) {
  let valid = true;
  for (const [id, rule] of Object.entries(rules)) {
    const el = document.getElementById(id);
    if (!el) continue;
    const val = el.value.trim();
    const errEl = document.getElementById(`${id}-error`);
    if (errEl) {
      if (rule.required && !val) {
        errEl.textContent = rule.message || `${rule.label || 'This field'} is required`;
        errEl.classList.remove('hidden');
        el.classList.add('input-error');
        valid = false;
      } else if (rule.pattern && val && !rule.pattern.test(val)) {
        errEl.textContent = rule.message || `Invalid format`;
        errEl.classList.remove('hidden');
        el.classList.add('input-error');
        valid = false;
      } else if (rule.minLength && val.length < rule.minLength) {
        errEl.textContent = rule.message || `Must be at least ${rule.minLength} characters`;
        errEl.classList.remove('hidden');
        el.classList.add('input-error');
        valid = false;
      } else {
        errEl.classList.add('hidden');
        el.classList.remove('input-error');
      }
    }
  }
  return valid;
}

function clearFieldErrors() {
  document.querySelectorAll('.field-error').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
}

/* ── Focus Trap ── */
function trapFocus(container) {
  const focusable = container.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const handler = (e) => {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  container.addEventListener('keydown', handler);
  return () => container.removeEventListener('keydown', handler);
}

/* ── Confirm / Prompt Dialogs ── */

/**
 * Show a confirmation dialog. Returns true if user confirms, false if cancelled.
 * @param {string} message
 * @returns {Promise<boolean>}
 */
function confirmDialog(message) {
  return new Promise(resolve => {
    const prevFocus = document.activeElement;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="dialog-box" role="alertdialog" aria-modal="true" aria-label="${escHtml(message)}">
        <p>${escHtml(message)}</p>
        <div class="dialog-actions">
          <button class="btn btn-sm btn-ghost" data-action="cancel">Cancel</button>
          <button class="btn btn-sm btn-danger" data-action="confirm">Confirm</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const cleanupFocus = trapFocus(overlay);
    const close = (result) => { overlay.remove(); cleanupFocus(); prevFocus?.focus(); resolve(result); };
    overlay.addEventListener('click', e => {
      const action = e.target.closest('[data-action]')?.dataset?.action;
      if (action === 'confirm') { close(true); }
      else if (action === 'cancel') { close(false); }
    });
    const onKey = (e) => { if (e.key === 'Escape') { close(false); } };
    document.addEventListener('keydown', onKey);
    const confirmBtn = overlay.querySelector('[data-action="confirm"]');
    if (confirmBtn) setTimeout(() => confirmBtn.focus(), 50);
  });
}

/**
 * Show a prompt dialog that asks the user for text input.
 * @param {string} message
 * @param {string} defaultValue
 * @returns {Promise<string|null>} — the entered value, or null if cancelled
 */
function promptDialog(message, defaultValue = '') {
  return new Promise(resolve => {
    const prevFocus = document.activeElement;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="dialog-box" role="dialog" aria-modal="true" aria-label="${escHtml(message)}">
        <p>${escHtml(message)}</p>
        <input type="text" class="dialog-input" value="${escHtml(defaultValue)}">
        <div class="dialog-actions">
          <button class="btn btn-sm btn-ghost" data-action="cancel">Cancel</button>
          <button class="btn btn-sm btn-primary" data-action="confirm">OK</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const cleanupFocus = trapFocus(overlay);
    const input = overlay.querySelector('.dialog-input');
    if (input) { input.focus(); input.select(); }
    const close = (result) => { overlay.remove(); cleanupFocus(); prevFocus?.focus(); resolve(result); };
    overlay.addEventListener('click', e => {
      const action = e.target.closest('[data-action]')?.dataset?.action;
      if (action === 'confirm') { close(input ? input.value : ''); }
      else if (action === 'cancel') { close(null); }
    });
    if (input) {
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { close(input.value); }
      });
      input.addEventListener('click', e => e.stopPropagation());
    }
    const onKey = (e) => { if (e.key === 'Escape') { close(null); } };
    document.addEventListener('keydown', onKey);
  });
}

/* ── Mobile Navigation ── */
function setupMobileNav() {
  const toggle = document.querySelector('.mobile-nav-toggle');
  if (!toggle) return;

  toggle.addEventListener('click', () => {
    document.body.classList.toggle('nav-open');
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') document.body.classList.remove('nav-open');
  });

  document.querySelectorAll('.sidebar-nav a, .sidebar-auth-prompt a').forEach(link => {
    link.addEventListener('click', () => {
      document.body.classList.remove('nav-open');
    });
  });
}

/* ── Credit limit check (call on pages where credits are consumed) ── */
async function checkCreditLimit() {
  if (typeof isAuthenticated !== 'function' || !isAuthenticated()) return;
  try {
    const res = await apiJSON('/billing/status');
    if (res.credits_used >= res.credits_limit && res.credits_limit > 0) {
      showToast('You\'ve used all your credits. Upgrade to continue processing.', 'warning');
      const existing = document.querySelector('.credit-upgrade-banner');
      if (!existing) {
        const banner = document.createElement('div');
        banner.className = 'credit-upgrade-banner';
        banner.style.cssText = 'background:linear-gradient(135deg,var(--purple-dim),var(--cyan-dim));border:1px solid var(--purple);border-radius:var(--radius-md);padding:1rem;margin-bottom:1rem;text-align:center;';
        banner.innerHTML = `<p style="margin-bottom:0.5rem;font-weight:600;">⚡ You've used all ${res.credits_limit} credits</p>
          <a href="billing.html" class="btn btn-primary btn-sm">Upgrade Plan</a>`;
        const mainArea = document.querySelector('.main-area');
        if (mainArea) mainArea.prepend(banner);
      }
    }
  } catch (e) { /* silently fail */ }
}

/* ── Service Worker Registration ── */
function registerSW() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/service-worker.js').then(reg => {
    reg.addEventListener('updatefound', () => {
      const newSW = reg.installing;
      if (!newSW) return;
      newSW.addEventListener('statechange', () => {
        if (newSW.state === 'installed' && navigator.serviceWorker.controller) {
          const toast = document.getElementById('toast-container');
          if (!toast) return;
          const el = document.createElement('div');
          el.className = 'toast toast-info';
          el.style.display = 'flex';
          el.style.alignItems = 'center';
          el.style.gap = '0.5rem';
          el.innerHTML = '<span style="flex:1">Update available</span><button class="btn btn-xs btn-primary" id="sw-update-btn" style="white-space:nowrap">Refresh</button>';
          el.setAttribute('role', 'alert');
          toast.appendChild(el);
          void el.offsetWidth;
          el.classList.add('toast-visible');
          el.querySelector('#sw-update-btn').addEventListener('click', () => {
            newSW.postMessage('SKIP_WAITING');
            window.location.reload();
          });
        }
      });
    });
  }).catch(() => {});
}

/* ── Initialize auth UI on load ── */
document.addEventListener('DOMContentLoaded', () => {
  const loginBtn = document.getElementById('login-btn');
  const logoutBtn = document.getElementById('logout-btn');

  loginBtn?.addEventListener('click', () => {
    window.location.href = 'login.html';
  });

  logoutBtn?.addEventListener('click', () => {
    if (typeof clearToken === 'function') clearToken();
    if (typeof logout === 'function') {
      logout();
    } else {
      window.location.href = 'login.html';
    }
  });

  updateAuthUI();
  setupNavigation();
  setupMobileNav();
  registerSW();
});

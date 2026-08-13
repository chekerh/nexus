/* Calendar — monthly view, compose drawer, timeline queue, rich preview */
(function () {
  'use strict';

  const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  function log(...args) { if (DEV) console.log(...args); }

  let currentYear = new Date().getFullYear();
  let currentMonth = new Date().getMonth();
  let allPosts = [];
  let allPersonas = [];

  document.addEventListener('DOMContentLoaded', () => {
    initCalendar();
    setupComposeDrawer();
    setupPostModal();
    updateAuthUI();
  });



  // ── Init Calendar ────────────────────────────────────────
  async function initCalendar() {
    const filter = document.getElementById('cal-persona-filter');
    filter.innerHTML = '<option value="">Loading personas...</option>';
    try {
      const pResp = await listPersonas();
      allPersonas = pResp.personas || [];
      filter.innerHTML = '<option value="">All Personas</option>';
      allPersonas.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        filter.appendChild(opt);
      });
      const params = new URLSearchParams(window.location.search);
      if (params.get('persona_id')) filter.value = params.get('persona_id');
    } catch (e) { console.error('Failed to load persona filter:', e); }

    document.getElementById('cal-prev').addEventListener('click', () => { currentMonth--; if (currentMonth < 0) { currentMonth = 11; currentYear--; } renderCalendar(); });
    document.getElementById('cal-next').addEventListener('click', () => { currentMonth++; if (currentMonth > 11) { currentMonth = 0; currentYear++; } renderCalendar(); });
    document.getElementById('cal-persona-filter').addEventListener('change', renderCalendar);
    document.getElementById('cal-platform-filter').addEventListener('change', renderCalendar);

    renderCalendar();
  }

  // ── Platform helpers ─────────────────────────────────────
  const PLATFORM_LABELS = {
    twitter: { icon: '𝕏', label: 'X', badge: 'twitter' },
    tiktok: { icon: '♪', label: 'TikTok', badge: 'tiktok' },
    instagram: { icon: '◻', label: 'Instagram', badge: 'instagram' },
    youtube: { icon: '▶', label: 'YouTube', badge: 'youtube' },
    linkedin: { icon: 'in', label: 'LinkedIn', badge: 'linkedin' },
    facebook: { icon: 'f', label: 'Facebook', badge: 'facebook' },
  };

  function platformBadgeHtml(platform) {
    const p = PLATFORM_LABELS[platform] || { icon: '?', label: platform, badge: '' };
    return `<span class="platform-badge ${p.badge}">${p.icon} ${p.label}</span>`;
  }

  // ── Render Calendar ──────────────────────────────────────
  async function renderCalendar() {
    const startDate = new Date(currentYear, currentMonth, 1);
    const endDate = new Date(currentYear, currentMonth + 1, 0);
    const personaId = document.getElementById('cal-persona-filter').value || undefined;
    const platform = document.getElementById('cal-platform-filter').value || undefined;

    const grid = document.getElementById('cal-grid');
    showLoading(grid, 'Loading calendar...');
    try {
      const resp = await getCalendar(startDate.toISOString(), endDate.toISOString(), personaId);
      allPosts = (resp.posts || []).filter(p => !platform || p.platform === platform);
    } catch (e) {
      console.error('Failed to load calendar:', e);
      allPosts = [];
    }

    document.getElementById('cal-month-year').textContent =
      new Date(currentYear, currentMonth).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const daysInPrev = new Date(currentYear, currentMonth, 0).getDate();
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const today = new Date();

    let html = dayNames.map(d => `<div class="cal-header">${d}</div>`).join('');

    // Previous month padding
    for (let i = firstDay - 1; i >= 0; i--) {
      html += `<div class="cal-day other-month"><div class="cal-day-number">${daysInPrev - i}</div></div>`;
    }

    // Current month
    for (let d = 1; d <= daysInMonth; d++) {
      const isToday = d === today.getDate() && currentMonth === today.getMonth() && currentYear === today.getFullYear();
      const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const dayPosts = allPosts.filter(p => p.scheduled_at && p.scheduled_at.slice(0, 10) === dateStr);

      html += `<div class="cal-day ${isToday ? 'today' : ''}" data-date="${dateStr}">
        <div class="cal-day-number">${d}</div>
        ${dayPosts.slice(0, 5).map(p =>
          `<div class="cal-post status-${p.status}" data-post-id="${p.id}">
            ${platformBadgeHtml(p.platform)} ${(escHtml(p.title) || 'Untitled').slice(0, 18)}
          </div>`
        ).join('')}
        ${dayPosts.length > 5 ? `<div class="cal-post" style="font-size:0.6rem;color:var(--text-dim);background:transparent">+${dayPosts.length - 5} more</div>` : ''}
      </div>`;
    }

    // Next month padding
    const totalCells = firstDay + daysInMonth;
    const remaining = 7 - (totalCells % 7);
    if (remaining < 7) {
      for (let i = 1; i <= remaining; i++) {
        html += `<div class="cal-day other-month"><div class="cal-day-number">${i}</div></div>`;
      }
    }

    grid.innerHTML = html;

    // Click post → open detail modal
    grid.querySelectorAll('.cal-post[data-post-id]').forEach(el => {
      el.addEventListener('click', e => {
        e.stopPropagation();
        openPostModal(el.dataset.postId);
      });
    });

    // Click day → open compose drawer
    grid.querySelectorAll('.cal-day:not(.other-month)').forEach(el => {
      el.addEventListener('click', () => {
        const date = el.dataset.date;
        if (date) openComposeDrawer(date);
      });
    });

    renderQueue();
  }

  // ── Compose Drawer ───────────────────────────────────────
  let composeDate = '';

  function setupComposeDrawer() {
    const overlay = document.getElementById('compose-drawer');
    if (!overlay) return;
    overlay.querySelectorAll('.drawer-close').forEach(el => {
      el.addEventListener('click', () => overlay.style.display = 'none');
    });
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; });
    document.getElementById('compose-save-btn')?.addEventListener('click', saveCompose);
    document.getElementById('compose-recurring')?.addEventListener('change', function() {
      document.getElementById('compose-recurring-options').style.display = this.checked ? '' : 'none';
    });
  }

  function openComposeDrawer(date) {
    composeDate = date;
    document.getElementById('compose-date').textContent = new Date(date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    document.getElementById('compose-persona').innerHTML = '<option value="">Select persona...</option>';
    allPersonas.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      document.getElementById('compose-persona').appendChild(opt);
    });
    // Pre-select persona filter
    const filterVal = document.getElementById('cal-persona-filter').value;
    if (filterVal) document.getElementById('compose-persona').value = filterVal;
    document.getElementById('compose-platform').value = document.getElementById('cal-platform-filter').value || 'twitter';
    document.getElementById('compose-title').value = '';
    document.getElementById('compose-body').value = '';
    document.getElementById('compose-time').value = '12:00';
    document.getElementById('compose-drawer').style.display = '';
    document.getElementById('compose-title').focus();
  }

  async function saveCompose() {
    const btn = document.getElementById('compose-save-btn');
    btn.disabled = true;
    btn.textContent = 'Scheduling...';
    const personaId = document.getElementById('compose-persona').value;
    if (!personaId) { showToast('Select a persona', 'error'); btn.disabled = false; btn.textContent = 'Schedule'; return; }
    const platform = document.getElementById('compose-platform').value;
    const title = document.getElementById('compose-title').value.trim();
    const body = document.getElementById('compose-body').value.trim();
    if (!title && !body) { showToast('Enter post content', 'error'); btn.disabled = false; btn.textContent = 'Schedule'; return; }
    const time = document.getElementById('compose-time').value || '12:00';
    const baseDate = new Date(`${composeDate}T${time}:00`);
    const scheduled_at = baseDate.toISOString();

    const recurring = document.getElementById('compose-recurring')?.checked;
    let dayChecks = [];
    if (recurring) {
      dayChecks = [...document.querySelectorAll('.recur-day:checked')].map(cb => cb.value);
      if (dayChecks.length === 0) { showToast('Select at least one day for recurring', 'warning'); btn.disabled = false; btn.textContent = 'Schedule'; return; }
    }

    try {
      await createPost({ persona_id: personaId, platform, title: title || body.slice(0, 60), body, scheduled_at });
      if (recurring && dayChecks.length > 0) {
        const dayNum = baseDate.getDay();
        for (const day of dayChecks) {
          const d = parseInt(day);
          if (d === dayNum) continue;
          const diff = (d - dayNum + 7) % 7;
          const nextDate = new Date(baseDate);
          nextDate.setDate(nextDate.getDate() + diff);
          await createPost({ persona_id: personaId, platform, title: title || body.slice(0, 60), body, scheduled_at: nextDate.toISOString() });
        }
      }
      showToast(`Post queued for ${composeDate}`, 'success');
      document.getElementById('compose-drawer').style.display = 'none';
      renderCalendar();
    } catch (err) { showToast(err.message, 'error'); }
    finally { btn.disabled = false; btn.textContent = 'Schedule'; }
  }

  // ── Queue (timeline) ─────────────────────────────────────
  async function renderQueue() {
    const div = document.getElementById('post-queue');
    showLoading(div, 'Loading queue...');
    try {
      const resp = await listPosts({ status: 'scheduled', limit: '15' });
      const posts = resp.posts || [];
      if (posts.length === 0) {
        showEmpty(div, '📅', 'No upcoming posts', 'Create a post on the calendar to see it here.');
        return;
      }
      div.innerHTML = `<div class="timeline">${posts.map(p => `
        <div class="timeline-item status-${p.status}" data-post-id="${p.id}">
          <div class="timeline-content">
            <div class="flex" style="justify-content:space-between;align-items:center">
              <div>
                <strong class="text-sm">${escHtml(p.title) || 'Untitled'}</strong>
                <div class="flex gap-1" style="margin-top:2px">
                  ${platformBadgeHtml(p.platform)}
                  <span class="text-dim text-xs">${p.scheduled_at ? new Date(p.scheduled_at).toLocaleString() : ''}</span>
                </div>
              </div>
              <span class="badge status-${escHtml(p.status)}" style="font-size:0.6rem;text-transform:capitalize;background:${statusBg(p.status)}">${escHtml(p.status)}</span>
            </div>
          </div>
        </div>`).join('')}</div>`;

      div.querySelectorAll('.timeline-item').forEach(el => {
        el.addEventListener('click', () => openPostModal(el.dataset.postId));
      });
    } catch (e) {
      console.error('Failed to load queue:', e);
      showError(div, e.message, 'renderQueue');
    }
  }

  function statusBg(status) {
    const map = {
      draft: 'rgba(148,163,184,0.08)',
      pending: 'rgba(251,191,36,0.12)',
      approved: 'rgba(0,229,255,0.1)',
      scheduled: 'rgba(74,222,128,0.1)',
      posted: 'rgba(74,222,128,0.1)',
      cancelled: 'rgba(248,113,113,0.1)',
    };
    return map[status] || 'rgba(148,163,184,0.08)';
  }

  // ── Post Modal ───────────────────────────────────────────
  function setupPostModal() {
    const modal = document.getElementById('post-modal');
    document.querySelectorAll('.modal-close').forEach(el => {
      el.addEventListener('click', () => { modal.style.display = 'none'; });
    });
    modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
  }

  async function openPostModal(postId) {
    try {
      const resp = await getPost(postId);
      const p = resp.post;
      const modal = document.getElementById('post-modal');
      document.getElementById('post-modal-title').textContent = p.title || 'Post Details';

      const personaName = (allPersonas.find(pa => pa.id === p.persona_id) || {}).name || p.persona_id;

      // Rich preview
      document.getElementById('post-modal-body').innerHTML = `
        <div class="post-preview-card" style="margin-bottom:1rem">
          <div class="post-platform-header">
            ${platformBadgeHtml(p.platform)}
            <span class="text-dim">via ${escHtml(personaName)}</span>
            <span class="badge" style="background:${statusBg(p.status)};text-transform:capitalize;margin-left:auto">${escHtml(p.status)}</span>
          </div>
          <div class="post-body">${escHtml(p.body) || 'No content'}</div>
          ${p.scheduled_at ? `<div class="text-dim text-xs" style="margin-top:0.75rem;padding-top:0.75rem;border-top:1px solid var(--glass-border)">Scheduled: ${new Date(p.scheduled_at).toLocaleString()}</div>` : ''}
          ${p.error ? `<div class="text-sm" style="margin-top:0.5rem;color:var(--red)">Error: ${escHtml(p.error)}</div>` : ''}
        </div>`;

      // Actions
      const actions = document.getElementById('post-modal-actions');
      let btns = '<button class="btn btn-ghost modal-close">Close</button>';

      if (p.status === 'draft') {
        btns += `<button class="btn btn-primary" id="post-approve-btn">Approve</button>`;
      } else if (p.status === 'pending') {
        btns += `<button class="btn btn-primary" id="post-approve-btn">Approve</button>
                 <button class="btn btn-ghost" id="post-cancel-btn" style="color:var(--red)">Cancel</button>`;
      } else if (p.status === 'approved') {
        btns += `<button class="btn btn-primary" id="post-schedule-btn">Set Schedule</button>
                 <button class="btn btn-ghost" id="post-cancel-btn" style="color:var(--red)">Cancel</button>`;
      } else if (p.status === 'scheduled') {
        btns += `<button class="btn btn-ghost" id="post-cancel-btn" style="color:var(--red)">Cancel</button>`;
      }
      if (p.status !== 'posted' && p.status !== 'cancelled') {
        btns += `<button class="btn btn-ghost" id="post-delete-btn" style="color:var(--red)">Delete</button>`;
      }

      actions.innerHTML = btns;

      // Bind action buttons
      document.getElementById('post-approve-btn')?.addEventListener('click', async function() {
        this.disabled = true;
        const orig = this.textContent;
        try {
          await approvePost(postId);
          showToast('Post ready to schedule', 'success');
          modal.style.display = 'none';
          renderCalendar();
        } catch (err) { showToast(err.message, 'error'); }
        finally { this.disabled = false; this.textContent = orig; }
      });

      document.getElementById('post-schedule-btn')?.addEventListener('click', () => {
        // Open compose-like schedule picker inline
        const bodyEl = document.getElementById('post-modal-body');
        const existing = bodyEl.querySelector('.schedule-picker');
        if (existing) existing.remove();
        const picker = document.createElement('div');
        picker.className = 'schedule-picker';
        picker.innerHTML = `
          <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid var(--glass-border)">
            <label class="text-dim text-sm" style="display:block;margin-bottom:0.3rem">Pick date & time</label>
            <div class="flex gap-1">
              <input type="datetime-local" id="schedule-dt" class="form-input" value="${new Date().toISOString().slice(0, 16)}" style="flex:1">
              <button class="btn btn-sm btn-primary" id="schedule-confirm-btn">Schedule</button>
            </div>
          </div>`;
        bodyEl.appendChild(picker);
        document.getElementById('schedule-confirm-btn').addEventListener('click', async function() {
          this.disabled = true;
          const orig = this.textContent;
          const val = document.getElementById('schedule-dt').value;
          if (!val) { this.disabled = false; return; }
          try {
            await schedulePost(postId, new Date(val).toISOString());
            showToast('Post scheduled', 'success');
            modal.style.display = 'none';
            renderCalendar();
          } catch (err) { showToast(err.message, 'error'); }
          finally { this.disabled = false; this.textContent = orig; }
        });
      });

      document.getElementById('post-cancel-btn')?.addEventListener('click', async function() {
        if (!await confirmDialog('Cancel this post?')) return;
        this.disabled = true;
        const orig = this.textContent;
        try {
          await cancelPost(postId);
          showToast('Post cancelled', 'warning');
          modal.style.display = 'none';
          renderCalendar();
        } catch (err) { showToast(err.message, 'error'); }
        finally { this.disabled = false; this.textContent = orig; }
      });

      document.getElementById('post-delete-btn')?.addEventListener('click', async function() {
        if (!await confirmDialog('Permanently delete this post?')) return;
        this.disabled = true;
        const orig = this.textContent;
        try {
          await deletePost(postId);
          showToast('Post removed', 'success');
          modal.style.display = 'none';
          renderCalendar();
        } catch (err) { showToast(err.message, 'error'); }
        finally { this.disabled = false; this.textContent = orig; }
      });

      modal.style.display = '';
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
})();

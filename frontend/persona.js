/* Personas — brand identities with stats, drawer, inline compose */
(function () {
  'use strict';

  const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  function log(...args) { if (DEV) console.log(...args); }

  let editingId = null;
  let allPersonas = [];
  let personaPostCounts = {};

  document.addEventListener('DOMContentLoaded', () => {
    loadPersonas();
    setupDrawer();
    setupRepurposeDrawer();
    updateAuthUI();
  });



  // ── Drawer (create/edit) ─────────────────────────────────
  function setupDrawer() {
    const overlay = document.getElementById('persona-drawer');
    if (!overlay) return;
    overlay.querySelectorAll('.drawer-close').forEach(el => {
      el.addEventListener('click', () => closeDrawer());
    });
    overlay.addEventListener('click', e => { if (e.target === overlay) closeDrawer(); });
    document.getElementById('save-persona-btn')?.addEventListener('click', savePersona);
    document.getElementById('create-persona-btn')?.addEventListener('click', () => openCreateDrawer());
  }

  function openCreateDrawer() {
    editingId = null;
    document.getElementById('drawer-title').textContent = 'Create Persona';
    document.getElementById('pf-id').value = '';
    document.getElementById('pf-name').value = '';
    document.getElementById('pf-bio').value = '';
    document.getElementById('pf-voice').value = '';
    document.getElementById('pf-audience').value = '';
    document.getElementById('pf-tone').value = 'professional';
    document.getElementById('pf-auto-approve').checked = false;
    document.getElementById('pf-pillars').value = '';
    document.getElementById('persona-drawer').style.display = '';
  }

  function openEditDrawer(persona) {
    editingId = persona.id;
    document.getElementById('drawer-title').textContent = 'Edit Persona';
    document.getElementById('pf-id').value = persona.id;
    document.getElementById('pf-name').value = persona.name;
    document.getElementById('pf-bio').value = persona.bio || '';
    document.getElementById('pf-voice').value = persona.voice_description || '';
    document.getElementById('pf-audience').value = persona.target_audience || '';
    document.getElementById('pf-tone').value = persona.tone || 'professional';
    document.getElementById('pf-auto-approve').checked = persona.auto_approve || false;
    document.getElementById('pf-pillars').value = (persona.content_pillars || []).join('\n');
    document.getElementById('persona-drawer').style.display = '';
  }

  function closeDrawer() {
    document.getElementById('persona-drawer').style.display = 'none';
    editingId = null;
  }

  async function savePersona() {
    const btn = document.getElementById('save-persona-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';
    const data = {
      name: document.getElementById('pf-name').value.trim(),
      bio: document.getElementById('pf-bio').value.trim(),
      voice_description: document.getElementById('pf-voice').value.trim(),
      target_audience: document.getElementById('pf-audience').value.trim(),
      tone: document.getElementById('pf-tone').value,
      auto_approve: document.getElementById('pf-auto-approve').checked,
      content_pillars: JSON.stringify(
        document.getElementById('pf-pillars').value.split('\n').map(s => s.trim()).filter(Boolean)
      ),
    };
    if (!data.name) { showToast('Name is required', 'error'); btn.disabled = false; btn.textContent = 'Save Persona'; return; }
    try {
      if (editingId) {
        await updatePersona(editingId, data);
        showToast(`"${data.name}" saved`, 'success');
      } else {
        await createPersona(data);
        showToast(`"${data.name}" ready`, 'success');
      }
      closeDrawer();
      loadPersonas();
    } catch (err) { showToast(err.message, 'error'); }
    finally { btn.disabled = false; btn.textContent = 'Save Persona'; }
  }

  // ── Repurpose Drawer ─────────────────────────────────────
  function setupRepurposeDrawer() {
    const overlay = document.getElementById('repurpose-drawer');
    if (!overlay) return;
    overlay.querySelectorAll('.drawer-close').forEach(el => {
      el.addEventListener('click', () => overlay.style.display = 'none');
    });
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.style.display = 'none'; });
    document.getElementById('repurpose-generate-btn')?.addEventListener('click', runRepurpose);
  }

  let repurposePersonaId = null;

  function openRepurposeDrawer(personaId) {
    repurposePersonaId = personaId;
    const persona = allPersonas.find(p => p.id === personaId);
    document.getElementById('repurpose-drawer-title').textContent = `Repurpose for ${persona?.name || 'Persona'}`;
    document.getElementById('repurpose-transcript').value = '';
    document.getElementById('repurpose-results').innerHTML = '';
    document.getElementById('repurpose-results').style.display = 'none';
    document.getElementById('repurpose-generate-btn').style.display = '';
    document.getElementById('repurpose-drawer').style.display = '';
  }

  async function runRepurpose() {
    const transcript = document.getElementById('repurpose-transcript').value.trim();
    if (!transcript) { showToast('Paste a transcript first', 'error'); return; }
    const btn = document.getElementById('repurpose-generate-btn');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    try {
      const resp = await repurposeContent(repurposePersonaId, transcript, ['twitter', 'linkedin', 'instagram', 'facebook']);
      const results = resp.results || {};
      const platforms = Object.keys(results);
      const container = document.getElementById('repurpose-results');
      container.style.display = '';

      let tabsHtml = '<div class="gen-tabs">';
      let contentHtml = '';
      platforms.forEach((platform, idx) => {
        const active = idx === 0 ? ' active' : '';
        tabsHtml += `<button class="gen-tab${active}" data-platform="${platform}">${platform}</button>`;
        contentHtml += `<div class="gen-platform-content" data-platform="${platform}" style="${idx === 0 ? '' : 'display:none'}">`;
        (results[platform] || []).forEach(post => {
          contentHtml += `
            <div class="gen-content-item">
              <strong style="font-size:0.85rem">${escHtml(post.title) || 'Untitled'}</strong>
              <p class="text-dim text-sm" style="margin:0.25rem 0">${escHtml(post.body)}</p>
              <button class="btn btn-xs btn-primary gen-use-btn" data-platform="${platform}" data-title="${(post.title || '').replace(/"/g, '&quot;')}" data-body="${(post.body || '').replace(/"/g, '&quot;')}">Use This</button>
            </div>`;
        });
        contentHtml += '</div>';
      });
      tabsHtml += '</div>';
      container.innerHTML = tabsHtml + contentHtml;

      // Tab switching
      container.querySelectorAll('.gen-tab').forEach(tab => {
        tab.addEventListener('click', () => {
          container.querySelectorAll('.gen-tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          container.querySelectorAll('.gen-platform-content').forEach(c => c.style.display = 'none');
          const el = container.querySelector(`.gen-platform-content[data-platform="${tab.dataset.platform}"]`);
          if (el) el.style.display = '';
        });
      });

      // "Use This" buttons
      container.querySelectorAll('.gen-use-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          btn.disabled = true;
          btn.textContent = 'Adding...';
          try {
            await createPost({
              persona_id: repurposePersonaId,
              platform: btn.dataset.platform,
              title: btn.dataset.title,
              body: btn.dataset.body,
              source_transcript: transcript.slice(0, 500),
            });
            showToast(`${btn.dataset.platform} post saved as draft`, 'success');
            btn.textContent = '✓ Added';
          } catch (err) {
            showToast(err.message, 'error');
            btn.disabled = false;
            btn.textContent = 'Use This';
          }
        });
      });
    } catch (err) {
      showToast(err.message, 'error');
      document.getElementById('repurpose-results').innerHTML = `<div class="text-dim" style="color:var(--red)">${escHtml(err.message)}</div>`;
    }
    btn.disabled = false;
    btn.textContent = 'Generate';
  }

  // ── Load Personas ────────────────────────────────────────
  async function loadPersonas() {
    const grid = document.getElementById('personas-grid');
    showLoading(grid, 'Loading personas...');
    try {
      const resp = await listPersonas();
      allPersonas = resp.personas || [];

      // Load post counts for each persona
      try {
        const postsResp = await listPosts({ limit: '500' });
        const posts = postsResp.posts || [];
        personaPostCounts = {};
        posts.forEach(p => {
          const pid = p.persona_id;
          if (!personaPostCounts[pid]) personaPostCounts[pid] = { total: 0, scheduled: 0, posted: 0 };
          personaPostCounts[pid].total++;
          if (p.status === 'scheduled') personaPostCounts[pid].scheduled++;
          if (p.status === 'posted') personaPostCounts[pid].posted++;
        });
      } catch (e) {}

      if (allPersonas.length === 0) {
        showEmpty(grid, '👤', 'No personas yet', 'Create your first brand identity to start posting');
        return;
      }
      grid.innerHTML = allPersonas.map(p => renderCard(p)).join('');
      bindCardActions();
    } catch (err) {
      showError(grid, err.message, 'loadPersonas');
    }
  }

  function getToneColor(tone) {
    const map = {
      professional: { bg: 'rgba(0,229,255,0.1)', color: 'var(--cyan)' },
      casual: { bg: 'rgba(74,222,128,0.1)', color: 'var(--green)' },
      humorous: { bg: 'rgba(251,191,36,0.12)', color: 'var(--amber)' },
      inspirational: { bg: 'rgba(139,92,246,0.12)', color: 'var(--purple)' },
      educational: { bg: 'rgba(236,72,153,0.1)', color: 'var(--pink)' },
      controversial: { bg: 'rgba(248,113,113,0.1)', color: 'var(--red)' },
    };
    return map[tone] || map.professional;
  }

  function renderCard(p) {
    const tc = getToneColor(p.tone);
    const initial = (p.name || '?')[0].toUpperCase();
    const stats = personaPostCounts[p.id] || { total: 0, scheduled: 0, posted: 0 };
    const pillarCount = (p.content_pillars || []).length;

    return `<div class="glass-card persona-card" data-id="${p.id}">
      <div class="flex" style="justify-content:space-between;align-items:flex-start">
        <div class="flex gap-2" style="align-items:center">
          <div class="persona-avatar" style="background:${tc.bg};color:${tc.color}">${initial}</div>
          <div>
            <h3 style="margin:0;font-size:1.05rem">${p.name}</h3>
            <div class="flex gap-1" style="margin-top:4px">
              <span class="badge" style="background:${tc.bg};color:${tc.color}">${p.tone}</span>
              <span class="badge" style="background:${p.auto_approve ? 'rgba(74,222,128,0.1)' : 'rgba(148,163,184,0.08)'};color:${p.auto_approve ? 'var(--green)' : 'var(--text-dim)'}">
                ${p.auto_approve ? 'Auto' : 'Manual'}
              </span>
            </div>
          </div>
        </div>
      </div>
      ${p.bio ? `<p class="text-dim text-sm" style="margin:0;line-height:1.4">${p.bio}</p>` : ''}
      <div class="persona-stats">
        <div class="persona-stat">
          <div class="persona-stat-value">${stats.total}</div>
          <div class="persona-stat-label">Posts</div>
        </div>
        <div class="persona-stat">
          <div class="persona-stat-value" style="color:var(--green)">${stats.scheduled}</div>
          <div class="persona-stat-label">Scheduled</div>
        </div>
        <div class="persona-stat">
          <div class="persona-stat-value" style="color:var(--cyan)">${stats.posted}</div>
          <div class="persona-stat-label">Posted</div>
        </div>
        <div class="persona-stat">
          <div class="persona-stat-value">${pillarCount}</div>
          <div class="persona-stat-label">Pillars</div>
        </div>
      </div>
      ${p.voice_description ? `<p class="text-dim text-xs" style="margin:0">🎙 ${p.voice_description}</p>` : ''}
      <div class="flex gap-1" style="margin-top:0.25rem">
        <button class="btn btn-xs btn-ghost edit-persona-btn">Edit</button>
        <button class="btn btn-xs btn-ghost repurpose-persona-btn">Repurpose</button>
        <button class="btn btn-xs btn-ghost schedules-persona-btn">Calendar</button>
        <button class="btn btn-xs btn-ghost delete-persona-btn" style="color:var(--red)">Delete</button>
      </div>
    </div>`;
  }

  function bindCardActions() {
    document.querySelectorAll('.edit-persona-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.closest('.persona-card').dataset.id;
        try {
          const resp = await getPersona(id);
          openEditDrawer(resp.persona);
        } catch (err) { showToast(err.message, 'error'); }
      });
    });

    document.querySelectorAll('.delete-persona-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.closest('.persona-card').dataset.id;
        const ok = await confirmDialog('This will permanently delete this persona and all its posts. This action cannot be undone.');
        if (!ok) return;
        try {
          await deletePersona(id);
          showToast('Persona removed', 'success');
          loadPersonas();
        } catch (err) { showToast(err.message, 'error'); }
      });
    });

    document.querySelectorAll('.schedules-persona-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        window.location.href = `/calendar.html?persona_id=${btn.closest('.persona-card').dataset.id}`;
      });
    });

    document.querySelectorAll('.repurpose-persona-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        openRepurposeDrawer(btn.closest('.persona-card').dataset.id);
      });
    });
  }
})();

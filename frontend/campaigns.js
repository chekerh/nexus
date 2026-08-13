/* Campaigns page — create, manage, activate campaigns */
(function() {
  'use strict';

  const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  function log(...args) { if (DEV) console.log(...args); }

  let editingId = null;
  let allPersonas = [];

  document.addEventListener('DOMContentLoaded', () => {
    setupModal();
    loadPersonas().then(() => loadCampaigns());
  });





  function setupModal() {
    const modal = document.getElementById('campaign-modal');
    document.querySelectorAll('.modal-close').forEach(el => {
      el.addEventListener('click', () => { modal.style.display = 'none'; editingId = null; });
    });
    modal.addEventListener('click', e => { if (e.target === modal) { modal.style.display = 'none'; editingId = null; }});
    document.getElementById('save-campaign-btn').addEventListener('click', saveCampaign);
    document.getElementById('create-campaign-btn').addEventListener('click', openCreateModal);
  }

  async function loadPersonas() {
    try {
      const resp = await listPersonas();
      allPersonas = resp.personas || [];
      const sel = document.getElementById('cf-persona');
      allPersonas.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        sel.appendChild(opt);
      });
    } catch (e) {}
  }

  function openCreateModal() {
    editingId = null;
    document.getElementById('campaign-modal-title').textContent = 'Create Campaign';
    document.getElementById('cf-id').value = '';
    document.getElementById('cf-name').value = '';
    document.getElementById('cf-description').value = '';
    document.getElementById('cf-persona').value = '';
    document.getElementById('cf-start').value = '';
    document.getElementById('cf-end').value = '';
    const btn = document.getElementById('save-campaign-btn');
    btn.disabled = false; btn.textContent = 'Create Campaign';
    document.getElementById('campaign-modal').style.display = '';
  }

  function openEditModal(c) {
    editingId = c.id;
    document.getElementById('campaign-modal-title').textContent = 'Edit Campaign';
    document.getElementById('cf-id').value = c.id;
    document.getElementById('cf-name').value = c.name;
    document.getElementById('cf-description').value = c.description || '';
    document.getElementById('cf-persona').value = c.persona_id || '';
    document.getElementById('cf-start').value = c.start_date ? c.start_date.slice(0, 10) : '';
    document.getElementById('cf-end').value = c.end_date ? c.end_date.slice(0, 10) : '';
    // Set platforms
    document.querySelectorAll('#cf-platforms input[type="checkbox"]').forEach(cb => {
      cb.checked = (c.platforms || []).includes(cb.value);
    });
    const btn = document.getElementById('save-campaign-btn');
    btn.disabled = false; btn.textContent = 'Save Campaign';
    document.getElementById('campaign-modal').style.display = '';
  }

  async function saveCampaign() {
    const btn = document.getElementById('save-campaign-btn');
    btn.disabled = true;
    btn.textContent = editingId ? 'Saving...' : 'Creating...';
    const name = document.getElementById('cf-name').value.trim();
    if (!name) { showToast('Name is required', 'error'); btn.disabled = false; btn.textContent = editingId ? 'Save Campaign' : 'Create Campaign'; return; }

    const platforms = Array.from(document.querySelectorAll('#cf-platforms input:checked')).map(cb => cb.value);
    const data = {
      name,
      description: document.getElementById('cf-description').value.trim(),
      platforms: JSON.stringify(platforms),
      persona_id: document.getElementById('cf-persona').value,
      start_date: document.getElementById('cf-start').value || null,
      end_date: document.getElementById('cf-end').value || null,
    };

    try {
      if (editingId) {
        await updateCampaign(editingId, data);
        showToast(`"${name}" saved`, 'success');
      } else {
        await createCampaign(data);
        showToast(`"${name}" ready`, 'success');
      }
      document.getElementById('campaign-modal').style.display = 'none';
      editingId = null;
      loadCampaigns();
      btn.disabled = false; btn.textContent = editingId ? 'Save Campaign' : 'Create Campaign';
    } catch (err) { showToast(err.message, 'error'); btn.disabled = false; btn.textContent = editingId ? 'Save Campaign' : 'Create Campaign'; }
  }

  async function loadCampaigns() {
    const grid = document.getElementById('campaigns-grid');
    showLoading(grid, 'Loading campaigns...');
    try {
      const resp = await listCampaigns();
      const campaigns = resp.campaigns || [];
      if (campaigns.length === 0) {
        showEmpty(grid, '🎯', 'No campaigns yet', 'Create your first campaign to automate content distribution.');
        return;
      }
      grid.innerHTML = campaigns.map(c => renderCampaignCard(c)).join('');
      bindActions();
    } catch (err) {
      showError(grid, err.message, 'loadCampaigns');
    }
  }

  function renderCampaignCard(c) {
    const persona = allPersonas.find(p => p.id === c.persona_id);
    const statusColors = { draft: 'var(--text-dim)', active: 'var(--green)', paused: 'var(--amber)', completed: 'var(--cyan)' };
    const platforms = (c.platforms || []).join(', ');
    return `<div class="glass-card" data-id="${c.id}">
      <div class="flex" style="justify-content:space-between;align-items:start">
        <div>
          <h3 style="margin:0 0 0.25rem;font-size:1.1rem">${escHtml(c.name)}</h3>
          <span class="text-dim text-sm">${platforms}</span>
        </div>
        <span class="badge" style="background:rgba(148,163,184,0.1);color:${statusColors[c.status] || 'var(--text-dim)'}">
          ${escHtml(c.status)}
        </span>
      </div>
      ${c.description ? `<p class="text-dim text-sm" style="margin:0.5rem 0">${escHtml(c.description)}</p>` : ''}
      <div class="text-dim text-xs" style="margin:0.25rem 0">
        ${persona ? `Persona: ${escHtml(persona.name)}` : 'No persona'}
        ${c.start_date ? ` · ${c.start_date.slice(0, 10)} → ${c.end_date ? c.end_date.slice(0, 10) : 'ongoing'}` : ''}
      </div>
      <div class="flex gap-1" style="margin-top:0.75rem">
        <button class="btn btn-xs btn-ghost view-campaign-btn">👁 View</button>
        <button class="btn btn-xs btn-ghost edit-campaign-btn">✏️ Edit</button>
        ${c.status === 'draft' ? `<button class="btn btn-xs btn-primary activate-campaign-btn">▶ Activate</button>` : ''}
        ${c.status === 'active' ? `<button class="btn btn-xs btn-ghost pause-campaign-btn">⏸ Pause</button>` : ''}
        <button class="btn btn-xs btn-ghost delete-campaign-btn" style="color:var(--red)">🗑 Delete</button>
      </div>
    </div>`;
  }

  function bindActions() {
    document.querySelectorAll('.view-campaign-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.closest('.glass-card').dataset.id;
        try {
          const resp = await getCampaign(id);
          const c = resp.campaign;
          const posts = resp.posts || [];
          const modal = document.getElementById('detail-modal');
          document.getElementById('detail-title').textContent = c.name;
          const persona = allPersonas.find(p => p.id === c.persona_id);
          document.getElementById('detail-body').innerHTML = `
            <div class="text-sm text-dim" style="margin-bottom:1rem">${escHtml(c.description) || 'No description'}</div>
            <div class="flex gap-1" style="margin-bottom:1rem">
              <span class="badge" style="background:rgba(148,163,184,0.1)">${escHtml(c.status)}</span>
              <span class="text-xs text-dim">${(c.platforms || []).join(', ')}</span>
              ${persona ? `<span class="text-xs text-dim">Persona: ${escHtml(persona.name)}</span>` : ''}
            </div>
            <h4 style="margin:0 0 0.5rem">Posts (${posts.length})</h4>
            ${posts.length === 0 ? '<div class="text-dim text-sm">No posts in this campaign yet. Create posts from Persona page.</div>' :
              posts.map(p => `<div class="text-sm" style="background:rgba(148,163,184,0.03);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:0.5rem;margin-bottom:0.3rem">
                <span class="badge" style="font-size:0.55rem;text-transform:capitalize;background:rgba(148,163,184,0.1)">${escHtml(p.platform)}</span>
                ${escHtml(p.title) || 'Untitled'}
                <span class="badge status-${escHtml(p.status)}" style="font-size:0.55rem;float:right">${escHtml(p.status)}</span>
              </div>`).join('')
            }
          `;
          document.getElementById('detail-activate-btn').classList.toggle('hidden', c.status !== 'draft');
          document.getElementById('detail-pause-btn').classList.toggle('hidden', c.status !== 'active');
          document.getElementById('detail-activate-btn').onclick = async () => {
            try { await activateCampaign(id); showToast('Campaign is live', 'success'); modal.style.display = 'none'; loadCampaigns(); } catch (err) { showToast(err.message, 'error'); }
          };
          document.getElementById('detail-pause-btn').onclick = async () => {
            try { await pauseCampaign(id); showToast('Campaign paused', 'warning'); modal.style.display = 'none'; loadCampaigns(); } catch (err) { showToast(err.message, 'error'); }
          };
          modal.style.display = '';
        } catch (err) { showToast(err.message, 'error'); }
      });
    });

    document.querySelectorAll('.edit-campaign-btn').forEach(btn => {
      const card = btn.closest('.glass-card');
      btn.addEventListener('click', async () => {
        try {
          const resp = await getCampaign(card.dataset.id);
          openEditModal(resp.campaign);
        } catch (err) { showToast(err.message, 'error'); }
      });
    });

    document.querySelectorAll('.activate-campaign-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.closest('.glass-card').dataset.id;
        try { await activateCampaign(id); showToast('Campaign is live', 'success'); loadCampaigns(); } catch (err) { showToast(err.message, 'error'); }
      });
    });

    document.querySelectorAll('.pause-campaign-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.closest('.glass-card').dataset.id;
        try { await pauseCampaign(id); showToast('Campaign paused', 'warning'); loadCampaigns(); } catch (err) { showToast(err.message, 'error'); }
      });
    });

    document.querySelectorAll('.delete-campaign-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!await confirmDialog('Delete this campaign? Posts will remain.')) return;
        try { await deleteCampaign(btn.closest('.glass-card').dataset.id); showToast('Deleted', 'success'); loadCampaigns(); } catch (err) { showToast(err.message, 'error'); }
      });
    });
  }
})();

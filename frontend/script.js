/* ================================================================
   Nexus-UGC v3 — Immersive App Logic
   ================================================================ */

(function() {
  'use strict';

  const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  function log(...args) { if (DEV) console.log(...args); }

  // ----- Navbar Scroll Effect -----
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          navbar.classList.toggle('scrolled', window.scrollY > 50);
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // ----- Scroll Reveal Animations -----
  const revealElements = document.querySelectorAll('.reveal');
  if (revealElements.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    );
    revealElements.forEach(el => observer.observe(el));
  }



  // ================================================================
  //  APP LOGIC
  // ================================================================

  // DOM refs
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const processBtn = document.getElementById('process-btn');
  const processDriveBtn = document.getElementById('process-drive-btn');
  const driveUrlInput = document.getElementById('drive-url');
  const statusSection = document.getElementById('status-section');
  const resultsSection = document.getElementById('results-section');
  const thinkingConsole = document.getElementById('thinking-console');
  const statusTitle = document.getElementById('status-title');
  const timingSummary = document.getElementById('timing-summary');
  const transcriptContent = document.getElementById('transcript-content');
  const analysisContent = document.getElementById('analysis-content');
  const clipsContainer = document.getElementById('clips-container');
  const stopBtn = document.getElementById('stop-btn');
  const progressFill = document.getElementById('progress-fill');

  const statusTimer = document.getElementById('status-timer');
  let timerInterval = null;
  let timerSeconds = 0;

  // Tab switching
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = {
    file: document.getElementById('content-file'),
    drive: document.getElementById('content-drive'),
    endscreen: document.getElementById('content-endscreen'),
  };

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      Object.values(tabContents).forEach(c => c?.classList.remove('active'));
      const tab = btn.dataset.tab;
      if (tabContents[tab]) tabContents[tab].classList.add('active');
    });
  });

  // File selection
  let selectedFile = null;

  if (dropzone) {
    dropzone.addEventListener('click', () => fileInput?.click());
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files.length) {
        selectedFile = e.dataTransfer.files[0];
        updateFileUI();
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        selectedFile = fileInput.files[0];
        updateFileUI();
      }
    });
  }

  function updateFileUI() {
    if (!dropzone || !selectedFile) return;
    const sizeStr = (selectedFile.size / (1024 * 1024)).toFixed(1);
    dropzone.querySelector('.dropzone-text').textContent = `📁 ${selectedFile.name} (${sizeStr} MB)`;
    dropzone.querySelector('.dropzone-hint').textContent = 'Click to change file';
    if (processBtn) processBtn.disabled = false;
  }

  // End screen
  let endscreenFile = null;
  const endscreenInput = document.getElementById('endscreen-input');
  const endscreenDropzone = document.getElementById('endscreen-dropzone');
  const endscreenBadge = document.getElementById('endscreen-badge');
  const ctaTextInput = document.getElementById('cta-text-input');

  if (endscreenDropzone) {
    endscreenDropzone.addEventListener('click', () => endscreenInput?.click());
    endscreenInput?.addEventListener('change', () => {
      if (endscreenInput.files.length) {
        endscreenFile = endscreenInput.files[0];
        if (endscreenBadge) {
          endscreenBadge.textContent = `🎯 End screen: ${endscreenFile.name}`;
          endscreenBadge.className = 'endscreen-badge active';
        }
      }
    });
  }

  // ---- Hero CTA scroll ----
  const heroCta = document.getElementById('hero-cta');
  if (heroCta) {
    heroCta.addEventListener('click', () => {
      document.getElementById('app')?.scrollIntoView({ behavior: 'smooth' });
    });
  }

  // Scroll-to-section buttons
  function scrollToFeatures() {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
  }
  document.getElementById('scroll-to-features')?.addEventListener('click', scrollToFeatures);

  function scrollToApp() {
    document.getElementById('app')?.scrollIntoView({ behavior: 'smooth' });
  }
  document.querySelectorAll('[id^="scroll-to-app-"]').forEach(btn => {
    btn.addEventListener('click', scrollToApp);
  });

  // ---- Processing ----
  let currentProcessId = null;
  let statusPollInterval = null;
  let sseSource = null;

  function startStatusTimer() {
    timerSeconds = 0;
    if (statusTimer) statusTimer.textContent = '00:00';
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      timerSeconds++;
      const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
      const s = String(timerSeconds % 60).padStart(2, '0');
      if (statusTimer) statusTimer.textContent = `${m}:${s}`;
    }, 1000);
  }

  function stopStatusTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  function connectSSE(processId) {
    if (sseSource) {
      sseSource.close();
      sseSource = null;
    }
    sseSource = connectProgressSSE(processId, {
      onThought(thought) {
        if (thinkingConsole) {
          const line = document.createElement('div');
          line.className = 'thinking-line';
          line.textContent = `> ${thought}`;
          thinkingConsole.appendChild(line);
          thinkingConsole.scrollTop = thinkingConsole.scrollHeight;
        }
      },
      onStage(stage) {
        const labels = {
          initializing: 'Initializing...',
          drive_download: 'Downloading from Drive...',
          transcription: 'Transcribing Audio...',
          translation: 'Translating...',
          analysis: 'Analyzing Content...',
          cutting: 'Rendering Clips...',
          virality_scoring: 'Scoring Clips...',
          completed: 'Complete!',
          failed: 'Failed',
        };
        if (statusTitle) statusTitle.innerText = labels[stage] || `AI Processing (${stage})...`;
      },
      onProgress(percent) {
        if (progressFill) progressFill.style.width = `${percent}%`;
      },
      onMessage(msg) {
        if (thinkingConsole) {
          const line = document.createElement('div');
          line.className = 'thinking-line';
          line.textContent = `> ${msg}`;
          thinkingConsole.appendChild(line);
          thinkingConsole.scrollTop = thinkingConsole.scrollHeight;
        }
      },
      onDone(data) {
        if (progressFill) progressFill.style.width = '100%';
        if (data.status === 'completed') {
          if (statusTitle) statusTitle.innerText = '✅ Complete!';
          if (thinkingConsole) {
            const line = document.createElement('div');
            line.className = 'thinking-line';
            line.textContent = '> Pipeline completed successfully.';
            thinkingConsole.appendChild(line);
          }
          stopStatusTimer();
          if (sseSource) { sseSource.close(); sseSource = null; }
          clearInterval(statusPollInterval);
          statusPollInterval = null;
          currentProcessId = null;
          if (stopBtn) stopBtn.disabled = false;
          showResults(data, processId);
          showToast(`Pipeline complete — Finished in ${data.timing?.total_seconds || '?'}s`, 'success');
        } else if (data.status === 'failed') {
          if (statusTitle) statusTitle.innerText = '❌ Failed';
          if (thinkingConsole) {
            const line = document.createElement('div');
            line.className = 'thinking-line error';
            line.textContent = `> Error: ${data.error || 'Unknown error'}`;
            thinkingConsole.appendChild(line);
          }
          stopStatusTimer();
          if (sseSource) { sseSource.close(); sseSource = null; }
          clearInterval(statusPollInterval);
          statusPollInterval = null;
          currentProcessId = null;
          if (processBtn) processBtn.disabled = false;
          if (processDriveBtn) { processDriveBtn.disabled = false; processDriveBtn.innerText = 'Fetch from Drive & Analyze'; }
          showToast(data.error || 'Pipeline failed', 'error');
        } else if (data.status === 'cancelled') {
          if (statusTitle) statusTitle.innerText = '⛔ Cancelled';
          if (thinkingConsole) {
            const line = document.createElement('div');
            line.className = 'thinking-line';
            line.textContent = '> Pipeline cancelled by user.';
            thinkingConsole.appendChild(line);
          }
          stopStatusTimer();
          if (sseSource) { sseSource.close(); sseSource = null; }
          clearInterval(statusPollInterval);
          statusPollInterval = null;
          currentProcessId = null;
          if (processBtn) processBtn.disabled = false;
          if (processDriveBtn) { processDriveBtn.disabled = false; processDriveBtn.innerText = 'Fetch from Drive & Analyze'; }
        }
      },
      onError() {
        if (thinkingConsole) {
          const line = document.createElement('div');
          line.className = 'thinking-line error';
          line.textContent = '> SSE connection lost, falling back to polling...';
          thinkingConsole.appendChild(line);
        }
      },
    });
  }

  function cleanupSSE() {
    if (sseSource) {
      sseSource.close();
      sseSource = null;
    }
  }

  // Upload handler
  if (processBtn) {
    processBtn.addEventListener('click', async () => {
      if (!selectedFile) return;

      const formData = new FormData();
      formData.append('file', selectedFile);
      if (endscreenFile) formData.append('endscreen_image', endscreenFile);
      formData.append('cta_text', ctaTextInput?.value?.trim() || 'Link in bio to try it free.');
      formData.append('language', document.getElementById('lang-select')?.value || 'en');
      formData.append('aspect_ratio', document.getElementById('ar-select')?.value || 'vertical_9_16');

      processBtn.disabled = true;
      if (statusSection) statusSection.style.display = '';
      if (resultsSection) resultsSection.style.display = 'none';
      if (thinkingConsole) thinkingConsole.innerHTML = '<div class="thinking-line">Initializing local AI pipeline...</div>';
      if (statusTitle) statusTitle.innerText = 'AI Processing...';
      if (timingSummary) timingSummary.innerText = 'Awaiting stage metrics...';
      if (progressFill) progressFill.style.width = '0%';
      if (statusSection) statusSection.scrollIntoView({ behavior: 'smooth' });
      startStatusTimer();

      try {
        const response = await api('/process', { method: 'POST', body: formData });
        const data = await response.json();
        currentProcessId = data.process_id;
        connectSSE(data.process_id);
        // Fallback polling (slower) for completion detection if SSE fails
        statusPollInterval = setInterval(async () => {
          try {
            const statusData = await apiJSON(`/status/${data.process_id}`);
            if (statusData.status === 'completed' || statusData.status === 'failed' || statusData.status === 'cancelled') {
              clearInterval(statusPollInterval);
              statusPollInterval = null;
            }
          } catch {}
        }, 5000);
      } catch (err) {
        if (thinkingConsole) thinkingConsole.innerHTML += `<div class="thinking-line error">Error: ${escHtml(err.message)}</div>`;
        processBtn.disabled = false;
      }
    });
  }

  // Drive handler
  if (processDriveBtn) {
    processDriveBtn.addEventListener('click', async () => {
      const driveUrl = driveUrlInput?.value?.trim();
      if (!driveUrl) { showToast('Please paste a Google Drive URL', 'error'); return; }

      processDriveBtn.disabled = true;
      processDriveBtn.innerText = 'Downloading...';
      if (statusSection) statusSection.style.display = '';
      if (resultsSection) resultsSection.style.display = 'none';
      if (thinkingConsole) thinkingConsole.innerHTML = '<div class="thinking-line">Connecting to Google Drive...</div>';
      if (statusTitle) statusTitle.innerText = 'AI Processing...';
      if (timingSummary) timingSummary.innerText = 'Awaiting stage metrics...';
      startStatusTimer();

      try {
        const drivelang = document.getElementById('drive-lang-select');
        const driveAr = document.getElementById('drive-ar-select');
        const data = await apiJSON('/process-drive', {
          method: 'POST',
          body: {
            drive_url: driveUrl,
            language: drivelang?.value || 'en',
            aspect_ratio: driveAr?.value || 'vertical_9_16'
          }
        });
        currentProcessId = data.process_id;
        connectSSE(data.process_id);
        statusPollInterval = setInterval(async () => {
          try {
            const statusData = await apiJSON(`/status/${data.process_id}`);
            if (statusData.status === 'completed' || statusData.status === 'failed' || statusData.status === 'cancelled') {
              clearInterval(statusPollInterval);
              statusPollInterval = null;
            }
          } catch {}
        }, 5000);
      } catch (err) {
        if (thinkingConsole) thinkingConsole.innerHTML += `<div class="thinking-line error">Error: ${escHtml(err.message)}</div>`;
        processDriveBtn.disabled = false;
        processDriveBtn.innerText = 'Fetch from Drive & Analyze';
      }
    });
  }

  // Cancel
  if (stopBtn) {
    stopBtn.addEventListener('click', async function() {
      if (!currentProcessId) return;
      this.disabled = true;
      try {
        await apiJSON(`/cancel/${currentProcessId}`, { method: 'POST' });
        if (thinkingConsole) thinkingConsole.innerHTML += `<div class="thinking-line">Cancelling...</div>`;
        cleanupSSE();
        clearInterval(statusPollInterval);
        statusPollInterval = null;
      } catch (err) {
        showToast(`Cancel failed: ${err.message}`, 'error');
      } finally {
        this.disabled = false;
      }
    });
  }

  // ---- Results ----
  function showResults(data, processId) {
    if (statusSection) statusSection.style.display = 'none';
    if (resultsSection) resultsSection.style.display = '';
    resultsSection?.scrollIntoView({ behavior: 'smooth' });

    if (transcriptContent) transcriptContent.innerText = data.transcript;

    // Clear
    if (clipsContainer) clipsContainer.innerHTML = '';

    // Analysis
    if (analysisContent && data.analysis?.hooks) {
      const langLabel = data.language && data.language !== 'en' ? ` (${data.language})` : '';
      analysisContent.innerHTML = data.analysis.hooks.map(hook => {
        const vs = hook.virality_score;
        const scoreBadge = vs
          ? `<span style="float:right;background:${vs>=70?'var(--green)':vs>=50?'var(--amber)':'var(--red)'};color:#000;padding:2px 10px;border-radius:12px;font-weight:700;font-size:0.8rem">${vs}/100</span>`
          : '';
        return `<div class="hook-item">${scoreBadge}<strong>${escHtml(hook.hook_name)}</strong> (${hook.start}s - ${hook.end}s)${escHtml(langLabel)}<br><span class="text-dim">${escHtml(hook.caption)}</span></div>`;
      }).join('<hr style="border-color:var(--glass-border);margin:0">');
    }

    // Clips
    if (data.clips && data.clips.length > 0 && clipsContainer) {
      clipsContainer.innerHTML = data.clips.map((clip, index) => {
        const hook = data.analysis?.hooks?.[index] || { hook_name: `Clip ${index+1}`, caption: '' };
        const vs = hook.virality_score;
        const scoreBadge = vs
          ? `<span style="display:inline-block;background:${vs>=70?'var(--green)':vs>=50?'var(--amber)':'var(--red)'};color:#000;padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:700">${vs}/100</span>`
          : '';
        const langBadge = data.language && data.language !== 'en'
          ? `<span style="display:inline-block;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.2);color:var(--cyan);padding:1px 8px;border-radius:10px;font-size:0.7rem">${escHtml(data.language)}</span>`
          : '';
        const escClip = escHtml(clip);
        return `<div class="glass-card clip-card" data-filename="${escClip}" data-process-id="${processId}" data-clip-index="${index}">
          <h4>${escHtml(hook.hook_name)} ${scoreBadge} ${langBadge}</h4>
          <div class="video-shell">
            <video controls width="100%" src="${mediaUrl('clips/' + encodeURIComponent(clip))}"></video>
          </div>
          <div class="clip-info">
            <p class="text-dim">${escHtml(hook.caption)}</p>
            <div class="flex gap-1">
              <a href="${mediaUrl('clips/' + encodeURIComponent(clip))}" download class="btn btn-sm btn-secondary">Download</a>
              <button class="btn btn-sm btn-primary publish-btn" data-index="${index}">Publish</button>
              <button class="btn btn-sm btn-ghost thumb-gen-btn" data-index="${index}">🎬 Thumbnails</button>
            </div>
          </div>
          <div class="thumb-gallery" id="thumb-gallery-${processId}-${index}" style="margin-top:0.8rem;display:none">
            <div class="thumb-gallery-header">
              <span class="text-sm text-dim">AI Thumbnails</span>
              <span class="thumb-status text-sm"></span>
            </div>
            <div class="thumb-grid" id="thumb-grid-${processId}-${index}"></div>
            <div class="thumb-ab-stats" id="thumb-stats-${processId}-${index}" style="display:none;margin-top:0.5rem"></div>
          </div>
        </div>`;
      }).join('');
    }

    // Bind thumbnail generation buttons
    document.querySelectorAll('.thumb-gen-btn').forEach(btn => {
      btn.addEventListener('click', async function() {
        const index = parseInt(this.dataset.index);
        const card = this.closest('.clip-card');
        const processId = card.dataset.processId;
        const gallery = document.getElementById(`thumb-gallery-${processId}-${index}`);
        if (gallery.style.display !== 'none') {
          gallery.style.display = 'none';
          return;
        }
        gallery.style.display = '';
        const grid = document.getElementById(`thumb-grid-${processId}-${index}`);
        grid.innerHTML = '<div class="text-dim text-sm" style="padding:1rem">Enter a title for AI-generated thumbnails...</div>';

        // Prompt for title
        const title = await promptDialog('Enter thumbnail title (leave empty for AI-generated):', '');
        const status = gallery.querySelector('.thumb-status');
        status.textContent = 'Generating...';

        generateThumbnails(processId, index, title || '')
          .then(resp => {
            status.textContent = `${resp.thumbnails.length} variants`;
            renderThumbnailGrid(grid, resp.thumbnails, processId, index);
            // Load A/B stats if any
            loadThumbnailStats(processId, index);
          })
          .catch(err => {
            status.textContent = 'Failed';
            grid.innerHTML = `<div class="text-dim text-sm" style="padding:1rem;color:var(--red)">Error: ${escHtml(err.message)}</div>`;
          });
      });
    });

    // Bind publish buttons
    document.querySelectorAll('.publish-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        const card = this.closest('.clip-card');
        const filename = card.dataset.filename;
        const processId = card.dataset.processId;
        openPublishDialog(filename, processId);
      });
    });

    if (processBtn) processBtn.disabled = false;
    if (processDriveBtn) { processDriveBtn.disabled = false; processDriveBtn.innerText = 'Fetch from Drive & Analyze'; }
  }

  // ---- Publish Dialog ----
  function openPublishDialog(clipFilename, processId) {
    // Remove existing modal
    const old = document.getElementById('publish-modal');
    if (old) old.remove();

    const modal = document.createElement('div');
    modal.id = 'publish-modal';
    modal.style.cssText = `
      position:fixed;top:0;left:0;right:0;bottom:0;z-index:9999;
      background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;
      backdrop-filter:blur(4px);
    `;
    modal.innerHTML = `
      <div class="glass-card" style="width:420px;max-width:90vw;padding:1.5rem;position:relative;">
        <button id="pub-close-btn" style="position:absolute;top:0.75rem;right:0.75rem;background:none;border:none;color:var(--text-dim);font-size:1.2rem;cursor:pointer;">✕</button>
        <h3 style="margin-bottom:0.25rem;">Publish Clip</h3>
        <p class="text-dim text-sm" style="margin-bottom:1rem;">${escHtml(clipFilename)}</p>

        <div class="form-group">
          <label>Platform</label>
          <select id="pub-platform" class="form-input">
            <option value="">Select platform...</option>
            <option value="youtube">YouTube</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
            <option value="twitter">X / Twitter</option>
            <option value="facebook">Facebook</option>
            <option value="linkedin">LinkedIn</option>
          </select>
        </div>
        <div class="form-group">
          <label>Account</label>
          <select id="pub-account" class="form-input"><option value="">Select platform first</option></select>
        </div>
        <div class="form-group">
          <label>Title</label>
          <input type="text" id="pub-title" class="form-input" placeholder="Video title" value="Nexus-UGC Clip">
        </div>
        <div class="form-group">
          <label>Description</label>
          <textarea id="pub-description" class="form-input" rows="2" placeholder="Optional description" style="resize:vertical"></textarea>
        </div>
        <div id="pub-error" class="text-sm" style="color:var(--red);margin-bottom:0.5rem;display:none;"></div>
        <button id="pub-submit-btn" class="btn btn-primary w-full">Publish Now</button>
      </div>
    `;
    document.body.appendChild(modal);

    // Attach events
    modal.querySelector('#pub-close-btn').addEventListener('click', () => modal.remove());
    modal.querySelector('#pub-platform').addEventListener('change', updateAccountSelect);
    modal.querySelector('#pub-submit-btn').addEventListener('click', () => doPublish(clipFilename));
    // Pre-populate accounts
    loadAccountsForPublish();
  }

  window.updateAccountSelect = async function() {
    const platform = document.getElementById('pub-platform').value;
    const select = document.getElementById('pub-account');
    select.innerHTML = '<option value="">Loading accounts...</option>';
    try {
      const data = await listAccounts();
      const filtered = data.accounts ? data.accounts.filter(a => a.platform === platform && a.is_active) : [];
      if (filtered.length === 0) {
        select.innerHTML = '<option value="">No accounts for this platform</option>';
      } else {
        select.innerHTML = filtered.map(a => `<option value="${a.id}">${escHtml(a.account_name)}</option>`).join('');
      }
    } catch (err) {
      select.innerHTML = '<option value="">Error loading accounts</option>';
    }
  };

  window.loadAccountsForPublish = async function() {
    try {
      const data = await listAccounts();
      window._pubAccounts = data.accounts || [];
    } catch (err) {
      window._pubAccounts = [];
    }
  };

  window.doPublish = async function(clipFilename) {
    const platform = document.getElementById('pub-platform').value;
    const accountId = document.getElementById('pub-account').value;
    const title = document.getElementById('pub-title').value.trim() || 'Nexus-UGC Clip';
    const description = document.getElementById('pub-description').value.trim();
    const errorDiv = document.getElementById('pub-error');
    const btn = document.getElementById('pub-submit-btn');

    errorDiv.style.display = 'none';
    if (!platform) { showFieldError('pub-error', 'Select a platform'); return; }
    if (!accountId) { showFieldError('pub-error', 'Select an account'); return; }

    btn.disabled = true;
    btn.textContent = 'Publishing...';
    try {
      const result = await publishClip({ platform, account_id: accountId, clip_filename: clipFilename, title, description });
      // If API returned a publish URL (mock or real), surface it to the user
      try {
        const publishObj = result.publish || result;
        const res = publishObj.result || publishObj;
        const resultUrl = res.result_url || res.video_url || res.mock_url || res.upload_url || null;
        const authSource = res.auth_source || 'account';
        if (resultUrl) {
          showPublishResult(resultUrl, authSource);
        } else {
          showToast(`Published to ${platform} successfully`, 'success');
        }
      } catch (e) {
        showToast(`Published to ${platform} successfully`, 'success');
      }
      document.getElementById('publish-modal').remove();
    } catch (err) {
      showFieldError('pub-error', err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Publish Now';
    }
  };

  function showPublishResult(url, authSource = 'account') {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'publish-result-modal';
    const note = authSource === 'system'
      ? 'Used the configured system credentials for this publish.'
      : authSource === 'mock'
        ? 'Used local mock publishing for this test run.'
        : 'Used the connected account for this publish.';
    modal.innerHTML = `
      <div class="modal-content">
        <h3>Publish Result</h3>
        <p>${escHtml(note)}</p>
        <p>View: <a href="${escHtml(url)}" target="_blank" rel="noopener">${escHtml(url)}</a></p>
        <div style="text-align:right;margin-top:0.5rem"><button id="publish-result-close" class="btn">Close</button></div>
      </div>
    `;
    document.body.appendChild(modal);
    document.getElementById('publish-result-close').addEventListener('click', () => modal.remove());
  }

  function showFieldError(id, msg) {
    const el = document.getElementById(id);
    if (el) { el.textContent = msg; el.style.display = ''; }
  }



  // ---- Thumbnail Gallery ----
  function renderThumbnailGrid(grid, thumbnails, processId, clipIndex) {
    if (!thumbnails || thumbnails.length === 0) {
      grid.innerHTML = '<div class="text-dim text-sm" style="padding:1rem">No thumbnails generated.</div>';
      return;
    }

    grid.innerHTML = thumbnails.map(t => {
      const safeTitle = escHtml(t.title_overlay || '');
      const safeUrl = escHtml(t.url || '');
      const safeLayout = escHtml(t.layout || '');
      return `
      <div class="thumb-card" data-thumb-id="${escHtml(t.id)}" data-url="${safeUrl}" data-layout="${safeLayout}" data-score="${escHtml(t.score)}" data-title="${safeTitle}">
        <div class="thumb-img-wrapper">
          <img src="${safeUrl}" alt="${safeTitle || 'Thumbnail'}" loading="lazy" onerror="this.style.display='none'">
          <div class="thumb-badge">${safeLayout}</div>
        </div>
        <div class="thumb-info">
          <div class="thumb-title">${safeTitle || 'No title'}</div>
          <div class="thumb-meta">
            <span class="thumb-score">${escHtml(t.score)}/10</span>
            <div class="thumb-actions">
              <button class="btn btn-xs btn-ghost thumb-use-btn" title="Set as winner">👑</button>
              <button class="btn btn-xs btn-ghost thumb-refresh-btn" title="Regenerate">🔄</button>
            </div>
          </div>
        </div>
      </div>`;
    }).join('');

    // Bind "use as winner" buttons
    grid.querySelectorAll('.thumb-use-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        const card = this.closest('.thumb-card');
        const thumbId = card.dataset.thumbId;
        declareWinner(thumbId).then(() => {
          showToast('This thumbnail will be used for publishing', 'success');
          grid.querySelectorAll('.thumb-card').forEach(c => c.classList.remove('winner'));
          card.classList.add('winner');
        }).catch(err => showToast(err.message, 'error'));
      });
    });

    // Bind "refresh" buttons (re-generate with specific layout)
    grid.querySelectorAll('.thumb-refresh-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        showToast('Re-generate this thumbnail with different text', 'info');
      });
    });
  }

  function loadThumbnailStats(processId, clipIndex) {
    listThumbnails(processId, clipIndex).then(resp => {
      if (!resp.thumbnails || resp.thumbnails.length === 0) return;
      const statsDiv = document.getElementById(`thumb-stats-${processId}-${clipIndex}`);
      if (!statsDiv) return;

      // Get stats for the first thumbnail
      const first = resp.thumbnails[0];
      getThumbnailStats(first.id).then(s => {
        if (!s.stats || s.stats.length === 0) return;
        statsDiv.style.display = '';
        statsDiv.innerHTML = `
          <h5 style="margin:0 0 0.3rem;font-size:0.85rem">A/B Test Performance</h5>
          <div class="ab-table">
            <table style="width:100%;border-collapse:collapse;font-size:0.78rem">
              <thead>
                <tr style="border-bottom:1px solid var(--glass-border)">
                  <th style="padding:4px 8px;text-align:left">Variant</th>
                  <th style="padding:4px 8px;text-align:center">Layout</th>
                  <th style="padding:4px 8px;text-align:center">Impressions</th>
                  <th style="padding:4px 8px;text-align:center">Clicks</th>
                  <th style="padding:4px 8px;text-align:center">CTR</th>
                  <th style="padding:4px 8px;text-align:center">Win Prob</th>
                </tr>
              </thead>
              <tbody>
                ${s.stats.map(st => `
                  <tr style="border-bottom:1px solid rgba(148,163,184,0.06)">
                    <td style="padding:4px 8px">${st.variant} ${st.is_winner ? '👑' : ''}</td>
                    <td style="padding:4px 8px;text-align:center">${st.layout}</td>
                    <td style="padding:4px 8px;text-align:center">${st.impressions}</td>
                    <td style="padding:4px 8px;text-align:center">${st.clicks}</td>
                    <td style="padding:4px 8px;text-align:center;font-weight:600;color:${st.ctr > 5 ? 'var(--green)' : st.ctr > 2 ? 'var(--amber)' : 'var(--red)'}">${st.ctr}%</td>
                    <td style="padding:4px 8px;text-align:center">${(st.prob_beats_control * 100).toFixed(0)}%</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          <div class="text-dim text-xs" style="margin-top:0.3rem">A/B test tracks real impressions & clicks when thumbnails are served</div>
        `;
      }).catch(() => {});
    }).catch(() => {});
  }





  // ---- Dashboard ----
  async function loadDashboard() {
    const section = document.getElementById('dashboard-section');
    if (!section) return;
    const isLoggedIn = isAuthenticated();
    section.style.display = isLoggedIn ? 'block' : 'none';
    if (!isLoggedIn) return;
    const accountsEl = document.getElementById('accounts-list');
    const postsEl = document.getElementById('posts-list');
    if (accountsEl) accountsEl.innerHTML = '<div class="loading-pulse" style="text-align:center;padding:1rem;color:var(--text-dim);font-size:0.8rem;">Loading accounts...</div>';
    if (postsEl) postsEl.innerHTML = '<div class="loading-pulse" style="text-align:center;padding:1rem;color:var(--text-dim);font-size:0.8rem;">Loading posts...</div>';
    ['stat-linked','stat-pending','stat-posted','stat-failed'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '...';
    });
    try {
      const data = await getDashboard();
      document.getElementById('stat-linked').textContent = data.connected_accounts || 0;
      document.getElementById('stat-pending').textContent = data.status_counts?.pending || 0;
      document.getElementById('stat-posted').textContent = data.status_counts?.posted || 0;
      document.getElementById('stat-failed').textContent = data.status_counts?.failed || 0;

      const accountsEl = document.getElementById('accounts-list');
      if (!data.accounts?.length) {
        showEmpty(accountsEl, '🔗', 'No accounts connected', 'Connect your first social account from the Accounts page.');
      } else {
        accountsEl.innerHTML = data.accounts.map(a => {
          const platformIcons = { youtube: '▶️', tiktok: '🎵', instagram: '📸', twitter: '🐦', facebook: '👍', linkedin: '💼' };
          return `<div class="flex items-center gap-2" style="padding:0.5rem 0;border-bottom:1px solid var(--glass-border);">
            <span>${platformIcons[a.platform] || '🔗'}</span>
            <strong>${a.name}</strong>
            <span class="badge ${a.is_system ? 'badge-system' : 'badge-user'}">${a.is_system ? 'auto' : 'user'}</span>
            <span class="badge ${a.token_ok ? 'badge-ok' : 'badge-warn'}">${a.token_ok ? '✓ tokens' : '⚠ no token'}</span>
            <span class="text-xs text-dim">${a.platform}</span>
          </div>`;
        }).join('');
      }

      const postsEl = document.getElementById('posts-list');
      const recentPosts = data.posts?.slice(0, 10) || [];
      if (!recentPosts.length) {
        showEmpty(postsEl, '📝', 'No posts yet', 'Generate your first post from Brain Rot.');
      } else {
        postsEl.innerHTML = recentPosts.map(p => {
          const statusColors = { posted: 'green', failed: 'red', pending: 'amber', approved: 'cyan', scheduled: 'blue', cancelled: 'gray', draft: 'dim' };
          const color = statusColors[p.status] || 'dim';
          return `<div class="flex items-center gap-2" style="padding:0.4rem 0;border-bottom:1px solid var(--glass-border);">
            <span style="color:var(--${color});">●</span>
            <span class="text-sm">${p.title || '(no title)'}</span>
            <span class="badge badge-${p.status}">${p.platform}</span>
            <span class="text-xs text-dim">${p.status}${p.error ? ': ' + p.error.substring(0, 40) : ''}</span>
          </div>`;
        }).join('');
      }
    } catch (e) {
      console.error('Dashboard load error:', e);
      if (accountsEl) showError(accountsEl, 'Failed to load dashboard', 'loadDashboard');
    }
  }

  // Initialize
  updateAuthUI();
  loadDashboard();
})();

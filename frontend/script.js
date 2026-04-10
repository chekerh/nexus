const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const processBtn = document.getElementById('process-btn');
const statusSection = document.getElementById('status-section');
const resultsSection = document.getElementById('results-section');
const statusMessage = document.getElementById('status-message');
const transcriptContent = document.getElementById('transcript-content');
const analysisContent = document.getElementById('analysis-content');
const statusTimer = document.getElementById('status-timer');
const timingSummary = document.getElementById('timing-summary');
const toastContainer = document.getElementById('toast-container');
const unloadBackendBtn = document.getElementById('unload-backend-btn');
const backendStatusLabel = document.getElementById('backend-status-label');

const stopBtn = document.getElementById('stop-btn');
const thinkingConsole = document.getElementById('thinking-console');
const statusTitle = document.getElementById('status-title');
const publishConsole = document.getElementById('publish-console');

// Google Drive elements
const tabFile = document.getElementById('tab-file');
const tabDrive = document.getElementById('tab-drive');
const contentFile = document.getElementById('content-file');
const contentDrive = document.getElementById('content-drive');
const driveUrlInput = document.getElementById('drive-url');
const processDriveBtn = document.getElementById('process-drive-btn');

// End Screen elements
const tabEndscreen = document.getElementById('tab-endscreen');
const contentEndscreen = document.getElementById('content-endscreen');
const endscreenDropzone = document.getElementById('endscreen-dropzone');
const endscreenInput = document.getElementById('endscreen-input');
const endscreenImgPreview = document.getElementById('endscreen-img-preview');
const endscreenPreview = document.getElementById('endscreen-preview');
const ctaTextInput = document.getElementById('cta-text-input');
const endscreenBadge = document.getElementById('endscreen-badge');

let selectedFile = null;
let endscreenFile = null;  // End screen image file
let currentProcessId = null;
let statusTimerInterval = null;
let statusStartMs = 0;

function formatElapsed(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    const mm = String(Math.floor(total / 60)).padStart(2, '0');
    const ss = String(total % 60).padStart(2, '0');
    return `${mm}:${ss}`;
}

function startStatusTimer() {
    stopStatusTimer();
    statusStartMs = Date.now();
    statusTimer.innerText = '00:00';
    statusTimerInterval = setInterval(() => {
        statusTimer.innerText = formatElapsed((Date.now() - statusStartMs) / 1000);
    }, 500);
}

function stopStatusTimer() {
    if (statusTimerInterval) {
        clearInterval(statusTimerInterval);
        statusTimerInterval = null;
    }
}

function renderTimingSummary(data) {
    const t = data?.timing || {};
    if (!t.total_seconds) {
        timingSummary.innerText = 'Awaiting stage metrics...';
        return;
    }
    timingSummary.innerText = `T:${t.total_seconds}s | W:${t.transcription_seconds || 0}s | A:${t.analysis_seconds || 0}s | C:${t.cutting_seconds || 0}s`;
}

function showToast(title, subtitle = '') {
    if (!toastContainer) return;
    const el = document.createElement('div');
    el.className = 'toast';
    el.innerHTML = `<div class="toast-title">${title}</div>${subtitle ? `<div class="toast-sub">${subtitle}</div>` : ''}`;
    toastContainer.appendChild(el);
    setTimeout(() => el.remove(), 6500);
}

function showClipReadyNotification(processId, clipCount) {
    const uniqueCode = `CUTS-${(processId || '').slice(-6).toUpperCase()}-${Date.now().toString().slice(-5)}`;
    const body = `${clipCount} clip(s) generated. Ref ${uniqueCode}`;
    showToast('Clips ready', body);

    if (!('Notification' in window)) return;
    const fire = () => new Notification('Nexus UGC: Clips generated', { body, tag: uniqueCode });
    if (Notification.permission === 'granted') {
        fire();
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(p => {
            if (p === 'granted') fire();
        });
    }
}

async function refreshBackendRuntimeStatus() {
    if (!backendStatusLabel) return;
    try {
        const res = await fetch('/ai/backend/status');
        const data = await res.json();
        const backend = data.backend || 'ollama';
        if (backend === 'airllm') {
            const loaded = !!data?.airllm?.loaded;
            backendStatusLabel.innerText = `Backend: airllm (${loaded ? 'loaded' : 'idle'})`;
        } else {
            backendStatusLabel.innerText = `Backend: ${backend}`;
        }
    } catch {
        backendStatusLabel.innerText = 'Backend: unavailable';
    }
}


// Handle File Selection
dropzone.onclick = () => fileInput.click();

fileInput.onchange = (e) => {
    selectedFile = e.target.files[0];
    if (selectedFile) {
        dropzone.innerText = `Selected: ${selectedFile.name}`;
        processBtn.disabled = false;
    }
};

// End Screen Image Handling
endscreenDropzone?.addEventListener('click', () => endscreenInput?.click());

endscreenInput.onchange = (e) => {
    const file = e.target.files[0];
    if (file) {
        endscreenFile = file;
        // Show preview
        const reader = new FileReader();
        reader.onload = (event) => {
            endscreenImgPreview.src = event.target.result;
            endscreenImgPreview.classList.remove('hidden');
            endscreenPreview.querySelector('.endscreen-placeholder')?.classList.add('hidden');
        };
        reader.readAsDataURL(file);
        // Update badge
        endscreenBadge.textContent = 'End screen ready';
        endscreenBadge.classList.remove('inactive');
        endscreenBadge.classList.add('active');
        showToast('End screen set', `Image "${file.name}" will appear at the end of each clip`);
    }
};

// Tab Switching
function switchTab(tab) {
    // Remove active from all tabs
    tabFile?.classList.remove('active');
    tabDrive?.classList.remove('active');
    tabEndscreen?.classList.remove('active');
    contentFile?.classList.remove('active');
    contentDrive?.classList.remove('active');
    contentEndscreen?.classList.remove('active');

    // Add active to selected tab
    if (tab === 'file') {
        tabFile?.classList.add('active');
        contentFile?.classList.add('active');
    } else if (tab === 'drive') {
        tabDrive?.classList.add('active');
        contentDrive?.classList.add('active');
    } else if (tab === 'endscreen') {
        tabEndscreen?.classList.add('active');
        contentEndscreen?.classList.add('active');
    }
}

tabFile?.addEventListener('click', () => switchTab('file'));
tabDrive?.addEventListener('click', () => switchTab('drive'));
tabEndscreen?.addEventListener('click', () => switchTab('endscreen'));

// Google Drive Processing
processDriveBtn?.addEventListener('click', async () => {
    const driveUrl = driveUrlInput?.value?.trim();
    if (!driveUrl) {
        showToast('Error', 'Please paste a Google Drive URL');
        return;
    }

    // Reset UI
    processDriveBtn.disabled = true;
    processDriveBtn.innerText = 'Downloading...';
    statusSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    thinkingConsole.innerHTML = '<div class="thinking-line">Connecting to Google Drive...</div>';
    statusTitle.innerText = "AI Processing...";
    timingSummary.innerText = 'Awaiting stage metrics...';
    startStatusTimer();

    try {
        const response = await fetch('/process-drive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ drive_url: driveUrl })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to process Drive video');
        }

        const { process_id } = await response.json();
        currentProcessId = process_id;
        pollStatus(process_id);
    } catch (err) {
        console.error(err);
        thinkingConsole.innerHTML += `<div class="thinking-line error">Error: ${err.message}</div>`;
        processDriveBtn.disabled = false;
        processDriveBtn.innerText = 'Fetch from Drive & Analyze';
    }
});

// Handle Processing
processBtn.onclick = async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Add end screen image if set
    if (endscreenFile) {
        formData.append('endscreen_image', endscreenFile);
    }

    // Add CTA text
    const ctaText = ctaTextInput?.value?.trim() || 'Link in bio to try it free.';
    formData.append('cta_text', ctaText);

    // Reset UI
    processBtn.disabled = true;
    statusSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    thinkingConsole.innerHTML = '<div class="thinking-line">Initializing local AI engine...</div>';
    if (endscreenFile) {
        thinkingConsole.innerHTML += `<div class="thinking-line">End screen configured: "${ctaText}"</div>`;
    }
    statusTitle.innerText = "AI Processing...";
    timingSummary.innerText = 'Awaiting stage metrics...';
    startStatusTimer();

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        const { process_id } = await response.json();
        currentProcessId = process_id;
        pollStatus(process_id);
    } catch (err) {
        console.error(err);
        thinkingConsole.innerHTML += `<div class="thinking-line error">Error uploading file: ${err}</div>`;
        processBtn.disabled = false;
    }
};

// Handle Stop Analysis
stopBtn.onclick = async () => {
    if (!currentProcessId) return;
    try {
        await fetch(`/cancel/${currentProcessId}`, { method: 'POST' });
        statusTitle.innerText = "Stopping Analysis...";
    } catch (err) {
        console.error("Stop failed", err);
    }
};

// Poll for Results
async function pollStatus(processId) {
    const poll = setInterval(async () => {
        try {
            const res = await fetch(`/status/${processId}`);
            const data = await res.json();

            // Update Thinking Console with new thoughts
            if (data.thinking) {
                const currentThoughts = thinkingConsole.querySelectorAll('.thinking-line').length;
                if (data.thinking.length > currentThoughts) {
                    for (let i = currentThoughts; i < data.thinking.length; i++) {
                        const line = document.createElement('div');
                        line.className = 'thinking-line';
                        line.innerText = `> ${data.thinking[i]}`;
                        thinkingConsole.appendChild(line);
                        thinkingConsole.scrollTop = thinkingConsole.scrollHeight;
                    }
                }
            }

            if (data.status === 'completed') {
                clearInterval(poll);
                stopStatusTimer();
                showResults(data, processId);
                showClipReadyNotification(processId, (data.clips || []).length);
            } else if (data.status === 'error') {
                clearInterval(poll);
                stopStatusTimer();
                statusTitle.innerText = "Process Failed";
                thinkingConsole.innerHTML += `<div class="thinking-line error">CRITICAL ERROR: ${data.error}</div>`;
                processBtn.disabled = false;
                processDriveBtn.disabled = false;
                processDriveBtn.innerText = 'Fetch from Drive & Analyze';
            } else if (data.status === 'cancelled') {
                clearInterval(poll);
                stopStatusTimer();
                statusTitle.innerText = "Analysis Cancelled";
                thinkingConsole.innerHTML += `<div class="thinking-line">Process terminated by user. Resources released.</div>`;
                processBtn.disabled = false;
                processDriveBtn.disabled = false;
                processDriveBtn.innerText = 'Fetch from Drive & Analyze';
            }

            renderTimingSummary(data);
        } catch (err) {
            clearInterval(poll);
            stopStatusTimer();
            console.error(err);
        }
    }, 1500);
}

const clipsContainer = document.getElementById('clips-container');

// Minimal accounts/groups cache for publishing functionality
let accountsCache = [];
let groupsCache = [];

async function loadAccounts() {
    try {
        const res = await fetch('/accounts');
        const data = await res.json();
        accountsCache = data.accounts || [];
    } catch (err) {
        console.error('Failed to load accounts', err);
    }
}

async function loadGroups() {
    try {
        const res = await fetch('/account-groups');
        const data = await res.json();
        groupsCache = data.groups || [];
    } catch (err) {
        console.error('Failed to load groups', err);
    }
}

function accountOptionsForPlatform(platform) {
    const filtered = accountsCache.filter(a => a.platform === platform);
    if (!filtered.length) return '<option value="">No accounts - add in Account Groups page</option>';
    return filtered.map(a => `<option value="${a.id}">${a.account_name}</option>`).join('');
}

async function publishClip(index) {
    const platformEl = document.getElementById(`platform-${index}`);
    const accountEl = document.getElementById(`account-${index}`);
    const titleEl = document.getElementById(`title-${index}`);
    const descEl = document.getElementById(`desc-${index}`);
    const ctaEl = document.getElementById(`cta-${index}`);
    const clip = document.getElementById(`clip-${index}`)?.getAttribute('data-filename');

    if (!clip) return;

    // Combine description with CTA
    const mainDesc = descEl.value.trim();
    const ctaText = ctaEl ? ctaEl.value.trim() : "";
    const fullDescription = ctaText ? `${mainDesc}\n\n${ctaText}` : mainDesc;

    const payload = {
        platform: platformEl.value,
        account_id: accountEl.value,
        clip_filename: clip,
        title: titleEl.value.trim(),
        description: fullDescription
    };

    if (!payload.account_id) {
        publishConsole.innerHTML = '<div class="publish-line error">Select an account for this platform first.</div>';
        return;
    }

    try {
        const res = await fetch('/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (!res.ok) {
            publishConsole.innerHTML = `<div class="publish-line error">Publish failed: ${data.error || 'Unknown error'}</div>`;
            return;
        }

        const result = data.publish.result;
        publishConsole.innerHTML = `
            <div class="publish-line">
                Ready for ${payload.platform} using account ${data.publish.account_name}. 
                <a href="${result.upload_url}" target="_blank" rel="noopener">Open upload page</a>
            </div>
        `;
    } catch (err) {
        publishConsole.innerHTML = `<div class="publish-line error">Publish failed: ${err}</div>`;
    }
}

async function publishClipToGroup(index) {
    const groupSelect = document.getElementById(`group-select-${index}`);
    const groupId = groupSelect?.value;
    const titleEl = document.getElementById(`title-${index}`);
    const descEl = document.getElementById(`desc-${index}`);
    const clip = document.getElementById(`clip-${index}`)?.getAttribute('data-filename');

    if (!clip) return;

    if (!groupId) {
        publishConsole.innerHTML = '<div class="publish-line error">Select a group to publish to.</div>';
        return;
    }

    const group = groupsCache.find(g => g.id === groupId);
    if (!group || !group.accounts || group.accounts.length === 0) {
        publishConsole.innerHTML = '<div class="publish-line error">Selected group has no accounts.</div>';
        return;
    }

    const title = titleEl.value.trim();
    const description = descEl.value.trim();

    publishConsole.innerHTML = `<div class="publish-line">Publishing to ${group.accounts.length} accounts in group "${group.name}"...</div>`;

    const results = [];
    for (const account of group.accounts) {
        try {
            const res = await fetch('/publish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    platform: account.platform,
                    account_id: account.id,
                    clip_filename: clip,
                    title: title,
                    description: description
                })
            });

            const data = await res.json();
            results.push({ account: account.account_name, platform: account.platform, success: res.ok, data });

            if (!res.ok) {
                publishConsole.innerHTML += `<div class="publish-line error">Failed for ${account.account_name}: ${data.error || 'Unknown error'}</div>`;
            } else {
                const result = data.publish.result;
                if (result.upload_url) {
                    publishConsole.innerHTML += `<div class="publish-line">${account.account_name} (${account.platform}): <a href="${result.upload_url}" target="_blank">Open upload</a></div>`;
                } else {
                    publishConsole.innerHTML += `<div class="publish-line">${account.account_name} (${account.platform}): Published successfully</div>`;
                }
            }
        } catch (err) {
            results.push({ account: account.account_name, platform: account.platform, success: false, error: err.message });
            publishConsole.innerHTML += `<div class="publish-line error">Error for ${account.account_name}: ${err.message}</div>`;
        }
    }

    const successCount = results.filter(r => r.success).length;
    publishConsole.innerHTML += `<div class="publish-line">Complete: ${successCount}/${group.accounts.length} accounts processed.</div>`;
}

function bindClipPublishActions() {
    // Platform select for single account mode
    document.querySelectorAll('.platform-select').forEach(select => {
        select.onchange = () => {
            const idx = select.getAttribute('data-index');
            const accountSelect = document.getElementById(`account-${idx}`);
            accountSelect.innerHTML = accountOptionsForPlatform(select.value);
        };
    });

    // Single account publish buttons
    document.querySelectorAll('.publish-btn').forEach(btn => {
        btn.onclick = () => publishClip(btn.getAttribute('data-index'));
    });

    // Publish mode tabs (single vs group)
    document.querySelectorAll('.publish-mode-tab').forEach(tab => {
        tab.onclick = () => {
            const idx = tab.getAttribute('data-index');
            const mode = tab.getAttribute('data-mode');

            // Update active tab
            document.querySelectorAll(`.publish-mode-tab[data-index="${idx}"]`).forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Show/hide sections
            const singleSection = document.getElementById(`publish-single-${idx}`);
            const groupSection = document.getElementById(`publish-group-${idx}`);

            if (mode === 'single') {
                singleSection.classList.remove('hidden');
                groupSection.classList.add('hidden');
            } else {
                singleSection.classList.add('hidden');
                groupSection.classList.remove('hidden');
            }
        };
    });

    // Group select change - update preview
    document.querySelectorAll('[id^="group-select-"]').forEach(select => {
        select.onchange = () => {
            const idx = select.id.replace('group-select-', '');
            const groupId = select.value;
            const previewEl = document.getElementById(`group-accounts-preview-${idx}`);

            if (!groupId) {
                previewEl.innerHTML = '';
                return;
            }

            const group = groupsCache.find(g => g.id === groupId);
            if (group && group.accounts) {
                previewEl.innerHTML = group.accounts.map(a =>
                    `<span class="account-chip">${a.account_name} (${a.platform})</span>`
                ).join('');
            } else {
                previewEl.innerHTML = '';
            }
        };
    });

    // Group publish buttons
    document.querySelectorAll('.publish-group-btn').forEach(btn => {
        btn.onclick = () => publishClipToGroup(btn.getAttribute('data-index'));
    });
}

async function bindStyledCaptionOverlays(clips) {
    for (let index = 0; index < clips.length; index++) {
        const clip = clips[index];
        const video = document.getElementById(`video-${index}`);
        const overlay = document.getElementById(`caption-overlay-${index}`);
        if (!video || !overlay) continue;

        const cuesUrl = `/video_clips/${encodeURIComponent(clip.replace(/\.mp4$/i, '.cues.json'))}`;
        let cuesPayload = null;
        try {
            const resp = await fetch(cuesUrl);
            if (resp.ok) cuesPayload = await resp.json();
        } catch (_) {}

        if (video.textTracks && video.textTracks[0]) {
            video.textTracks[0].mode = 'hidden';
        }

        if (!cuesPayload || !Array.isArray(cuesPayload.cues)) {
            continue;
        }

        const cues = cuesPayload.cues;
        const variantPalette = {
            1: { color: '#ffffff', bg: 'rgba(0,0,0,.62)', shadow: '0 8px 20px rgba(0,0,0,.35)' },
            2: { color: '#d7e7ff', bg: 'rgba(37,45,112,.78)', shadow: '0 10px 24px rgba(54,74,220,.28)' },
            3: { color: '#c7ffd3', bg: 'rgba(9,72,34,.82)', shadow: '0 10px 24px rgba(65,190,86,.28)' },
            4: { color: '#ffd6dc', bg: 'rgba(116,20,46,.84)', shadow: '0 10px 24px rgba(238,86,117,.28)' }
        };
        const styleAnim = {
            neutral: 'none',
            impact: 'cap-pop .25s ease-out',
            question: 'cap-float .55s ease-in-out',
            money: 'cap-glow 1.2s ease-in-out infinite',
            warning: 'cap-shake .3s ease-in-out',
            hype: 'cap-pop .3s ease-out'
        };
        const updateOverlay = () => {
            const t = video.currentTime || 0;
            const active = cues.find(c => t >= c.start && t <= c.end);
            if (!active) {
                overlay.innerHTML = '';
                overlay.className = 'caption-overlay';
                return;
            }
            overlay.innerHTML = `<span>${active.text}</span>`;
            const styleClass = active.style ? `cap-${active.style}` : 'cap-neutral';
            const variantClass = active.variant ? `cap-v${active.variant}` : 'cap-v1';
            overlay.className = `caption-overlay ${styleClass} ${variantClass}`;
            const span = overlay.querySelector('span');
            if (span) {
                const palette = variantPalette[active.variant] || variantPalette[1];
                span.style.color = palette.color;
                span.style.background = palette.bg;
                span.style.boxShadow = palette.shadow;
                span.style.animation = styleAnim[active.style] || 'none';
            }
        };

        video.addEventListener('timeupdate', updateOverlay);
        video.addEventListener('seeked', updateOverlay);
        video.addEventListener('play', updateOverlay);
        video.addEventListener('pause', updateOverlay);
    }
}

function showResults(data, processId) {
    statusSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    
    transcriptContent.innerText = data.transcript;
    
    // Clear previous results
    clipsContainer.innerHTML = '';

    // Format JSON Analysis
    if (data.analysis && data.analysis.hooks) {
        analysisContent.innerHTML = data.analysis.hooks.map(hook => `
            <div class="hook-item">
                <strong>${hook.hook_name}</strong> (${hook.start}s - ${hook.end}s)<br>
                <em>${hook.caption}</em>
            </div>
        `).join('<hr>');
    }

    // Render Video Clips
    if (data.clips && data.clips.length > 0) {
        clipsContainer.innerHTML = data.clips.map((clip, index) => {
            const hook = data.analysis.hooks[index] || { hook_name: `Clip ${index+1}`, caption: '' };
            const encodedClip = encodeURIComponent(clip);
            const vtt = encodeURIComponent(clip.replace(/\.mp4$/i, '.vtt'));
            const defaultTitle = hook.hook_name || `Clip ${index + 1}`;
            const defaultDesc = hook.caption || '';

            const hasGroups = groupsCache.length > 0;
            const groupOptions = hasGroups
                ? groupsCache.map(g => `<option value="${g.id}">${g.name} (${g.accounts?.length || 0} accounts)</option>`).join('')
                : '<option value="">No groups - create one first</option>';

            return `
                <div class="card clip-card" id="clip-${index}" data-filename="${clip}">
                    <h4>${hook.hook_name}</h4>
                    <div class="video-shell">
                    <video id="video-${index}" controls width="100%" src="/video_clips/${encodedClip}">
                        <track kind="subtitles" srclang="en" label="English" src="/video_clips/${vtt}" default>
                    </video>
                    <div id="caption-overlay-${index}" class="caption-overlay"></div>
                    </div>
                    <div class="clip-info">
                        <p>${hook.caption}</p>
                        <a href="/video_clips/${encodedClip}" download class="btn btn-secondary">Download Clip</a>
                        <input id="title-${index}" class="publish-input" value="${defaultTitle.replaceAll('"', '&quot;')}">
                        <textarea id="desc-${index}" class="publish-textarea">${defaultDesc}</textarea>

                        <div class="publish-section">
                            <div class="publish-section-title">Publish To</div>
                            <div class="publish-mode-tabs">
                                <button class="publish-mode-tab active" data-mode="single" data-index="${index}">Single Account</button>
                                <button class="publish-mode-tab ${!hasGroups ? 'disabled' : ''}" data-mode="group" data-index="${index}">Account Group</button>
                            </div>

                            <div id="publish-single-${index}" class="publish-single-section">
                                <select id="platform-${index}" class="publish-select platform-select" data-index="${index}">
                                    <option value="tiktok">TikTok</option>
                                    <option value="instagram">Instagram</option>
                                    <option value="youtube">YouTube</option>
                                </select>
                                <select id="account-${index}" class="publish-select">${accountOptionsForPlatform('tiktok')}</select>
                                <button class="btn btn-primary publish-btn" data-index="${index}">Post to Account</button>
                            </div>

                            <div id="publish-group-${index}" class="publish-group-section hidden">
                                <div class="publish-group-select">
                                    <select id="group-select-${index}">
                                        <option value="">Select a group...</option>
                                        ${groupOptions}
                                    </select>
                                </div>
                                <div id="group-accounts-preview-${index}" class="group-accounts-preview"></div>
                                <button class="btn btn-publish-multi publish-group-btn" data-index="${index}" ${!hasGroups ? 'disabled' : ''}>
                                    Post to All Accounts in Group
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        bindClipPublishActions();
        bindStyledCaptionOverlays(data.clips);
    } else {
        clipsContainer.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-dim);">No clips were generated for this video.</p>';
    }

    processBtn.disabled = false;
    processDriveBtn.disabled = false;
    processDriveBtn.innerText = 'Fetch from Drive & Analyze';
    if (data?.timing?.total_seconds) {
        showToast('Pipeline complete', `Process ${String(processId || '').slice(-6).toUpperCase()} finished in ${data.timing.total_seconds}s`);
    }
    refreshBackendRuntimeStatus();
}

if (unloadBackendBtn) {
    unloadBackendBtn.onclick = async () => {
        try {
            const res = await fetch('/ai/backend/unload', { method: 'POST' });
            const data = await res.json();
            showToast('Runtime memory', data.message || 'Unload request completed');
            await refreshBackendRuntimeStatus();
        } catch (err) {
            showToast('Runtime memory', `Unload failed: ${err}`);
        }
    };
}

// Initialize
loadAccounts();
loadGroups();
refreshBackendRuntimeStatus();

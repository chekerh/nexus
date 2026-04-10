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
const navPipeline = document.getElementById('nav-pipeline');
const navAccounts = document.getElementById('nav-accounts');
const sidebarAccountsPanel = document.getElementById('sidebar-accounts-panel');
const toastContainer = document.getElementById('toast-container');
const unloadBackendBtn = document.getElementById('unload-backend-btn');
const backendStatusLabel = document.getElementById('backend-status-label');

const stopBtn = document.getElementById('stop-btn');
const thinkingConsole = document.getElementById('thinking-console');
const statusTitle = document.getElementById('status-title');
const addAccountBtn = document.getElementById('add-account-btn');
const accountPlatform = document.getElementById('account-platform');
const accountName = document.getElementById('account-name');
const accountNotes = document.getElementById('account-notes');
const accountRefreshToken = document.getElementById('account-refresh-token');
const accountYoutubePrivacy = document.getElementById('account-youtube-privacy');
const accountInstagramUserId = document.getElementById('account-instagram-user-id');
const accountInstagramToken = document.getElementById('account-instagram-token');
const accountTikTokOpenId = document.getElementById('account-tiktok-open-id');
const accountTikTokRefreshToken = document.getElementById('account-tiktok-refresh-token');
const accountTikTokAccessToken = document.getElementById('account-tiktok-access-token');
const accountsList = document.getElementById('accounts-list');
const publishConsole = document.getElementById('publish-console');

// Account Groups Elements
const groupName = document.getElementById('group-name');
const groupDescription = document.getElementById('group-description');
const addGroupBtn = document.getElementById('add-group-btn');
const groupsList = document.getElementById('groups-list');
const toggleAccountFormBtn = document.getElementById('toggle-account-form');
const accountFormContainer = document.getElementById('account-form-container');

// Google Drive elements
const tabFile = document.getElementById('tab-file');
const tabDrive = document.getElementById('tab-drive');
const contentFile = document.getElementById('content-file');
const contentDrive = document.getElementById('content-drive');
const driveUrlInput = document.getElementById('drive-url');
const processDriveBtn = document.getElementById('process-drive-btn');

let selectedFile = null;
let currentProcessId = null;
let accountsCache = [];
let groupsCache = [];
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

function setSidebarView(view) {
    if (view === 'accounts') {
        sidebarAccountsPanel.classList.remove('hidden');
        navAccounts.classList.add('active');
        navPipeline.classList.remove('active');
    } else {
        sidebarAccountsPanel.classList.add('hidden');
        navPipeline.classList.add('active');
        navAccounts.classList.remove('active');
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

// Tab Switching
function switchTab(tab) {
    if (tab === 'file') {
        tabFile.classList.add('active');
        tabDrive.classList.remove('active');
        contentFile.classList.add('active');
        contentDrive.classList.remove('active');
    } else {
        tabFile.classList.remove('active');
        tabDrive.classList.add('active');
        contentFile.classList.remove('active');
        contentDrive.classList.add('active');
    }
}

tabFile?.addEventListener('click', () => switchTab('file'));
tabDrive?.addEventListener('click', () => switchTab('drive'));

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

    // Reset UI
    processBtn.disabled = true;
    statusSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    thinkingConsole.innerHTML = '<div class="thinking-line">Initializing local AI engine...</div>';
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

async function loadAccounts() {
    try {
        const res = await fetch('/accounts');
        const data = await res.json();
        accountsCache = data.accounts || [];
        renderAccountsList();
    } catch (err) {
        console.error('Failed to load accounts', err);
    }
}

async function loadGroups() {
    try {
        const res = await fetch('/account-groups');
        const data = await res.json();
        groupsCache = data.groups || [];
        renderGroupsList();
    } catch (err) {
        console.error('Failed to load groups', err);
    }
}

function renderGroupsList() {
    if (!groupsList) return;

    if (!groupsCache.length) {
        groupsList.innerHTML = '<p class="account-empty">No groups created yet. Create a group to organize your accounts.</p>';
        return;
    }

    groupsList.innerHTML = groupsCache.map(group => {
        const accounts = group.accounts || [];
        const accountChips = accounts.map(acc => `
            <span class="group-account-chip">
                ${acc.account_name}
                <button onclick="removeAccountFromGroup('${group.id}', '${acc.id}')" title="Remove from group">×</button>
            </span>
        `).join('');

        const ungroupedAccounts = accountsCache.filter(a =>
            !accounts.some(g => g.id === a.id) &&
            a.platform === (group.targetPlatform || a.platform)
        );

        const addToGroupForm = ungroupedAccounts.length > 0 ? `
            <div class="add-to-group-form">
                <select id="add-to-group-${group.id}">
                    <option value="">Add account...</option>
                    ${ungroupedAccounts.map(a => `<option value="${a.id}">${a.account_name} (${a.platform})</option>`).join('')}
                </select>
                <button class="btn btn-xs btn-add-account" onclick="addAccountToGroup('${group.id}')">Add</button>
            </div>
        ` : '';

        return `
            <div class="group-row" data-group-id="${group.id}">
                <div class="group-header">
                    <div>
                        <span class="group-name">${group.name}</span>
                        ${group.description ? `<span class="group-description"> - ${group.description}</span>` : ''}
                    </div>
                    <div class="group-actions">
                        <button class="btn btn-xs btn-danger" onclick="deleteGroup('${group.id}')">Delete</button>
                    </div>
                </div>
                ${accounts.length > 0 ? `
                    <div class="group-accounts">
                        ${accountChips}
                    </div>
                ` : '<div class="group-accounts"><span style="color: var(--muted); font-size: .75rem;">No accounts in this group yet.</span></div>'}
                ${addToGroupForm}
            </div>
        `;
    }).join('');
}

async function createGroup() {
    const name = groupName?.value?.trim();
    const description = groupDescription?.value?.trim();

    if (!name) {
        showToast('Error', 'Please enter a group name');
        return;
    }

    try {
        await fetch('/account-groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, account_ids: [] })
        });

        groupName.value = '';
        groupDescription.value = '';
        await loadGroups();
        showToast('Success', `Group "${name}" created`);
    } catch (err) {
        console.error('Failed to create group', err);
        showToast('Error', 'Failed to create group');
    }
}

async function deleteGroup(groupId) {
    if (!confirm('Delete this group? Accounts will not be deleted.')) return;

    try {
        await fetch(`/account-groups/${groupId}`, { method: 'DELETE' });
        await loadGroups();
        showToast('Success', 'Group deleted');
    } catch (err) {
        console.error('Failed to delete group', err);
        showToast('Error', 'Failed to delete group');
    }
}

async function addAccountToGroup(groupId) {
    const select = document.getElementById(`add-to-group-${groupId}`);
    const accountId = select?.value;

    if (!accountId) {
        showToast('Error', 'Please select an account');
        return;
    }

    try {
        await fetch(`/account-groups/${groupId}/accounts/${accountId}`, { method: 'POST' });
        await loadGroups();
        showToast('Success', 'Account added to group');
    } catch (err) {
        console.error('Failed to add account to group', err);
        showToast('Error', 'Failed to add account to group');
    }
}

async function removeAccountFromGroup(groupId, accountId) {
    try {
        await fetch(`/account-groups/${groupId}/accounts/${accountId}`, { method: 'DELETE' });
        await loadGroups();
        showToast('Success', 'Account removed from group');
    } catch (err) {
        console.error('Failed to remove account from group', err);
        showToast('Error', 'Failed to remove account from group');
    }
}

function renderAccountsList() {
    if (!accountsCache.length) {
        accountsList.innerHTML = '<p class="account-empty">No accounts added yet.</p>';
        return;
    }

    accountsList.innerHTML = accountsCache.map(acc => `
        <div class="account-row">
            <div>
                <strong>${acc.account_name}</strong>
                <span class="account-tag">${acc.platform}</span>
                ${acc.has_oauth_refresh_token ? '<span class="account-tag">api-ready</span>' : ''}
                ${acc.has_instagram_access_token ? '<span class="account-tag">ig-api-ready</span>' : ''}
                ${acc.has_tiktok_refresh_token || acc.has_tiktok_access_token ? '<span class="account-tag">tt-api-ready</span>' : ''}
            </div>
            <button class="btn btn-danger account-delete-btn" data-account-id="${acc.id}">Delete</button>
        </div>
    `).join('');

    document.querySelectorAll('.account-delete-btn').forEach(btn => {
        btn.onclick = async () => {
            const id = btn.getAttribute('data-account-id');
            await fetch(`/accounts/${id}`, { method: 'DELETE' });
            await loadAccounts();
            await loadGroups(); // Refresh groups to reflect account removal
        };
    });
}

addAccountBtn.onclick = async () => {
    const platform = accountPlatform.value;
    const name = accountName.value.trim();
    const notes = accountNotes.value.trim();
    const refreshToken = accountRefreshToken.value.trim();
    const youtubePrivacyStatus = accountYoutubePrivacy.value;
    const instagramUserId = accountInstagramUserId.value.trim();
    const instagramAccessToken = accountInstagramToken.value.trim();
    const tiktokOpenId = accountTikTokOpenId.value.trim();
    const tiktokRefreshToken = accountTikTokRefreshToken.value.trim();
    const tiktokAccessToken = accountTikTokAccessToken.value.trim();

    if (!name) return;

    try {
        await fetch('/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform,
                account_name: name,
                notes,
                auth_mode: (refreshToken || instagramAccessToken || tiktokRefreshToken || tiktokAccessToken) ? 'api' : 'manual',
                oauth_refresh_token: refreshToken,
                youtube_privacy_status: youtubePrivacyStatus,
                instagram_user_id: instagramUserId,
                instagram_access_token: instagramAccessToken,
                tiktok_open_id: tiktokOpenId,
                tiktok_refresh_token: tiktokRefreshToken,
                tiktok_access_token: tiktokAccessToken,
            })
        });

        accountName.value = '';
        accountNotes.value = '';
        accountRefreshToken.value = '';
        accountInstagramUserId.value = '';
        accountInstagramToken.value = '';
        accountTikTokOpenId.value = '';
        accountTikTokRefreshToken.value = '';
        accountTikTokAccessToken.value = '';
        await loadAccounts();
        await loadGroups(); // Refresh groups to show new account in add-to-group dropdowns
    } catch (err) {
        console.error('Failed to add account', err);
    }
};

function updateAccountCredentialInputs() {
    const isYoutube = accountPlatform.value === 'youtube';
    const isInstagram = accountPlatform.value === 'instagram';
    const isTikTok = accountPlatform.value === 'tiktok';
    accountRefreshToken.disabled = !isYoutube;
    accountYoutubePrivacy.disabled = !isYoutube;
    accountInstagramUserId.disabled = !isInstagram;
    accountInstagramToken.disabled = !isInstagram;
    accountTikTokOpenId.disabled = !isTikTok;
    accountTikTokRefreshToken.disabled = !isTikTok;
    accountTikTokAccessToken.disabled = !isTikTok;
    if (!isYoutube) {
        accountRefreshToken.value = '';
    }
    if (!isInstagram) {
        accountInstagramUserId.value = '';
        accountInstagramToken.value = '';
    }
    if (!isTikTok) {
        accountTikTokOpenId.value = '';
        accountTikTokRefreshToken.value = '';
        accountTikTokAccessToken.value = '';
    }
}

accountPlatform.onchange = updateAccountCredentialInputs;

function accountOptionsForPlatform(platform) {
    const filtered = accountsCache.filter(a => a.platform === platform);
    if (!filtered.length) return '<option value="">No account</option>';
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

navPipeline.onclick = (e) => {
    e.preventDefault();
    setSidebarView('pipeline');
};

navAccounts.onclick = (e) => {
    e.preventDefault();
    setSidebarView('accounts');
};

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

// Group management event handlers
addGroupBtn?.addEventListener('click', createGroup);

toggleAccountFormBtn?.addEventListener('click', () => {
    accountFormContainer?.classList.toggle('hidden');
    const isHidden = accountFormContainer?.classList.contains('hidden');
    toggleAccountFormBtn.innerText = isHidden ? '+ Add Account' : '- Hide Form';
});

// Initialize
loadAccounts();
loadGroups();
updateAccountCredentialInputs();
setSidebarView('pipeline');
refreshBackendRuntimeStatus();

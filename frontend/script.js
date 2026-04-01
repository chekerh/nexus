const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const processBtn = document.getElementById('process-btn');
const statusSection = document.getElementById('status-section');
const resultsSection = document.getElementById('results-section');
const statusMessage = document.getElementById('status-message');
const transcriptContent = document.getElementById('transcript-content');
const analysisContent = document.getElementById('analysis-content');

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

let selectedFile = null;
let currentProcessId = null;
let accountsCache = [];

// Handle File Selection
dropzone.onclick = () => fileInput.click();

fileInput.onchange = (e) => {
    selectedFile = e.target.files[0];
    if (selectedFile) {
        dropzone.innerText = `Selected: ${selectedFile.name}`;
        processBtn.disabled = false;
    }
};

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
                showResults(data);
            } else if (data.status === 'error') {
                clearInterval(poll);
                statusTitle.innerText = "Process Failed";
                thinkingConsole.innerHTML += `<div class="thinking-line error">CRITICAL ERROR: ${data.error}</div>`;
                processBtn.disabled = false;
            } else if (data.status === 'cancelled') {
                clearInterval(poll);
                statusTitle.innerText = "Analysis Cancelled";
                thinkingConsole.innerHTML += `<div class="thinking-line">Process terminated by user. Resources released.</div>`;
                processBtn.disabled = false;
            }
        } catch (err) {
            clearInterval(poll);
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
    const clip = document.getElementById(`clip-${index}`)?.getAttribute('data-filename');

    if (!clip) return;

    const payload = {
        platform: platformEl.value,
        account_id: accountEl.value,
        clip_filename: clip,
        title: titleEl.value.trim(),
        description: descEl.value.trim()
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

function bindClipPublishActions() {
    document.querySelectorAll('.platform-select').forEach(select => {
        select.onchange = () => {
            const idx = select.getAttribute('data-index');
            const accountSelect = document.getElementById(`account-${idx}`);
            accountSelect.innerHTML = accountOptionsForPlatform(select.value);
        };
    });

    document.querySelectorAll('.publish-btn').forEach(btn => {
        btn.onclick = () => publishClip(btn.getAttribute('data-index'));
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
            video.textTracks[0].mode = 'showing';
        }

        if (!cuesPayload || !Array.isArray(cuesPayload.cues)) {
            continue;
        }

        const cues = cuesPayload.cues;
        const updateOverlay = () => {
            const t = video.currentTime || 0;
            const active = cues.find(c => t >= c.start && t <= c.end);
            if (!active) {
                overlay.innerHTML = '';
                overlay.className = 'caption-overlay';
                return;
            }
            overlay.innerHTML = `<span>${active.text}</span>`;
            overlay.className = `caption-overlay ${(active.style ? `cap-${active.style}` : 'cap-neutral')}`;
        };

        video.addEventListener('timeupdate', updateOverlay);
        video.addEventListener('seeked', updateOverlay);
        video.addEventListener('play', updateOverlay);
        video.addEventListener('pause', updateOverlay);
    }
}

function showResults(data) {
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
                        <select id="platform-${index}" class="publish-select platform-select" data-index="${index}">
                            <option value="tiktok">TikTok</option>
                            <option value="instagram">Instagram</option>
                            <option value="youtube">YouTube</option>
                        </select>
                        <select id="account-${index}" class="publish-select">${accountOptionsForPlatform('tiktok')}</select>
                        <button class="btn btn-primary publish-btn" data-index="${index}">Post via Selected Account</button>
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
}

loadAccounts();
updateAccountCredentialInputs();

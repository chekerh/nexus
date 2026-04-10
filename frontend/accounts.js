/* Account Groups Page - Dedicated Page Logic */

// DOM Elements
const groupName = document.getElementById('group-name');
const groupDescription = document.getElementById('group-description');
const addGroupBtn = document.getElementById('add-group-btn');
const groupsList = document.getElementById('groups-list');

const accountPlatform = document.getElementById('account-platform');
const accountName = document.getElementById('account-name');
const accountNotes = document.getElementById('account-notes');
const addAccountBtn = document.getElementById('add-account-btn');
const accountsList = document.getElementById('accounts-list');

const unloadBackendBtn = document.getElementById('unload-backend-btn');
const toastContainer = document.getElementById('toast-container');

// State
let groupsCache = [];
let accountsCache = [];

// Platform icons
const platformIcons = {
    tiktok: '🎵',
    instagram: '📸',
    youtube: '📺'
};

// Toast notifications
function showToast(title, message, duration = 3000) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
    `;
    toastContainer.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('show'));

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Backend status
async function refreshBackendRuntimeStatus() {
    try {
        const res = await fetch('/ai/backend/status');
        const data = await res.json();
        const label = document.getElementById('backend-status-label');
        if (label) label.textContent = `Backend: ${data.backend || 'unknown'}`;
    } catch (err) {
        const label = document.getElementById('backend-status-label');
        if (label) label.textContent = 'Backend: offline';
    }
}

// Load data
async function loadGroups() {
    try {
        const res = await fetch('/account-groups');
        const data = await res.json();
        groupsCache = data.groups || [];
        renderGroups();
        updateStats();
    } catch (err) {
        console.error('Failed to load groups', err);
        showToast('Error', 'Failed to load groups');
    }
}

async function loadAccounts() {
    try {
        const res = await fetch('/accounts');
        const data = await res.json();
        accountsCache = data.accounts || [];
        renderAccounts();
        updateStats();
    } catch (err) {
        console.error('Failed to load accounts', err);
        showToast('Error', 'Failed to load accounts');
    }
}

function updateStats() {
    const groupsEl = document.getElementById('stat-groups');
    const accountsEl = document.getElementById('stat-accounts');
    if (groupsEl) groupsEl.textContent = groupsCache.length;
    if (accountsEl) accountsEl.textContent = accountsCache.length;
}

// Render groups
function renderGroups() {
    if (!groupsList) return;

    if (!groupsCache.length) {
        groupsList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📭</span>
                <p>No groups yet. Create your first group above!</p>
            </div>
        `;
        return;
    }

    groupsList.innerHTML = groupsCache.map(group => {
        const accounts = group.accounts || [];
        const accountChips = accounts.map(acc => `
            <span class="account-chip">
                <span class="platform-icon">${platformIcons[acc.platform] || '●'}</span>
                ${acc.account_name}
                <button class="remove-btn" onclick="removeAccountFromGroup('${group.id}', '${acc.id}')" title="Remove">×</button>
            </span>
        `).join('');

        // Get accounts not in this group
        const availableAccounts = accountsCache.filter(a => 
            !accounts.some(g => g.id === a.id)
        );

        const addDropdown = availableAccounts.length > 0 ? `
            <div class="add-to-group-row">
                <select id="add-to-group-${group.id}" class="add-select">
                    <option value="">Add account to group...</option>
                    ${availableAccounts.map(a => `
                        <option value="${a.id}">${platformIcons[a.platform] || '●'} ${a.account_name}</option>
                    `).join('')}
                </select>
                <button class="btn btn-sm btn-add" onclick="addAccountToGroup('${group.id}')">Add</button>
            </div>
        ` : '';

        return `
            <div class="group-card" data-group-id="${group.id}">
                <div class="group-card-header">
                    <div class="group-info">
                        <h4>${group.name}</h4>
                        ${group.description ? `<p>${group.description}</p>` : `<p class="no-description">No description</p>`}
                    </div>
                    <div class="group-actions">
                        <button class="btn-icon-action delete" onclick="deleteGroup('${group.id}')" title="Delete group">🗑️</button>
                    </div>
                </div>
                ${accounts.length > 0 ? `
                    <div class="group-accounts-chips">
                        ${accountChips}
                    </div>
                ` : '<p class="no-accounts">No accounts in this group yet</p>'}
                ${addDropdown}
            </div>
        `;
    }).join('');
}

// Render accounts
function renderAccounts() {
    if (!accountsList) return;

    if (!accountsCache.length) {
        accountsList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">👤</span>
                <p>No accounts yet. Add your first account above!</p>
            </div>
        `;
        return;
    }

    accountsList.innerHTML = accountsCache.map(account => `
        <div class="account-card" data-account-id="${account.id}">
            <div class="account-avatar ${account.platform}">
                ${platformIcons[account.platform] || '●'}
            </div>
            <div class="account-details">
                <h4>${account.account_name}</h4>
                <span class="platform-badge ${account.platform}">${account.platform}</span>
                ${account.notes ? `<p class="account-notes">${account.notes}</p>` : ''}
            </div>
            <button class="btn-icon-action delete" onclick="deleteAccount('${account.id}')" title="Delete account">🗑️</button>
        </div>
    `).join('');
}

// Actions
async function createGroup() {
    const name = groupName?.value?.trim();
    const description = groupDescription?.value?.trim();

    if (!name) {
        showToast('Error', 'Please enter a group name');
        return;
    }

    try {
        const res = await fetch('/account-groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, account_ids: [] })
        });

        if (!res.ok) throw new Error('Failed to create group');

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
        const res = await fetch(`/account-groups/${groupId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete');
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
        const res = await fetch(`/account-groups/${groupId}/accounts/${accountId}`, { method: 'POST' });
        if (!res.ok) throw new Error('Failed to add');
        await loadGroups();
        showToast('Success', 'Account added to group');
    } catch (err) {
        console.error('Failed to add account', err);
        showToast('Error', 'Failed to add account to group');
    }
}

async function removeAccountFromGroup(groupId, accountId) {
    try {
        const res = await fetch(`/account-groups/${groupId}/accounts/${accountId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to remove');
        await loadGroups();
        showToast('Success', 'Account removed from group');
    } catch (err) {
        console.error('Failed to remove account', err);
        showToast('Error', 'Failed to remove account from group');
    }
}

async function createAccount() {
    const platform = accountPlatform?.value;
    const name = accountName?.value?.trim();
    const notes = accountNotes?.value?.trim();

    if (!name) {
        showToast('Error', 'Please enter an account name');
        return;
    }

    const payload = {
        platform,
        account_name: name,
        notes
    };

    // Add platform-specific fields
    if (platform === 'youtube') {
        const refreshToken = document.getElementById('account-refresh-token')?.value?.trim();
        const privacy = document.getElementById('account-youtube-privacy')?.value;
        if (refreshToken) payload.refresh_token = refreshToken;
        if (privacy) payload.youtube_privacy = privacy;
    } else if (platform === 'instagram') {
        const userId = document.getElementById('account-instagram-user-id')?.value?.trim();
        const token = document.getElementById('account-instagram-token')?.value?.trim();
        if (userId) payload.instagram_user_id = userId;
        if (token) payload.instagram_access_token = token;
    } else if (platform === 'tiktok') {
        const openId = document.getElementById('account-tiktok-open-id')?.value?.trim();
        const refreshToken = document.getElementById('account-tiktok-refresh-token')?.value?.trim();
        const accessToken = document.getElementById('account-tiktok-access-token')?.value?.trim();
        if (openId) payload.tiktok_open_id = openId;
        if (refreshToken) payload.tiktok_refresh_token = refreshToken;
        if (accessToken) payload.tiktok_access_token = accessToken;
    }

    try {
        const res = await fetch('/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('Failed to add account');

        // Clear form
        accountName.value = '';
        accountNotes.value = '';
        document.querySelectorAll('.credential-section input').forEach(input => input.value = '');

        await loadAccounts();
        showToast('Success', `Account "${name}" added`);
    } catch (err) {
        console.error('Failed to add account', err);
        showToast('Error', 'Failed to add account');
    }
}

async function deleteAccount(accountId) {
    if (!confirm('Delete this account? It will be removed from all groups.')) return;

    try {
        const res = await fetch(`/accounts/${accountId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete');
        await Promise.all([loadAccounts(), loadGroups()]);
        showToast('Success', 'Account deleted');
    } catch (err) {
        console.error('Failed to delete account', err);
        showToast('Error', 'Failed to delete account');
    }
}

// Platform selector - show/hide credential fields
function updateCredentialFields() {
    const platform = accountPlatform?.value;
    document.querySelectorAll('.credential-section').forEach(section => {
        section.classList.add('hidden');
    });
    const activeSection = document.querySelector(`.credential-section[data-platform="${platform}"]`);
    if (activeSection) activeSection.classList.remove('hidden');
}

// Event listeners
addGroupBtn?.addEventListener('click', createGroup);
addAccountBtn?.addEventListener('click', createAccount);
accountPlatform?.addEventListener('change', updateCredentialFields);

unloadBackendBtn?.addEventListener('click', async () => {
    try {
        const res = await fetch('/ai/backend/unload', { method: 'POST' });
        const data = await res.json();
        showToast('Runtime', data.message || 'Unload completed');
        await refreshBackendRuntimeStatus();
    } catch (err) {
        showToast('Error', `Unload failed: ${err.message}`);
    }
});

// Initialize
loadGroups();
loadAccounts();
updateCredentialFields();
refreshBackendRuntimeStatus();

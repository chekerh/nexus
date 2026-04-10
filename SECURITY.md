# Nexus-UGC Security Guide

This document outlines the security features and best practices for Nexus-UGC.

## Overview

Nexus-UGC is designed to run locally, keeping your data and social media credentials on your own machine. However, several security measures are implemented to protect your sensitive information.

## Security Features

### 1. Token Encryption

All social media tokens (YouTube refresh tokens, Instagram access tokens, TikTok tokens) are **encrypted at rest** using AES-256 encryption.

**How it works:**
- When you add an account with API credentials, tokens are encrypted before being stored
- Encryption key is stored separately with restrictive file permissions (`0o600` - only owner can read/write)
- Tokens are automatically decrypted when needed for publishing
- If the cryptography library is not available, a machine-specific obfuscation is used as fallback

**File locations:**
- Encrypted accounts: `backend/data/accounts.json`
- Encryption key: `backend/data/.security_key`

### 2. Password Protection

Enable password protection to prevent unauthorized access to the dashboard.

**Setup:**
```bash
# Via API (or use the UI)
curl -X POST http://localhost:8000/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"password": "your-secure-password"}'
```

**Features:**
- PBKDF2-HMAC-SHA256 password hashing (100,000 iterations)
- 24-hour session tokens
- Password must be at least 8 characters
- Optional - can be disabled if running in a trusted environment

### 3. File Upload Validation

All uploaded video files are validated for security:

**Checks performed:**
- File extension validation (only `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, `.flv`)
- Path traversal detection (blocks filenames with `..`, `/`, `\`)
- File size limit: 2GB maximum
- MIME type logging for unusual content types

### 4. Audit Logging

All sensitive operations are logged for security monitoring:

**Logged actions:**
- Account created/deleted
- Authentication attempts (success/failure)
- Password protection enabled/disabled
- File uploads (accepted/rejected)
- Publishing attempts

**Log location:** `backend/data/audit.log`

**Example log entry:**
```json
{"timestamp": "2026-04-10T14:30:00", "action": "account_created", "details": {"account_id": "...", "platform": "youtube", "account_name": "MyChannel"}, "success": true}
```

### 5. Secure Data Storage

**File permissions:**
- Database files: `0o644` (owner read/write, group/others read-only)
- Encryption key: `0o600` (owner read/write only)
- Authentication config: `0o600` (owner read/write only)

**Data directories:**
- Uploads: `backend/data/` (temporary, cleaned up after processing)
- Clips: `backend/data/clips/` (generated content)
- Databases: `backend/data/*.json`

## API Keys and Social Media Integration

### Do You Need API Keys?

**No** - The system works without API keys. You can:
- Add accounts without credentials (manual mode)
- Generate clips and download them
- Get manual upload links for each platform

**API Keys are only needed for:**
- Direct auto-publishing to social media platforms
- Automatic video posting without manual intervention

### Supported Platforms

| Platform | Auto-Publish | Required Credentials |
|----------|-------------|---------------------|
| YouTube | Yes* | OAuth refresh token |
| Instagram | Yes* | User ID + Long-lived access token |
| TikTok | Yes* | Client Key + Client Secret + Access/Refresh tokens |

*Requires public URL access for TikTok and proper app approval

### Getting API Credentials

**YouTube:**
1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials
4. Get refresh token using OAuth flow

**Instagram:**
1. Create a Facebook Developer account
2. Set up Instagram Basic Display or Graph API
3. Generate long-lived access token
4. Note your Instagram User ID

**TikTok:**
1. Apply for [TikTok for Developers](https://developers.tiktok.com/)
2. Create an app to get Client Key and Secret
3. Complete OAuth flow for access/refresh tokens
4. Set `PUBLIC_BASE_URL` in `.env` to your publicly accessible URL

## Best Practices

### 1. Run Behind a Reverse Proxy

For production use, run behind Nginx or Apache with HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. Enable Password Protection

Always enable password protection if the service is accessible from the network:

1. Go to Settings in the UI
2. Set a strong password (12+ characters recommended)
3. Store the password in a password manager

### 3. Restrict Network Access

By default, the server binds to `0.0.0.0` (all interfaces). To restrict to localhost only:

```bash
# In .env or when starting
UVICORN_HOST=127.0.0.1
```

### 4. Regular Backups

Back up your encrypted data:

```bash
# Important files to backup
cp backend/data/accounts.json backup/
cp backend/data/account_groups.json backup/
cp backend/data/.security_key backup/  # Required to decrypt tokens!
```

### 5. Monitor Audit Logs

Regularly check the audit log for suspicious activity:

```bash
# View recent activity
tail -f backend/data/audit.log

# Check for failed login attempts
grep '"success": false' backend/data/audit.log
```

### 6. Keep Dependencies Updated

```bash
pip install -r requirements.txt --upgrade
```

## Security Checklist

- [ ] Password protection enabled (if network-accessible)
- [ ] Running behind HTTPS reverse proxy
- [ ] File permissions checked on `.security_key` and `.auth_config`
- [ ] Network access restricted to necessary interfaces
- [ ] Audit logs reviewed regularly
- [ ] Backups created with encryption key
- [ ] Dependencies kept up to date

## Reporting Security Issues

If you discover a security vulnerability:
1. Do not open a public issue
2. Document the vulnerability with reproduction steps
3. Contact the maintainers privately

## Security Limitations

**Known limitations:**
1. **Local-only encryption key** - If the `.security_key` file is lost, tokens cannot be recovered
2. **No multi-user support** - Designed for single-user local deployment
3. **Session tokens in memory** - Server restart invalidates sessions
4. **No IP rate limiting** - Use a reverse proxy for rate limiting
5. **Machine-bound obfuscation** - Without cryptography library, obfuscation is tied to machine ID

## Technical Details

### Encryption Algorithm

- **Library:** `cryptography` (Fernet)
- **Algorithm:** AES-256 in CBC mode with HMAC-SHA256 authentication
- **Key derivation:** PBKDF2-HMAC-SHA256 (100,000 iterations)
- **Key storage:** Separate file with 0o600 permissions

### Password Hashing

- **Algorithm:** PBKDF2-HMAC-SHA256
- **Iterations:** 100,000
- **Salt:** Fixed per-installation (upgrade planned for per-password salts)
- **Storage:** `.auth_config` with 0o600 permissions

## Migration from Older Versions

If upgrading from a version without encryption:
1. Accounts with plain text tokens will still work
2. New accounts will have encrypted tokens
3. Old tokens are migrated on first read (transparent)
4. Consider re-adding accounts to ensure all tokens are encrypted

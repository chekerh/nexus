# Nexus-UGC Security Guide

This guide matches the current app behavior and security controls.

## Current security model

- JWT auth uses `JWT_SECRET` and sets httpOnly cookies for browser flows.
- Social account tokens are stored encrypted in the database and decrypted only when publishing.
- CSRF protection is enabled for cookie-based requests and rotates tokens after mutating requests.
- Rate limiting is enforced in middleware with memory or database backend support.
- Security headers are added globally, including HSTS, CSP, frame blocking, and request IDs.

## Secrets and credentials

- Keep `JWT_SECRET`, `ENCRYPTION_KEY`, `STRIPE_*`, `WHOP_*`, and OAuth client credentials out of source control.
- Use `.env` locally and GitHub Secrets or a secrets manager in CI and production.
- If you enable `SYSTEM_ACCOUNTS_ENABLED`, the app can auto-provision system-level social accounts at startup.

## Token and account handling

- User social accounts are persisted through the SQLAlchemy models in `backend/app/models/account.py`.
- OAuth flows live under `/api/v1/oauth/*` and persist tokens after callback validation.
- Publishing can use either connected account tokens or system-level fallback credentials when configured.

## File upload and publishing validation

- Clip filenames are validated before publish and path traversal is rejected.
- The publish API only accepts clips already present under `UPLOAD_DIR/clips`.
- Missing provider credentials return `manual_required` with a platform upload link instead of silently failing.

## Operational checks

Run these before production promotion:

```bash
make smoke
python -m pytest -q tests
```

## Security headers

The app adds these headers globally:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`

## Production checklist

- [ ] `PUBLIC_BASE_URL` points at the HTTPS deployment URL
- [ ] `JWT_SECRET` and `ENCRYPTION_KEY` are unique and strong
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] PostgreSQL is used in production
- [ ] OAuth app credentials are configured for the platforms you want to publish to
- [ ] `make smoke` passes against the deployed environment

## Incident response

1. Check `GET /health` and `GET /api/v1/system/check`.
2. Review `GET /api/v1/metrics` and the app logs for `request_id`.
3. If publishing fails, inspect `POST /api/v1/publish` responses and `publish_history` rows.
4. If a webhook fails, confirm its signature secret and replay the payload with the correct signature header.

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

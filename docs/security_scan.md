# Security Scan Checklist
Run before production launch.

## Automated Scans

```bash
# 1. Lint security rules
ruff check backend/ --select S     # flake8-bandit rules (if enabled)

# 2. Dependency audit
pip-audit --requirement requirements.txt

# 3. Deployment smoke test
make smoke

# 4. Full regression suite
python -m pytest tests/ -v
```

## Manual Checks

| Check | Method | Expected |
|-------|--------|----------|
| Rate limiting | `curl -v http://localhost:8000/api/v1/auth/login` × 20 | 429 after auth_limit |
| CSRF protection | POST to a state-changing endpoint without `X-CSRF-Token` | 403 |
| CORS | `curl -H "Origin: https://evil.com" -I http://localhost:8000` | No `Access-Control-Allow-Origin: *` |
| HSTS | `curl -sI http://localhost:8000 \| grep Strict-Transport` | `max-age=31536000; includeSubDomains` |
| JWT expiry | Use expired token | 401 |
| SQL injection | `/api/v1/pipeline/submit?filename=' OR 1=1 --` | 422 or 400, not 200 |
| Directory traversal | `/api/v1/publish` with `clip_filename=../../etc/passwd` | 400 |
| Large upload | Upload oversized file | 413 or 400 |

## Security Headers (check with `curl -sI`)

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'nonce-...'; ...
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Infrastructure

- [ ] TLS via Caddy (auto certs)
- [ ] `PUBLIC_BASE_URL` set to production URL
- [ ] `JWT_SECRET` rotated (not default)
- [ ] `ENCRYPTION_KEY` generated (32 bytes base64)
- [ ] Rate limiting enabled (`RATE_LIMIT_ENABLED=true`)
- [ ] Database connection uses TLS for PostgreSQL
- [ ] Ollama bound to localhost only (not exposed)
- [ ] Prometheus endpoint restricted to internal IPs in reverse proxy
- [ ] `make smoke` passes against the deployed environment

# Nexus-UGC Production Readiness Audit

**Generated:** 2026-06-16  
**Version:** 2.0.0  
**Goal:** Ship a production-ready, monetizable UGC platform

---

## Executive Summary

Nexus-UGC is a **feature-complete MVP** with impressive local-AI video processing. It has:
- ✅ FastAPI backend with 20+ API endpoints
- ✅ SQLite/PostgreSQL with Alembic migrations
- ✅ JWT auth (httpOnly cookies + CSRF)
- ✅ Video pipeline: Whisper → Ollama strategist → FFmpeg → Publish
- ✅ Multi-platform publishing (YouTube, TikTok, Instagram, etc.)
- ✅ Stripe + Whop billing integration
- ✅ Admin dashboard with 11 endpoints
- ✅ Docker + Caddy reverse proxy with auto-SSL
- ✅ Sentry error tracking
- ✅ Rate limiting (memory + DB-backed)

**But it has critical gaps for production monetization:**

| Category | Status | Blockers |
|----------|--------|----------|
| **UI/UX** | ❌ Poor | No design system, broken focus rings, no light theme, inline handlers, no loading skeletons |
| **Self-Improvement** | 🟡 Partial | Backend endpoint added, needs frontend polish + real Ollama testing |
| **Real-time Progress** | ❌ Missing | No SSE endpoint for job status |
| **Analytics** | 🟡 Basic | Only 1 endpoint, no time-series, no funnel |
| **Observability** | 🟡 Basic | Sentry only, no metrics, no alerting |
| **CI/CD** | ❌ Missing | No GitHub Actions |
| **Email/Notifications** | ❌ Missing | No transactional email |
| **Webhook Hardening** | 🟡 Basic | Stripe/Whop handlers exist but untested |
| **Backup/DR** | 🟡 Script only | Manual script, no automation/scheduling |
| **API Versioning** | ❌ None | v1 only, no deprecation strategy |

---

## Detailed Gap Analysis

### 1. UI/UX — Critical (User explicitly called this out)

**Current State:**
- 14 HTML pages with duplicated navbar/sidebar code
- `style.css` = 2100+ lines, no design tokens, no light theme
- `admin.css` = 396 lines, duplicates sidebar styles
- 3 different focus ring implementations (`.dialog-input:focus`, `:focus-visible` in new code, button focus)
- No skeleton loaders, empty states only in queue.html
- Button loading state (`.btn-loading`) only on login pages
- 14 inline `onclick` handlers in queue.html (being refactored)
- No theme toggle on main app pages
- Mobile: sidebar doesn't collapse on admin, navbar works but no hamburger on app pages
- Accessibility: missing ARIA labels, no focus trap on all modals, color contrast unverified

**Required:**
- Unified design token system (spacing, typography, colors, shadows, radius)
- Light/dark theme with localStorage persistence on ALL pages
- Skeleton loading components for every data fetch
- Empty/error states for every data container
- Consistent button loading states
- Event delegation everywhere (no inline handlers)
- Responsive admin sidebar with hamburger
- Theme toggle in navbar
- Accessibility audit (WCAG 2.1 AA)

### 2. Self-Improvement Admin Dashboard — High Priority

**Current State:**
- Backend endpoint: `POST /api/v1/admin/suggest-features` ✅ (just added)
- Scans backend + frontend code, sends to Ollama, returns NDJSON suggestions
- Frontend: `brainstorm` tab in admin.js ✅ (just added)
- Voting system for suggestions ✅

**Gaps:**
- No persistence of suggestions/votes (in-memory only)
- No "implement" workflow (create GitHub issue, assign, track)
- No scheduling (run nightly, show history)
- Ollama prompt could be improved with more context (errors, logs, user feedback)
- No fallback if Ollama unavailable

### 3. Real-Time Job Progress — Critical for UX

**Current State:**
- Job queue exists (`backend/app/services/job_queue.py`)
- Pipeline worker runs in background
- Frontend polls or shows static "processing" screen
- No SSE/WebSocket for live updates

**Required:**
- `GET /api/v1/jobs/{id}/stream` SSE endpoint
- Frontend: progress bar with stage breakdown (transcribe → analyze → render → publish)
- Cancel button that actually works
- WebSocket fallback for better real-time

### 4. Analytics Dashboard — High Priority

**Current State:**
- `GET /api/v1/analytics/dashboard` — single endpoint, user-scoped
- Admin has `/admin/stats` but no time-series
- No funnel analysis (upload → process → publish → views)
- No retention/churn metrics

**Required:**
- Time-series endpoints (daily/weekly/monthly)
- Funnel visualization
- Revenue metrics (MRR, ARPU, churn)
- Platform performance comparison
- Export to CSV

### 5. Backend Hardening

| Component | Status | Issues |
|-----------|--------|--------|
| **Migrations** | 🟡 | Alembic exists but only 3 migrations; no downgrade testing |
| **Rate Limiting** | 🟡 | DB-backed works but cleanup every 100 writes may miss bursts |
| **Webhooks** | 🟡 | Stripe/Whop handlers exist, no signature verification testing, no idempotency keys |
| **Error Handling** | 🟡 | Good try/except but inconsistent error codes, no correlation IDs |
| **Database** | 🟡 | SQLite dev, PG prod — but no connection pooling config, no read replicas |
| **Job Queue** | 🟡 | Single worker, no priority queue, no dead letter queue |
| **File Storage** | 🟡 | Local disk only, no S3/R2, no CDN |

### 6. Security Hardening

| Area | Status | Gaps |
|------|--------|------|
| **CSP** | 🟡 | Header set but `unsafe-inline` for scripts/styles — need nonce/hash |
| **Auth** | ✅ | JWT httpOnly cookie + CSRF, good |
| **Secrets** | 🟡 | `.env` only, no Vault/AWS Secrets Manager integration |
| **Headers** | ✅ | SecurityHeadersMiddleware exists |
| **Input Validation** | 🟡 | Pydantic models but some raw SQL in migrations |
| **Rate Limiting** | ✅ | Per-IP + auth endpoints |
| **CORS** | 🟡 | `*` in dev, needs strict origins in prod |

### 7. FinOps / Observability

| Component | Status |
|-----------|--------|
| **Metrics** | ❌ None (no Prometheus/metrics endpoint) |
| **Logging** | 🟡 Structured logging configured, but no log aggregation |
| **Tracing** | ❌ None |
| **Alerting** | ❌ None |
| **Cost Tracking** | ❌ None (no per-user cost attribution) |
| **Sentry** | ✅ Configured |

### 8. CI/CD Pipeline — Missing

- No GitHub Actions
- No automated tests on PR
- No staging environment
- No automated deploy
- No database migration automation

### 9. Documentation

| Doc | Status |
|-----|--------|
| API Reference | ❌ (FastAPI auto-docs only) |
| Deployment Guide | 🟡 Partial (README) |
| Runbooks | ❌ |
| Architecture Diagrams | 🟡 In `architecture/` folder |
| Changelog | ❌ |

### 10. Monetization Readiness

| Flow | Status | Gaps |
|------|--------|------|
| Stripe Checkout | ✅ | Works but no email receipt |
| Stripe Portal | ✅ | Works |
| Stripe Webhooks | 🟡 | Handler exists, needs idempotency + retry |
| Whop Licenses | ✅ | Claim endpoint exists |
| Credit System | ✅ | Per-tier limits, usage tracking |
| Billing Retry | ❌ | No dunning management |
| Invoice/Receipts | ❌ | None |
| Trial Management | ❌ | No trial logic |
| Affiliate/Referral | ❌ | None |

---

## Production Readiness Plan — 11 Phases

### Phase 1: UI/UX Overhaul (Week 1)
**Goal:** Professional, consistent, accessible UI

- [ ] Create design token system in `style.css` (spacing, type, color, shadow, radius scales)
- [ ] Add light theme variables + theme toggle component
- [ ] Build skeleton loader components (card, table, list, chart)
- [ ] Add empty/error state components to `ui.js`
- [ ] Refactor all inline `onclick` → event delegation
- [ ] Add theme toggle to navbar (all pages)
- [ ] Fix admin sidebar responsive (hamburger + collapse)
- [ ] Unify focus rings (single `:focus-visible` system)
- [ ] Add button loading states globally
- [ ] Accessibility audit: ARIA labels, focus traps, contrast
- [ ] Extract shared navbar/sidebar into partial or JS component

### Phase 2: Self-Improvement Dashboard (Week 1-2)
**Goal:** Nexus improves itself via Ollama

- [ ] Persist suggestions to DB (new `FeatureSuggestion` model)
- [ ] Add suggestion history + status (new/in-review/implemented/dismissed)
- [ ] Nightly cron job to run brainstorm automatically
- [ ] "Create Issue" button → GitHub API integration
- [ ] Improve Ollama prompt with: error logs, user feedback, feature requests
- [ ] Add fallback model chain (qwen2.5 → phi3 → llama3.2)
- [ ] Admin: filter by category, effort, votes

### Phase 3: Real-Time Job Progress (Week 2)
**Goal:** Live progress for video processing

- [ ] SSE endpoint: `GET /api/v1/jobs/{id}/stream`
- [ ] Pipeline worker emits progress events (stage, %, message)
- [ ] Frontend: progress modal with stage breakdown
- [ ] Cancel endpoint that actually kills FFmpeg process
- [ ] Reconnection logic for SSE

### Phase 4: Analytics Enhancement (Week 2)
**Goal:** Actionable business metrics

- [ ] Time-series endpoints: `/analytics/timeseries?metric=posts&interval=day`
- [ ] Funnel: upload → transcribe → analyze → render → publish → views
- [ ] Revenue: MRR, ARPU, churn, LTV
- [ ] Platform comparison table
- [ ] Export CSV endpoint
- [ ] Admin analytics tab with charts (Chart.js or simple CSS bars)

### Phase 5: Backend Hardening (Week 2-3)
**Goal:** Reliable, scalable backend

- [ ] Add alembic migration for `FeatureSuggestion` model
- [ ] Add `dead_letter_queue` table for failed jobs
- [ ] Priority queue for job processing
- [ ] Connection pooling config for PostgreSQL
- [ ] S3/R2 storage abstraction (local dev, S3 prod)
- [ ] Webhook idempotency keys + signature verification
- [ ] Correlation IDs on all requests (X-Request-ID)
- [ ] Structured error codes (ERR_AUTH, ERR_QUOTA, ERR_PROCESSING, etc.)

### Phase 6: Security Hardening (Week 3)
**Goal:** Production-grade security

- [ ] CSP with nonces for inline scripts/styles
- [ ] Remove `unsafe-inline` from CSP
- [ ] Integrate AWS Secrets Manager / HashiCorp Vault for prod secrets
- [ ] Add security.txt
- [ ] Rate limit: sliding window + Redis backend option
- [ ] Audit all SQL for injection (use SQLAlchemy ORM everywhere)
- [ ] Add HSTS preload submission
- [ ] Penetration test checklist

### Phase 7: FinOps/Observability (Week 3)
**Goal:** Visibility into costs and performance

- [ ] Prometheus metrics endpoint (`/metrics`)
- [ ] Key metrics: request latency, job duration, queue depth, error rate, active users
- [ ] Grafana dashboards (JSON export)
- [ ] Alert rules: queue depth > 50, error rate > 5%, disk > 80%
- [ ] Cost attribution: per-user GPU/CPU minutes, API calls
- [ ] Structured JSON logging with correlation IDs
- [ ] Log aggregation (Loki/ELK)

### Phase 8: CI/CD Pipeline (Week 3-4)
**Goal:** Automated quality gates

- [ ] GitHub Actions: lint (ruff), typecheck (mypy), test (pytest)
- [ ] Frontend: lint (eslint), test (playwright)
- [ ] Build Docker image on merge to main
- [ ] Deploy to staging on merge
- [ ] Manual approval for production deploy
- [ ] Database migration automation in deploy
- [ ] Smoke tests post-deploy

### Phase 9: Documentation (Week 4)
**Goal:** Operable by others

- [ ] OpenAPI/Swagger enhancements (examples, descriptions)
- [ ] Deployment guide: Docker, Caddy, PostgreSQL, SSL
- [ ] Runbooks: deploy, rollback, backup/restore, incident response
- [ ] Architecture decision records (ADRs)
- [ ] Changelog automation

### Phase 10: Monetization Polish (Week 4)
**Goal:** Revenue-ready billing

- [ ] Stripe webhook idempotency + retry with exponential backoff
- [ ] Email receipts (SendGrid/Resend) for successful payments
- [ ] Dunning management: retry failed payments, email reminders
- [ ] Invoice generation + download
- [ ] Trial logic (14-day Pro trial)
- [ ] Referral system (invite keys → credit bonus)
- [ ] Whop webhook: license activated/cancelled → tier sync

### Phase 11: Launch Readiness (Week 4-5)
**Goal:** Ship with confidence

- [ ] Load test: 100 concurrent users, 50 concurrent jobs
- [ ] Chaos test: kill worker mid-job, verify recovery
- [ ] Backup/restore drill
- [ ] Run all tests: `pytest -xvs`, frontend e2e
- [ ] Security scan: `bandit`, `safety check`
- [ ] Performance baseline: p95 latency < 500ms
- [ ] Go/no-go checklist

---

## Architecture Decisions (ADRs)

| ID | Decision | Status |
|----|----------|--------|
| ADR-001 | Local-first AI (Ollama/Whisper) | ✅ Implemented |
| ADR-002 | SQLite dev / PostgreSQL prod | ✅ Implemented |
| ADR-003 | JWT in httpOnly cookie + CSRF | ✅ Implemented |
| ADR-004 | Caddy for auto-SSL reverse proxy | ✅ Implemented |
| ADR-005 | DB-backed rate limiting (no Redis) | ✅ Implemented |
| ADR-006 | Single worker + priority queue (Phase 5) | 🟡 Planned |
| ADR-007 | S3/R2 abstraction for file storage (Phase 5) | 🟡 Planned |
| ADR-008 | SSE for real-time (Phase 3) | 🟡 Planned |
| ADR-009 | Feature suggestion persistence (Phase 2) | 🟡 Planned |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Ollama unavailable in prod | Medium | High | Fallback model chain, health check alerts |
| FFmpeg version incompatibility | Medium | High | Pin FFmpeg version in Dockerfile, test filter chains |
| Stripe webhook failures | Low | High | Idempotency keys, retry logic, dead letter queue |
| Database migration failure | Low | Critical | Test migrations on staging, backup before migrate |
| GPU memory OOM on video render | Medium | High | Monitor memory, queue limits, fallback to CPU |
| Cost overrun (local GPU) | Medium | Medium | Per-user quotas, cost tracking, alerts |
| Single point of failure (worker) | High | High | Phase 5: priority queue + dead letter + health checks |

---

## Success Metrics (Launch KPIs)

| Metric | Target |
|--------|--------|
| **Uptime** | 99.9% |
| **API p95 latency** | < 500ms |
| **Job success rate** | > 95% |
| **Time to first clip** | < 5 min (short video) |
| **Error rate** | < 1% |
| **MRR (Month 1)** | $1,000 |
| **Churn (Month 1)** | < 10% |
| **NPS** | > 40 |

---

## File Inventory for Reference

### Backend (67 Python files)
```
backend/app/
├── main.py                 # FastAPI app, middleware, startup/shutdown
├── core/
│   ├── config.py           # Settings (159 lines, comprehensive)
│   ├── database.py         # Engine, sessions, migrations (117 lines)
│   ├── security.py         # JWT, encryption, passwords
│   ├── logging.py          # Structured logging
│   ├── middleware.py       # Rate limit, upload size, CSRF, headers
│   ├── video_editor.py     # FFmpeg pipeline
│   ├── transcriber.py      # Whisper.cpp wrapper
│   ├── publisher.py        # Multi-platform publishing
│   ├── analyst.py          # Virality scoring
│   ├── brainrot.py         # AI script generation
│   ├── whop.py             # Whop integration
│   ├── thumbnails.py       # A/B testing
│   ├── drive_downloader.py # Google Drive
│   ├── model_router.py     # Dynamic model selection
│   └── ...
├── api/v1/ (20 routers)
│   ├── auth.py             # Login, register, API keys
│   ├── pipeline.py         # Video upload/process
│   ├── brainrot.py         # AI content generation
│   ├── posts.py            # Post CRUD + queue
│   ├── personas.py         # Persona management
│   ├── campaigns.py        # Campaign scheduling
│   ├── accounts.py         # OAuth connections
│   ├── billing.py          # Stripe checkout/portal
│   ├── admin.py            # Admin dashboard (11 endpoints)
│   ├── analytics.py        # User analytics
│   ├── whop.py             # Whop license webhooks
│   ├── oauth.py            # Google OAuth
│   ├── publish.py          # Manual publish
│   ├── thumbnails.py       # Thumbnail A/B
│   └── system.py           # Health, config
├── models/ (12 models)
├── services/ (5 services)
└── workers/
    └── pipeline.py         # Background video processing
```

### Frontend (25 files)
```
frontend/
├── index.html              # Landing + dashboard (429 lines)
├── brainrot.html           # AI content generator (367 lines)
├── queue.html              # Post queue (336 lines) - BEST UX
├── billing.html            # Billing + usage (11k lines)
├── setup.html              # Onboarding wizard (29k lines)
├── admin.html              # Admin shell (2.3k lines)
├── admin-login.html        # Admin login
├── personas.html           # Persona management
├── campaigns.html          # Campaign builder
├── calendar.html           # Content calendar
├── accounts.html           # Social accounts
├── login.html              # User login
├── style.css               # Main design system (2100+ lines)
├── admin.css               # Admin styles (396 lines)
├── choko.css               # Mascot styles
├── api.js                  # Shared API client (293 lines)
├── ui.js                   # Shared UI utilities (268 lines)
├── script.js               # Index page logic
├── brainrot.js             # (inline in HTML)
├── queue.js                # (inline in HTML)
├── admin.js                # Admin dashboard (578 lines - just rewritten)
├── personas.js
├── campaigns.js
├── calendar.js
├── particles.js            # Background animation
├── choko.js                # Mascot AI assistant
└── choko-knowledge.js      # Mascot knowledge base
```

---

## Next Steps

**Immediate (This Session):**
1. Complete Phase 1 UI/UX — design tokens, theme, skeletons, empty states
2. Complete Phase 2 Self-Improvement — persist suggestions, improve prompt
3. Complete Phase 3 SSE — real-time job progress
4. Complete Phase 4 Analytics — time-series + funnel

**Then:**
5. Run full test suite, fix failures
6. Load test locally
7. Deploy to staging
8. Production deploy with monitoring

---

*This audit is a living document. Update as phases complete.*
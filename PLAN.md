# Nexus-UGC Master Plan

## Vision
A social media automation OS: upload video → AI pipeline → repurpose into multi-platform content → schedule → confirm → auto-publish. Monetized via Whop.

---

## Architecture

### Data Models
```
User (existing)
  ├── Persona       — brand identity (voice, avatar, tone, bio, audience)
  │     ├── Schedule — per-platform posting times (day + hour)
  │     └── Post     — content items (draft → pending → approved → posted)
  ├── Job (existing) — pipeline runs
  │     ├── Clip (in job.clips_json)
  │     └── Thumbnail (existing)
  ├── Account (existing) — connected social accounts
  └── Campaign     — grouped content with shared target platforms
```

### Phases

**Phase 0 — ✅ Done**
- Pipeline: transcription → analysis → cutting
- Multi-language captions (16 languages)
- Virality score (heuristic + AI)
- Auto reframe (5 aspect ratios)
- AI Thumbnails + A/B testing
- Account management + basic publishing (YouTube, TikTok, Instagram)
- Billing/credits
- Frontend redesign

**Phase 1 — ✅ Complete (Persona + Scheduling)**
- **Persona System**: Persona model + CRUD API + creation UI (`personas.html`)
- **Post Queue**: Post model + status workflow (draft→pending→approved→scheduled→posted)
- **Schedule Calendar**: Per-platform day/time scheduling + calendar UI (`calendar.html`)
- **Approval Flow**: User confirms before auto-publish
- **Content Repurposing**: Ollama generates platform-specific posts from transcript via /repurpose endpoint

**Phase 2 — ✅ Complete (Campaigns + Auto-Publish)**
- **Campaign System**: Campaign model + CRUD API + management UI (`campaigns.html`)
- **Auto-Publish Worker**: Background thread checks every 60s, publishes scheduled posts to YouTube, TikTok, Instagram, Facebook, X/Twitter, LinkedIn
- **Expanded Publishing**: Unified publish module supporting all 6 platforms with media upload and text posts
- Campaign dashboard with progress tracking

**Phase 3 — 📝 Planned**
- **Whop Integration**: Webhooks → auto-provision accounts → license key validation → tier mapping
- Webhook receiver for purchase/license events
- License key validation
- Auto-account provisioning
- Tier mapping

**Phase 4 — 📝 Planned**
- **Platform Expansion Enhancements**: Better error handling, retry logic, per-platform rate limits
- OAuth refresh token management
- Publishing analytics dashboard

### File Inventory

```
backend/
├── app/
│   ├── models/
│   │   ├── user.py            (existing)
│   │   ├── job.py             (existing)
│   │   ├── account.py         (existing)
│   │   ├── api_key.py         (existing)
│   │   ├── thumbnail.py       (existing)
│   │   ├── persona.py         ← Phase 1
│   │   └── campaign.py        ← Phase 2
│   ├── core/
│   │   ├── database.py        (existing - modified for migrations)
│   │   ├── config.py          (existing)
│   │   ├── video_editor.py    (existing)
│   │   ├── translator.py      (existing)
│   │   ├── virality.py        (existing)
│   │   ├── thumbnails.py      (existing)
│   │   ├── ab_testing.py      (existing)
│   │   ├── repurposer.py      ← Phase 1 (via personas.py)
│   │   ├── scheduler.py       ← Phase 1 (via posts.py)
│   │   └── whop.py            ← Phase 3
│   ├── api/v1/
│   │   ├── router.py          (existing - modified)
│   │   ├── auth.py            (existing)
│   │   ├── pipeline.py        (existing)
│   │   ├── accounts.py        (existing)
│   │   ├── publish.py         (existing - modified for helpers)
│   │   ├── billing.py         (existing)
│   │   ├── thumbnails.py      (existing)
│   │   ├── personas.py        ← Phase 1
│   │   ├── posts.py           ← Phase 1
│   │   ├── campaigns.py       ← Phase 2
│   ├── services/
│   │   ├── job_queue.py       (existing)
│   │   ├── billing.py         (existing)
│   │   ├── usage.py           (existing)
│   │   └── publisher.py       ← Phase 2 (auto-publish worker)
│   └── main.py                (existing - modified for publish worker)
frontend/
├── index.html                 (existing - navbar updated)
├── login.html                 (existing)
├── accounts.html              (existing)
├── personas.html              ← Phase 1
├── calendar.html              ← Phase 1
├── campaigns.html             ← Phase 2
├── style.css                  (existing - added modal/badge/app-layout)
├── script.js                  (existing)
├── persona.js                 ← Phase 1
├── calendar.js                ← Phase 1
├── campaigns.js               ← Phase 2
└── api.js                     (existing - added all new API functions)
```

### Post Status Workflow
```
Draft ──→ Pending ──→ Approved ──→ Scheduled ──→ Posted
            │            │                            │
            └─→ Cancelled └─→ Cancelled          Failed
```

### Key Design Decisions
- Persona voice is stored as text prompt fragments, used to seed Ollama content generation
- Post queue is processed by a lightweight scheduler (not cron — checked via API or on-demand worker)
- Approval is required by default; each persona can opt into "auto-post" mode
- Campaigns use the same post queue but group posts under a campaign_id
- Whop integration: webhook receives `purchase.created` → POST to Nexus API → creates user + provisions credits
- All content generation uses Ollama (local, no API costs)
- Platform publishing reuses existing `publish.py` infrastructure; adds LinkedIn and X modules

### Next Context Window Read
1. Read PLAN.md to understand full scope
2. Read `backend/app/models/persona.py`, `backend/app/api/v1/personas.py`, `backend/app/api/v1/scheduler.py`
3. Read `frontend/personas.html`, `frontend/calendar.html`, `frontend/persona.js`
4. Read `backend/app/core/repurposer.py` for Phase 2
5. Check `backend/app/api/v1/router.py` for all registered routes
6. Check `backend/app/core/database.py` for migration logic

---

## Remaining Delivery Plan

### Item 1 — OAuth completion and readiness checks
- Verify the YouTube, TikTok, and Instagram OAuth flows end-to-end with tests around authorize URL generation, callback state handling, and error paths.
- Keep the existing system-account fallback path intact for local development.
- Acceptance: OAuth routes return valid provider URLs, callbacks persist tokens, and invalid state/signature failures are rejected.
- Validation: `python -m pytest -q tests/test_oauth.py tests/test_auth.py`

### Item 2 — Billing and Whop integration hardening
- Cover Whop webhook processing, license validation, and claim flow with tests.
- Confirm billing trial, checkout, portal, cancel, and status behavior stays stable.
- Acceptance: Whop purchase events provision accounts/licenses, billing status is consistent, and invalid requests are rejected safely.
- Validation: `python -m pytest -q tests/test_billing.py tests/test_whop.py`

### Item 3 — Deployment hardening and smoke checks
- Add a lightweight production smoke test that exercises the health endpoint, pricing endpoint, and authenticated status endpoints.
- Keep Docker and CI checks aligned with the runtime behavior verified by the app.
- Acceptance: smoke test passes locally and in CI against the built app.
- Validation: `python -m pytest -q tests/test_deployment_smoke.py tests/test_security_headers.py`

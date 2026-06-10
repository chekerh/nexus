# Nexus-UGC v2: System Architecture

## Overview

Nexus-UGC is an AI-powered UGC production system that analyzes long-form videos,
identifies viral-worthy moments, generates optimized short-form clips, and
publishes to social platforms (TikTok, Instagram, YouTube).

**v2 improvements:** database persistence, multi-tenant user accounts,
background job queue (survives restarts), API versioning, Stripe billing,
Docker deployment.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vanilla JS)                  │
│        Dashboard · Account Manager · Billing              │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI · API v1 (/api/v1/)                 │
│  ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Auth   │ │ Pipeline │ │ Accounts │ │ Billing      │ │
│  │ /auth  │ │ /process │ │/accounts │ │ /billing     │ │
│  └───┬────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
└──────┼───────────┼────────────┼──────────────┼─────────┘
       │           │            │              │
┌──────▼───────────▼────────────▼──────────────▼─────────┐
│                   Services Layer                         │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────────┐    │
│  │  JobQueue    │ │ Usage    │ │ Billing (Stripe)  │    │
│  │  (DB-backed) │ │ Tracking │ │                  │    │
│  └──────┬───────┘ └──────────┘ └──────────────────┘    │
└─────────┼───────────────────────────────────────────────┘
          │ polls
┌─────────▼───────────────────────────────────────────────┐
│              Background Worker Thread                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │ Whisper  │ │ Strategist│ │ FFmpeg   │                │
│  │ .cpp     │ │ (Qwen)   │ │ Editor   │                │
│  └──────────┘ └──────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────┘
```

## Database

- **ORM:** SQLAlchemy 2.0
- **Default:** SQLite (`backend/data/nexus.db`)
- **Production:** PostgreSQL (set `DATABASE_URL` env)
- **Tables:** `users`, `jobs`, `social_accounts`, `account_groups`,
  `group_accounts`, `api_keys`

## Job Queue

Replaces the v1 in-memory `processing_results` dict with a persistent
`jobs` table. A background worker thread polls for `pending` jobs and
executes the pipeline. Survives server restarts.

## API Endpoints

| Group | Endpoints | Auth |
|-------|-----------|------|
| Auth | POST/register, POST/login, GET/me, CRUD /api-keys | None / Bearer |
| Pipeline | POST/process, POST/process-drive, GET/status/{id}, POST/cancel/{id}, GET/jobs | Bearer |
| Accounts | GET/accounts, POST/accounts, DELETE/accounts/{id}, CRUD /account-groups | Bearer |
| Publish | POST/publish, GET/publish/history | Bearer |
| Billing | GET/pricing, POST/billing/checkout, POST/billing/webhook, GET/billing/status | Bearer |

## Subscription Tiers

| Tier | Price | Credits/Month | Max File Size | Max Video |
|------|-------|---------------|---------------|-----------|
| Free | $0 | 5 | 512 MB | 30 min |
| Pro | $29/mo | 50 | 2 GB | 120 min |
| Enterprise | $99/mo | 500 | 4 GB | 600 min |

## Processing Pipeline

1. **Upload** → validate, check quota, enqueue job
2. **Perception** → FFmpeg audio extraction → Whisper.cpp transcription
3. **Analysis** → heuristic scoring + Qwen strategist → 3 viral hooks
4. **Editing** → FFmpeg clip cutting, transitions, zoom, captions (ASS/SRT/VTT), CTA overlay, end screen
5. **Delivery** → clip artifacts in `backend/data/clips/`
6. **Publishing** → YouTube OAuth, Instagram Graph, TikTok Open API (or manual fallback)

## Deployment

- **Local:** `./run_app.sh` — auto-creates venv, starts Ollama, launches Uvicorn
- **Docker:** `docker compose up` — app + optional PostgreSQL
- **Production:** Set `DATABASE_URL`, `JWT_SECRET`, `STRIPE_SECRET_KEY`, `PUBLIC_BASE_URL`

# Nexus-UGC

AI-powered UGC production system. Upload long-form videos → get viral short-form clips with AI captions, ready to publish to TikTok, Instagram, and YouTube.

## Quick Start

```bash
./run_app.sh
```

Opens at [http://localhost:8000](http://localhost:8000). API docs at [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs).

### Prerequisites

- Python 3.12+
- [FFmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- [Ollama](https://ollama.com/) (`brew install ollama`) with `qwen2.5:7b` (or smaller: `qwen2.5:3b`)
- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) binary at `/usr/local/bin/whisper-main` with `ggml-base.en.bin` model

## Architecture

```
Frontend (Vanilla JS)  →  FastAPI v1 (/api/v1/)  →  Worker Thread
                             ├── Auth (JWT)              ├── Whisper.cpp
                             ├── Pipeline                ├── Qwen (Ollama)
                             ├── Accounts/Groups         └── FFmpeg
                             ├── Publish
                             └── Billing (Stripe)
```

## Subscription Tiers

| Tier | Price | Credits/Month |
|------|-------|---------------|
| Free | $0 | 5 |
| Pro | $29/mo | 50 |
| Enterprise | $99/mo | 500 |

Set `STRIPE_SECRET_KEY` in `.env` to enable billing. Without it, checkout returns a mock URL for local development.

## Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

Key settings:
- `DATABASE_URL` — empty for SQLite; set `postgresql://...` for production
- `JWT_SECRET` — change to a random 32+ char string in production
- `STRIPE_SECRET_KEY` — your Stripe secret key (optional for local dev)
- `OLLAMA_MODEL` — Ollama model name (default: `qwen2.5:7b`)
- `WHISPER_BINARY_PATH` — path to your Whisper.cpp binary

## API

All endpoints under `/api/v1/`:

| Endpoint | Description | Auth |
|----------|-------------|------|
| `POST /auth/register` | Create account | None |
| `POST /auth/login` | Sign in | None |
| `GET /auth/me` | Current user | Bearer |
| `POST /process` | Upload video | Bearer* |
| `POST /process-drive` | Import from Drive | Bearer* |
| `GET /status/{id}` | Poll job status | Bearer* |
| `POST /cancel/{id}` | Cancel job | Bearer* |
| `GET /accounts` | List accounts | Bearer |
| `POST /accounts` | Add account | Bearer |
| `GET /account-groups` | List groups | Bearer |
| `POST /account-groups` | Create group | Bearer |
| `POST /publish` | Publish clip | Bearer |
| `GET /pricing` | Pricing info | None |
| `POST /billing/checkout` | Create checkout | Bearer |

_* Pipeline endpoints also work without auth (anonymous free-tier user)._

## Deployment

### Docker

```bash
docker compose up
```

For PostgreSQL, uncomment the `db` service in `docker-compose.yml` and set `DATABASE_URL`.

### Production Checklist

- [ ] Change `JWT_SECRET` to a strong random value
- [ ] Set `DATABASE_URL` to PostgreSQL
- [ ] Set `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` + price IDs
- [ ] Set `PUBLIC_BASE_URL` to your domain
- [ ] Configure OAuth credentials for YouTube/Instagram/TikTok publishing
- [ ] Run behind a reverse proxy (nginx/Caddy) with HTTPS

## Pipeline

1. **Upload** → validate file, check quota, enqueue job
2. **Transcription** → FFmpeg audio extraction → Whisper.cpp
3. **Analysis** → heuristics + Qwen strategist → 3 viral hooks
4. **Editing** → FFmpeg clips with captions, transitions, zoom, CTA, end screen
5. **Publishing** → direct API or manual upload fallback

## License

MIT

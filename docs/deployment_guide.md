# Deployment Guide

## Requirements
- Python 3.14+, FFmpeg, Ollama (for analysis), Whisper.cpp (for transcription)
- PostgreSQL for production, SQLite for local development
- Stripe account for billing and Whop credentials if you use license-based access
- OAuth credentials for YouTube, TikTok, Instagram, Twitter, Facebook, and LinkedIn publishing

## Quick Start (Dev)

```bash
git clone <repo> && cd nexus-ugc
cp .env.example .env        # Edit with your secrets
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run_app.sh                # Starts at http://localhost:8000
```

## Production (systemd)

```ini
# /etc/systemd/system/nexus-ugc.service
[Unit]
Description=Nexus-UGC Backend
After=network.target ollama.service

[Service]
Type=simple
User=nexus
WorkingDirectory=/opt/nexus-ugc
ExecStart=/opt/nexus-ugc/.venv/bin/uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8000 --workers 4
Restart=always
Environment=LOG_FORMAT=structured

[Install]
WantedBy=multi-user.target
```

## Reverse Proxy (Caddy)

```caddyfile
ugc.example.com {
    reverse_proxy 127.0.0.1:8000
    header /api/v1/metrics {
        # Restrict metrics to internal network
        @deny not remote_ip 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
        header @deny "" 403
    }
}
```

## Database
- **Dev**: SQLite (`backend/data/nexus.db`) — zero config
- **Prod**: PostgreSQL for concurrent access. Set `DATABASE_URL=postgresql://user:pass@host/nexus`

## Required Env Vars
| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | JWT signing key (generate a strong random value) |
| `ENCRYPTION_KEY` | Token encryption key (32 bytes, base64) |
| `PUBLIC_BASE_URL` | Public HTTPS URL used for OAuth and public media |
| `STRIPE_SECRET_KEY` | Stripe API secret |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `WHOP_WEBHOOK_SECRET` | Whop webhook signing secret |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | YouTube OAuth app credentials |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | TikTok OAuth app credentials |
| `FACEBOOK_CLIENT_ID` / `FACEBOOK_CLIENT_SECRET` | Meta app credentials for Instagram |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth app credentials |

## Monitoring
- Endpoint: `GET /api/v1/metrics` (Prometheus scrape target)
- Health: `GET /health` for the app and `GET /api/v1/system/check` for runtime checks
- Logs: Structured JSON when `LOG_FORMAT=structured`

## Smoke test

Run a final verification pass before promotion:

```bash
make smoke
```

This exercises the deployment checks used by CI: health, pricing, billing status, and security headers.

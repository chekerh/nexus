# Runbooks — Operations Guide

## Startup & Health

```bash
./run_app.sh        # Full startup: DB init, data dirs, worker, uvicorn
curl http://localhost:8000/health               # App health
curl http://localhost:8000/api/v1/system/check  # Runtime checks (Ollama, FFmpeg, RAM)
curl http://localhost:8000/api/v1/metrics       # Prometheus metrics
make smoke                                      # Local deployment smoke test
```

Startup checks: Ollama running, FFmpeg installed, Whisper binary path valid, DB connected.

## Logs

| Format | Config | Example |
|--------|--------|---------|
| Human-readable | `LOG_FORMAT=human` (default) | `2026-06-26 12:00:00 [INFO] nexus.api: GET /health 200` |
| Structured JSON | `LOG_FORMAT=structured` | `{"timestamp":"...","level":"INFO","logger":"nexus.api","message":"...","request_id":"..."}` |

Structured mode adds `request_id` to every log line via `CorrelationIDMiddleware`.

## Common Procedures

### Reset a stuck job
```sql
UPDATE jobs SET status='pending', progress_percent=0, progress_stage='' WHERE id='<job_id>';
```

### Manual webhook replay
```bash
# Find the event's raw payload from webhook_events table
# Replay via curl
curl -X POST http://localhost:8000/api/v1/billing/webhook \
  -H "Stripe-Signature: ..." \
  -H "Content-Type: application/json" \
  -d '{"id":"evt_...","type":"customer.subscription.updated","data":{"object":{...}}}'
```

For Whop webhooks, send `X-Whop-Signature` and JSON content to `POST /api/v1/whop/webhook`.

### Check CSP violation reports
```sql
-- CSP violations are logged at WARNING level. Grep logs:
grep "CSP violation" /var/log/nexus/app.log
```

### View dead-lettered webhooks
```sql
SELECT * FROM webhook_events WHERE NOT processed OR error != '';
```

### Drain the dead letter queue
```bash
# Identify failed events, fix the underlying issue, then:
UPDATE webhook_events SET processed=TRUE WHERE source='stripe' AND NOT processed;
```

## Backup & Restore

```bash
# SQLite backup
sqlite3 backend/data/nexus.db ".backup 'backups/nexus-$(date +%Y%m%d-%H%M%S).db'"

# Restore
cp backup/nexus-YYYYMMDD-HHMMSS.db backend/data/nexus.db

# PostgreSQL (production)
pg_dump nexus > backup-$(date +%Y%m%d).sql
psql nexus < backup-YYYYMMDD.sql
```

## Upgrading

```bash
git pull
./venv/bin/pip install -r requirements.txt
alembic upgrade head    # Run migrations
./run_app.sh            # Restart
```

## Incident Response

1. **Check health**: `curl localhost:8000/api/v1/system/check`
2. **Check app health**: `curl localhost:8000/health`
3. **Check metrics**: `curl localhost:8000/api/v1/metrics`
4. **Check logs**: Look for `ERROR` or `CRITICAL` with context of `request_id`
5. **Queue stuck?**: Check `queue_depth` metric; reset stuck jobs
6. **Ollama down?**: Restart: `ollama serve`; check `GET /api/v1/system/check` ollama_running
7. **Webhook failing?**: Check `webhook_events` table for `error != ''` and replay with valid signatures

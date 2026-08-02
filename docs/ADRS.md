# ADRs — Architecture Decision Records

## ADR-001: Background Pipeline with SSE Progress
**Status:** Accepted · **Date:** 2026-06-26

### Context
Video processing (transcribe → translate → analyze → cut → score) takes 30s–10min. Users need live progress.

### Decision
- Background thread (`services/job_queue.py`) pulls pending jobs from DB.
- Pipeline stages emit progress via `job.set_progress(stage, percent, message)` which writes to `Job` model.
- SSE endpoint `GET /api/v1/pipeline/stream/{process_id}` pushes real-time events.
- Frontend uses `EventSource` with 5s fallback polling for browsers that drop SSE.

### Consequences
- No Celery/Redis dependency — thread is sufficient for single-node.
- SSE connection survives page nav if user leaves then returns (state in DB).
- Thread can't span multiple workers — use DB-backed rate limiting for multi-worker.

---

## ADR-002: Idempotent Webhooks via DB Table
**Status:** Accepted · **Date:** 2026-06-26

### Context
Stripe and Whop can retry webhook deliveries. Without idempotency, duplicate events double-process (double user creation, double provisioning).

### Decision
- `WebhookEvent` table with `UNIQUE(source, event_id)` constraint.
- Both webhook endpoints check `is_already_processed()` before any business logic.
- `dead_letter()` records failures with error context.

### Consequences
- Idempotency is atomic (DB unique constraint prevents race conditions).
- Dead-letter rows provide audit trail for debugging failed webhooks.
- Stripe: uses `event.id`. Whop: uses `event_data.id`.

---

## ADR-003: CSP Nonce via Request State
**Status:** Accepted · **Date:** 2026-06-26

### Context
Strict CSP requires nonces on inline scripts. The frontend has no build step.

### Decision
- `SecurityHeadersMiddleware` generates `secrets.token_hex(16)` per request.
- Nonce injected into `request.state.csp_nonce`, available in templates.
- The enforced `Content-Security-Policy` includes the nonce plus the current inline-friendly fallback while the HTML frontend is gradually tightened.
- Security headers are set globally and the nonce is available to any server-rendered template or response that emits script tags.

### Consequences
- The app has meaningful CSP protection without breaking the current static frontend.
- The remaining work is to remove inline handlers and move toward stricter nonce-only scripts.
- Any future server-rendered templates should render `nonce="{{ csp_nonce }}"` on `<script>` tags.

---

## ADR-004: Ollama-Powered Feature Brainstorm
**Status:** Accepted · **Date:** 2026-06-26

### Context
Admin dashboard should propose improvements automatically instead of relying on manual feature requests.

### Decision
- `POST /api/v1/suggest-features` reads backend/frontend source files → sends codebase context to local Ollama model → parses newline-delimited JSON suggestions → persists to `feature_suggestions` table.
- Suggestions have status workflow: `proposed → in_review → accepted → implemented`.
- Voting mechanism allows surfacing popular suggestions.

### Consequences
- Suggestions are local-first (no data leaves the machine).
- Quality depends on Ollama model used; `qwen2.5:latest` is default.
- Persistence enables tracking suggestion lifecycle over time.

---

## ADR-005: Prometheus Metrics Without External Exporter
**Status:** Accepted · **Date:** 2026-06-26

### Context
Need observability for HTTP throughput, latency, queue depth, credit consumption.

### Decision
- `prometheus-client` library instruments counters/histograms/gauges in-process.
- `PrometheusMiddleware` records `http_requests_total`, `http_request_duration_seconds` per (method, path, status).
- `GET /api/v1/metrics` exposes `/metrics` endpoint (no auth for scrapers).
- Additional metrics: `pipeline_jobs_total`, `pipeline_job_duration_seconds`, `queue_depth`, `credits_consumed_total`, `active_users`.

### Consequences
- Zero additional infrastructure — single binary scrape endpoint.
- Metrics are ephemeral (reset on restart). For durable metrics, scrape to Prometheus server.
- Metric cardinality could grow with dynamic paths; keep `/api/v1/...` as path label.

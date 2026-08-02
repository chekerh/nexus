# Nexus-UGC Product Roadmap

**Last updated:** 2026-08-02  
**Status:** Active development / backlog tracker

## Current shipped state

- Core pipeline, publishing, billing, OAuth, Whop, CI, and smoke checks are already in place.
- The remaining items in this document are feature backlog and UX polish, not baseline app readiness.

---

## Legend

| Icon | Meaning |
|------|---------|
| ⚠️ | Security / stability critical |
| 🎯 | Competitive parity gap |
| ✨ | New feature / improvement |
| 🧹 | Code quality / tech debt |
| 📐 | Architecture / performance |
| ♿ | Accessibility / UX |

---

## Sprint 1: Safety & Stability

> **Goal:** Eliminate crash-causing bugs, close security holes, make the app safe.  
> **Effort:** 2-3 days  
> **Dependencies:** None (can start immediately)

### 1.1 ⚠️ Fix Python 2 syntax errors

**Files:** `workers/pipeline.py:59`, `workers/video_editor.py:81`

```python
# BROKEN (Python 2 syntax — raises TypeError in Python 3)
except json.JSONDecodeError, TypeError:

# FIXED
except (json.JSONDecodeError, TypeError):
```

**Tasks:**
- [ ] Change `except X, Y:` to `except (X, Y):` in `pipeline.py`
- [ ] Change `except X, Y:` to `except (X, Y):` in `video_editor.py`
- [ ] Verify with `python -c "exec(open('workers/pipeline.py').read())"` no syntax error

**Acceptance criteria:** Server starts without `SyntaxError`. All `except` clauses use Python 3 tuple syntax.

---

### 1.2 ⚠️ Fix SQL injection in analytics.py

**Files:** `backend/app/services/analytics.py:120-200`

`date_trunc` is built with f-strings in raw SQL. Replace raw SQL with SQLAlchemy `func.date_trunc()` or parameterized queries.

**Tasks:**
- [ ] Audit all raw SQL in `analytics.py` for f-string interpolation
- [ ] Replace raw SQL with SQLAlchemy `func.date_trunc()` / `func.date()` equivalents
- [ ] Add integration test that exercises each analytics query

**Acceptance criteria:** No f-string interpolated SQL in `analytics.py`. All queries use SQLAlchemy ORM or parameterized text.

---

### 1.3 ⚠️ Make Stripe webhook verification mandatory

**File:** `backend/app/api/v1/billing.py:104-119`

`STRIPE_WEBHOOK_SECRET` is optional — when unset, unverified payloads are processed. Remove the fallback path.

**Tasks:**
- [ ] Raise `HTTPException(500)` if `STRIPE_WEBHOOK_SECRET` is not configured
- [ ] Remove the `else` branch that parses unsigned payloads
- [ ] Add a startup health check that warns if webhook secret is missing

**Acceptance criteria:** All webhook events are signature-verified. Unverified payloads return 400. Startup logs a warning if secret is missing.

---

### 1.4 ⚠️ Hash password reset and verification tokens

**Files:** `backend/app/api/v1/auth.py:307, 344`

Reset tokens and email verification tokens are stored as plaintext. Hash them with SHA-256 before storing (same pattern as API keys).

**Tasks:**
- [ ] Add `reset_token_hash` column (migration for existing rows)
- [ ] Add `verification_token_hash` column (migration)
- [ ] Add `reset_token_expires_at` column if not present
- [ ] Hash tokens before DB storage in `/forgot-password`
- [ ] Hash tokens before DB storage in `/send-verification`
- [ ] Compare hashed tokens on `/reset-password` and `/verify-email`

**Acceptance criteria:** DB stores `sha256(token)` not raw token. Existing tokens continue to work (migrate on read). Reset tokens expire after 1 hour.

---

### 1.5 ⚠️ Secure token comparison

**File:** `backend/app/middleware.py:150-180`

Ensure all token comparison uses constant-time `hmac.compare_digest()` not `==`.

**Tasks:**
- [ ] Search all `.py` files for `==` comparison against tokens/hashes
- [ ] Replace with `hmac.compare_digest()` where applicable
- [ ] Verify API key auth uses constant-time comparison

**Acceptance criteria:** No timing-attack-vulnerable token comparisons in the codebase.

---

### 1.6 ⚠️ Fix SecureStorage.decrypt silent failure

**File:** `backend/app/core/security.py:64-67`

When decryption fails, the raw ciphertext is returned as valid data. Raise an exception instead.

**Tasks:**
- [ ] Change `except Exception: return data` to `except Exception: raise`
- [ ] Update all callers to handle `DecryptionError`
- [ ] Log decryption failures at `ERROR` level with context

**Acceptance criteria:** Corrupted encrypted data raises `DecryptionError` (or logs + returns `None`) instead of silently returning ciphertext.

---

### 1.7 ⚠️ Add CSP enforcement

**Files:** `backend/app/core/config.py:101`, `backend/app/middleware.py:41-49`

The CSP nonce is only used in report-only mode. Enforcement mode uses `'unsafe-inline'`.

**Tasks:**
- [ ] Use the nonce in enforcement mode (remove `'unsafe-inline'`)
- [ ] Update all inline `<script>` blocks in HTML to use `<script nonce="...">`
- [ ] Remove `CSP_REPORT_ONLY` or make it a config toggle
- [ ] Verify all inline event handlers (`onclick="..."`) are converted to `addEventListener`

**Acceptance criteria:** CSP header uses nonces for inline scripts. `'unsafe-inline'` is removed. Report-Only mode is config-disabled in production.

---

### 1.8 ⚠️ Add rate limiting to auth endpoints

**File:** `backend/app/api/v1/auth.py:301, 339`

`/forgot-password` and `/send-verification` have no rate limiting. Add per-email and per-IP limits.

**Tasks:**
- [ ] Add `@rate_limit("forgot_password", max=3, window=300)` decorator
- [ ] Add `@rate_limit("send_verification", max=3, window=300)` decorator
- [ ] Verify rate limit is enforced with meaningful error message

**Acceptance criteria:** Max 3 forgot-password requests per email per 5 minutes. Max 3 verification emails per email per 5 minutes. Returns 429 with retry-after header.

---

### 1.9 🧹 Add missing DB indexes

**Files:** Models for `Post`, `Job`, `PublishHistory`, `OAuthState`

**Tasks:**
- [ ] Add index on `Post.status`
- [ ] Add index on `Post.platform`
- [ ] Add index on `Job.status`
- [ ] Add index on `PublishHistory.platform`
- [ ] Add index on `OAuthState.created_at`
- [ ] Generate Alembic migration for all indexes

**Acceptance criteria:** `EXPLAIN QUERY PLAN` on common analytics queries shows index usage. Migration is reversible.

---

### 1.10 🧹 Fix `os.chmod` race window

**File:** `backend/app/core/security.py:43-48`

Use `os.open()` with mode parameter instead of separate `write` + `chmod` calls.

**Tasks:**
- [ ] Replace `open()` + `os.chmod()` with `os.open()` including mode
- [ ] Use `umask` approach as alternative
- [ ] Verify file permissions are 0o600 on key file creation

**Acceptance criteria:** Key file is created with correct permissions atomically. No window where file is readable by others.

---

## Sprint 2: UX Quality & Polish

> **Goal:** Fix the most visible user-facing issues — empty states, loading indicators, validation, consistency.  
> **Effort:** 3-4 days  
> **Dependencies:** Sprint 1 (should do releases in order, but technically independent)

### 2.1 ✨ Add empty states to all data pages

**Files:** `accounts.html`, `campaigns.html`, `calendar.html`, `queue.html`, `personas.html`

The `showEmpty(container, icon, title, message)` helper already exists in `ui.js:227` — use it consistently.

**Tasks:**
- [ ] `accounts.html` — empty state when no social accounts linked
- [ ] `campaigns.html` — empty state when no campaigns exist
- [ ] `calendar.html` — empty state when no scheduled posts
- [ ] `queue.html` — empty state when queue is empty
- [ ] `personas.html` — empty state when no personas created
- [ ] Verify each state has: icon, title, description, and CTA button

**Acceptance criteria:** Every list/table view shows a helpful empty state with a clear next action when there's no data.

---

### 2.2 ✨ Add loading states to all async operations

**Files:** All inline `<script>` blocks across HTML pages

**Tasks:**
- [ ] Audit all API calls: every `fetch`/`apiJSON()` must have loading state
- [ ] Audit all form submissions: button must disable + show spinner
- [ ] Ensure `finally` blocks always restore button state
- [ ] Add `showLoading(container)` for page sections that fetch data

**Acceptance criteria:** No button or UI element is clickable during an in-flight request it triggered. Loading spinners show within 200ms of action. Errors restore the UI to its pre-action state.

---

### 2.3 ✨ Add client-side input validation

**Files:** `login.html`, `register` (login.html toggle), `billing.html`, `setup.html`, `reset-password.html`

**Tasks:**
- [ ] `login.html` — email format regex ✅ (done), password min-length, required fields
- [ ] `billing.html` — validate tier selection, confirm before Stripe redirect
- [ ] `setup.html` — validate platform credentials format before API call
- [ ] `reset-password.html` — password match, password strength indicator
- [ ] Create reusable `validateForm(rules)` helper in `ui.js`

**Acceptance criteria:** All forms show field-level validation errors before API calls. Validation is consistent across pages. Errors appear inline, not just in toasts.

---

### 2.4 ✨ Standardize error display

**Files:** All HTML pages

Currently some errors show as toasts, some as field errors, some as inline divs, some as alerts. Pick ONE pattern per context.

**Tasks:**
- [ ] Form submission errors → show inline above the submit button (never toast)
- [ ] API fetch errors → show inline in the relevant content area with retry button
- [ ] Auth/global errors → toast (only for non-field errors)
- [ ] Remove ALL `showToast` calls from form submit handlers
- [ ] Ensure no duplicate error display (same message shown twice)

**Acceptance criteria:** No form submission shows both a toast AND an inline error. Toast is reserved for non-field events (success, global warnings, credit limits).

---

### 2.5 🧹 Remove debug code and stub assets

**Tasks:**
- [ ] Remove all `console.log` statements from JS files
- [ ] Delete `style2.css` and `test_write.css`
- [ ] Remove `<link>` references to deleted CSS from all HTML files
- [ ] Remove `console.warn` for non-actionable failures (silent catch blocks)

**Acceptance criteria:** Zero `console.log` in production JS. No orphan CSS references in HTML. No empty stub assets loaded.

---

### 2.6 ♿ Add `display=swap` to Google Fonts

**File:** All HTML files (17 pages)

```html
<!-- BEFORE -->
<link href="https://fonts.googleapis.com/css2?family=Inter:...&family=JetBrains+Mono:...&display=swap" rel="stylesheet">

<!-- AFTER — add display=swap at the end of the URL before & -->
```

**Tasks:**
- [ ] Update font URL in every HTML `<head>` to include `&display=swap`
- [ ] Verify `font-display: swap` is applied in rendered CSS

**Acceptance criteria:** Text is visible during font load (no FOIT). Pages show text in fallback font until Inter/JetBrains Mono loads.

---

### 2.7 ♿ Convert inline event handlers to `addEventListener`

**Files:** Multiple HTML files use `onclick="fn()"`, `onchange="fn()"` etc.

**Tasks:**
- [ ] Find all `on*` inline event handlers across HTML files
- [ ] Convert each to `element.addEventListener(event, handler)` in the page's `<script>` block
- [ ] Move handlers out of HTML attributes into the DOMContentLoaded setup

**Acceptance criteria:** No inline event handlers in any HTML file. All event binding is done via JS `addEventListener`.

---

### 2.8 ✨ Add `autocomplete` attributes to forms

**Files:** `login.html`, `reset-password.html`, `admin-login.html`

**Tasks:**
- [ ] `login.html`: `autocomplete="email"` on email, `autocomplete="current-password"` on password
- [ ] `reset-password.html`: `autocomplete="email"` on email input
- [ ] `admin-login.html`: same as login.html

**Acceptance criteria:** Password managers suggest credentials on login forms. Autofill works correctly.

---

### 2.9 ✨ Disable particles on auth/static pages

**Files:** All HTML pages that load `particles.js`

`particles.js` runs a full canvas particle system on every page, including login, terms, privacy — pages where users are focused on form input or reading.

**Tasks:**
- [ ] Create a `<body>` class or data-attribute that disables particles
- [ ] Add `data-particles="off"` to login, terms, privacy, reset-password, verify-email pages
- [ ] Check for the attribute in `particles.js` before initializing
- [ ] OR: only load the `<script defer src="particles.js">` tag on pages that need it

**Acceptance criteria:** No particle canvas on login, terms, privacy, reset-password, or verify-email pages. Particles still work on dashboard, brainrot, campaigns, etc.

---

## Sprint 3: PWA & Offline

> **Goal:** Make the PWA installable and useful offline with proper update lifecycle.  
> **Effort:** 1-2 days  
> **Dependencies:** Sprint 2 (clean HTML structure needed for proper caching)

### 3.1 ✨ Add offline fallback page

**Files:** `frontend/offline.html` (new), `frontend/service-worker.js`

**Tasks:**
- [ ] Create `offline.html` — branded offline message with "Check your connection" + "Retry" button
- [ ] Add `offline.html` to service worker pre-cache list
- [ ] Register `fetch` event handler that returns `offline.html` for navigation requests when offline
- [ ] Verify: airplane mode → navigate to any page → see offline.html

**Acceptance criteria:** Navigating to any Nexus-UGC page while offline shows the branded offline page, not the browser's default error page.

---

### 3.2 ✨ Service worker update notification

**File:** `frontend/service-worker.js`, `frontend/ui.js`

**Tasks:**
- [ ] Listen for `updatefound` on SW registration
- [ ] When `statechange` → `installed` and SW is controlling page, show "Update available" toast
- [ ] Add "Refresh" button to toast that calls `skipWaiting()` + reload
- [ ] Add `SKIP_WAITING` message handler in SW

**Acceptance criteria:** When a new service worker is detected, user sees a toast within 10 seconds. Clicking "Update" refreshes the page with the new version.

---

### 3.3 ✨ Clean old caches on activate

**File:** `frontend/service-worker.js`

**Tasks:**
- [ ] Define `CACHE_VERSION` at top of SW
- [ ] In `activate` event, iterate all caches and delete those not matching `CACHE_VERSION`
- [ ] Verify: cache name changes → old cache is purged on next activate

**Acceptance criteria:** Only current-version caches exist after SW activate. Old caches are cleaned up to prevent unbounded storage growth.

---

### 3.4 ✨ Enrich manifest.json

**File:** `frontend/manifest.json`

**Tasks:**
- [ ] Add `description: "AI-powered viral video generator — scripts, captions, and publish in one click"`
- [ ] Add `categories: ["video", "productivity", "social"]`
- [ ] Add `shortcuts` for key pages: [Create, Queue, Billing]
- [ ] Add PNG fallback icons for Safari/Edge (192px, 512px)

**Acceptance criteria:** Lighthouse PWA checklist passes for "installable" criteria. Manifest includes description, categories, shortcuts, and PNG icons.

---

### 3.5 ✨ Add `<meta name="description">` to all pages

**Files:** All 16 HTML pages (besides index.html which already has one)

**Tasks:**
- [ ] Add unique, descriptive `<meta name="description">` to each page
- [ ] Each description should be 120-160 characters, include target keywords
- [ ] Add OG meta tags (`og:title`, `og:description`, `og:type`) to each page

**Acceptance criteria:** Every HTML page has a unique meta description. OG tags are present on all pages. Lighthouse SEO audit passes.

---

## Sprint 4: Competitive Parity — Content Features

> **Goal:** Close the gap with competitors on core content creation features.  
> **Effort:** 1-2 weeks  
> **Dependencies:** Sprint 3 (clean PWA baseline)

### 4.1 🎯 Social media scheduling

**Files:** `frontend/calendar.html`, `backend/app/services/scheduler.py` (new)

Integrate the calendar with a scheduling engine that auto-publishes at optimal times.

**Tasks:**
- [ ] `backend`: Create `SchedulerService` that picks pending posts and publishes at `scheduled_at`
- [ ] `backend`: Add `scheduled_at` column to `Post` model
- [ ] `backend`: Add `POST /posts/schedule` endpoint
- [ ] `backend`: Background worker polls every 5 minutes for due posts
- [ ] `frontend`: Calendar view shows scheduled posts with publish status
- [ ] `frontend`: Drag-to-schedule from queue to calendar date
- [ ] `frontend`: Schedule modal with time picker + platform selector
- [ ] `frontend`: Recurring schedule option ("every Tuesday at 10am")

**Acceptance criteria:** User can schedule a post for a future time. Post publishes automatically. Calendar shows scheduled, published, and failed posts.

---

### 4.2 🎯 Caption style library (5 → 20+ styles)

**Files:** `frontend/brainrot.html`, `backend/app/services/caption_style.py`

Submagic has 35+ styles. Nexus-UGC has 3 (brain_rot, hype, clean).

**Tasks:**
- [ ] Research top caption styles from Submagic, CapCut, OpusClip
- [ ] Define 15 new styles: `neon`, `retro`, `minimal_white`, `gradient`, `outline`, `typewriter`, `bounce`, `glitch`, `highlight`, `quote`, `split`, `karaoke`, `emoji_grid`, `ticker`, `cinematic`
- [ ] Add `CaptionStyle` model with font, color, animation, position, timing
- [ ] Store styles as JSON presets in `config/caption_styles.json`
- [ ] Frontend: style selector with visual preview (thumbnail of style)
- [ ] Frontend: style preview updates in real-time on the video preview
- [ ] Frontend: custom style builder (font, color, animation, position)

**Acceptance criteria:** 20+ caption styles available. Each style has a unique visual preview. Users can preview a style before generating. Custom styles can be saved as presets.

---

### 4.3 🎯 AI B-roll generation

**Files:** `backend/app/services/broll.py` (new)

Insert relevant stock footage between talking-head segments.

**Tasks:**
- [ ] Integrate with Pexels/Pixabay free stock API for background footage
- [ ] AI analyzes script keywords to pick relevant B-roll
- [ ] Insert B-roll at detected transition points (scene changes in audio)
- [ ] Configurable B-roll frequency: "none", "low", "medium", "high"
- [ ] Frontend: B-roll toggle in generator form
- [ ] Frontend: Replace individual B-roll clips manually

**Acceptance criteria:** Generated videos include relevant B-roll based on script keywords. B-roll transitions are smooth. Users can control frequency. Users can replace individual clips.

---

### 4.4 🎯 Multi-speaker detection

**Files:** `backend/app/services/speaker_diarization.py` (new)

Detect multiple speakers and enable split-screen mode for podcasts/interviews.

**Tasks:**
- [ ] Integrate speaker diarization (pyannote-audio or WhisperX)
- [ ] Detect speaker segments during transcription
- [ ] Split-screen video output: one speaker per panel
- [ ] Auto-switch active speaker panel based on who's talking
- [ ] Frontend: toggle between "single speaker" and "multi-speaker" mode
- [ ] Frontend: manual speaker label editing

**Acceptance criteria:** Multiple speakers are detected and labeled. Video output shows active speaker highlighted. Split-screen works for 2+ speakers.

---

### 4.5 🎯 Multi-language dubbing

**Files:** `backend/app/services/dubbing.py` (new)

AI voiceover in multiple languages (matching Klap's 29-language support).

**Tasks:**
- [ ] Integrate with local TTS (Ollama + Piper, or Coqui TTS)
- [ ] Support 10 target languages: English, Spanish, French, German, Portuguese, Japanese, Korean, Hindi, Arabic, Chinese
- [ ] Preserve original timing — dubbed audio matches video length
- [ ] Frontend: language selector on generator form
- [ ] Frontend: side-by-side preview (original vs dubbed)
- [ ] Keep original audio as separate track for manual mix

**Acceptance criteria:** Generated video can be dubbed into any supported language. Audio sync is maintained. Original audio is preserved as optional overlay track.

---

### 4.6 🎯 Template system

**Files:** `frontend/templates.html` (new), `backend/app/models/template.py` (new)

Pre-saved presets combining niche, style, platform, and duration.

**Tasks:**
- [ ] Create `Template` model with: niche, caption_style, platform, duration, b-roll_mode, language
- [ ] CRUD API: `GET /templates`, `POST /templates`, `PUT /templates/{id}`, `DELETE /templates/{id}`
- [ ] Frontend: template library page with visual cards
- [ ] Frontend: "Save as Template" button on generator form
- [ ] Frontend: apply template pre-fills all generator fields
- [ ] Pre-seed 10 starter templates: "Gaming Hook", "Motivation Speech", "Fact Bomb", etc.

**Acceptance criteria:** Users can save any generation configuration as a template. Templates appear on a library page. One click applies a template. Starter templates are available out of the box.

---

## Sprint 5: Competitive Parity — Platform & Distribution

> **Goal:** Expand from single-user web app to platform with team support, public API, mobile presence.  
> **Effort:** 2-3 weeks  
> **Dependencies:** Sprint 4

### 5.1 🎯 Team accounts / shared workspaces

**Files:** `backend/app/models/workspace.py` (new), `backend/app/api/v1/workspaces.py` (new)

**Tasks:**
- [ ] `backend`: Create `Workspace` model with `owner_id`, `name`, `member_ids`
- [ ] `backend`: Create `WorkspaceMember` join table with role (admin/member/viewer)
- [ ] `backend`: CRUD API for workspaces
- [ ] `backend`: All resources (posts, accounts, templates) scoped to workspace + user
- [ ] `backend`: Billing per-workspace (all members share plan credits)
- [ ] `frontend`: Workspace switcher in sidebar
- [ ] `frontend`: Member management (invite, role, remove)
- [ ] `frontend`: Activity feed per workspace

**Acceptance criteria:** Multiple users can be added to a workspace. All members share the plan's credit pool. Workspace admin can manage members and roles. Resources are isolated between workspaces.

---

### 5.2 🎯 Public API

**Files:** `backend/app/api/v2/` (new), `docs/api.md` (new)

**Tasks:**
- [ ] Design REST API surface: `POST /v2/generate`, `GET /v2/posts`, `GET /v2/credits`, webhooks for completion
- [ ] Implement API key auth (existing but extend)
- [ ] Rate limit per API key (not just per IP)
- [ ] Swagger/OpenAPI docs exposed at `/docs/v2`
- [ ] Webhook notification on pipeline completion (`POST user's webhook URL`)
- [ ] SDK examples: curl, Python, JavaScript
- [ ] API docs page on the marketing site
- [ ] Usage tracking per API key in billing

**Acceptance criteria:** External users can generate videos via API. Rate limits apply per key. Pipeline completion sends webhook. Docs are live at `/docs/v2`. SDK examples in 3 languages.

---

### 5.3 🎯 Mobile app (React Native)

**Files:** `mobile/` (new directory)

**Tasks:**
- [ ] Scaffold React Native project with Expo
- [ ] Implement auth flow (QR code scan from web → mobile login)
- [ ] Core screens: Dashboard, Create (niche + style + platform), Queue, Calendar, Settings
- [ ] Camera/mic: record video directly in-app
- [ ] Push notifications: "Clip is ready to publish"
- [ ] Offline queue: draft videos sync when online
- [ ] Share sheet: "Send to Nexus-UGC" from gallery

**Acceptance criteria:** Users can log in, create a short, and publish from mobile. Push notifications alert on completion. Videos can be recorded in-app or imported from gallery.

---

### 5.4 🎯 Virality scoring v2

**Files:** `backend/app/services/scoring.py`

Current scoring is heuristic (keyword density, speech rate, scene boundaries). Upgrade to trained model.

**Tasks:**
- [ ] Collect engagement data from published clips (views, likes, shares, retention)
- [ ] Train a lightweight model (XGBoost or small NN) on engagement signals
- [ ] Features: hook type, pacing, caption style, platform, niche, time-of-day, audio energy
- [ ] Replace heuristics with model inference
- [ ] A/B test: compare v2 scores vs v1 scores on actual published content
- [ ] Frontend: show virality score breakdown (hook, pacing, style, timing)

**Acceptance criteria:** Virality score correlates with actual engagement. Score is broken down into 4 sub-scores. A/B test shows v2 outperforms v1.

---

### 5.5 🎯 Eye contact correction

**Files:** `backend/app/services/eye_contact.py` (new)

Uses AI to redirect gaze toward camera for talking-head clips.

**Tasks:**
- [ ] Integrate with open-source eye contact model (e.g., GazeGAN or similar)
- [ ] Only apply when face is detected and gaze deviates > 15°
- [ ] Configurable intensity: "off", "subtle", "natural", "strong"
- [ ] Frontend: toggle in generator form
- [ ] Process as post-render step (apply after video is rendered)

**Acceptance criteria:** Off-angle talking-head clips are corrected to look at camera. Correction is subtle enough to appear natural. Processing adds < 30s to pipeline.

---

## Sprint 6: Performance & Architecture

> **Goal:** Production-ready performance, observability, and scalability.  
> **Effort:** 1-2 weeks  
> **Dependencies:** Sprint 5 (API surface defined before optimizing)

### 6.1 📐 Split monolithic style.css

**Tasks:**
- [ ] Extract critical above-fold CSS (~10KB) and inline in `<head>`
- [ ] Split remaining CSS by route: `auth.css` (login, register), `app.css` (sidebar apps), `marketing.css` (index.html)
- [ ] Load non-critical CSS with `media="print" onload="this.media='all'"`
- [ ] Verify: first paint shows styled content without waiting for full CSS

**Acceptance criteria:** Time to First Painted Content (FPC) improves by loading critical CSS inline. Non-critical CSS loads asynchronously. No flash of unstyled content (FOUC).

---

### 6.2 📐 Route-scoped JS loading

**Tasks:**
- [ ] Audit which pages actually need each JS file
- [ ] `campaigns.js` → only on campaigns.html
- [ ] `choko.js` + `choko-knowledge.js` → only on pages where the mascot is shown (not login, terms, privacy)
- [ ] `particles.js` → only on pages where particle canvas is active (see 2.9)
- [ ] Load page-specific scripts with conditional `<script>` tags or `document.write` fallback

**Acceptance criteria:** Each HTML page loads only the JS files it needs. Total JS per page is reduced by 40%+ on auth pages.

---

### 6.3 📐 Replace DB-backed rate limiter

**File:** `backend/app/middleware.py:166-207`

Current rate limiter creates/deletes a row per request. Replace with sliding window counter.

**Tasks:**
- [ ] Implement sliding window counter using a single row update per IP (increment + expiry)
- [ ] Add index on `rate_limit_entries.ip_address + rate_limit_entries.endpoint`
- [ ] Alternative: use Redis-backed rate limiter as optional upgrade path
- [ ] Clean up expired entries with periodic batch delete

**Acceptance criteria:** Rate limiter uses 1 DB write per request (not 2). Expired entries are cleaned up periodically. Redis adapter is available as drop-in replacement.

---

### 6.4 📐 Background task lifecycle management

**File:** `backend/app/main.py:159-161, 304`

Background tasks (OAuth cleanup, trial expiry, dunning) are not cancelled on shutdown.

**Tasks:**
- [ ] Track all background asyncio tasks on startup
- [ ] Cancel all tracked tasks on shutdown with timeout
- [ ] Add graceful shutdown logging (which tasks were cancelled)
- [ ] Verify: `SIGTERM` → tasks cancelled within 30s → process exits cleanly

**Acceptance criteria:** Server shutdown cancels all background tasks. Each task gets a 5-second grace period. Logs show clean shutdown sequence.

---

### 6.5 📐 Graceful FFmpeg missing handling

**File:** `backend/app/core/config.py` + `workers/video_editor.py`

**Tasks:**
- [ ] Check `ffmpeg` availability at startup (run `ffmpeg -version`)
- [ ] Add `settings.FFMPEG_AVAILABLE` flag
- [ ] Return meaningful error to user when FFmpeg is not installed
- [ ] Add health check endpoint at `/health` that reports FFmpeg status

**Acceptance criteria:** If FFmpeg is not installed, the API returns a clear error message (not `FileNotFoundError`). Health endpoint reports FFmpeg status.

---

### 6.6 📐 Observability: structured logging + metrics

**Tasks:**
- [ ] Replace ad-hoc `logger.info/warning/error` with structured JSON logging
- [ ] Add request ID middleware (correlation ID per request)
- [ ] Export Prometheus metrics: request count, latency P50/P95/P99, error rate, pipeline duration
- [ ] Add health check endpoint (`/health`) including DB connection, FFmpeg, Ollama status
- [ ] Add readiness probe (is the app accepting traffic?) vs liveness probe (is the app running?)

**Acceptance criteria:** All logs are structured JSON with correlation IDs. Prometheus metrics are available at `/metrics`. Health endpoint is suitable for K8s probes.

---

### 6.7 🧹 Fix circular import / architecture violations

**Tasks:**
- [ ] Move `_get_account_for_platform` from `api/v1/publish.py` to `services/publisher.py`
- [ ] Move OAuth business logic from `api/v1/oauth.py` (694 lines) to `services/oauth.py`
- [ ] Remove all `api/v1/` imports from `services/` modules
- [ ] Verify with `ruff check --select=I` that no import cycle exists

**Acceptance criteria:** Service layer never imports from API layer. OAuth route is a thin wrapper around service methods. No circular imports.

---

## Appendix A: Sprint Dependency Graph

```
Sprint 1 (Safety)
  │
  ▼
Sprint 2 (UX Polish)
  │
  ▼
Sprint 3 (PWA / Offline)
  │
  ▼
Sprint 4 (Content Features)
  │
  ▼
Sprint 5 (Platform & Distribution)
  │
  ▼
Sprint 6 (Performance & Architecture)
```

**Notes:**
- Sprints 1-3 are independent of 4-6 and can be done first for immediate value
- Sprint 3 (PWA) is a prerequisite for mobile app (Sprint 5.3)
- Sprint 4 (Content) should precede Sprint 5.4 (Virality Scoring v2) because v2 needs v1's output for training data
- Sprint 6 can run in parallel with 4-5 if team permits

## Appendix B: File Change Impact Summary

| Sprint | Backend files | Frontend files | New files |
|--------|--------------|----------------|-----------|
| 1 | 8 | 0 | 0 |
| 2 | 0 | 17 | 0 |
| 3 | 0 | 18 | 2 |
| 4 | 6 | 4 | 6 |
| 5 | 6 | 5 | 12 |
| 6 | 5 | 0 | 0 |

## Appendix C: Effort Estimates (Person-Days)

| Sprint | Backend | Frontend | Total |
|--------|---------|----------|-------|
| 1 | 2 | 0 | 2 |
| 2 | 0 | 3 | 3 |
| 3 | 0 | 2 | 2 |
| 4 | 5 | 4 | 9 |
| 5 | 6 | 8 | 14 |
| 6 | 5 | 2 | 7 |
| **Total** | **18** | **19** | **37** |

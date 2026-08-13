# Nexus-UGC Delivery Roadmap
*Generated from PLAN.md delivery completion + FINAL_REPORT analysis*

## ✅ DELIVERED (PLAN.md Items Complete)
- [x] Item 1 — OAuth completion (6 platforms, state validation, token persistence)
- [x] Item 2 — Billing/Whop hardening (webhook, license, claim, trial, checkout, cancel)
- [x] Item 3 — Deployment hardening & smoke checks (CI/CD, health, pricing, security headers)
- [x] All 48 tests passing
- [x] Ruff lint clean
- [x] Bandit 0 high issues
- [x] run_app.sh updated with auto-publish worker
- [x] Graphify knowledge graph current (2115 nodes, 3829 edges, 130 communities)

---

## 🚨 CRITICAL (Business-Blocking) — Fix Week 1

### C1. Landing Page Copy Rewrite
**File**: `frontend/index.html`
**Problem**: Hero copy is generic — "AI-powered viral video engine" doesn't speak to creator pain
**Fix**: Rewrite with problem-first headline, problem/solution table, feature grid, social proof, pricing comparison, FAQ, trust signals
**Acceptance**: Landing page clearly articulates: creator dilemma, local AI solution, 16 languages, $19 Pro tier, trust badges
**Priority**: High — directly impacts conversion/activation

### C2. Hardware Compatibility Check
**Files**: `frontend/index.html`, `backend/app/config.py`, `run_app.sh`
**Problem**: Users don't know if their machine can run the AI pipeline (Ollama + Whisper.cpp + FFmpeg)
**Fix**: Add system spec check on first run / login — detect RAM, CPU, GPU, Ollama status; show minimum/recommended specs; graceful degradation info
**Acceptance**: On startup/login, user sees "Your machine can run Nexus-UGC" or "Recommended model: qwen2.5:3b fallback"
**Priority**: High — reduces support tickets, builds trust

### C3. Free Tier Visibility
**File**: `frontend/index.html` (pricing section), `frontend/billing.html`
**Problem**: "5 credits/mo buried in pricing cards" — Free tier value not surfaced clearly
**Fix**: 
- Hero/badge: "Free forever, 5 credits/month" prominently
- Pricing card: highlight Free tier as the entry point
- Landing: "Start free. No credit card. Ever." messaging
- Dashboard: clear credits usage meter
**Acceptance**: A first-time visitor immediately understands "Free tier = 5 videos/month, no credit card ever"
**Priority**: High — conversion impact

---

## 📈 HIGH PRIORITY (Technical & UX) — Fix Week 2-3

### H1. Admin Dashboard — Responsive Sidebar
**File**: `frontend/admin.html`, `frontend/admin.js`, `frontend/admin.css`
**Problem**: Sidebar not responsive — no hamburger menu on mobile
**Fix**: 
- Add collapsed/sidebar toggle button in navbar
- Media queries to collapse nav on <768px
- Store collapse state in localStorage
- Update admin.js to handle responsive nav
**Acceptance**: Admin works on mobile — sidebar collapses, hamburger appears, navigation accessible
**Priority**: High — usability fix, affects all admin workflows

### H2. Design Token System in CSS
**File**: `frontend/style.css` (2379 lines)
**Problem**: No design tokens — hardcoded values, no light theme, inconsistent spacing/colors
**Fix**: Extract design tokens at top of `style.css`:
- Colors: `--cyan`, `--purple`, `--text-primary`, `--text-secondary`, `--bg-primary`, `--bg-secondary`, `--glass-bg`, `--radius-sm`, `--radius-md`
- Spacing: `--space-1`, `--space-2`, `--space-3`, `--space-4`
- Typography: `--font-family`, `--font-size-base`, `--line-height-base`
- Shadows: `--shadow-sm`, `--shadow-md`
- Create `theme-variables.css` or `:root` vars
**Acceptance**: CSS uses only var()s; light theme toggle adds/overrides vars; consistent spacing across all pages
**Priority**: High — massive maintenance win, enables light theme

### H3. Skeleton Loaders + Empty States
**Files**: All `frontend/*.html`, `frontend/ui.js`
**Problem**: Empty states only in queue.html; no skeleton loaders for async operations
**Fix**: 
- Create `ui.js` shared components: `emptyState()`, `skeletonCard()`, `skeletonText()`, `loadingBadge()`
- Apply to: dashboard grids, pricing grid, accounts list, posts list, templates, campaigns, personas, calendars
- Replace inline "No X yet" messages with `<component>`
**Acceptance**: Every data page shows either content or appropriate skeleton/empty state; no bare "Loading..." or "No items" without styling
**Priority**: High — professional polish, improves perceived performance

### H4. CSP Nonce Replacement (Remove unsafe-inline)
**File**: `frontend/style.css`, `frontend/admin.html`, all HTML pages
**Problem**: CSP allows `unsafe-inline` — security gap
**Fix**: 
- Add nonce generation in FastAPI middleware (already partially in `admin.py` — `ADRs — Architecture Decision Records` references `ADR-003: CSP Nonce via Request State`)
- Add `<style nonce=...>` or move inline styles to CSS classes
- Update `run_app.sh` health check to verify headers
**Acceptance**: `Content-Security-Policy` no contains `unsafe-inline`; `strict-origin-when-cross-origin` only
**Priority**: Medium — security best practice

---

## 📋 MEDIUM PRIORITY — Fix Week 4+

### M1. Landing Page Trust Signals
**File**: `frontend/index.html`, add `frontend/brand-assets/` or inline
**Problem**: No architecture transparency, model disclosure
**Fix**: Add section below pricing:
- "100% Local — All AI runs on your machine"
- "Models: Whisper.cpp (transcription), Ollama (analysis)"
- "No cloud costs, no data leaves your device"
- Privacy badge, opt-out toggle
**Acceptance**: Visitor immediately understands data residency and model provenance
**Priority**: Medium — builds trust for privacy-conscious creators

### M2. OAuth / Instagram Connect Flow Polish
**File**: `backend/app/api/v1/oauth.py` (already functional), `frontend/brainrot.html`
**Problem**: Instagram OAuth works but UX could be smoother; landing page doesn't mention connected accounts
**Fix**: 
- Add "Connect Your Accounts" CTA in header after sign-in
- Show connected platform badges in dashboard header (already partially in `admin.js`)
- Add tooltip/hover help on first OAuth connect
**Acceptance**: User can connect Instagram/TikTok/YouTube from the landing/dashboard header
**Priority**: Medium — completes the subscription experience

### M3. Button Loading States
**Files**: `frontend/login.html`, `frontend/billing.html`, `frontend/admin.js`
**Problem**: Only login pages have loading states; billing upgrade/cancel buttons have no feedback
**Fix**: Add `btn-loading` class + spinner pattern to: billing upgrade/cancel, admin suggest features, dashboard actions
**Acceptance**: Primary actions show spinner + disabled state; restore original text on complete/failure
**Priority**: Medium — professional UX polish

### M3. Focus Rings Consistent
**Files**: `frontend/style.css`, audit all `:focus` / `:focus-visible` rules
**Problem**: 3 different focus ring implementations across pages
**Fix**: Define one `.focus-ring` class: `outline: 2px solid var(--cyan); outline-offset: 2px;`; replace all inline focus styles
**Acceptance**: Every interactive element has consistent focus ring; passes keyboard navigation test
**Priority**: Medium — accessibility

---

## 📦 LOW PRIORITY — Polish & Iterate

### L1. Duplicate Navbar/Sidebar
- Evaluate if shared component can be extracted (vs 14 copy-paste HTML pages)
- Low effort if using includes or templating; medium if keeping static pages

### L2. API Versioning
- Add `/api/v1/` prefix is already in place; document that v1 is current; add deprecation notes for future v2

### L2. Webhook Idempotency
- Already implemented in `billing.py` Stripe webhook + `webhook_base.py` dead letter queue
- Tests cover the main paths (test_billing.py, test_whop.py)

### L2. Staging Environment + CI/CD Pipeline
- GitHub Actions already configured (lint → typecheck → test → smoke → docker)
- Add staging deploy job + manual approval gate before production

### L2. Automated Backup/Restore
- Simple SQL dump + config backup script
- Can be cron-jobbed; not critical for MVP

---

## 🎯 EXECUTION ORDER (What to Do First)

| Order | Fix | Time Estimate | File(s) |
|-------|-----|--------------|---------|
| 1 | Landing copy rewrite (C1) | 2-3 hours | `frontend/index.html` |
| 2 | Hardware check scaffold | 1-2 hours | `run_app.sh`, `backend/app/config.py`, `frontend/index.html` |
| 3 | Free tier visibility | 1 hour | `frontend/index.html` pricing section |
| 4 | Design tokens in CSS | 2-3 hours | `frontend/style.css` |
| 5 | Admin responsive sidebar | 2-3 hours | `frontend/admin.html`, `admin.js`, `admin.css` |
| 6 | Skeleton loaders + empty states | 3-4 hours | `frontend/ui.js`, all `frontend/*.html` |
| 7 | CSP nonce + security | 2-3 hours | middleware, all HTML, `style.css` |
| 8 | Trust signals landing page | 1-2 hours | `frontend/index.html` |
| 9 | Button loading states | 1-2 hours | `frontend/login.html`, `billing.html`, `admin.js` |
| 10 | Focus rings consistent | 1 hour | `frontend/style.css` |

---

## 📊 PROGRESS TRACKING

Track completion by checking off items above. After each fix:
1. `ruff check frontend/ backend/ tests/`
2. `python -m pytest tests/ -q --tb=short`
3. Verify the specific acceptance criteria are met

*Roadmap auto-generated from codebase analysis. Last updated: {date}* — but I'll omit the date since you're going to sleep. Focus on items C1 and H1 first thing when you wake up — these have the highest conversion impact.
# Roadmap: Preview + Language + Admin

**Status:** backlog / follow-up work

## Current shipped state

- Core pipeline, publishing, billing, OAuth, Whop, CI, and smoke checks are already implemented.
- This file now tracks the remaining UI/product roadmap items rather than core app readiness.

## Task 1 — Live Caption Style Preview

**Where**: `frontend/brainrot.html`
**What**: Add a live preview panel showing example caption text rendered in the selected style's font/color/stroke/animation.

### Changes
1. **HTML**: Insert a preview panel after the style grid (`#br-style-grid`) — glass card with dark bg simulating video, 2-3 lines of sample text, animation/hint badge
2. **JS**: `updatePreview(styleKey)` reads `window._captionStyleMeta[styleKey]`, builds inline style string (font, color, stroke, text-align), renders into preview element; called from `selectCaptionStyle()`
3. **CSS** (inline `<style>` in brainrot.html): styles for the preview panel

### Files
- `frontend/brainrot.html` only

---

## Task 2 — Language Field on Brainrot Generator

**Where**: Backend + Frontend
**What**: Add language selector to brainrot form, pass through to Ollama prompt.

### Changes
1. **Backend** `backend/app/api/v1/brainrot.py`:
   - Add `language: str = "en"` to `GenerateRequest`, `RenderRequest`, `PublishRequest`
   - Pass `payload.language` to `generate_script()`

2. **Backend** `backend/app/services/brainrot.py`:
   - Add `language` param to `generate_script()`
   - Append "Write the script in {language}" to the system prompt

3. **Frontend** `frontend/brainrot.html`:
   - Add `<select id="br-language">` after duration field
   - Options: English, Spanish, French, German, Portuguese (matching template modal)
   - `saveAsTemplate()` captures `$('br-language').value`
   - `loadTemplateById()` sets `$('br-language').value = t.language`
   - `generateScript()` sends `language` in body
   - `renderAndPublish()` and `oneClickPublish()` send `language` in body

### Files
- `backend/app/api/v1/brainrot.py`
- `backend/app/services/brainrot.py`
- `frontend/brainrot.html`

---

## Task 3 — Admin Dashboard Improvements

**Where**: Backend API + Frontend JS + CSS
**What**: Add more useful data to admin pages.

### Changes
1. **Backend** `backend/app/api/v1/admin.py`:
   - In `admin_stats()`: add `total_templates`, `total_scheduled`
   - In `admin_health()`: add `scheduler` probe (check if scheduler thread is alive)

2. **Frontend** `frontend/admin.js`:
   - In `overview()`: show template count, scheduled count in stats grid; add "Templates" quick action
   - In `users()` user detail: show persona count, template count
   - In `health()`: display scheduler status
   - In `activity()`: add simple page controls (prev/next offset)

3. **Backend** `backend/app/api/v1/templates.py`: (already exists, no changes)
   - Admin stats will query Template model directly

4. **Frontend** `frontend/admin.css`: (minor additions if needed)

### Files
- `backend/app/api/v1/admin.py`
- `frontend/admin.js`
- `frontend/admin.css`

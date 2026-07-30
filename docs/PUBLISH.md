# Publishing guide — YouTube, TikTok, Instagram (dev + real)

This document explains how to configure and test publishing from Nexus-UGC locally.

Prerequisites
- Run the app locally: `./run_app.sh` (started uvicorn at http://127.0.0.1:8000).
- Install `ngrok` if you need an externally reachable `PUBLIC_BASE_URL` for OAuth callbacks.
- Make sure `ffmpeg` is installed for video processing.

Key environment variables
- `PUBLIC_BASE_URL` — public URL for callbacks (e.g. https://abc.ngrok.io). Optional for local manual flows.
- `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` — Google OAuth app for YouTube uploads.
- `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` — TikTok Open Platform app credentials.
- `SYSTEM_YOUTUBE_REFRESH_TOKEN` — (optional) system-level refresh token to enable direct posting without OAuth per-user.
- `SYSTEM_TIKTOK_*`, `SYSTEM_INSTAGRAM_*` — system-level tokens the app can use for automated posting.

Where the app exposes flows
- OAuth: `/api/v1/oauth/*` — endpoints to start OAuth flows for YouTube, TikTok, Instagram.
  - Example: `GET /api/v1/oauth/youtube/authorize` opens the Google OAuth flow.
- Publish API: `POST /api/v1/publish` — publish a clip to a platform. See backend API for JSON schema.

Quick dev-mode test (no API keys)
1. Start the app locally: `./run_app.sh`.
2. Create a clip via the frontend or upload a video to `backend/data/uploads`.
3. Use the publish API to exercise the publish path with dev fallback (mock/manual instructions are returned when platform keys are missing):

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/publish" \
  -H "Content-Type: application/json" \
  -d '{"platform":"youtube","title":"Test","description":"dev publish","video_path":"/path/to/video.mp4"}'
```

Using system tokens for immediate posting
- If you have valid tokens and want to bypass OAuth per-user flows, set the `SYSTEM_YOUTUBE_REFRESH_TOKEN` and `SYSTEM_YOUTUBE_CHANNEL_ID` in your `.env` and restart the app. The auto-publish worker and publish endpoints will use these tokens when available.

Testing with real accounts (high level)
1. Create an OAuth app for the platform (Google Cloud Console for YouTube, TikTok Open Platform, Facebook/Meta for Instagram).
2. Set `PUBLIC_BASE_URL` to your ngrok URL and configure the OAuth redirect URIs in the provider console:
   - YouTube redirect: `https://<PUBLIC_BASE_URL>/api/v1/oauth/youtube/callback`
3. Configure `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, etc., in `.env` and restart the app.
4. In the UI, connect the account via the `Connect` / `Setup` pages or call the OAuth endpoints directly.

Safety and notes
- The app will not post to production accounts without valid tokens; you must manually provide API keys or approve OAuth flows.
- Never commit `.env` or secrets to source control.
- For CI, use encrypted secrets or a secrets manager.

Next steps (suggested)
- Add a dev-mode publish mock that records publish attempts to `backend/data/publish_history.json` and returns a deterministic published response for testing.
- Add an integration test that uploads a small sample clip to `backend/data/uploads` and posts to `/api/v1/publish` using the mock.

If you want, I can implement the dev-mode mock and an integration test next.

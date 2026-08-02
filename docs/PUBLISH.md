# Publishing Guide

How publishing works today in Nexus-UGC:

- The UI sends `POST /api/v1/publish` with `platform`, `account_id`, `clip_filename`, `title`, and `description`.
- The backend looks up the connected `SocialAccount`, validates the clip exists under `UPLOAD_DIR/clips`, and then tries the platform-specific publisher.
- If `DEV_PUBLISH_MOCK=true`, the app returns a deterministic published result and writes a log entry for local and CI testing.
- If platform credentials are missing or the provider rejects the request, the API returns `manual_required` with the platform upload URL.

## Local setup

Prerequisites:

- Run the app with `./run_app.sh`.
- Install `ffmpeg`.
- Use `PUBLIC_BASE_URL` only when you need OAuth callbacks or external platform fetches.

Key environment variables:

- `JWT_SECRET` and `ENCRYPTION_KEY` for auth and token storage.
- `PUBLIC_BASE_URL` for OAuth redirects and public media URLs.
- `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` for YouTube OAuth.
- `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` for TikTok OAuth.
- `FACEBOOK_CLIENT_ID` / `FACEBOOK_CLIENT_SECRET` for Instagram OAuth.
- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` for LinkedIn OAuth.
- `SYSTEM_ACCOUNTS_ENABLED=true` plus `SYSTEM_*` token variables if you want startup to auto-provision system accounts.

## OAuth flows

- YouTube: `GET /api/v1/oauth/youtube/authorize` and `/callback`
- TikTok: `GET /api/v1/oauth/tiktok/authorize` and `/callback`
- Instagram: `GET /api/v1/oauth/instagram/authorize` and `/callback`
- Twitter, Facebook, and LinkedIn are also wired in the API for account connection and future publish expansion.

## Fast dev test

1. Start the app.
2. Create or connect a social account.
3. Place a clip under `UPLOAD_DIR/clips`.
4. Enable mock publishing and call the API:

```bash
export DEV_PUBLISH_MOCK=true
curl -X POST http://127.0.0.1:8000/api/v1/publish \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "platform": "youtube",
    "account_id": "<account-id>",
    "clip_filename": "sample.mp4",
    "title": "Test publish",
    "description": "Local verification"
  }'
```

## Real account path

1. Configure the provider app credentials.
2. Set `PUBLIC_BASE_URL` to the public HTTPS URL that can receive callbacks.
3. Connect the account from the Accounts page.
4. Publish from the queue or the clip modal.

## Verification

- `make smoke`
- `python -m pytest -q tests/test_publish_mock.py tests/test_oauth.py tests/test_whop.py`

## Safety notes

- Never commit secrets or `.env`.
- Keep `PUBLIC_BASE_URL` unset for purely local manual testing.
- Use the manual upload fallback if a provider app is not approved for direct posting.

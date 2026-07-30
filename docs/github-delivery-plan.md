# GitHub delivery plan

This rollout is split into three focused commits so the work can be reviewed and pushed incrementally.

## Section 1 — Local startup and publish foundation
- Add a reliable launcher for local startup.
- Document the local run and publishing setup.
- Add a dev-mode publish fallback so local publishing can be tested without real API credentials.

## Section 2 — Testing and CI
- Add publish and scheduler integration tests.
- Add a CI workflow so tests run on push and pull requests.

## Section 3 — Publish UX
- Show the publish result URL in the UI after a mock or real publish completes.

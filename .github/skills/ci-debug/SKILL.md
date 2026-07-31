---
name: ci-debug
description: Use when GitHub Actions, tests, builds, deployment, or CI fails.
---

Goal: find failing command, root cause, minimal fix.

Process:
1. Read only failing job summary first.
2. Extract final error + first relevant stack trace.
3. Avoid pasting full logs.
4. Reproduce locally if possible.
5. Patch smallest cause.
6. Run targeted test/build.
7. Report: cause, files changed, verify command.

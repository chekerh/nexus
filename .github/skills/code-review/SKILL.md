---
name: code-review
description: Use for reviewing diffs, pull requests, or risky changes.
---

Review order:
1. Correctness bugs.
2. Security/privacy risk.
3. Breaking API/schema changes.
4. Performance regressions.
5. Missing tests.
6. Maintainability.

Output:
- Blockers
- Important fixes
- Nice-to-have
- Exact patch suggestions where possible

No style nitpicks unless they affect maintainability.

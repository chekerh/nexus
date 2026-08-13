"""CI guard: verify every frontend API call resolves to a backend route.

Scans frontend JS/HTML for API path references and cross-checks them against
the routes registered on the FastAPI app. Exits non-zero on any reference that
has no matching route, so a renamed/removed endpoint can never silently strand
the UI (e.g. the /pipeline/cancel vs /cancel and /pipeline/stream vs /stream
regressions caught during the UX audit).

Usage:
    python scripts/check_api_refs.py
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"

API_CALL_RE = re.compile(
    r"""(?:apiJSON|apiGet|apiPost|apiPut|apiDelete|fetch)\s*\(\s*["'`]([^"'`]+)["'`]"""
)
PATH_RE = re.compile(r"/api/v1/[A-Za-z0-9_${}/.{}:-]*")

# Locally-computed dynamic segments we cannot statically resolve are replaced
# with a wildcard before matching against backend routes.
SEGMENT_RE = re.compile(r"\$\{[^}]+\}")


def extract_candidate_paths() -> set[str]:
    candidates: set[str] = set()
    for pattern in ("*.js", "*.html"):
        for path in FRONTEND_DIR.glob(pattern):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in API_CALL_RE.finditer(text):
                path_template = m.group(1)
                if "api/v1" in path_template:
                    candidates.add(path_template)
            for m in PATH_RE.finditer(text):
                candidate = m.group(0)
                if "fetch" in candidate or "apiJSON" in candidate:
                    continue
                if candidate.rstrip("}").endswith("$"):
                    continue
                candidates.add(candidate)
    return {c for c in candidates if "/api/" in c}


def registered_routes() -> set[str]:
    os.environ.setdefault("SECRET_KEY", "ci-smoke-secret")
    os.environ.setdefault("ENCRYPTION_KEY", "ci-smoke-encryption-key")
    os.environ.setdefault("JWT_SECRET", "ci-smoke-jwt")
    os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/nexus-refcheck.db")
    sys.path.insert(0, str(ROOT))
    from backend.app.main import app  # noqa: PLC0415

    routes: set[str] = set()
    for route in app.routes:
        if hasattr(route, "path") and route.path.startswith("/api"):
            routes.add(route.path)
    return routes


def normalize(candidate: str) -> str:
    candidate = SEGMENT_RE.sub("{dynamic}", candidate)
    candidate = candidate.replace("${API_BASE}", "").strip()
    return candidate


def matches(route: str, candidate: str) -> bool:
    route_pat = re.escape(re.sub(r"\{[^}]*\}", "__SEG__", route))
    route_pat = route_pat.replace("__SEG__", r"[^/]+")
    return re.fullmatch(route_pat, candidate) is not None


def matches_either(route: str, candidate: str) -> bool:
    if matches(route, candidate):
        return True
    cand_pat = re.escape(re.sub(r"\{[^}]*\}", "__SEG__", candidate))
    cand_pat = cand_pat.replace("__SEG__", r"[^/]+")
    return re.fullmatch(cand_pat, route) is not None


def main() -> int:
    routes = registered_routes()
    candidates = extract_candidate_paths()
    failures: list[str] = []
    for candidate in sorted(candidates):
        normalized = normalize(candidate).split("?")[0]
        if normalized.startswith("/api/"):
            if not any(matches_either(r, normalized) for r in routes):
                failures.append(candidate)
    if failures:
        print(f"FAIL: {len(failures)} frontend API reference(s) with no backend route:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {len(candidates)} frontend API reference(s) all resolve to backend routes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

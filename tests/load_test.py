"""Load test — concurrent pipeline submissions and status checks.

Usage: python -m tests.load_test [--concurrency 10] [--duration 30]
"""

import argparse
import concurrent.futures
import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000/api/v1")
AUTH_TOKEN = os.environ.get("TEST_AUTH_TOKEN", "")


def _request(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"status": resp.status, "body": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": str(e)}


def health_check() -> dict:
    return _request("GET", "/system/check")


def submit_job() -> dict:
    return _request(
        "POST",
        "/pipeline/submit",
        {
            "filename": f"load_test_{time.time()}.mp4",
            "youtube_url": "",
        },
    )


def status_job(job_id: str) -> dict:
    return _request("GET", f"/status/{job_id}")


def run_load_test(concurrency: int, duration: int):
    print(f"Load test: {concurrency} workers, {duration}s duration")
    start = time.perf_counter()
    submitted = 0
    errors = 0
    latencies = []

    def worker():
        nonlocal submitted, errors
        t0 = time.perf_counter()
        try:
            result = submit_job()
            lat = time.perf_counter() - t0
            latencies.append(lat)
            if result.get("status", 0) in (200, 201):
                submitted += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    while time.perf_counter() - start < duration:
        batch = min(concurrency, 5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch) as ex:
            list(ex.map(lambda _: worker(), range(batch)))
        time.sleep(0.5)

    elapsed = time.perf_counter() - start
    print(f"\nResults ({elapsed:.1f}s):")
    print(f"  Submitted: {submitted}")
    print(f"  Errors: {errors}")
    if latencies:
        print(f"  Avg latency: {sum(latencies) / len(latencies):.3f}s")
        print(f"  P50: {sorted(latencies)[len(latencies) // 2]:.3f}s")
        print(f"  P95: {sorted(latencies)[int(len(latencies) * 0.95)]:.3f}s")
    print(f"  Throughput: {submitted / elapsed:.1f} req/s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()
    run_load_test(args.concurrency, args.duration)

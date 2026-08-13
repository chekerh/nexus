"""Prometheus metrics instrumentation for Nexus-UGC."""

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# HTTP metrics
http_requests_total = Counter(
    "nexus_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "nexus_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Pipeline metrics
pipeline_jobs_total = Counter(
    "nexus_pipeline_jobs_total",
    "Total pipeline jobs processed",
    ["status"],  # completed, failed, cancelled
)
pipeline_job_duration_seconds = Histogram(
    "nexus_pipeline_job_duration_seconds",
    "Pipeline job duration in seconds",
    buckets=(30, 60, 120, 300, 600, 1800, 3600),
)

# Queue metrics
queue_depth = Gauge("nexus_queue_depth", "Current number of jobs in the queue")

# Credit metrics
credits_consumed_total = Counter(
    "nexus_credits_consumed_total",
    "Total credits consumed",
)

# User metrics
active_users = Gauge("nexus_active_users", "Number of active users")


def metrics_endpoint() -> Response:
    """Expose Prometheus metrics at GET /metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

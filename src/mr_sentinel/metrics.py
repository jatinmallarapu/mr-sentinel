"""Track operational counters without project names, prompts, or other high-cardinality labels."""

from prometheus_client import Counter, Histogram

REVIEW_LATENCY = Histogram("review_latency_seconds", "Elapsed end-to-end review time")
REVIEW_OUTCOMES = Counter("review_outcomes_total", "Review results", ["status"])
AGENT_ERRORS = Counter("agent_errors_total", "Failed specialist or judge calls", ["agent"])
TOKENS = Counter("tokens_total", "Tokens reported by the model endpoint")
WEBHOOK_JOBS = Counter("webhook_jobs_total", "GitLab delivery processing outcomes", ["status"])

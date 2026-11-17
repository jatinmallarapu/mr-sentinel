"""Optional Ray Serve ingress with a separately managed model backend."""
from ray import serve

from mr_sentinel.api import app


@serve.deployment(max_ongoing_requests=8)
@serve.ingress(app)
class SentinelGateway:
    """Bound concurrent requests per replica so the backend can apply backpressure."""


deployment = SentinelGateway.bind()

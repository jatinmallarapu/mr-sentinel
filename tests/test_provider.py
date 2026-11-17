"""Use HTTPX transport mocks to exercise structured output retries."""

import json

import httpx
import pytest

from mr_sentinel.providers.base import ProviderError
from mr_sentinel.providers.openai_compat import OpenAICompatProvider
from mr_sentinel.schemas import Summary


async def test_retries_invalid_json_without_reflecting_it():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        output = "INVALID" if len(requests) == 1 else '{"summary":"valid"}'
        return httpx.Response(
            200, json={"choices": [{"message": {"content": output}}], "usage": {"total_tokens": 5}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatProvider(client, "http://model.test/v1", "fixture")
        assert (
            await provider.complete("Trusted role", "Untrusted data", Summary)
        ).summary == "valid"
    assert [msg["role"] for msg in requests[1]["messages"]] == ["system", "user"]
    assert "INVALID" not in requests[1]["messages"][0]["content"]


@pytest.mark.parametrize("status", [200, 503])
async def test_invalid_and_unavailable_endpoints_fail_safely(status):
    def handler(request):
        return httpx.Response(status, json={"private": "value"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatProvider(client, "http://model.test/v1", "fixture")
        with pytest.raises(ProviderError, match="Model"):
            await provider.complete("system", "user", Summary)

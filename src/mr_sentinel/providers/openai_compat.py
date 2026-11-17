"""Request bounded JSON completions from vLLM or SGLang."""

import json

import httpx
from pydantic import ValidationError

from ..metrics import TOKENS
from .base import ProviderError, T


class OpenAICompatProvider:
    def __init__(self, client: httpx.AsyncClient, base_url: str, model: str, key: str = ""):
        self.client = client
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.name = model
        self.headers = {"Authorization": f"Bearer {key}"} if key else {}

    async def complete(self, system: str, user: str, schema: type[T]) -> T:
        instruction = (
            system + "\nReturn only JSON matching: " + json.dumps(schema.model_json_schema())
        )
        for attempt in range(2):
            try:
                response = await self.client.post(
                    self.url,
                    headers=self.headers,
                    json={
                        "model": self.name,
                        "temperature": 0,
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "system", "content": instruction},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError:
                raise ProviderError("Model endpoint request failed") from None
            try:
                data = response.json()
                usage = data.get("usage") or {}
                total = usage.get("total_tokens")
                if type(total) is int and total >= 0:
                    TOKENS.inc(total)
                return schema.model_validate_json(data["choices"][0]["message"]["content"])
            except (AttributeError, IndexError, KeyError, TypeError, ValueError, ValidationError):
                if attempt == 1:
                    raise ProviderError("Model returned invalid structured output") from None
                # Retry without echoing the invalid completion into the next prompt.
                instruction += "\nThe last response did not validate. Output one JSON object."
        raise AssertionError("Retry loop did not terminate")

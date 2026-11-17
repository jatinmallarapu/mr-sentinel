"""Allow orchestration tests to replace inference without patching HTTP."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelProvider(Protocol):
    name: str

    async def complete(self, system: str, user: str, schema: type[T]) -> T: ...


class ProviderError(RuntimeError):
    """A failure safe to log without exposing prompts or generated text."""

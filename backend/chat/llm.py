"""A11 — Single abstraction layer for all LLM calls.

All code that needs to call the Anthropic API MUST go through this module.
Never import anthropic directly in routes or other modules.

Design: D5 (class + lazy singleton), D9 (high-level stream API), D10 (dataclasses).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from config import settings


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


@dataclass
class StreamEvent:
    type: str  # "text_delta" | "complete"
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    """Thin wrapper around AsyncAnthropic with lazy initialization."""

    def __init__(self) -> None:
        self._client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Non-streaming completion. Use for short, one-shot calls."""
        response = await self.client.messages.create(
            model=settings.anthropic_model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            stop_reason=response.stop_reason,
        )

    async def stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming completion. Yields text deltas, then a final 'complete' event."""
        async with self.client.messages.stream(
            model=settings.anthropic_model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield StreamEvent(type="text_delta", text=text)

            final = await stream.get_final_message()
            yield StreamEvent(
                type="complete",
                text="",
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )

    async def classify(
        self,
        system: str,
        message: str,
    ) -> str:
        """Lightweight call for intent classification. Low max_tokens."""
        response = await self.complete(
            system=system,
            messages=[{"role": "user", "content": message}],
            max_tokens=50,
        )
        return response.text.strip().lower()


llm_client = LLMClient()

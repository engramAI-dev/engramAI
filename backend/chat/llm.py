"""A11 — Single abstraction layer for all LLM calls.

All code that needs to call an LLM MUST go through this module.
Never import google.genai or anthropic directly in routes or other modules.

Design: D5 (class + lazy singleton), D9 (high-level streaming), D10 (dataclasses),
D45 (configurable provider: Gemini free tier or Anthropic Claude).

Switch provider via LLM_PROVIDER env var ("gemini" or "anthropic").
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

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
    """Provider-agnostic LLM client. Supports Gemini and Anthropic via config."""

    def __init__(self) -> None:
        self._gemini_client = None
        self._anthropic_client = None

    @property
    def _provider(self) -> str:
        return settings.llm_provider

    def _get_gemini(self):  # type: ignore[no-untyped-def]
        if self._gemini_client is None:
            from google import genai
            self._gemini_client = genai.Client(api_key=settings.google_api_key)
        return self._gemini_client

    def _get_anthropic(self):  # type: ignore[no-untyped-def]
        if self._anthropic_client is None:
            from anthropic import AsyncAnthropic
            self._anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic_client

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Non-streaming completion."""
        if self._provider == "anthropic":
            return await self._complete_anthropic(system, messages, max_tokens)
        return await self._complete_gemini(system, messages, max_tokens)

    async def stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming completion. Yields text deltas, then a final 'complete' event."""
        if self._provider == "anthropic":
            async for event in self._stream_anthropic(system, messages, max_tokens):
                yield event
        else:
            async for event in self._stream_gemini(system, messages, max_tokens):
                yield event

    async def classify(
        self,
        system: str,
        message: str,
    ) -> str:
        """Lightweight call for intent classification."""
        response = await self.complete(
            system=system,
            messages=[{"role": "user", "content": message}],
            max_tokens=50,
        )
        return response.text.strip().lower()

    # ── Gemini implementation ──

    async def _complete_gemini(
        self, system: str, messages: list[dict], max_tokens: int,
    ) -> LLMResponse:
        from google import genai
        client = self._get_gemini()
        contents = _build_gemini_contents(messages)
        response = await client.aio.models.generate_content(
            model=settings.llm_model,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        usage = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            input_tokens=usage.prompt_token_count or 0 if usage else 0,
            output_tokens=usage.candidates_token_count or 0 if usage else 0,
            model=settings.llm_model,
            stop_reason=response.candidates[0].finish_reason.name if response.candidates else "unknown",
        )

    async def _stream_gemini(
        self, system: str, messages: list[dict], max_tokens: int,
    ) -> AsyncIterator[StreamEvent]:
        from google import genai
        client = self._get_gemini()
        contents = _build_gemini_contents(messages)
        total_input = 0
        total_output = 0

        async for chunk in await client.aio.models.generate_content_stream(
            model=settings.llm_model,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        ):
            if chunk.text:
                yield StreamEvent(type="text_delta", text=chunk.text)
            if chunk.usage_metadata:
                total_input = chunk.usage_metadata.prompt_token_count or total_input
                total_output = chunk.usage_metadata.candidates_token_count or total_output

        yield StreamEvent(
            type="complete", text="",
            input_tokens=total_input, output_tokens=total_output,
        )

    # ── Anthropic implementation ──

    async def _complete_anthropic(
        self, system: str, messages: list[dict], max_tokens: int,
    ) -> LLMResponse:
        client = self._get_anthropic()
        response = await client.messages.create(
            model=settings.llm_model,
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

    async def _stream_anthropic(
        self, system: str, messages: list[dict], max_tokens: int,
    ) -> AsyncIterator[StreamEvent]:
        client = self._get_anthropic()
        async with client.messages.stream(
            model=settings.llm_model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield StreamEvent(type="text_delta", text=text)

            final = await stream.get_final_message()
            yield StreamEvent(
                type="complete", text="",
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )


def _build_gemini_contents(messages: list[dict]) -> list:
    """Convert internal message format to Gemini's Content format."""
    from google import genai
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(genai.types.Content(
            role=role,
            parts=[genai.types.Part(text=msg["content"])],
        ))
    return contents


llm_client = LLMClient()

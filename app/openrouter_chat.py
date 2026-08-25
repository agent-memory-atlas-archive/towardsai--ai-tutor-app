"""OpenRouter chat-model compatibility helpers.

OpenRouter normalizes reasoning across the models it routes: requests take a
unified ``reasoning`` object (``{"enabled": ...}``) regardless of the
underlying model, and streamed deltas carry the thought text in a
``reasoning`` field (verified live against ``deepseek/deepseek-v4-flash``,
2026-08-25). The stock ``ChatOpenAI`` wrapper drops that nonstandard delta
field, so this subclass maps it into
``additional_kwargs["reasoning_content"]`` -- the same slot the DeepSeek
adapter uses -- and ``provider_events.extract_reasoning_deltas`` then works
unchanged for either provider.
"""

from __future__ import annotations

from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI


class TutorChatOpenRouter(ChatOpenAI):
    """ChatOpenAI that preserves OpenRouter's streamed ``reasoning`` field."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None
        choices = chunk.get("choices") or []
        if choices and isinstance(generation_chunk.message, AIMessageChunk):
            reasoning = (choices[0].get("delta") or {}).get("reasoning")
            if reasoning:
                generation_chunk.message.additional_kwargs["reasoning_content"] = (
                    reasoning
                )
        return generation_chunk

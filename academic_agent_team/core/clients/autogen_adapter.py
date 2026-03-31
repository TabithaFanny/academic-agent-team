"""
AutoGen 0.7 ChatCompletionClient adapter.

Adapt project BaseModelClient (complete interface) to AutoGen ChatCompletionClient
so existing provider clients can be reused in AssistantAgent/GraphFlow.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Mapping, Sequence

from autogen_core import CancellationToken
from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    LLMMessage,
    ModelInfo,
    RequestUsage,
)


class ModelClientAdapter(ChatCompletionClient):
    """Adapter from BaseModelClient to AutoGen ChatCompletionClient."""

    def __init__(self, base_client: Any):
        self._client = base_client
        self._usage = RequestUsage(prompt_tokens=0, completion_tokens=0)

    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Any] = (),
        tool_choice: Any = "auto",
        json_output: bool | type | None = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: CancellationToken | None = None,
    ) -> CreateResult:
        del tools, tool_choice, json_output, cancellation_token

        system_parts: list[str] = []
        user_parts: list[str] = []
        for msg in messages:
            source = getattr(msg, "source", "")
            content = str(getattr(msg, "content", ""))
            if source == "system":
                system_parts.append(content)
            else:
                user_parts.append(content)

        system_text = "\n\n".join(system_parts)
        prompt = "\n\n".join(user_parts)
        temperature = float(extra_create_args.get("temperature", 0.5))
        max_tokens = int(extra_create_args.get("max_tokens", 4096))

        response = self._client.complete(
            prompt=prompt,
            system=system_text,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        self._usage = RequestUsage(
            prompt_tokens=self._usage.prompt_tokens + int(getattr(response, "input_tokens", 0)),
            completion_tokens=self._usage.completion_tokens + int(getattr(response, "output_tokens", 0)),
        )

        return CreateResult(
            finish_reason="stop",
            content=response.content,
            usage=RequestUsage(
                prompt_tokens=int(getattr(response, "input_tokens", 0)),
                completion_tokens=int(getattr(response, "output_tokens", 0)),
            ),
            cached=False,
            logprobs=None,
            thought=None,
        )

    async def create_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Any] = (),
        tool_choice: Any = "auto",
        json_output: bool | type | None = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncGenerator[str | CreateResult, None]:
        result = await self.create(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )
        yield result

    def close(self) -> None:
        return None

    def actual_usage(self) -> RequestUsage:
        return self._usage

    def total_usage(self) -> RequestUsage:
        return self._usage

    def count_tokens(self, messages: Sequence[LLMMessage], *, tools: Sequence[Any] = ()) -> int:
        del tools
        total_chars = sum(len(str(getattr(msg, "content", ""))) for msg in messages)
        return total_chars // 2

    def remaining_tokens(self, messages: Sequence[LLMMessage], *, tools: Sequence[Any] = ()) -> int:
        used = self.count_tokens(messages, tools=tools)
        return max(0, 8192 - used)

    @property
    def capabilities(self) -> ModelInfo:
        return {
            "vision": False,
            "function_calling": False,
            "json_output": True,
            "structured_output": False,
            "multiple_system_messages": False,
            "family": "unknown",
        }

    @property
    def model_info(self) -> ModelInfo:
        return self.capabilities

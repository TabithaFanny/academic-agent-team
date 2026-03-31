"""
core/autogen_adapter.py

将 BaseModelClient 适配为 AutoGen 0.7 ChatCompletionClient 接口。

用法：
    from academic_agent_team.core.autogen_adapter import ModelClientAdapter
    from academic_agent_team.core.clients import AnthropicClient

    client = ModelClientAdapter(AnthropicClient(model_id="claude-sonnet-4-5"))
    agent = AssistantAgent("advisor", model_client=client, system_message="...")
"""

from __future__ import annotations

from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    ChatCompletionTokenLogprob,
    CreateResult,
    ModelFamily,
    ModelInfo,
    RequestUsage,
    SystemMessage,
    UserMessage,
)
from autogen_agentchat.messages import TextMessage
from typing import Any, AsyncGenerator, Literal, Mapping, Sequence

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse

__all__ = ["ModelClientAdapter"]


# ─── tiktoken 编码缓存（按 encoding_name 缓存）──────────────────────────────────

_token_encoders: dict[str, Any] = {}  # type: ignore[name-defined]


def _get_encoder(encoding_name: str = "cl100k_base") -> Any:  # type: ignore[name-defined]
    if encoding_name not in _token_encoders:
        try:
            import tiktoken
            _token_encoders[encoding_name] = tiktoken.get_encoding(encoding_name)
        except ImportError:
            return None
    return _token_encoders.get(encoding_name)


def _count_tokens_text(text: str, encoding_name: str = "cl100k_base") -> int:
    """对文本进行 token 计数（tiktoken fallback：4字符≈1 token）。"""
    enc = _get_encoder(encoding_name)
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # fallback: 中英文混合估算
    chinese_chars = sum(1 for c in text if ord(c) > 127)
    ascii_chars = len(text) - chinese_chars
    return chinese_chars // 2 + ascii_chars // 4


def _count_tokens_messages(
    messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
) -> int:
    """对 AutoGen 消息列表进行 token 计数。"""
    total = 0
    for m in messages:
        content: str
        if isinstance(m, (SystemMessage, TextMessage, AssistantMessage)):
            content = m.content
        elif isinstance(m, UserMessage):
            content = m.content if isinstance(m.content, str) else str(m.content)
        else:
            content = str(getattr(m, "content", ""))
        total += _count_tokens_text(content)
    return total


# ─── AutoGen ChatCompletionClient 适配器 ───────────────────────────────────────


class ModelClientAdapter(ChatCompletionClient):
    """
    将 BaseModelClient 包装为 AutoGen 0.7 ChatCompletionClient。

    参数：
        base_client: BaseModelClient 实例（mock/anthropic/openai/deepseek/...）
        model_id: 传给 AutoGen 的逻辑模型 ID（用于 `model` 字段）
        provider_name: 用于选择 tiktoken 编码（"openai" → cl100k_base,
                     "anthropic" → cl100k_base, 其他 → cl100k_base）
        max_tokens: 单次输出最大 token 数（默认 8192）
    """

    def __init__(
        self,
        base_client: BaseModelClient,
        *,
        model_id: str | None = None,
        provider_name: str = "openai",
        max_tokens: int = 8192,
    ) -> None:
        self._client = base_client
        self._model_id = model_id or getattr(base_client, "model_id", "unknown")
        self._provider = provider_name
        self._max_tokens = max_tokens
        self._total_usage = RequestUsage(prompt_tokens=0, completion_tokens=0)

    # ── 非流式 create ─────────────────────────────────────────────────────────

    async def create(
        self,
        messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
        *,
        tools: Sequence[Any] = (),  # noqa: ANN401
        tool_choice: str | Any = "auto",  # noqa: ANN401
        json_output: bool | type | None = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Any | None = None,  # noqa: ANN401
    ) -> CreateResult:
        # 转换 AutoGen 消息 → BaseModelClient 格式
        prompt, system = _convert_messages(messages)

        # 调用异步接口（优先），无则用线程池包装同步调用
        if hasattr(self._client, "complete_async"):
            response: ModelResponse = await self._client.complete_async(
                prompt=prompt,
                system=system,
                temperature=_get_temperature(extra_create_args),
                max_tokens=_get_max_tokens(extra_create_args, self._max_tokens),
            )
        else:
            import asyncio
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.complete(
                    prompt=prompt,
                    system=system,
                    temperature=_get_temperature(extra_create_args),
                    max_tokens=_get_max_tokens(extra_create_args, self._max_tokens),
                ),
            )

        # 更新累计用量
        self._total_usage = RequestUsage(
            prompt_tokens=self._total_usage.prompt_tokens + response.input_tokens,
            completion_tokens=self._total_usage.completion_tokens + response.output_tokens,
        )

        return CreateResult(
            finish_reason=_finish_reason_from_response(response),
            content=response.content,
            usage=RequestUsage(
                prompt_tokens=response.input_tokens,
                completion_tokens=response.output_tokens,
            ),
            cached=False,
        )

    # ── 流式 create_stream ───────────────────────────────────────────────────

    async def create_stream(
        self,
        messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
        *,
        tools: Sequence[Any] = (),  # noqa: ANN401
        tool_choice: str | Any = "auto",  # noqa: ANN401
        json_output: bool | type | None = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Any | None = None,  # noqa: ANN401
    ) -> AsyncGenerator[str | CreateResult, None]:
        prompt, system = _convert_messages(messages)

        # 调用异步接口（如果 client 没有异步实现则同步包装）
        if hasattr(self._client, "complete_async"):
            gen = self._client.complete_async(
                prompt=prompt,
                system=system,
                temperature=_get_temperature(extra_create_args),
                max_tokens=_get_max_tokens(extra_create_args, self._max_tokens),
            )
            accumulated = ""
            async for chunk in gen:
                accumulated += chunk
                yield chunk
            # 最终块
            yield _build_result_from_content(accumulated, messages)
        else:
            # 同步包装（模拟流式）
            import asyncio
            response: ModelResponse = self._client.complete(
                prompt=prompt,
                system=system,
                temperature=_get_temperature(extra_create_args),
                max_tokens=_get_max_tokens(extra_create_args, self._max_tokens),
            )
            # 逐字 yield（延迟 10ms 模拟打字）
            for char in response.content:
                await asyncio.sleep(0)  # 让出控制权
                yield char
            self._total_usage = RequestUsage(
                prompt_tokens=self._total_usage.prompt_tokens + response.input_tokens,
                completion_tokens=self._total_usage.completion_tokens + response.output_tokens,
            )
            yield _build_result_from_content(response.content, messages)

    # ── Token 计数 ───────────────────────────────────────────────────────────

    def count_tokens(
        self,
        messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
        *,
        tools: Sequence[Any] = (),  # noqa: ANN401
    ) -> int:
        encoding = "cl100k_base"  # 默认编码（适用于 GPT-4 / Claude / DeepSeek）
        return _count_tokens_messages(messages)

    def remaining_tokens(
        self,
        messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
        *,
        tools: Sequence[Any] = (),  # noqa: ANN401
    ) -> int:
        used = self.count_tokens(messages, tools=tools)
        return max(0, 128000 - used)  # 保守假设 128k 上下文

    # ── 用量查询 ─────────────────────────────────────────────────────────────

    def actual_usage(self) -> RequestUsage:
        return self._total_usage

    def total_usage(self) -> RequestUsage:
        return self._total_usage

    def close(self) -> None:
        if hasattr(self._client, "close"):
            self._client.close()

    @property
    def capabilities(self) -> ModelInfo:
        """返回模型能力描述（对齐 AutoGen ChatCompletionClient 接口）。"""
        return ModelInfo(
            vision=False,
            function_calling=True,  # 必须 True，否则 handoffs（内部用 function calling）无法工作
            json_output=False,
            structured_output=False,
            family=ModelFamily.ANY,
            multiple_system_messages=True,
        )

    @property
    def model_info(self) -> ModelInfo:
        """返回模型元信息（同 capabilities）。"""
        return self.capabilities

    # ── 组件序列化（AutoGen 需要）──────────────────────────────────────────────

    def dump_component(self) -> dict[str, Any]:
        return {
            "type": "ModelClientAdapter",
            "model_id": self._model_id,
            "provider": self._provider,
            "max_tokens": self._max_tokens,
        }

    @classmethod
    def load_component(cls, model: dict[str, Any]) -> "ModelClientAdapter":
        # 懒加载：实际从 dump 重建需要重新实例化 BaseModelClient
        raise NotImplementedError(
            "ModelClientAdapter.load_component requires a factory. "
            "Use ModelClientAdapter.from_factory() instead."
        )


# ─── 消息格式转换 ─────────────────────────────────────────────────────────────


def _convert_messages(
    messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
) -> tuple[str, str]:
    """
    将 AutoGen 消息列表转换为 (prompt, system) 二元组。
    prompt = 连续的用户/助手消息文本
    system = system_message 内容（取第一条 SystemMessage）
    """
    system_parts: list[str] = []
    prompt_parts: list[str] = []

    for m in messages:
        if isinstance(m, SystemMessage):
            # SystemMessage 没有 source 字段
            system_parts.append(m.content)
        else:
            # UserMessage / TextMessage / AssistantMessage 有 source 字段
            source = getattr(m, "source", "unknown")
            prefix = f"[{source}]"
            if isinstance(m, (TextMessage, AssistantMessage)):
                content = getattr(m, "content", "")
                prompt_parts.append(f"{prefix} {content}")
            elif isinstance(m, UserMessage):
                content = m.content if isinstance(m.content, str) else str(m.content)
                prompt_parts.append(f"{prefix} {content}")

    system = "\n".join(system_parts) if system_parts else ""
    prompt = "\n".join(prompt_parts) if prompt_parts else ""
    return prompt, system


def _get_temperature(extra_create_args: Mapping[str, Any]) -> float:
    return float(extra_create_args.get("temperature", 0.5))


def _get_max_tokens(extra_create_args: Mapping[str, Any], default: int) -> int:
    return int(extra_create_args.get("max_tokens", default))


def _finish_reason_from_response(response: ModelResponse) -> "Literal['stop', 'length', 'function_calls', 'content_filter', 'unknown']":  # noqa: F821
    """根据 ModelResponse latency_ms 判断是否超时。"""
    if response.latency_ms < 0:
        return "length"
    return "stop"


def _build_result_from_content(
    content: str,
    messages: Sequence[UserMessage | AssistantMessage | SystemMessage | TextMessage],
) -> CreateResult:
    """从累积的 content 构造 CreateResult。"""
    # 估算 token（4 char ≈ 1 token）
    completion_tokens = len(content) // 4
    prompt_tokens = _count_tokens_messages(messages)
    return CreateResult(
        finish_reason="stop",
        content=content,
        usage=RequestUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
        cached=False,
    )

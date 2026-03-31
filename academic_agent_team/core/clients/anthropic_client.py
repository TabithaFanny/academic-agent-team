"""
core/clients/anthropic_client.py

Anthropic Claude client（官方 anthropic Python SDK）。
对齐 PRD Section 7.7 MODEL_REGISTRY。
"""

from __future__ import annotations

import os
import time
from typing import Any

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class AnthropicClient(BaseModelClient):
    """
    Anthropic Claude API client.
    支持 claude-sonnet-4-5 / claude-opus-4-5 / claude-haiku-3-5 等。
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        # 默认使用 sonnet（PRD 7.7 性价比推荐）
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    # ─── 定价（CNY/1M tokens）─对齐 PRD Section 10.6 ─────────────────────────
    _PRICING: dict[str, tuple[float, float]] = {
        "claude-opus-4-5":  (36.0,  180.0),
        "claude-sonnet-4-5": (21.6,  108.0),
        "claude-haiku-3-5":  (7.2,   36.0),
    }
    _DEFAULT = (21.6, 108.0)

    # ─── API ───────────────────────────────────────────────────────────────────

    def _call_api(
        self,
        messages: list[dict[str, str]],
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic>=0.40"
            ) from e

        client = Anthropic(api_key=self.api_key)

        start = time.time()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        # Anthropic API 使用 roles: user / assistant
        # 支持 messages list 或 prompt（legacy）
        if len(messages) == 1 and messages[0]["role"] == "user":
            kwargs["messages"] = [{"role": "user", "content": messages[0]["content"]}]
        else:
            kwargs["messages"] = messages

        resp = client.messages.create(**kwargs)
        latency_ms = int((time.time() - start) * 1000)

        # 提取文本内容（Anthropic 返回 content block 列表）
        text = ""
        for block in resp.content:
            if block.type == "text":
                text = block.text
                break

        usage = resp.usage
        inp, out = self._PRICING.get(self.model, self._DEFAULT)
        cost_cny = round(
            (usage.input_tokens / 1_000_000) * inp
            + (usage.output_tokens / 1_000_000) * out,
            6,
        )

        return {
            "content": text,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_cny": cost_cny,
            "model_id": self.model,
            "latency_ms": latency_ms,
        }

    # ─── BaseModelClient 接口 ─────────────────────────────────────────────────

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 8192,
    ) -> ModelResponse:
        messages = [{"role": "user", "content": prompt}]
        result = self._call_api(messages, system, temperature, max_tokens)
        return ModelResponse(**result)

    async def complete_async(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 8192,
    ) -> ModelResponse:
        return self.complete(prompt, system, temperature, max_tokens)

    def health_check(self) -> bool:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)
            client.messages.create(
                model=self.model, max_tokens=10,
                messages=[{"role": "user", "content": "hi"}]
            )
            return True
        except Exception:
            return False

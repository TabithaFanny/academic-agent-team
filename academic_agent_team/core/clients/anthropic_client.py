"""Anthropic Claude Client — 继承 BaseModelClient。"""

from __future__ import annotations

import os
import time

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class AnthropicClient(BaseModelClient):
    """
    Anthropic Claude 模型 client（使用官方 anthropic Python SDK）。

    环境变量：
        ANTHROPIC_API_KEY: API Key
    """

    def __init__(self, api_key: str | None = None):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            )
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = anthropic.Anthropic(api_key=self._api_key)
        self.model_id = "claude-sonnet-4-5"

    def _call(self, messages: list, system: str, temperature: float, max_tokens: int) -> dict:
        params = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }
        start = time.time()
        response = self._client.messages.create(**params)
        latency_ms = int((time.time() - start) * 1000)

        text = "".join(block.text for block in response.content if block.type == "text")

        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens

        # Claude Sonnet 4.5 定价（CNY/1M tokens）
        input_cost = (input_tokens / 1_000_000) * 21.6
        output_cost = (output_tokens / 1_000_000) * 108.0
        cost_cny = input_cost + output_cost

        return {
            "content": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_cny": round(cost_cny, 6),
            "model_id": self.model_id,
            "latency_ms": latency_ms,
        }

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        messages = [{"role": "user", "content": prompt}]
        result = self._call(messages, system, temperature, max_tokens)
        return ModelResponse(**result)

    async def complete_async(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        return self.complete(prompt, system, temperature, max_tokens)

    def health_check(self) -> bool:
        try:
            self._client.messages.create(
                model=self.model_id,
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False

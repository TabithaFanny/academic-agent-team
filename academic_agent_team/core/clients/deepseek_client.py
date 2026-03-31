"""
core/clients/deepseek_client.py

DeepSeek client（官方 DeepSeek API，OpenAI-compatible 接口）。
对齐 PRD Section 7.7 MODEL_REGISTRY。
DeepSeek V3 定价：input ¥0.27/¥1M（cache hit ¥0.02），output ¥1.1/¥1M。
"""

from __future__ import annotations

import os
import time
from typing import Any

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class DeepSeekClient(BaseModelClient):
    """
    DeepSeek API client（OpenAI-compatible endpoint）。
    官方定价（折合 CNY）：input ¥2.02/¥1M，output ¥3.02/¥1M。
    """

    BASE_URL = "https://api.deepseek.com/v1"
    # DeepSeek V3 model ID（PRD 7.7 修正：不是 deepseek-chat）
    DEFAULT_MODEL = "deepseek-chat"  # API 实际 ID

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL", self.BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("DEEPSEEK_MODEL", self.DEFAULT_MODEL)

    # 定价（¥/1M tokens）
    _INPUT_CNY_PER_1M = 2.02
    _OUTPUT_CNY_PER_1M = 3.02

    # ─── API ───────────────────────────────────────────────────────────────────

    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai package not installed. Run: pip install openai") from e

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        start = time.time()
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.time() - start) * 1000)

        usage = resp.usage
        cost_cny = round(
            (usage.prompt_tokens / 1_000_000) * self._INPUT_CNY_PER_1M
            + (usage.completion_tokens / 1_000_000) * self._OUTPUT_CNY_PER_1M,
            6,
        )

        return {
            "content": resp.choices[0].message.content or "",
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        result = self._call_api(messages, temperature, max_tokens)
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
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            client.models.list()
            return True
        except Exception:
            return False

"""
core/clients/openai_client.py

OpenAI 兼容 API client（支持 DeepSeek / Qwen / 本地模型等 OpenAI-compatible 接口）。
对齐 PRD Section 7.7 MODEL_REGISTRY。
"""

from __future__ import annotations

import os
import time
from typing import Any

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class OpenAIClient(BaseModelClient):
    """
    OpenAI-compatible model client.
    支持 DeepSeek / Qwen / 本地模型等任何兼容 OpenAI chat completions API 的端点。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "not-set")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # ─── 定价映射 ─────────────────────────────────────────────────────────────
    # 按 provider/model 估算 USD → CNY（固定 7.2）
    _USD_TO_CNY = 7.2

    _PRICING: dict[str, tuple[float, float]] = {
        # (input_cny_per_1m, output_cny_per_1m)
        "deepseek-chat": (0.27 * 7.2, 1.1 * 7.2),     # DeepSeek V3
        "gpt-4o":         (18.0,         72.0),
        "gpt-4-turbo":   (72.0,         216.0),
        "gpt-4o-mini":    (3.6,           14.4),
        "gpt-3.5-turbo":  (3.6,           14.4),
        # Qwen / 其他使用通用定价
    }
    _GENERIC = (0.5 * 7.2, 1.5 * 7.2)  # 通用 OpenAI-compatible

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
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            ) from e

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
        inp, out = self._PRICING.get(self.model, self._GENERIC)
        cost_cny = round(
            (usage.prompt_tokens / 1_000_000) * inp
            + (usage.completion_tokens / 1_000_000) * out,
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
        max_tokens: int = 4096,
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
        max_tokens: int = 4096,
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

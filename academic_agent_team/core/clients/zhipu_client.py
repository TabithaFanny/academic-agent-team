"""
core/clients/zhipu_client.py

智谱 AI（Zhipu GLM）client（OpenAI-compatible 接口）。
对齐 PRD Section 7.7 MODEL_REGISTRY。
定价：GLM-4 Flash ¥1/¥1M，GLM-4 旗舰 ¥100/¥100M。
"""

from __future__ import annotations

import os
import time
from typing import Any

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class ZhipuClient(BaseModelClient):
    """
    智谱 AI GLM client（OpenAI-compatible）。
    官方 API: https://open.bigmodel.cn/api/paas/v4
    """

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("ZHIPU_API_KEY", "")
        self.base_url = (base_url or os.environ.get("ZHIPU_BASE_URL", self.BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("ZHIPU_MODEL", "glm-4-flash")

    # 定价（¥/1M tokens）
    _PRICING: dict[str, tuple[float, float]] = {
        "glm-4-flash":    (1.0, 1.0),
        "glm-4":          (100.0, 100.0),
    }
    _DEFAULT = (1.0, 1.0)

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
        inp, out = self._PRICING.get(self.model, self._DEFAULT)
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

"""智谱 GLM Client — 继承 BaseModelClient，OpenAI 兼容 API。"""

from __future__ import annotations

import os
import time

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class ZhipuClient(BaseModelClient):
    """
    智谱 GLM-4 client（OpenAI 兼容 API）。

    环境变量：
        ZHIPU_API_KEY: API Key
        ZHIPU_BASE_URL: API Base URL（默认 https://open.bigmodel.cn/api/paas/v4）
        ZHIPU_MODEL: 模型名（默认 glm-4-flash）
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        self._api_key = api_key or os.environ.get("ZHIPU_API_KEY", "")
        self._base_url = (base_url or os.environ.get(
            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
        )).rstrip("/")
        self.model = model or os.environ.get("ZHIPU_MODEL", "glm-4-flash")
        self._client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url)

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

        start = time.time()
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.time() - start) * 1000)

        usage = resp.usage
        text = resp.choices[0].message.content or ""

        # GLM-4-Flash 定价：¥1.0/1M input + ¥1.0/1M output
        input_cost = (usage.prompt_tokens / 1_000_000) * 1.0
        output_cost = (usage.completion_tokens / 1_000_000) * 1.0
        cost_cny = input_cost + output_cost

        return ModelResponse(
            content=text,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            cost_cny=round(cost_cny, 6),
            model_id=self.model,
            latency_ms=latency_ms,
        )

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
            self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            )
            return True
        except Exception:
            return False

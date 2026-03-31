"""Ollama 本地模型 Client — 继承 BaseModelClient，OpenAI 兼容 API。"""

from __future__ import annotations

import os
import time

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class OllamaClient(BaseModelClient):
    """
    Ollama 本地模型 client（OpenAI 兼容 API）。

    本地部署，免费使用，需要 GPU。

    环境变量：
        OLLAMA_BASE_URL: API Base URL（默认 http://localhost:11434/v1）
        OLLAMA_MODEL: 模型名（默认 llama3:8b）
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ):
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        self._base_url = (base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3:8b")
        self._client = openai.OpenAI(api_key="ollama", base_url=self._base_url)

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

        usage = resp.usage or type("U", (), {"prompt_tokens": 0, "completion_tokens": 0})()
        text = resp.choices[0].message.content or ""

        # Ollama 本地免费
        return ModelResponse(
            content=text,
            input_tokens=getattr(usage, "prompt_tokens", 0),
            output_tokens=getattr(usage, "completion_tokens", 0),
            cost_cny=0.0,
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

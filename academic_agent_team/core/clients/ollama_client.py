"""
core/clients/ollama_client.py

Ollama 本地模型 client。
对齐 PRD Section 7.7 MODEL_REGISTRY。
Ollama 本地运行，费用为 0。
"""

from __future__ import annotations

import os
import time
from typing import Any

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class OllamaClient(BaseModelClient):
    """
    Ollama 本地 LLM client（REST API）。
    默认端点: http://localhost:11434
    """

    BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        api_key: str | None = None,  # Ollama 不需要 key，保留接口兼容
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", self.BASE_URL)).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3:8b")

    # ─── API ───────────────────────────────────────────────────────────────────

    def _call_api(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        url = f"{self.base_url}/api/chat"
        # 把 messages 转成 Ollama 格式
        ollama_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        body: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        req = urllib.request.Request(
            url,
            data=str(body).encode("utf-8"),  # Ollama 接受 JSON string
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Ollama API error {e.code}: {e.read().decode()}")
        latency_ms = int((time.time() - start) * 1000)

        import json as _json
        data = _json.loads(raw)

        # Ollama 返回: {"message": {"role": "assistant", "content": "..."}}
        message = data.get("message", {})
        text = message.get("content", "")
        stats = data.get("total_duration", {}) or {}

        # Ollama token 计数在不同版本不一致，用字符数估算
        input_tokens = sum(len(m["content"]) for m in messages) // 4
        output_tokens = len(text) // 4

        return {
            "content": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_cny": 0.0,  # 本地模型免费
            "model_id": f"ollama/{self.model}",
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
            import urllib.error
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

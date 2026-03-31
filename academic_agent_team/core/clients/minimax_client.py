from __future__ import annotations

import os
import time
import urllib.request
import json

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class MiniMaxClient(BaseModelClient):
    """
    MiniMax LLM client using Anthropic-compatible API.
    Endpoint: https://api.minimaxi.com/anthropic

    MiniMax-M2 uses extended thinking (thought chain) by default, which consumes
    output tokens. We disable it via 'thinking.skip=true' to ensure clean text output.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        self.base_url = base_url or os.environ.get(
            "ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"
        ).rstrip("/")
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2")

    def _call_api(self, messages: list[dict], system: str, temperature: float, max_tokens: int) -> dict:
        """Call MiniMax Anthropic-compatible endpoint."""
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Disable extended thinking so output tokens go to text only
            "thinking": {"type": "enabled", "skip": True},
        }
        if system:
            body["system"] = system

        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"MiniMax API error {e.code}: {err_body}")
        latency_ms = int((time.time() - start) * 1000)

        data = json.loads(raw)

        # MiniMax uses Anthropic response format; content is a list of blocks
        # Each block has type: "text" or "thinking"
        content_blocks = data.get("content", [])
        text = ""
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    break
            if not text:
                # Fallback: extract thinking content stripped of internal notes
                # MiniMax returns thinking blocks even when skip=True on some models
                thinking_parts = []
                for b in content_blocks:
                    if b.get("type") == "thinking":
                        raw = b.get("thinking", "")
                        lines = raw.strip().split("\n")
                        for line in reversed(lines):
                            stripped = line.strip()
                            if stripped and not stripped.startswith("But ") and not stripped.startswith("So "):
                                thinking_parts.append(stripped)
                                break
                        else:
                            if lines:
                                thinking_parts.append(lines[-1].strip())
                text = " ".join(filter(None, thinking_parts))
                if not text:
                    text = str(content_blocks)
        else:
            text = str(content_blocks)

        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Rough cost estimate for MiniMax-M2 (CNY per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * 1.0
        output_cost = (output_tokens / 1_000_000) * 4.0
        cost_cny = input_cost + output_cost

        return {
            "content": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_cny": round(cost_cny, 6),
            "model_id": self.model,
            "latency_ms": latency_ms,
        }

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 8192,
    ) -> ModelResponse:
        messages = []
        messages.append({"role": "user", "content": prompt})
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
            messages = [{"role": "user", "content": "hi"}]
            self._call_api(messages, "", 0.5, 10)
            return True
        except Exception:
            return False

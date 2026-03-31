"""
core/clients/minimax_client.py

MiniMax LLM client（MiniMax-M2，MCP 兼容接口）。
对齐 PRD Section 7.7 MODEL_REGISTRY。

MiniMax-M2 使用 extended thinking（thought chain）默认开启，
消耗 output tokens。设置 thinking.skip=true 强制纯文本输出。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class MiniMaxClient(BaseModelClient):
    """
    MiniMax Anthropic-compatible API client.
    Endpoint: https://api.minimaxi.com/anthropic
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        self.base_url = (
            (base_url or os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"))
            .rstrip("/")
        )
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2")

    # ─── API ───────────────────────────────────────────────────────────────────

    def _call_api(
        self,
        messages: list[dict[str, str]],
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # MiniMax-M2 关闭 extended thinking，输出 token 全部用于文本
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

        # MiniMax Anthropic 兼容格式：content 是 block 列表
        text = self._extract_text(data.get("content", []))
        usage = data.get("usage", {})

        input_cost = (usage.get("input_tokens", 0) / 1_000_000) * 1.0
        output_cost = (usage.get("output_tokens", 0) / 1_000_000) * 4.0

        return {
            "content": text,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_cny": round(input_cost + output_cost, 6),
            "model_id": self.model,
            "latency_ms": latency_ms,
        }

    @staticmethod
    def _extract_text(content_blocks: list) -> str:
        """从 Anthropic block 格式中提取文本，fallback 到 thinking 内容。"""
        if not isinstance(content_blocks, list):
            return str(content_blocks)

        # 优先取 text block
        for block in content_blocks:
            if block.get("type") == "text":
                return block.get("text", "")

        # Fallback：提取 thinking block 的末尾行（去除 But/So 前缀）
        parts = []
        for block in content_blocks:
            if block.get("type") == "thinking":
                raw = block.get("thinking", "")
                lines = raw.strip().split("\n")
                # 取最后一行有意义的非指令内容
                for line in reversed(lines):
                    stripped = line.strip()
                    if stripped and not stripped.startswith(("But ", "So ", "And ")):
                        parts.append(stripped)
                        break
                else:
                    if lines:
                        parts.append(lines[-1].strip())
        return " ".join(filter(None, parts)) if parts else str(content_blocks)

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
            self._call_api([{"role": "user", "content": "hi"}], "", 0.5, 10)
            return True
        except Exception:
            return False

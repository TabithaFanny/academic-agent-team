from __future__ import annotations

import os
import time
from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class OpenAIClient(BaseModelClient):
    """OpenAI-compatible model client (supports DeepSeek, Qwen, local models, etc.)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "not-set")
        self.base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def _call_api(self, messages: list[dict], temperature: float, max_tokens: int) -> dict:
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            )

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        # Remove base_url trailing slash
        if self.base_url.endswith("/"):
            base = self.base_url[:-1]
        else:
            base = self.base_url

        # Detect if using OpenAI official API
        is_official = "api.openai.com" in base

        start = time.time()
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.time() - start) * 1000)

        usage = resp.usage
        # Pricing: DeepSeek is cheaper; use rough estimates
        if "deepseek" in self.model.lower():
            input_cost = (usage.prompt_tokens / 1_000_000) * 0.27  # $0.27/M input
            output_cost = (usage.completion_tokens / 1_000_000) * 1.1  # $1.1/M output
        elif is_official:
            input_cost = (usage.prompt_tokens / 1_000_000) * 0.15
            output_cost = (usage.completion_tokens / 1_000_000) * 0.60
        else:
            # Generic OpenAI-compatible
            input_cost = (usage.prompt_tokens / 1_000_000) * 0.50
            output_cost = (usage.completion_tokens / 1_000_000) * 1.50

        cost_cny = (input_cost + output_cost) * 7.2  # rough USD->CNY

        return {
            "content": resp.choices[0].message.content or "",
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "cost_cny": round(cost_cny, 6),
            "model_id": self.model,
            "latency_ms": latency_ms,
        }

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
        # Sync version for simplicity; use httpx/aiohttp for true async
        return self.complete(prompt, system, temperature, max_tokens)

    def health_check(self) -> bool:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            client.models.list()
            return True
        except Exception:
            return False

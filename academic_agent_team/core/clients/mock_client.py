from __future__ import annotations

from academic_agent_team.core.base_client import BaseModelClient, ModelResponse


class MockClient(BaseModelClient):
    """Local-only mock model client used for fast development and tests."""

    MOCK_RESPONSES = {
        "advisor": "{\"summary\": \"推荐方向2：制度视角 + AI 融合\", \"innovation_score\": 8.5}",
        "researcher": "{\"summary\": \"已整理20篇相关文献并完成验证\"}",
        "writer": "# 引言\n这是一篇关于社区治理 AI 分流的研究草稿。",
        "reviewer": "{\"verdict\": \"minor_revision\", \"overall_score\": 7.5}",
        "polisher": "{\"readability_before\": 3.1, \"readability_after\": 4.3}",
    }

    def _detect_agent_from_prompt(self, prompt: str) -> str:
        p = prompt.lower()
        if "advisor" in p or "选题" in prompt:
            return "advisor"
        if "research" in p or "文献" in prompt:
            return "researcher"
        if "review" in p or "审稿" in prompt:
            return "reviewer"
        if "polish" in p or "润色" in prompt:
            return "polisher"
        return "writer"

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        agent = self._detect_agent_from_prompt(prompt)
        return ModelResponse(
            content=self.MOCK_RESPONSES.get(agent, "Mock response"),
            input_tokens=100,
            output_tokens=50,
            cost_cny=0.0,
            model_id="mock",
            latency_ms=200,
        )

    async def complete_async(self, *args, **kwargs) -> ModelResponse:
        return self.complete(*args, **kwargs)

    def health_check(self) -> bool:
        return True

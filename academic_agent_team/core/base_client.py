from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelResponse:
    content: str
    input_tokens: int
    output_tokens: int
    cost_cny: float
    model_id: str
    latency_ms: int


class BaseModelClient(ABC):
    """Base interface for all model provider clients."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """Synchronous completion call."""

    @abstractmethod
    async def complete_async(self, *args, **kwargs) -> ModelResponse:
        """Asynchronous completion call."""

    @abstractmethod
    def health_check(self) -> bool:
        """Report whether the provider is available."""

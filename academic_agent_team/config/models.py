from __future__ import annotations

from dataclasses import dataclass

from academic_agent_team.core.clients.mock_client import MockClient


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    name: str
    model_id: str
    input_cny_per_1m: float
    output_cny_per_1m: float
    client_class: type


MODEL_REGISTRY = {
    "mock": {
        "client_class": MockClient,
        "models": {
            "default": {
                "id": "mock",
                "input_cny_per_1m": 0.0,
                "output_cny_per_1m": 0.0,
            }
        },
    }
}

AGENT_MODEL_MAP = {
    "advisor": ("mock", "default"),
    "researcher": ("mock", "default"),
    "writer": ("mock", "default"),
    "reviewer": ("mock", "default"),
    "polisher": ("mock", "default"),
}

FALLBACK_ORDER = [
    ("mock", "default"),
]


def get_model_spec(provider: str, name: str) -> ModelSpec:
    provider_info = MODEL_REGISTRY[provider]
    model_info = provider_info["models"][name]
    return ModelSpec(
        provider=provider,
        name=name,
        model_id=model_info["id"],
        input_cny_per_1m=model_info["input_cny_per_1m"],
        output_cny_per_1m=model_info["output_cny_per_1m"],
        client_class=provider_info["client_class"],
    )

"""
config/models.py

对齐 PRD Section 7.7 模型注册表。
新模型接入 = 加一个 MODEL_REGISTRY 条目 + 实现一个 client 类，Agent 代码零修改。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, is_dataclass
from typing import TYPE_CHECKING

from academic_agent_team.config.role_profiles import (
    AGENTS,
    DEFAULT_BUDGET_CAP_CNY,
    DEFAULT_ROLE_PROFILE,
    FALLBACK_ORDER,
    ROLE_FALLBACK,
    resolve_fallback_chain,
)

# Alias for backward compatibility
AGENT_MODEL_MAP = DEFAULT_ROLE_PROFILE

if TYPE_CHECKING:
    from academic_agent_team.core.base_client import BaseModelClient


# ─── ModelSpec ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelSpec:
    """
    单个模型实例的完整规格。
    所有 client 实现后在此注册，配方的变更不涉及 Agent 代码。
    """
    provider: str
    name: str
    model_id: str
    input_cny_per_1m: float
    output_cny_per_1m: float
    supports_streaming: bool = True
    supports_vision: bool = False
    max_tokens: int = 8192

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        in_cny = (input_tokens / 1_000_000) * self.input_cny_per_1m
        out_cny = (output_tokens / 1_000_000) * self.output_cny_per_1m
        return round(in_cny + out_cny, 6)

    def get_client_class(self) -> "BaseModelClient | None":
        """懒加载并返回对应的 client 类。"""
        return _lazy_client(self.provider, self.name)


# ─── Model Registry ───────────────────────────────────────────────────────────
# 对齐 PRD Section 7.7 MODEL_REGISTRY
# TODO: AnthropicClient / DeepSeekClient / ZhipuClient / OllamaClient 待实现（P1-1）

_loaded_clients: dict[str, type["BaseModelClient"]] = {}


def _load_client_class(path: str) -> type["BaseModelClient"] | None:
    """懒加载 client 类，失败返回 None（allow health_check 兜底 mock）。"""
    if path in _loaded_clients:
        return _loaded_clients[path]
    try:
        from importlib import import_module
        module_path, class_name = path.rsplit(".", 1)
        mod = import_module(module_path)
        cls = getattr(mod, class_name)
        _loaded_clients[path] = cls
        return cls
    except Exception:
        return None


def _lazy_client(provider: str, model_name: str) -> type["BaseModelClient"] | None:
    """根据 provider 懒加载对应 client 类。"""
    mapping = {
        "anthropic": "academic_agent_team.core.clients.anthropic_client.AnthropicClient",
        "openai":    "academic_agent_team.core.clients.openai_client.OpenAIClient",
        "deepseek":  "academic_agent_team.core.clients.deepseek_client.DeepSeekClient",
        "zhipu":     "academic_agent_team.core.clients.zhipu_client.ZhipuClient",
        "minimax":   "academic_agent_team.core.clients.minimax_client.MiniMaxClient",
        "ollama":    "academic_agent_team.core.clients.ollama_client.OllamaClient",
        "mock":      "academic_agent_team.core.clients.mock_client.MockClient",
    }
    path = mapping.get(provider)
    if not path:
        return None
    return _load_client_class(path)


# ─── MODEL_REGISTRY ──────────────────────────────────────────────────────────
# 对齐 PRD Section 7.7 表定价（统一 CNY 口径，1 USD ≈ 7.2 CNY）

MODEL_REGISTRY: dict[str, dict[str, ModelSpec]] = {}

_PROVIDER_DEFINITIONS: dict[str, list[tuple[str, str, float, float]]] = {
    "anthropic": [
        ("sonnet", "claude-sonnet-4-5",  21.6,  108.0),
        ("opus",   "claude-opus-4-5",    36.0,  180.0),
        ("haiku",  "claude-haiku-3-5",    7.2,   36.0),
    ],
    "openai": [
        ("gpt4o",      "gpt-4o",            18.0,   72.0),
        ("gpt4turbo",  "gpt-4-turbo-preview", 72.0, 216.0),
    ],
    "deepseek": [
        ("v3", "deepseek-chat", 0.27 * 7.2, 1.1 * 7.2),  # ¥/1M ≈ 2.02 in / 7.92 out
    ],
    "zhipu": [
        ("glm4flash",    "glm-4-flash", 1.0, 1.0),
        ("glm4flagship", "glm-4",      100.0, 100.0),
    ],
    "minimax": [
        ("default", os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2"), 1.0, 4.0),
    ],
    "ollama": [
        ("llama3", "llama3:8b", 0.0, 0.0),
    ],
    "mock": [
        ("default", "mock", 0.0, 0.0),
    ],
}

for provider, models in _PROVIDER_DEFINITIONS.items():
    MODEL_REGISTRY[provider] = {}
    for name, model_id, inp, out in models:
        MODEL_REGISTRY[provider][name] = ModelSpec(
            provider=provider,
            name=name,
            model_id=model_id,
            input_cny_per_1m=inp,
            output_cny_per_1m=out,
        )


# ─── Agent → Model 映射 ───────────────────────────────────────────────────────
# 默认 AGENT_MODEL_MAP：对齐 PRD 7.7（会话级可热切换）

def get_agent_default(agent: str) -> tuple[str, str]:
    """返回 Agent 的默认 (provider, model_name)。"""
    return DEFAULT_ROLE_PROFILE.get(agent, ("mock", "default"))


# ─── 查询接口 ─────────────────────────────────────────────────────────────────

def get_model_spec(provider: str, name: str) -> ModelSpec:
    """根据 provider + name 查找 ModelSpec，不存在则抛 KeyError。"""
    if provider not in MODEL_REGISTRY:
        raise KeyError(f"Unknown provider: {provider}")
    if name not in MODEL_REGISTRY[provider]:
        raise KeyError(f"Unknown model {name!r} in provider {provider!r}. "
                        f"Available: {list(MODEL_REGISTRY[provider].keys())}")
    return MODEL_REGISTRY[provider][name]


def list_providers() -> list[str]:
    return list(MODEL_REGISTRY.keys())


def list_models(provider: str) -> list[str]:
    return list(MODEL_REGISTRY.get(provider, {}).keys())

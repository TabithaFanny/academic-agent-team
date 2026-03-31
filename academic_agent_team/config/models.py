"""
模型注册表 — PRD 7.7 规格。

新模型接入 = 在 MODEL_REGISTRY 加一条 + 实现一个 client 类，Agent 代码零修改。
定价统一使用人民币口径（CNY），与 PRD 10.6 保持一致。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from academic_agent_team.core.base_client import BaseModelClient
from academic_agent_team.core.clients.anthropic_client import AnthropicClient
from academic_agent_team.core.clients.deepseek_client import DeepSeekClient
from academic_agent_team.core.clients.minimax_client import MiniMaxClient
from academic_agent_team.core.clients.mock_client import MockClient
from academic_agent_team.core.clients.ollama_client import OllamaClient
from academic_agent_team.core.clients.openai_client import OpenAIClient
from academic_agent_team.core.clients.zhipu_client import ZhipuClient


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    name: str
    model_id: str
    input_cny_per_1m: float
    output_cny_per_1m: float
    client_class: type


# ── 模型注册表（PRD 7.7 规格）────────────────────────────────────────────────

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
    },
    "anthropic": {
        "client_class": AnthropicClient,
        "models": {
            "sonnet": {
                "id": "claude-sonnet-4-5",
                "input_cny_per_1m": 21.6,
                "output_cny_per_1m": 108.0,
            },
            "haiku": {
                "id": "claude-haiku-3-5",
                "input_cny_per_1m": 7.2,
                "output_cny_per_1m": 36.0,
            },
        },
    },
    "openai": {
        "client_class": OpenAIClient,
        "models": {
            "gpt4o": {
                "id": "gpt-4o",
                "input_cny_per_1m": 18.0,
                "output_cny_per_1m": 72.0,
            },
            "gpt4turbo": {
                "id": "gpt-4-turbo-preview",
                "input_cny_per_1m": 72.0,
                "output_cny_per_1m": 216.0,
            },
        },
    },
    "deepseek": {
        "client_class": DeepSeekClient,
        "models": {
            "v3": {
                "id": "deepseek-chat",  # DeepSeek V3
                "input_cny_per_1m": 0.27,
                "output_cny_per_1m": 2.18,
            },
        },
    },
    "zhipu": {
        "client_class": ZhipuClient,
        "models": {
            "glm4flash": {
                "id": "glm-4-flash",
                "input_cny_per_1m": 1.0,
                "output_cny_per_1m": 1.0,
            },
        },
    },
    "minimax": {
        "client_class": MiniMaxClient,
        "models": {
            "default": {
                "id": os.environ.get("MINIMAX_MODEL", "MiniMax-M2"),
                "input_cny_per_1m": 1.0,
                "output_cny_per_1m": 4.0,
            }
        },
    },
    "ollama": {
        "client_class": OllamaClient,
        "models": {
            "llama3": {
                "id": os.environ.get("OLLAMA_MODEL", "llama3:8b"),
                "input_cny_per_1m": 0.0,
                "output_cny_per_1m": 0.0,
            },
        },
    },
}


# ── 各 Agent 默认模型分配（PRD 7.7 ROLE_PROFILE 规格）────────────────────────
# 推荐默认配置，可通过 `role set` 运行时切换

AGENT_MODEL_MAP = {
    "advisor":    ("anthropic", "sonnet"),
    "researcher": ("deepseek", "v3"),
    "writer":     ("anthropic", "sonnet"),
    "reviewer":   ("openai",   "gpt4o"),
    "polisher":   ("deepseek", "v3"),
}


# ── 角色级降级顺序（PRD 7.7 ROLE_FALLBACK 规格）─────────────────────────────

ROLE_FALLBACK = {
    "advisor":    [("anthropic", "sonnet"), ("openai", "gpt4o"), ("deepseek", "v3"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
    "researcher": [("deepseek",  "v3"),     ("openai", "gpt4o"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
    "writer":     [("anthropic", "sonnet"), ("deepseek", "v3"),  ("openai", "gpt4o"), ("ollama", "llama3")],
    "reviewer":   [("openai",   "gpt4o"),  ("anthropic", "sonnet"), ("deepseek", "v3"), ("ollama", "llama3")],
    "polisher":   [("deepseek",  "v3"),    ("openai", "gpt4o"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
}


# ── 全局降级顺序（无 agent 配置时的兜底）─────────────────────────────────────

FALLBACK_ORDER = [
    ("deepseek",  "v3"),
    ("openai",    "gpt4o"),
    ("anthropic", "sonnet"),
    ("ollama",    "llama3"),
    ("mock",      "default"),
]


def get_model_spec(provider: str, name: str) -> ModelSpec:
    """解析 MODEL_REGISTRY，返回 ModelSpec（不含实例化的 client）。"""
    if provider not in MODEL_REGISTRY:
        raise KeyError(f"Unknown provider: {provider}")
    provider_info = MODEL_REGISTRY[provider]
    if name not in provider_info["models"]:
        raise KeyError(f"Unknown model '{name}' for provider '{provider}'")
    model_info = provider_info["models"][name]
    return ModelSpec(
        provider=provider,
        name=name,
        model_id=model_info["id"],
        input_cny_per_1m=model_info["input_cny_per_1m"],
        output_cny_per_1m=model_info["output_cny_per_1m"],
        client_class=provider_info["client_class"],
    )


def get_client_for_agent(agent: str) -> BaseModelClient:
    """
    根据 AGENT_MODEL_MAP 为 agent 返回可用 client，
    失败时按 ROLE_FALLBACK → FALLBACK_ORDER 降级。
    """
    if agent not in AGENT_MODEL_MAP:
        raise ValueError(f"Unknown agent: {agent}")

    # agent 专属降级链
    fallback_chain = ROLE_FALLBACK.get(agent, FALLBACK_ORDER)

    tried: list[str] = []
    for provider, name in fallback_chain:
        try:
            spec = get_model_spec(provider, name)
            client = spec.client_class()
            if client.health_check():
                print(f"[{agent}] provider={provider} model={spec.model_id}")
                return client
        except Exception as e:
            tried.append(f"{provider}/{name}({e})")

    raise RuntimeError(
        f"No available model client for agent '{agent}'. Tried: {tried}"
    )


def build_role_profile() -> dict:
    """根据 AGENT_MODEL_MAP 构建当前角色配置快照（用于入库）。"""
    return {
        agent: {"provider": p, "model": m}
        for agent, (p, m) in AGENT_MODEL_MAP.items()
    }

"""
config/role_profiles.py

对齐 PRD Section 7.7 模型路由策略。
支持会话级角色配置热切换，不改任何 Agent 代码。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


# ─── Agent 角色名常量 ────────────────────────────────────────────────────────

AGENTS = (
    "advisor",
    "researcher",
    "writer",
    "reviewer",
    "polisher",
    "visualizer",  # v1.1
)


# ─── Provider / Model 定义 ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelConfig:
    """单个模型的定价和元信息。"""
    provider: str          # "anthropic" | "openai" | "deepseek" | "zhipu" | "minimax" | "ollama" | "mock"
    name: str              # 注册表内的模型名（不是 API model_id）
    model_id: str          # API 实际使用的 ID
    input_cny_per_1m: float
    output_cny_per_1m: float
    supports_streaming: bool = True
    supports_vision: bool = False
    max_tokens: int = 8192


# ─── Role Profile ────────────────────────────────────────────────────────────
# 默认角色配置：对齐 PRD 7.7 ROLE_PROFILE
# 用户可在会话中通过 /role set 覆盖，仅影响后续阶段

RoleProfile = dict[str, tuple[str, str]]  # {agent: (provider, model_name)}


DEFAULT_ROLE_PROFILE: RoleProfile = {
    "advisor":     ("anthropic", "sonnet"),
    "researcher":  ("deepseek",  "v3"),
    "writer":      ("anthropic", "sonnet"),
    "reviewer":    ("openai",    "gpt4o"),
    "polisher":    ("deepseek",  "v3"),
    "visualizer":  ("openai",    "gpt4o"),  # v1.1
}


# ─── Role Fallback Chain ─────────────────────────────────────────────────────
# 对齐 PRD 7.7 ROLE_FALLBACK
# 主模型不可用时按此顺序降级

ROLE_FALLBACK: dict[str, list[tuple[str, str]]] = {
    "advisor": [
        ("anthropic", "sonnet"),
        ("openai",    "gpt4o"),
        ("deepseek",  "v3"),
        ("ollama",    "llama3"),
    ],
    "researcher": [
        ("deepseek",  "v3"),
        ("openai",    "gpt4o"),
        ("zhipu",     "glm4flash"),
        ("ollama",    "llama3"),
    ],
    "writer": [
        ("anthropic", "sonnet"),
        ("deepseek",  "v3"),
        ("openai",    "gpt4o"),
        ("ollama",    "llama3"),
    ],
    "reviewer": [
        ("openai",    "gpt4o"),
        ("anthropic", "sonnet"),
        ("deepseek",  "v3"),
        ("ollama",    "llama3"),
    ],
    "polisher": [
        ("deepseek",  "v3"),
        ("openai",    "gpt4o"),
        ("zhipu",     "glm4flash"),
        ("ollama",    "llama3"),
    ],
    "visualizer": [
        ("openai",    "gpt4o"),
        ("anthropic", "sonnet"),
    ],
}


# ─── 全局降级顺序 ────────────────────────────────────────────────────────────

FALLBACK_ORDER = [
    ("anthropic", "sonnet"),
    ("openai",    "gpt4o"),
    ("deepseek",  "v3"),
    ("ollama",    "llama3"),
]


# ─── 预算上限 ────────────────────────────────────────────────────────────────

DEFAULT_BUDGET_CAP_CNY: float = 35.0  # 对齐 PRD 7.5 cost_limit_per_paper_cny


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def build_role_profile_snapshot(
    profile: RoleProfile | None = None,
) -> dict[str, dict[str, str]]:
    """
    序列化 role profile 为 dict（存入 sessions.model_config）。
    格式: {"advisor": {"provider": "anthropic", "model": "sonnet"}, ...}
    """
    src = profile or DEFAULT_ROLE_PROFILE
    return {
        agent: {"provider": prov, "model": name}
        for agent, (prov, name) in src.items()
    }


# Alias for backward compatibility
build_role_profile = build_role_profile_snapshot


def parse_role_profile_snapshot(
    snapshot: dict,
) -> RoleProfile:
    """从 sessions.model_config JSON 反序列化回 RoleProfile。"""
    return {
        agent: (d["provider"], d["model"])
        for agent, d in snapshot.items()
    }


def resolve_fallback_chain(agent: str) -> list[tuple[str, str]]:
    """返回指定 agent 的降级链，fallback 到全局 FALLBACK_ORDER。"""
    return ROLE_FALLBACK.get(agent, FALLBACK_ORDER)

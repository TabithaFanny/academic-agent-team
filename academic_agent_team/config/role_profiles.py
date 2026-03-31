"""
角色配置（Role Profiles）— PRD 7.7 规格。

支持会话中运行时切换角色模型配置。
配置文件可通过 paper-team role --set 命令修改。
"""

from __future__ import annotations

import json
from pathlib import Path

from academic_agent_team.config.models import AGENT_MODEL_MAP, ROLE_FALLBACK

# ── 预定义角色配置 ─────────────────────────────────────────────────────────────

ROLE_PROFILES = {
    # 平衡档（推荐）：DeepSeek 主力 + Claude/GPT 关键节点
    "balanced": {
        "advisor":    ("anthropic", "sonnet"),
        "researcher": ("deepseek",  "v3"),
        "writer":     ("anthropic", "sonnet"),
        "reviewer":   ("openai",    "gpt4o"),
        "polisher":   ("deepseek",  "v3"),
        "description": "推荐配置：DeepSeek 主力跑文献和润色，Claude/GPT 跑选题和审稿，平衡质量与成本",
    },

    # 经济档：DeepSeek 全流程，极致性价比
    "economy": {
        "advisor":    ("deepseek", "v3"),
        "researcher": ("deepseek", "v3"),
        "writer":     ("deepseek", "v3"),
        "reviewer":   ("deepseek", "v3"),
        "polisher":   ("deepseek",  "v3"),
        "description": "经济配置：DeepSeek 全流程，单篇成本 ¥0.3-0.8，适合打底稿",
    },

    # 质量档：Claude/GPT 主力，多轮审稿打磨
    "quality": {
        "advisor":    ("anthropic", "sonnet"),
        "researcher": ("openai",    "gpt4turbo"),
        "writer":     ("anthropic", "sonnet"),
        "reviewer":   ("openai",   "gpt4o"),
        "polisher":   ("anthropic", "sonnet"),
        "description": "质量配置：Claude/GPT 主力，单篇成本 ¥6-12，适合高要求投稿前打磨",
    },

    # 本地档：Ollama 全本地，免费但需 GPU
    "local": {
        "advisor":    ("ollama", "llama3"),
        "researcher": ("ollama", "llama3"),
        "writer":     ("ollama", "llama3"),
        "reviewer":   ("ollama", "llama3"),
        "polisher":   ("ollama", "llama3"),
        "description": "本地配置：Ollama 全流程，免费，需本地 GPU 部署",
    },
}


def load_profile(name: str) -> dict:
    """加载预定义角色配置。"""
    if name not in ROLE_PROFILES:
        raise KeyError(
            f"Unknown profile '{name}'. "
            f"Available: {list(ROLE_PROFILES.keys())}"
        )
    return ROLE_PROFILES[name].copy()


def apply_profile(name: str) -> None:
    """将预定义配置应用到 AGENT_MODEL_MAP（全局状态）。"""
    profile = load_profile(name)
    # 去掉 description 字段，只保留 agent 映射
    for agent in AGENT_MODEL_MAP:
        if agent in profile and agent in ROLE_FALLBACK:
            AGENT_MODEL_MAP[agent] = profile[agent]


def show_profiles() -> None:
    """打印所有预定义配置。"""
    for name, profile in ROLE_PROFILES.items():
        print(f"\n【{name}】 — {profile['description']}")
        for agent, (p, m) in profile.items():
            if agent != "description":
                print(f"  {agent:<12} → {p}/{m}")


def load_runtime_role_map(base_dir: Path) -> dict[str, tuple[str, str]]:
    """
    读取 runtime 角色配置（跨进程持久化）。
    文件不存在或格式非法时回退到 AGENT_MODEL_MAP 当前值。
    """
    path = base_dir / "session_store" / "role_profile.json"
    if not path.exists():
        return dict(AGENT_MODEL_MAP)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(AGENT_MODEL_MAP)

    resolved: dict[str, tuple[str, str]] = {}
    for agent in AGENT_MODEL_MAP:
        value = data.get(agent)
        if isinstance(value, list) and len(value) == 2:
            resolved[agent] = (str(value[0]), str(value[1]))
        elif isinstance(value, tuple) and len(value) == 2:
            resolved[agent] = (str(value[0]), str(value[1]))
        else:
            resolved[agent] = AGENT_MODEL_MAP[agent]
    return resolved


def save_runtime_role_map(base_dir: Path, role_map: dict[str, tuple[str, str]]) -> Path:
    """保存 runtime 角色配置到 `session_store/role_profile.json`。"""
    path = base_dir / "session_store" / "role_profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {agent: [provider, model] for agent, (provider, model) in role_map.items()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

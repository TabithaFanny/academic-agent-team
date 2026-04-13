"""
Plugins 模块初始化。
"""

from academic_agent_team.plugins.base import (
    BasePlugin,
    PluginInterface,
    PluginRegistry,
    plugin_registry,
)

__all__ = [
    "BasePlugin",
    "PluginInterface",
    "PluginRegistry",
    "plugin_registry",
]

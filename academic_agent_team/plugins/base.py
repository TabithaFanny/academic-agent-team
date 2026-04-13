"""
插件基类 — 定义可热加载插件接口。

符合 PRD F106 插件系统要求。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class PluginInterface(Protocol):
    """插件接口协议 — 所有插件必须实现。"""
    
    name: str
    version: str
    description: str
    
    def register_tools(self) -> list[Callable[..., Any]]:
        """返回插件提供的工具函数列表，用于 Agent Tool Calling。"""
        ...
    
    def health_check(self) -> bool:
        """检查插件是否可用。"""
        ...
    
    def cleanup(self) -> None:
        """清理插件资源。"""
        ...


class BasePlugin(ABC):
    """插件基类 — 提供通用实现。"""
    
    name: str = "base"
    version: str = "0.1.0"
    description: str = "Base plugin"
    
    def __init__(self):
        self._tools: list[Callable[..., Any]] = []
        self._initialized = False
    
    @abstractmethod
    def _register_tools(self) -> list[Callable[..., Any]]:
        """子类实现：注册工具函数。"""
        ...
    
    def register_tools(self) -> list[Callable[..., Any]]:
        """返回插件工具列表。"""
        if not self._initialized:
            self._tools = self._register_tools()
            self._initialized = True
        return self._tools
    
    def health_check(self) -> bool:
        """默认健康检查。"""
        return True
    
    def cleanup(self) -> None:
        """默认清理。"""
        self._tools = []
        self._initialized = False


class PluginRegistry:
    """插件注册表 — 管理所有已加载插件。"""
    
    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
    
    def register(self, plugin: BasePlugin) -> None:
        """注册插件。"""
        self._plugins[plugin.name] = plugin
    
    def unregister(self, name: str) -> None:
        """注销插件。"""
        if name in self._plugins:
            self._plugins[name].cleanup()
            del self._plugins[name]
    
    def get(self, name: str) -> BasePlugin | None:
        """获取插件。"""
        return self._plugins.get(name)
    
    def get_all_tools(self) -> list[Callable[..., Any]]:
        """获取所有插件的工具列表。"""
        tools = []
        for plugin in self._plugins.values():
            if plugin.health_check():
                tools.extend(plugin.register_tools())
        return tools
    
    def health_check_all(self) -> dict[str, bool]:
        """检查所有插件健康状态。"""
        return {name: plugin.health_check() for name, plugin in self._plugins.items()}


# 全局插件注册表
plugin_registry = PluginRegistry()

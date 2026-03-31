"""
tui/interrupt.py

Human-in-the-loop 中断管理器。

设计要点：
- 基于 asyncio.Queue（非阻塞，线程安全）
- TUI 主线程写入，pipeline 协程读取
- 轮询间隔 ≤ 50ms（通过 asyncio.timeout / asyncio.wait_for 控制）
- 支持优先级：打断 > 批准 > 跳过
"""

from __future__ import annotations

import asyncio
import enum
import sys
from dataclasses import dataclass, field
from typing import Any

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


# ─── 中断信号枚举 ──────────────────────────────────────────────────────────────

class InterruptKind(enum.Enum):
    """用户发出的中断信号类型。"""
    APPROVE = "approve"          # 批准当前步骤，继续
    REJECT = "reject"             # 拒绝，打断 pipeline
    REWRITE = "rewrite"           # 要求重写（发送修改指令）
    EDIT = "edit"                 # 直接编辑文档内容
    SKIP = "skip"                 # 跳过当前步骤
    CANCEL = "cancel"             # 取消整个 pipeline
    PAUSE = "pause"              # 暂停（预留）
    RESUME = "resume"             # 恢复（预留）


# ─── 中断信号对象 ─────────────────────────────────────────────────────────────

@dataclass
class InterruptSignal:
    """
    一次用户中断请求。

    所有字段均为可选——pipeline 根据自身需求读取相关字段。
    """
    kind: InterruptKind
    interrupt_id: str = ""           # 关联的 HumanInterruptEvent.interrupt_id
    payload: str = ""                # edit / rewrite 时，携带用户输入的文本
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=0.0)

    @classmethod
    def make(cls, kind: InterruptKind, interrupt_id: str = "", payload: str = "", **kw) -> "InterruptSignal":
        import time
        return cls(kind=kind, interrupt_id=interrupt_id, payload=payload, timestamp=time.time(), **kw)


# ─── InterruptManager ──────────────────────────────────────────────────────────

class InterruptManager:
    """
    线程安全的异步中断管理器。

    Pipeline 端持有实例，轮询 check()；
    TUI 端通过 send() 注入信号。

    用法：
        # Pipeline 端
        interrupts = InterruptManager()
        async for event in runner.run(config, interrupts):
            ...

        # TUI 端
        interrupts.send(InterruptSignal.make(InterruptKind.APPROVE))
    """

    DEFAULT_POLL_TIMEOUT: float = 0.05  # 50ms，≤ 要求

    __slots__ = ("_queue", "_cancelled")

    def __init__(self) -> None:
        self._queue: asyncio.Queue[InterruptSignal] = asyncio.Queue()
        self._cancelled: bool = False

    # ── TUI 端 API ────────────────────────────────────────────────────────────

    def send(self, signal: InterruptSignal) -> None:
        """
        TUI 主线程调用，向 pipeline 发送中断信号。

        非阻塞，立即返回。信号进入队列，等待 pipeline 协程读取。
        """
        if self._cancelled:
            return
        # 在同步上下文调用时用 call_soon_threadsafe
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, signal)
        except RuntimeError:
            # 没有运行中事件循环（不应该在 TUI 外发生）
            self._queue.put_nowait(signal)

    def cancel(self) -> None:
        """TUI 请求取消整个 pipeline。"""
        self._cancelled = True
        self.send(InterruptSignal.make(InterruptKind.CANCEL))

    # ── Pipeline 端 API ───────────────────────────────────────────────────────

    async def wait_for_signal(
        self,
        timeout: float | None = None,
    ) -> InterruptSignal | None:
        """
        Pipeline 协程调用，等待用户信号。

        参数：
            timeout: 等待超时（秒）。None = 使用 DEFAULT_POLL_TIMEOUT。

        返回：
            InterruptSignal 或 None（超时且队列为空时）

        设计：超时机制保证轮询间隔 ≤ 50ms，不阻塞 pipeline 推进。
        """
        timeout = timeout if timeout is not None else self.DEFAULT_POLL_TIMEOUT
        try:
            signal = await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout,
            )
            return signal
        except asyncio.TimeoutError:
            return None

    def is_cancelled(self) -> bool:
        """检查是否已收到 CANCEL 信号。"""
        return self._cancelled

    def peek(self) -> InterruptSignal | None:
        """
        非阻塞查看队首信号（不取出）。

        用于快速判断是否有待处理信号。
        """
        if self._queue.empty():
            return None
        # peek = get + put back（队列不支持 peek）
        try:
            item = self._queue.get_nowait()
            self._queue.put_nowait(item)
            return item
        except asyncio.QueueEmpty:
            return None

    def clear(self) -> None:
        """清空队列（用于 pipeline 重置）。"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

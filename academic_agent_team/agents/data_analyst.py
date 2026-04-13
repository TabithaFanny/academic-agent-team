"""数据分析师 Agent — 基于 AutoGen 0.7 AssistantAgent。

提供数据分析、图表生成、统计摘要等功能，运行在安全沙箱中。
"""

from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from autogen_agentchat.agents import AssistantAgent

if TYPE_CHECKING:
    from autogen_core import ChatCompletionClient


# ── 输出数据结构 ─────────────────────────────────────────────────────────────

@dataclass
class Figure:
    """图表输出结构。"""
    path: str
    caption: str
    type: Literal["line", "bar", "scatter", "histogram", "pie", "heatmap", "boxplot", "other"]


@dataclass
class StatisticalTable:
    """统计表格输出结构。"""
    name: str
    data: dict[str, Any]
    description: str


@dataclass
class AnalysisResult:
    """分析结果输出结构。"""
    summary: str
    figures: list[Figure] = field(default_factory=list)
    tables: list[StatisticalTable] = field(default_factory=list)
    code_used: str = ""
    success: bool = True
    error_message: str | None = None


# ── 安全沙箱 ────────────────────────────────────────────────────────────────

class SafeExecutionError(Exception):
    """沙箱执行错误。"""
    pass


class SecureSandbox:
    """
    安全执行沙箱。

    限制只能使用以下模块：
    - pandas (as pd)
    - numpy (as np)
    - matplotlib.pyplot (as plt)
    - seaborn (as sns)

    禁止：
    - 文件系统访问（除指定 data_path）
    - 网络访问
    - 系统调用
    - 危险内置函数
    """

    # 允许的内置函数白名单
    SAFE_BUILTINS = {
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "frozenset", "int", "isinstance", "issubclass", "iter", "len", "list",
        "map", "max", "min", "next", "pow", "print", "range", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip",
        "True", "False", "None",
    }

    # 禁止的危险属性和模块
    FORBIDDEN_NAMES = {
        "__import__", "eval", "exec", "compile", "open", "file", "input",
        "raw_input", "execfile", "reload", "__builtins__", "globals", "locals",
        "vars", "dir", "getattr", "setattr", "delattr", "hasattr",
        "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
        "importlib", "pickle", "marshal", "ctypes", "multiprocessing",
    }

    def __init__(self, allowed_data_paths: list[str] | None = None, output_dir: str = "output"):
        """
        初始化安全沙箱。

        Args:
            allowed_data_paths: 允许访问的数据路径列表
            output_dir: 图表输出目录
        """
        self.allowed_data_paths = [Path(p).resolve() for p in (allowed_data_paths or [])]
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _create_safe_builtins(self) -> dict[str, Any]:
        """创建安全的内置函数字典。"""
        import builtins
        safe = {}
        for name in self.SAFE_BUILTINS:
            if hasattr(builtins, name):
                safe[name] = getattr(builtins, name)
        return safe

    def _is_path_allowed(self, path: str) -> bool:
        """检查路径是否在允许列表中。"""
        resolved = Path(path).resolve()
        for allowed in self.allowed_data_paths:
            try:
                resolved.relative_to(allowed)
                return True
            except ValueError:
                continue
            if resolved == allowed:
                return True
        return False

    def _create_safe_open(self, data_path: str) -> Any:
        """创建受限的 open 函数，只允许读取指定数据文件。"""
        allowed_path = Path(data_path).resolve()

        def safe_open(file: str, mode: str = "r", *args, **kwargs):
            resolved = Path(file).resolve()
            # 只允许读取模式
            if "w" in mode or "a" in mode or "x" in mode:
                raise SafeExecutionError(f"写入文件被禁止: {file}")
            # 只允许访问指定数据路径
            if resolved != allowed_path and not self._is_path_allowed(str(resolved)):
                raise SafeExecutionError(f"文件访问被拒绝: {file}")
            return open(file, mode, *args, **kwargs)

        return safe_open

    def execute(self, code: str, data_path: str) -> tuple[dict[str, Any], str]:
        """
        在安全沙箱中执行代码。

        Args:
            code: 要执行的 Python 代码
            data_path: 允许访问的数据文件路径

        Returns:
            tuple: (命名空间字典, 输出字符串)

        Raises:
            SafeExecutionError: 执行失败或安全违规
        """
        # 检查危险名称
        for forbidden in self.FORBIDDEN_NAMES:
            if forbidden in code:
                raise SafeExecutionError(f"禁止使用: {forbidden}")

        # 延迟导入以减少启动时间
        try:
            import pandas as pd
            import numpy as np
            import matplotlib
            matplotlib.use("Agg")  # 非交互式后端
            import matplotlib.pyplot as plt
            import seaborn as sns
        except ImportError as e:
            raise SafeExecutionError(f"缺少必要依赖: {e}")

        # 捕获输出
        output_buffer = io.StringIO()

        # 创建安全命名空间
        safe_globals = {
            "__builtins__": self._create_safe_builtins(),
            "pd": pd,
            "np": np,
            "plt": plt,
            "sns": sns,
            "open": self._create_safe_open(data_path),
            "DATA_PATH": data_path,
            "OUTPUT_DIR": str(self.output_dir),
            "print": lambda *args, **kwargs: print(*args, **kwargs, file=output_buffer),
        }

        safe_locals: dict[str, Any] = {}

        try:
            # 编译并执行代码
            compiled = compile(code, "<analysis>", "exec")
            exec(compiled, safe_globals, safe_locals)
        except SafeExecutionError:
            raise
        except Exception as e:
            raise SafeExecutionError(f"执行错误: {type(e).__name__}: {e}")

        return safe_locals, output_buffer.getvalue()


# ── 数据分析师 Agent ──────────────────────────────────────────────────────────

DATA_ANALYST_SYSTEM_PROMPT = """你是一位专业的数据分析师，擅长使用 Python 进行数据分析、可视化和统计建模。

你的能力包括：
1. 数据清洗和预处理
2. 描述性统计分析
3. 数据可视化（matplotlib, seaborn）
4. 相关性分析
5. 假设检验
6. 回归分析

可用的库：
- pandas (as pd)
- numpy (as np)
- matplotlib.pyplot (as plt)
- seaborn (as sns)

代码约束：
- 数据文件路径通过 DATA_PATH 变量获取
- 图表保存到 OUTPUT_DIR 目录
- 禁止使用 os、sys 等系统模块
- 禁止网络访问

输出格式：严格以 JSON 格式输出，字段：
- analysis_type: str（分析类型：descriptive/correlation/regression/visualization）
- code: str（完整的 Python 代码）
- interpretation: str（结果解读，200-500字）
- key_findings: list[str]（主要发现，3-5条）
"""


class DataAnalystAgent(AssistantAgent):
    """数据分析师 Agent — 执行数据分析、生成图表和统计摘要。"""

    name = "data_analyst"
    description = "数据分析师：执行数据分析、生成图表、提供统计摘要"

    def __init__(
        self,
        model_client: "ChatCompletionClient",
        output_dir: str = "output/figures",
    ):
        """
        初始化数据分析师 Agent。

        Args:
            model_client: AutoGen 模型客户端
            output_dir: 图表输出目录
        """
        super().__init__(
            name=self.name,
            model_client=model_client,
            system_message=DATA_ANALYST_SYSTEM_PROMPT,
            description=self.description,
            handoffs=["writer", "reviewer"],
        )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._sandbox: SecureSandbox | None = None

    def _get_sandbox(self, data_path: str) -> SecureSandbox:
        """获取或创建沙箱实例。"""
        if self._sandbox is None or data_path not in [str(p) for p in self._sandbox.allowed_data_paths]:
            self._sandbox = SecureSandbox(
                allowed_data_paths=[data_path],
                output_dir=str(self.output_dir),
            )
        return self._sandbox

    def execute_analysis(self, code: str, data_path: str) -> AnalysisResult:
        """
        在安全沙箱中执行分析代码。

        Args:
            code: 要执行的 Python 分析代码
            data_path: 数据文件路径

        Returns:
            AnalysisResult: 分析结果
        """
        # 验证数据路径存在
        if not Path(data_path).exists():
            return AnalysisResult(
                summary="",
                code_used=code,
                success=False,
                error_message=f"数据文件不存在: {data_path}",
            )

        sandbox = self._get_sandbox(data_path)

        try:
            namespace, output = sandbox.execute(code, data_path)

            # 收集生成的图表
            figures = self._collect_figures(namespace, output)

            # 收集统计表格
            tables = self._collect_tables(namespace)

            return AnalysisResult(
                summary=output or "分析执行完成",
                figures=figures,
                tables=tables,
                code_used=code,
                success=True,
            )

        except SafeExecutionError as e:
            return AnalysisResult(
                summary="",
                code_used=code,
                success=False,
                error_message=str(e),
            )

    def _collect_figures(self, namespace: dict[str, Any], output: str) -> list[Figure]:
        """从命名空间收集生成的图表。"""
        figures = []

        # 检查是否有保存的图表
        import matplotlib.pyplot as plt

        # 获取当前所有 figure
        fig_nums = plt.get_fignums()
        for i, num in enumerate(fig_nums):
            fig = plt.figure(num)
            fig_id = str(uuid.uuid4())[:8]
            fig_path = self.output_dir / f"figure_{fig_id}.png"
            fig.savefig(fig_path, dpi=150, bbox_inches="tight")
            figures.append(Figure(
                path=str(fig_path),
                caption=f"Figure {i + 1}",
                type="other",
            ))
            plt.close(fig)

        # 检查命名空间中显式定义的 figure 变量
        if "figures" in namespace and isinstance(namespace["figures"], list):
            for fig_info in namespace["figures"]:
                if isinstance(fig_info, dict):
                    figures.append(Figure(
                        path=fig_info.get("path", ""),
                        caption=fig_info.get("caption", ""),
                        type=fig_info.get("type", "other"),
                    ))

        return figures

    def _collect_tables(self, namespace: dict[str, Any]) -> list[StatisticalTable]:
        """从命名空间收集统计表格。"""
        tables = []

        # 查找 DataFrame 类型的变量
        try:
            import pandas as pd
            for name, value in namespace.items():
                if isinstance(value, pd.DataFrame) and not name.startswith("_"):
                    tables.append(StatisticalTable(
                        name=name,
                        data=value.to_dict(),
                        description=f"DataFrame: {value.shape[0]} rows × {value.shape[1]} columns",
                    ))
        except ImportError:
            pass

        # 检查显式定义的 tables 变量
        if "tables" in namespace and isinstance(namespace["tables"], list):
            for tbl_info in namespace["tables"]:
                if isinstance(tbl_info, dict):
                    tables.append(StatisticalTable(
                        name=tbl_info.get("name", "unnamed"),
                        data=tbl_info.get("data", {}),
                        description=tbl_info.get("description", ""),
                    ))

        return tables

    def generate_chart(
        self,
        data: Any,
        chart_type: Literal["line", "bar", "scatter", "histogram", "pie", "heatmap", "boxplot"],
        title: str,
        **kwargs: Any,
    ) -> Figure:
        """
        生成指定类型的图表。

        Args:
            data: 数据（pandas DataFrame 或 dict）
            chart_type: 图表类型
            title: 图表标题
            **kwargs: 传递给绑定绑定库的额外参数

        Returns:
            Figure: 生成的图表信息
        """
        try:
            import pandas as pd
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns
        except ImportError as e:
            raise SafeExecutionError(f"缺少必要依赖: {e}")

        # 转换数据为 DataFrame
        if isinstance(data, dict):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            raise ValueError(f"不支持的数据类型: {type(data)}")

        # 创建图表
        fig, ax = plt.subplots(figsize=kwargs.get("figsize", (10, 6)))

        x = kwargs.get("x")
        y = kwargs.get("y")

        if chart_type == "line":
            if x and y:
                ax.plot(df[x], df[y], **{k: v for k, v in kwargs.items() if k not in ("x", "y", "figsize")})
            else:
                df.plot(ax=ax)
        elif chart_type == "bar":
            if x and y:
                ax.bar(df[x], df[y], **{k: v for k, v in kwargs.items() if k not in ("x", "y", "figsize")})
            else:
                df.plot.bar(ax=ax)
        elif chart_type == "scatter":
            if x and y:
                ax.scatter(df[x], df[y], **{k: v for k, v in kwargs.items() if k not in ("x", "y", "figsize")})
            else:
                raise ValueError("scatter 图需要指定 x 和 y 列")
        elif chart_type == "histogram":
            column = kwargs.get("column") or (df.columns[0] if len(df.columns) > 0 else None)
            if column:
                ax.hist(df[column], bins=kwargs.get("bins", 30))
        elif chart_type == "pie":
            values = kwargs.get("values")
            labels = kwargs.get("labels")
            if values and labels:
                ax.pie(df[values], labels=df[labels], autopct="%1.1f%%")
            else:
                raise ValueError("pie 图需要指定 values 和 labels 列")
        elif chart_type == "heatmap":
            sns.heatmap(df.corr() if kwargs.get("correlation", True) else df, ax=ax, annot=True, cmap="coolwarm")
        elif chart_type == "boxplot":
            df.boxplot(ax=ax)

        ax.set_title(title)
        plt.tight_layout()

        # 保存图表
        fig_id = str(uuid.uuid4())[:8]
        fig_path = self.output_dir / f"{chart_type}_{fig_id}.png"
        fig.savefig(fig_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return Figure(
            path=str(fig_path),
            caption=title,
            type=chart_type,
        )

    def statistical_summary(self, data: Any) -> StatisticalTable:
        """
        生成数据的统计摘要。

        Args:
            data: 数据（pandas DataFrame、dict 或文件路径）

        Returns:
            StatisticalTable: 统计摘要表格
        """
        try:
            import pandas as pd
            import numpy as np
        except ImportError as e:
            raise SafeExecutionError(f"缺少必要依赖: {e}")

        # 加载数据
        if isinstance(data, str):
            # 假定是文件路径
            path = Path(data)
            if path.suffix == ".csv":
                df = pd.read_csv(path)
            elif path.suffix in (".xls", ".xlsx"):
                df = pd.read_excel(path)
            elif path.suffix == ".json":
                df = pd.read_json(path)
            else:
                raise ValueError(f"不支持的文件格式: {path.suffix}")
        elif isinstance(data, dict):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            raise ValueError(f"不支持的数据类型: {type(data)}")

        # 基础统计量
        summary_stats = {
            "shape": {"rows": df.shape[0], "columns": df.shape[1]},
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
            "missing_percentage": (df.isnull().sum() / len(df) * 100).round(2).to_dict(),
        }

        # 数值列统计
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            desc = df[numeric_cols].describe()
            summary_stats["descriptive"] = desc.to_dict()

            # 相关性矩阵（如果有多个数值列）
            if len(numeric_cols) > 1:
                corr = df[numeric_cols].corr()
                summary_stats["correlation"] = corr.to_dict()

        # 分类列统计
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        if categorical_cols:
            cat_stats = {}
            for col in categorical_cols:
                value_counts = df[col].value_counts()
                cat_stats[col] = {
                    "unique_count": df[col].nunique(),
                    "top_values": value_counts.head(5).to_dict(),
                }
            summary_stats["categorical"] = cat_stats

        # 构建描述
        description_parts = [
            f"数据集包含 {df.shape[0]} 行 × {df.shape[1]} 列。",
            f"数值列: {len(numeric_cols)} 个，分类列: {len(categorical_cols)} 个。",
        ]
        missing_total = df.isnull().sum().sum()
        if missing_total > 0:
            description_parts.append(f"缺失值总数: {missing_total}。")

        return StatisticalTable(
            name="statistical_summary",
            data=summary_stats,
            description=" ".join(description_parts),
        )

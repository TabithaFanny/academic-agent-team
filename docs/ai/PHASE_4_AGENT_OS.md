# Phase 4: Agent Operating System

> **状态**: 🔄 进行中  
> **门禁**: 待人类确认  
> **创建时间**: 2026-04-08  
> **前置**: Phase 3 架构已批准，编码禁令已解除

---

## 1. Agent 角色定义

### 1.1 学术论文 Agent 团队

| 角色 | 职责 | 输入 | 输出 | 参与 GroupChat |
|------|------|------|------|----------------|
| **Advisor** | 选题分析、方向推荐 | topic + journal | TopicDone | 选题讨论组 |
| **Researcher** | 文献搜索、RAG 综述 | 研究方向 | LiteratureDone | 选题讨论组 |
| **Writer** | 论文各章节撰写 | 文献综述 | WritingDone | 写作-审稿组 |
| **Reviewer** | 审稿、修改意见 | 论文初稿 | ReviewDone | 写作-审稿组 + 润色终审组 |
| **Polisher** | 语言润色、降重 | 审稿通过稿 | PolishDone | 润色终审组 |

### 1.2 开发 Agent 团队（AI 开发时使用）

| 角色 | 职责 | 触发时机 |
|------|------|----------|
| **Planner** | 任务分解、依赖分析 | 每个功能开始前 |
| **Coder** | 代码实现 | Planner 输出后 |
| **Reviewer** | 代码审查 | Coder 完成后 |
| **Debugger** | 错误定位、修复 | 测试失败时 |

---

## 2. 执行顺序

### 2.1 论文生成执行顺序

```
┌─────────────────────────────────────────────────────────────────┐
│                        Pipeline Orchestrator                     │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ Phase 1 │ ──────► │ Phase 2 │ ──────► │ Phase 3 │
    │选题讨论  │         │文献调研  │         │写作审稿  │
    └─────────┘         └─────────┘         └─────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    GroupChat            Sequential            GroupChat
    (Advisor +           (Researcher           (Writer +
     Researcher)          + Tools)              Reviewer)
         │                    │                    │
         ▼                    ▼                    ▼
    TopicDone            LiteratureDone       WritingDone
                                              ReviewDone
                                                   │
                              ┌────────────────────┘
                              ▼
                         ┌─────────┐         ┌─────────┐
                         │ Phase 4 │ ──────► │ Phase 5 │
                         │润色终审  │         │  导出   │
                         └─────────┘         └─────────┘
                              │                    │
                              ▼                    ▼
                         GroupChat            Sequential
                         (Polisher +          (Export +
                          Reviewer)            Gates)
                              │                    │
                              ▼                    ▼
                         PolishDone           paper.md
```

### 2.2 单个 GroupChat 执行顺序

```python
# 写作-审稿 GroupChat 示例
async def writing_review_chat(context: SessionContext) -> tuple[WritingDone, ReviewDone]:
    chat = SelectorGroupChat(
        participants=[writer, reviewer],
        model_client=get_selector_client(),
        termination_condition=AcceptTermination(),
        max_turns=10,  # 5 轮对话
    )
    
    initial_task = f"""
    基于以下文献综述，撰写论文：
    {context.literature_done.json()}
    
    目标期刊: {context.journal_type}
    """
    
    messages = []
    async for msg in chat.run_stream(task=initial_task):
        messages.append(msg)
        # 实时记录到数据库
        insert_message(conn, session_id, msg.source, "team", ...)
    
    # 提取最终结果
    writing_done = extract_writing_done(messages)
    review_done = extract_review_done(messages)
    
    return writing_done, review_done
```

---

## 3. 记忆策略

### 3.1 记忆层级

| 层级 | 存储位置 | 生命周期 | 内容 |
|------|----------|----------|------|
| **短期记忆** | GroupChat 上下文 | 单次对话 | 当前轮次的对话历史 |
| **中期记忆** | SQLite messages 表 | 单个会话 | 所有 Agent 消息、产物 |
| **长期记忆** | Chroma 向量库 | 跨会话 | 文献库、用户偏好 |

### 3.2 上下文传递

```python
@dataclass
class SessionContext:
    """会话上下文 — 跨阶段传递的状态"""
    session_id: str
    topic: str
    journal_type: str
    language: str
    
    # 阶段产物（逐步填充）
    topic_done: TopicDone | None = None
    literature_done: LiteratureDone | None = None
    writing_done: WritingDone | None = None
    review_done: ReviewDone | None = None
    polish_done: PolishDone | None = None
    
    # 文献库引用
    vector_collection: str | None = None
    
    # 迭代计数
    revision_count: int = 0
    
    def to_prompt_context(self) -> str:
        """生成传递给 Agent 的上下文摘要"""
        ...
```

### 3.3 记忆注入点

| 阶段 | 注入的记忆 |
|------|-----------|
| 选题讨论 | 用户历史偏好（长期）、当前 topic/journal |
| 文献调研 | TopicDone、已有文献库（长期） |
| 写作-审稿 | TopicDone + LiteratureDone + RAG 召回 |
| 润色终审 | WritingDone + ReviewDone |
| 导出 | 全部产物 |

---

## 4. Agent 提示模板

### 4.1 Writer Agent

```python
WRITER_SYSTEM_PROMPT = """你是一位专业的学术论文写手，擅长根据文献综述撰写高质量论文。

## 输入
- 研究方向（TopicDone）
- 文献综述（LiteratureDone）
- 目标期刊类型

## 输出要求
严格输出 JSON 格式，包含：
- sections: dict[str, str]  # 各章节内容
- word_count: int
- version_id: str

## 章节结构
1. abstract（摘要）
2. introduction（引言）
3. literature_review（文献综述）
4. methodology（方法）
5. results（结果）
6. discussion（讨论）
7. conclusion（结论）

## 写作规范
- 引用格式：[作者, 年份] 或 (DOI: xxx)
- 避免口号化表述
- 每个引用必须来自 LiteratureDone 中的 papers

## 禁止动作
- ❌ 编造不存在的引用
- ❌ 使用未经验证的数据
- ❌ 输出非 JSON 格式
"""
```

### 4.2 Reviewer Agent

```python
REVIEWER_SYSTEM_PROMPT = """你是一位严谨的学术审稿人，负责审查论文质量并提出修改意见。

## 输入
- 论文初稿（WritingDone）
- 目标期刊标准

## 输出要求
严格输出 JSON 格式，包含：
- verdict: "accept" | "minor_revision" | "major_revision" | "reject"
- overall_score: float (0-10)
- major_issues: list[Issue]
- minor_issues: list[Issue]
- adopted_issues: list[str]  # 已采纳的问题 ID

## 审查维度
1. 创新性（是否有新贡献）
2. 严谨性（方法是否合理）
3. 完整性（结构是否完整）
4. 规范性（格式是否符合期刊要求）
5. 引用（是否真实、充分）

## 禁止动作
- ❌ 无依据地全盘否定
- ❌ 给出模糊意见（必须具体到章节和问题）
- ❌ 忽略引用核查
"""
```

### 4.3 Researcher Agent (RAG 增强版)

```python
RESEARCHER_RAG_SYSTEM_PROMPT = """你是一位专业的学术文献检索专家，配备以下工具：

## 可用工具
- search_arxiv(query, max_results): 搜索 arXiv
- search_semantic(query, max_results): 搜索 Semantic Scholar
- pdf_parse(url): 解析 PDF 提取结构化内容
- rag_query(question, collection): 基于文献库问答
- add_to_library(doc): 添加文献到向量库

## 工作流程
1. 根据研究方向，搜索相关文献
2. 下载并解析 PDF
3. 将文献加入向量库
4. 使用 RAG 生成文献综述

## 输出要求
严格输出 JSON 格式（LiteratureDone）：
- papers: list[Paper]
- literature_matrix: str (Markdown 表格)
- verified_count: int
- total_found: int

## 禁止动作
- ❌ 编造不存在的 DOI
- ❌ 跳过 PDF 解析直接生成综述
- ❌ 返回未经验证的文献
"""
```

---

## 5. 错误控制闭环

### 5.1 错误类型与处理

| 错误类型 | 检测方式 | 处理策略 |
|----------|----------|----------|
| **合约校验失败** | Pydantic ValidationError | 记录日志 + 要求 Agent 重新生成 |
| **API 超时** | 请求超时 | 重试 3 次 + 降级到备用模型 |
| **RAG 召回为空** | 返回空列表 | 扩大搜索范围 + 提示用户上传 |
| **GroupChat 死循环** | 超过 max_turns | 记录上下文 + 升级人类 |
| **引用不存在** | DOI 验证失败 | 标记移除 + 警告 |

### 5.2 重复 Bug 防护

```python
class BugTracker:
    """追踪重复出现的错误"""
    
    def __init__(self, max_repeats: int = 3):
        self.error_history: dict[str, int] = {}
        self.max_repeats = max_repeats
    
    def record_error(self, error_type: str, context: str) -> bool:
        """返回 True 表示需要升级人类"""
        key = f"{error_type}:{hash(context)}"
        self.error_history[key] = self.error_history.get(key, 0) + 1
        
        if self.error_history[key] >= self.max_repeats:
            logger.error(f"重复错误超过 {self.max_repeats} 次: {error_type}")
            return True  # 升级人类
        return False
```

### 5.3 回归预防

```python
# 每次阶段完成后，验证产物不回退
def check_no_regression(current: SessionContext, previous: SessionContext) -> list[str]:
    """检查是否有回归"""
    issues = []
    
    if current.writing_done and previous.writing_done:
        if current.writing_done.word_count < previous.writing_done.word_count * 0.8:
            issues.append("字数大幅减少，可能是回归")
    
    if current.review_done and previous.review_done:
        if current.review_done.overall_score < previous.review_done.overall_score:
            issues.append("评分下降，检查修改是否正确")
    
    return issues
```

### 5.4 上下文丢失防护

```python
# Pipeline 层的 checkpoint 机制
async def run_phase_with_checkpoint(
    phase_name: str,
    phase_func: Callable,
    context: SessionContext,
    conn: sqlite3.Connection,
) -> SessionContext:
    """带检查点的阶段执行"""
    
    # 1. 阶段开始前保存快照
    save_checkpoint(conn, context, f"pre_{phase_name}")
    
    try:
        # 2. 执行阶段
        result = await phase_func(context)
        
        # 3. 验证结果
        if not validate_phase_output(phase_name, result):
            raise PhaseValidationError(phase_name)
        
        # 4. 阶段完成后保存快照
        save_checkpoint(conn, result, f"post_{phase_name}")
        return result
        
    except Exception as e:
        # 5. 失败时恢复到上一个检查点
        logger.error(f"阶段 {phase_name} 失败: {e}")
        restored = restore_checkpoint(conn, f"pre_{phase_name}")
        raise PhaseExecutionError(phase_name, e, restored)
```

---

## 6. 开发阶段 Agent 配置

### 6.1 Planner 角色

```yaml
role: Planner
trigger: 每个功能实现开始前
input:
  - PRD.md 相关段落
  - ARCH.md 相关段落
  - 当前代码结构
output:
  - 任务分解列表
  - 依赖关系图
  - 估计复杂度
constraints:
  - 必须引用 PRD/ARCH 段落
  - 不可自行增加范围
```

### 6.2 Coder 角色

```yaml
role: Coder
trigger: Planner 输出后
input:
  - Planner 的任务列表
  - 相关现有代码
  - 合约定义
output:
  - 代码变更
  - 测试代码
constraints:
  - 遵循 ARCH.md 分层边界
  - 不可绕过合约校验
  - 必须附带测试
```

### 6.3 Reviewer 角色

```yaml
role: Reviewer
trigger: Coder 完成后
input:
  - 代码变更 diff
  - 相关测试结果
  - PRD/ARCH 参考
output:
  - 审查意见
  - 通过/拒绝决定
constraints:
  - 检查是否符合 ARCH.md
  - 检查是否有禁止行为 (P001-P008)
  - 不可忽略测试覆盖
```

### 6.4 Debugger 角色

```yaml
role: Debugger
trigger: 测试失败
input:
  - 失败测试输出
  - 相关代码
  - 错误堆栈
output:
  - 根因分析
  - 修复建议
constraints:
  - 必须定位到具体代码行
  - 不可用 try-except 掩盖错误
```

---

## 输出契约

| 项目 | 内容 |
|------|------|
| **Current Phase** | Phase 4: Agent Operating System |
| **What was completed** | Agent 角色定义、执行顺序、记忆策略、提示模板、错误闭环 |
| **Gate status** | 🔄 等待人类确认 |
| **Risks** | GroupChat 实现复杂度；错误闭环需实际验证 |
| **Need human decision?** | **Yes** |
| **Next action** | 人类确认后进入 Phase 5: 稳定性与回滚 |

---

## ⚠️ 请确认是否进入下一阶段（Yes/No）

请确认：
1. Agent 角色定义是否完整？
2. 执行顺序是否合理？
3. 记忆策略是否满足需求？
4. 错误控制闭环是否充分？

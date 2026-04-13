# PaperGenius Pro — 架构设计文档 (ARCH)

> **版本**: 1.0  
> **状态**: 🔄 Phase 5 进行中（架构已批准，进入实现与稳定性收敛）  
> **创建时间**: 2026-04-08  
> **前置文档**: PRD.md, VISION.md

---

## 1. 技术栈选型（唯一）

| 层 | 技术 | 版本 | 选型理由 |
|----|------|------|----------|
| **Agent 编排** | AutoGen | ≥0.4 | 现有架构，稳定运行 |
| **向量数据库** | Chroma | ≥0.4 | 本地优先，嵌入式 |
| **RAG 引擎** | paper-qa | ≥5.0 | 科学文献专用，高精度 |
| **PDF 解析** | pymupdf4llm | ≥0.0.10 | 布局感知，公式支持 |
| **元数据存储** | SQLite | - | 现有，会话+文献元数据 |
| **Embedding (云端)** | OpenAI text-embedding-3-small | - | 高质量 |
| **Embedding (本地)** | bge-m3 / nomic-embed | - | 离线模式 |
| **CLI** | Rich + argparse | - | 现有 |
| **测试** | pytest | ≥8.0 | 现有 |

---

## 2. 分层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI 层                                      │
│                         (console.py)                                     │
│                    用户命令 → 参数解析 → 调用 Pipeline                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Pipeline 层                                    │
│              (pipeline_v2.py [默认] / pipeline_real.py [回退])           │
│              编排 GroupChat 执行，管理状态机，记录日志                    │
│     ┌──────────────────────────────────────────────────────────┐       │
│     │                   GroupChat 编排器                        │       │
│     │  选题讨论 → 文献调研 → 写作-审稿循环 → 润色终审 → 导出   │       │
│     └──────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Agent 层                                      │
│     ┌──────────┬──────────┬──────────┬──────────┬──────────┐           │
│     │ Advisor  │Researcher│  Writer  │ Reviewer │ Polisher │           │
│     │  Agent   │RAG Agent │  Agent   │  Agent   │  Agent   │           │
│     └──────────┴──────────┴──────────┴──────────┴──────────┘           │
│                              │                                          │
│                    ┌─────────┴─────────┐                               │
│                    ▼                   ▼                               │
│            ┌─────────────┐     ┌─────────────┐                        │
│            │ SelectorChat│     │ Tool Calling│                        │
│            │ (多Agent讨论)│     │ (搜索/RAG) │                        │
│            └─────────────┘     └─────────────┘                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Plugin 层                                      │
│     ┌──────────────┬──────────────┬──────────────┐                     │
│     │ pdf_extract  │ literature   │     rag      │                     │
│     │   plugin     │search plugin │   plugin     │                     │
│     └──────────────┴──────────────┴──────────────┘                     │
│                              │                                          │
│                              ▼                                          │
│     ┌──────────────────────────────────────────────────────────┐       │
│     │                   Plugin Interface                        │       │
│     │        register_tools() | health_check() | cleanup()      │       │
│     └──────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Storage 层                                      │
│     ┌──────────────────────┬──────────────────────┐                     │
│     │     SQLite DB        │     Chroma DB        │                     │
│     │  (sessions, messages │  (文献向量 + 元数据)  │                     │
│     │   artifacts, costs)  │                      │                     │
│     └──────────────────────┴──────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Core 层                                         │
│     ┌──────────────────────┬──────────────────────┐                     │
│     │    Model Clients     │    Embedding Clients │                     │
│     │ (Anthropic/OpenAI/   │ (OpenAI / local bge) │                     │
│     │  DeepSeek/Ollama)    │                      │                     │
│     └──────────────────────┴──────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 边界定义

### 3.1 模块边界

| 模块 | 职责 | 不负责 |
|------|------|--------|
| CLI | 参数解析、用户交互 | 业务逻辑 |
| Pipeline | Agent 编排、状态管理 | 具体生成逻辑 |
| Agent | 单阶段任务执行 | 跨阶段状态 |
| Tools | 原子操作（搜索/解析/查询）| 组合逻辑 |
| Plugin | 可插拔功能单元 | 核心流程 |
| Storage | 数据持久化 | 业务逻辑 |
| Core | LLM/Embedding 调用 | 高层逻辑 |

### 3.2 接口边界

| 接口 | 输入 | 输出 | 约束 |
|------|------|------|------|
| Agent → Tool | 函数调用参数 | 结构化结果 | Pydantic 校验 |
| Pipeline → Agent | 上阶段 payload | 本阶段 payload | 合约校验 |
| Tool → Storage | 文档/查询 | 结果/ID | 幂等操作 |
| Core → LLM | prompt + config | response | 超时/重试 |

---

## 4. 单一事实源

| 数据 | 事实源 | 消费者 |
|------|--------|--------|
| 会话状态 | SQLite `sessions` 表 | CLI, Pipeline |
| 阶段产物 | SQLite `artifacts` 表 | Pipeline, Export |
| 文献向量 | Chroma `papers` collection | RAG Tools |
| 文献元数据 | Chroma metadata + SQLite | Search, RAG |
| 角色配置 | `role_profile.json` | Pipeline |
| 合约定义 | `contracts/agent_contracts.py` | 所有 Agent |

---

## 5. 数据流（不可变路径）

### 5.1 文献入库流程

```
用户输入关键词
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ search_arxiv │ ──► │ download_pdf│ ──► │  pdf_parse  │
│ search_ss    │     │             │     │ (pymupdf4llm│
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   chunk +   │
                                        │  embedding  │
                                        └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ Chroma DB   │
                                        │ (persist)   │
                                        └─────────────┘
```

### 5.2 RAG 查询流程

```
用户问题
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  embedding  │ ──► │ vector search│ ──► │  rerank     │
│  (query)    │     │ (Chroma)    │     │ (optional)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ LLM 生成    │
                                        │ + 引用注入  │
                                        └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ RAGResponse │
                                        │ (带 sources)│
                                        └─────────────┘
```

### 5.3 论文生成流程（多 Agent 讨论模式）

```
用户输入 (topic, journal)
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 1: 选题讨论                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              GroupChat (选题)                            │   │
│  │   Advisor ⟷ Researcher                                  │   │
│  │   多轮讨论 → 达成共识 → TopicDone                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 2: 文献调研                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Researcher + RAG Tools                      │   │
│  │   搜索 → 下载 → 解析 → 入库 → LiteratureDone             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 3: 写作-审稿循环                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              GroupChat (写作)                            │   │
│  │   Writer ⟷ Reviewer                                     │   │
│  │   ┌──────────────────────────────────────────────────┐  │   │
│  │   │ Round 1: Writer 生成初稿                          │  │   │
│  │   │ Round 2: Reviewer 提出修改意见                    │  │   │
│  │   │ Round 3: Writer 修改                              │  │   │
│  │   │ Round N: 直到 Reviewer verdict == "accept"        │  │   │
│  │   │ (最大迭代: 5 轮，超时升级人类)                     │  │   │
│  │   └──────────────────────────────────────────────────┘  │   │
│  │   → WritingDone + ReviewDone                            │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 4: 润色终审                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              GroupChat (终审)                            │   │
│  │   Polisher ⟷ Reviewer                                   │   │
│  │   润色 → 终审确认 → PolishDone                          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 5: 导出                              │
│   质量门禁检查 → Export → paper.md + artifacts                 │
└─────────────────────────────────────────────────────────────────┘
```

**GroupChat 配置**:

| 讨论组 | 参与者 | 最大轮次 | 终止条件 |
|--------|--------|----------|----------|
| 选题讨论 | Advisor + Researcher | 3 | 双方确认方向 |
| 写作-审稿 | Writer + Reviewer | 5 | verdict == "accept" |
| 润色终审 | Polisher + Reviewer | 3 | 终审通过 |

**AutoGen GroupChat 实现**:
```python
from autogen_agentchat.teams import SelectorGroupChat

writing_review_chat = SelectorGroupChat(
    participants=[writer, reviewer],
    selector_prompt="根据当前状态选择下一个发言者",
    termination_condition=AcceptTermination(),  # verdict == accept
    max_turns=10,  # 5 轮对话 = 10 条消息
)
```

**超时/死循环防护**:
- 单组最大轮次限制
- 超过限制 → 记录日志 + 升级人类决策
- 支持 `--max-revision N` 参数覆盖

---

## 6. 目录结构

```
academic-agent-team/
├── academic_agent_team/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── advisor.py
│   │   ├── researcher.py        # 改造：集成 RAG Tools
│   │   ├── writer.py
│   │   ├── reviewer.py
│   │   ├── polisher.py
│   │   └── pipelined_team.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── console.py           # CLI 命令入口（默认 v2，引擎可切换）
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── journals.py
│   │   └── role_profiles.py
│   ├── contracts/
│   │   ├── __init__.py
│   │   └── agent_contracts.py   # 编辑：新增 RAG 相关合约
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base_client.py
│   │   ├── clients/
│   │   │   ├── anthropic_client.py
│   │   │   ├── openai_client.py
│   │   │   ├── ...
│   │   │   └── embedding_client.py   # 🆕 新增
│   │   └── agent_prompts.py
│   ├── plugins/                       # 🆕 新增目录
│   │   ├── __init__.py
│   │   ├── base.py                    # 🆕 PluginInterface
│   │   ├── pdf_extract/
│   │   │   ├── __init__.py
│   │   │   ├── plugin.py
│   │   │   └── parser.py
│   │   ├── literature_search/
│   │   │   ├── __init__.py
│   │   │   ├── plugin.py
│   │   │   ├── arxiv_client.py
│   │   │   └── semantic_client.py
│   │   └── rag/
│   │       ├── __init__.py
│   │       ├── plugin.py
│   │       └── paper_qa_adapter.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   └── vector_db.py               # 🆕 新增 Chroma 封装
│   ├── tools/                         # 🆕 新增目录
│   │   ├── __init__.py
│   │   ├── search_arxiv.py
│   │   ├── search_semantic.py
│   │   ├── pdf_parse.py
│   │   ├── rag_query.py
│   │   └── library_ops.py
│   ├── pipeline.py
│   ├── pipeline_v2.py
│   ├── pipeline_real.py
│   └── session_logger.py
├── tests/
│   ├── test_pdf_parser.py             # 🆕 新增
│   ├── test_vector_db.py              # 🆕 新增
│   ├── test_rag.py                    # 🆕 新增
│   ├── test_literature_search.py      # 🆕 新增
│   └── ...
├── session_store/                     # 会话数据库与日志
├── docs/
│   └── ai/                            # Governance 文档
├── pyproject.toml
└── README.md
```

---

## 7. 禁止行为

| ID | 禁止行为 | 理由 | 检测方式 |
|----|----------|------|----------|
| P001 | 绕过合约校验直接入库 | 数据一致性 | Code Review |
| P002 | 跨层直接调用（如 CLI 直接调 LLM）| 架构耦合 | Import 检查 |
| P003 | 在 Agent 层持有跨阶段状态 | 状态泄漏 | 单元测试 |
| P004 | 向量库存储未解析原始 PDF | 召回失败 | 集成测试 |
| P005 | RAG 返回不带 sources | 溯源缺失 | 合约校验 |
| P006 | 硬编码 API Key | 安全风险 | CI 扫描 |
| P007 | 阻塞式网络调用无超时 | 用户体验 | Code Review |
| P008 | 修改现有 CLI 接口签名 | 向后兼容 | API 测试 |

---

## 8. 架构风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| paper-qa 版本升级破坏 API | 🟡 中 | 封装 adapter 层，隔离依赖 |
| Chroma 大文献库性能 | 🟡 中 | 分 collection，定期清理 |
| Embedding 模型切换复杂 | 🟢 低 | 统一 EmbeddingClient 接口 |
| 插件加载失败阻塞启动 | 🟡 中 | 插件异常捕获 + 降级 |

---

## 9. 文件变更清单（Phase 4 编码范围）

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| pyproject.toml | 编辑 | 添加新依赖 |
| academic_agent_team/plugins/__init__.py | 新建 | 插件系统入口 |
| academic_agent_team/plugins/base.py | 新建 | PluginInterface |
| academic_agent_team/plugins/pdf_extract/* | 新建 | PDF 解析插件 |
| academic_agent_team/plugins/literature_search/* | 新建 | 文献搜索插件 |
| academic_agent_team/plugins/rag/* | 新建 | RAG 插件 (paper-qa adapter) |
| academic_agent_team/storage/vector_db.py | 新建 | Chroma 封装 |
| academic_agent_team/core/clients/embedding_client.py | 新建 | Embedding 客户端 |
| academic_agent_team/tools/*.py | 新建 | Agent Tools |
| academic_agent_team/agents/researcher.py | 编辑 | 集成 RAG Tools |
| academic_agent_team/contracts/agent_contracts.py | 编辑 | 新增合约 |
| academic_agent_team/cli/console.py | 编辑 | 默认引擎切换为 `v2`，新增 `db-migrate` |
| tests/test_*.py | 新建 | 新功能测试 |
| session_store/sessions.db | 迁移 | 补齐 `run_mode` / `budget_cap_cny` 列 |

---

## 输出契约

| 项目 | 内容 |
|------|------|
| **Current Phase** | Phase 5: 稳定性与实现 |
| **What was completed** | 技术栈选型、分层架构、数据流、禁止行为、文件变更清单 |
| **Gate status** | ✅ Phase 5 已完成（Gate 5 已确认） |
| **Risks** | Phase 5 剩余风险主要在发布验收与 RC 基线确认，需保持门禁自动化稳定 |
| **Need human decision?** | No |
| **Next action** | 以 `v1.1 RC` 为发布基线推进正式发布，并规划 v1.2 架构演进 |

---

> 注：以上为历史架构文档的当前状态补丁，阶段推进与门禁请以 `docs/ai/state.yaml` 为唯一真相。

# PaperGenius Pro — 产品需求文档 (PRD)

> ⚠️ **状态说明（2026-04-10）**: 本文件为 PRD 主文档（含历史条目）。当前项目治理状态以 `docs/ai/state.yaml` 为唯一真相；当前处于 **Phase 5: 稳定性与实现**。  
> 执行基线采用：`docs/ai/PRODUCT_OVERVIEW.md` + `docs/ai/state.yaml`。

> **版本**: 1.1  
> **状态**: 🔄 Phase 5 进行中（PRD 已确认）  
> **创建时间**: 2026-04-08  
> **基于**: Grok PRD v1.0 + 现有 academic-agent-team 项目

---

## 1. 文档信息

### 1.1 目的
定义 PaperGenius Pro 完整产品需求，实现"一键输入关键词 → 输出可投稿完整论文"的端到端自动化工作流。

### 1.2 范围
覆盖选题、文献调研、PDF 解析、智能写作、引用管理、格式排版、查重润色全链路。

### 1.3 参考标准
- 期刊格式：GB/T 7714、APA、MLA、IEEE
- 数据源：arXiv、Semantic Scholar、CNKI（模拟）

---

## 2. 功能需求清单

### 2.1 现有功能 (已实现)

| ID | 功能 | 描述 | 状态 | 清晰度 |
|----|------|------|------|--------|
| F001 | 5-Agent 流水线 | advisor→researcher→writer→reviewer→polisher | ✅ 已有 | Clear |
| F002 | 多 Provider 支持 | Anthropic/OpenAI/DeepSeek/Ollama/MiniMax/智谱 | ✅ 已有 | Clear |
| F003 | 会话持久化 | SQLite 存储会话、消息、产物 | ✅ 已有 | Clear |
| F004 | 成本追踪 | 记录每次 API 调用费用 | ✅ 已有 | Clear |
| F005 | Pydantic 合约 | 每阶段输出强校验 | ✅ 已有 | Clear |
| F006 | CLI 命令集 | start/status/cost/role/export 等 | ✅ 已有 | Clear |
| F007 | Mock 模式 | 本地无 API 测试 | ✅ 已有 | Clear |
| F008 | 角色配置切换 | 运行时切换 agent 使用的模型 | ✅ 已有 | Clear |

### 2.2 MVP 功能 (本次交付)

| ID | 功能 | 描述 | 优先级 | 清晰度 |
|----|------|------|--------|--------|
| F101 | PDF 解析 | 上传 PDF → 结构化提取 (文本/表格/公式) | **MVP** | Clear |
| F102 | 向量数据库 | Chroma 本地存储文献向量 | **MVP** | Clear |
| F103 | 文献搜索 | arXiv + Semantic Scholar API 集成 | **MVP** | Clear |
| F104 | RAG 问答 | 基于文献库的检索增强生成 | **MVP** | Clear |
| F105 | RAG Researcher | 增强版文献研究员，支持 Tool Calling | **MVP** | Clear |
| F106 | 插件基类 | 定义插件接口，支持热加载 | **MVP** | Clear |
| F107 | AI 生成检测 | ZeroGPT + GPTZero 双引擎 + 改写建议 | **MVP** | Clear |
| F108 | 引用验证 | CrossRef DOI + CNKI 链接验证 | **MVP** | Clear |
| F109 | 查重降重 | 自研语义查重 + 外部 API 降重建议 | **MVP** | Clear |
| F110 | Data Analyst Agent | 数据分析、统计检验、图表生成 | **MVP** | Clear |
| F111 | LaTeX 导出 | 多模板导出与编译准备 | **MVP** | Clear |
| F112 | CNKI 搜索 | CNKI 检索（含降级策略） | **MVP** | Clear |

### 2.3 Phase 2 功能 (1个月后)

| ID | 功能 | 描述 | 优先级 | 清晰度 |
|----|------|------|--------|--------|
| F201 | 代码沙箱 | 安全执行 Python 数据分析代码 | Optional | Clear |
| F202 | Data Analyst Agent | 数据分析 + 图表生成 Agent | Optional | Clear |
| F203 | 引用管理 | BibTeX 提取 + 格式化 | Optional | Clear |
| F204 | LaTeX 编译 | 本地编译 + 模板支持 | Optional | Clear |
| F205 | Zotero 集成 | 同步 Zotero 文献库 | Optional | Ambiguous |

### 2.4 Phase 3 功能 (2个月后)

| ID | 功能 | 描述 | 优先级 | 清晰度 |
|----|------|------|--------|--------|
| F301 | 查重模块 | 语义相似度检测 | Optional | Clear |
| F302 | 降重建议 | 自动改写建议 | Optional | Ambiguous |
| F303 | 投稿助手 | 期刊匹配 + Cover Letter | Optional | Clear |
| F304 | Web UI | Next.js 前端 | Optional | Ambiguous |

### 2.5 长期愿景 (未排期)

| ID | 功能 | 描述 | 优先级 | 清晰度 |
|----|------|------|--------|--------|
| F401 | 插件市场 | 一键安装 GitHub 项目 | Future | Ambiguous |
| F402 | 团队协作 | 多人实时编辑 | Future | Ambiguous |
| F403 | 知识图谱 | 引用网络可视化 | Future | Ambiguous |
| F404 | 语音输入 | 实验笔记转论文 | Future | Ambiguous |

---

## 3. MVP 功能详细规格

### 3.1 F101: PDF 解析

**输入**:
- PDF 文件路径或 URL
- 支持格式：学术论文 PDF（单栏/双栏）

**输出** (Pydantic 合约):
```python
class PdfExtractPayload(BaseModel):
    file_path: str
    page_count: int
    text_content: str  # 全文文本
    sections: dict[str, str]  # 按章节分割
    tables: list[dict]  # 提取的表格
    figures: list[dict]  # 图片元数据
    equations: list[str]  # LaTeX 公式
    metadata: dict  # 标题/作者/摘要等
    extract_quality: float  # 0-1 质量评分
```

**技术选型**: pymupdf4llm (布局感知)

**验收标准**:
- 80%+ 学术 PDF 可成功解析
- 表格提取准确率 ≥ 70%
- 公式识别准确率 ≥ 60%

---

### 3.2 F102: 向量数据库

**输入**:
- 文档文本 + 元数据
- Embedding 向量 (OpenAI/本地)

**接口**:
```python
class VectorStore:
    def add_documents(self, docs: list[Document]) -> list[str]: ...
    def query(self, query: str, k: int = 5) -> list[SearchResult]: ...
    def delete(self, doc_ids: list[str]) -> None: ...
    def get_sources(self, doc_ids: list[str]) -> list[Document]: ...
```

**技术选型**: Chroma (本地持久化)

**验收标准**:
- 支持 10000+ 文档
- 查询延迟 < 500ms
- 持久化到本地目录

---

### 3.3 F103: 文献搜索（混合架构）

**输入**:
- 关键词 / 研究方向
- 搜索数量限制
- 数据源选择（可选）

**输出**:
```python
class SearchResult(BaseModel):
    title: str
    authors: list[str]
    year: int
    abstract: str
    doi: str | None
    arxiv_id: str | None
    pdf_url: str | None
    source: Literal["arxiv", "semantic_scholar", "cnki", "local", "zotero"]
```

**数据源架构**:

| 层级 | 数据源 | 接入方式 | 优先级 |
|------|--------|----------|--------|
| API 层 | arXiv | 官方 API (arxiv 库) | P0 MVP |
| API 层 | Semantic Scholar | 官方 API | P0 MVP |
| MCP 层 | CNKI | h-lu/cnki-mcp | P1 Phase 2 |
| 本地层 | 用户上传 PDF | 直接解析 | P0 MVP |
| 本地层 | Zotero 同步 | Zotero API | P1 Phase 2 |

**集成方案**:
- **paper-qa (future-house/paper-qa)**: 高精度 PDF RAG，作为核心解析+问答引擎
- **cnki-mcp**: CNKI 搜索的 MCP 服务器，供 Agent 调用

**验收标准**:
- 每次搜索返回 10-50 篇相关文献
- 支持中英文关键词
- 多源自动去重
- API 失败时优雅降级（不阻塞流程）

---

### 3.4 F104: RAG 问答

**输入**:
- 用户问题
- 可选：限定文献范围

**输出**:
```python
class RAGResponse(BaseModel):
    answer: str
    sources: list[dict]  # 引用来源 [{doc_id, chunk, relevance}]
    confidence: float
```

**流程**:
1. Query → Embedding
2. Vector Search → Top-K chunks
3. Rerank (可选)
4. LLM 生成 + 引用注入

**验收标准**:
- 召回准确率 ≥ 70%
- 响应时间 < 5s
- 所有引用可溯源

---

### 3.5 F105: RAG Researcher Agent

**改造现有** `researcher.py`:

```python
class ResearcherRAGAgent(AssistantAgent):
    tools = [
        search_arxiv,      # F103
        search_semantic,   # F103  
        pdf_parse,         # F101
        rag_query,         # F104
        add_to_library,    # F102
    ]
```

**流程**:
1. 接收研究方向
2. 调用 search_* 搜索文献
3. 下载 PDF → pdf_parse 解析
4. add_to_library 入向量库
5. rag_query 生成文献综述
6. 输出 LiteratureDone payload

**验收标准**:
- 兼容现有 5-Agent 流水线
- 支持 `--engine v2|legacy` 引擎切换
- 保持合约校验

---

### 3.6 F106: 插件基类

**定义**:
```python
class PluginInterface(Protocol):
    name: str
    version: str
    
    def register_tools(self) -> list[Callable]: ...
    def health_check(self) -> bool: ...
    def cleanup(self) -> None: ...
```

**插件目录结构**:
```
plugins/
├── pdf_extract/
│   ├── __init__.py
│   ├── plugin.py      # 实现 PluginInterface
│   └── parser.py      # 核心逻辑
├── literature_search/
└── rag/
```

**验收标准**:
- 插件可独立安装/卸载
- 热加载无需重启
- 版本兼容性检查

---

## 4. 不可妥协约束 (Invariants)

| ID | 约束 | 违反后果 | 验证方式 |
|----|------|----------|----------|
| INV-001 | 所有引用必须可溯源 | 学术不端风险 | RAG 强制返回 sources |
| INV-002 | Pydantic 合约校验不可绕过 | 数据一致性破坏 | 单元测试覆盖 |
| INV-003 | 现有 CLI 接口向后兼容 | 用户流程中断 | 回归测试 |
| INV-004 | SQLite schema 变更需迁移脚本 | 数据丢失 | 迁移测试 |
| INV-005 | 本地模式必须可离线运行 | 隐私承诺破坏 | Ollama 端到端测试 |
| INV-006 | PDF 解析失败不阻塞流水线 | 单点故障 | 降级处理 + 日志 |

---

## 5. 阻塞问题清单

| ID | 问题 | 状态 | 决策 |
|----|------|------|------|
| B001 | CNKI API 无官方接口 | ✅ 已决策 | MCP 方案 (h-lu/cnki-mcp)，P1 Phase 2 |
| B002 | Embedding 模型选择 | ⏳ 待决策 | 建议 C: 可切换 |
| B003 | paper-qa vs 自研 RAG | ⏳ 待决策 | 建议 A: 集成 paper-qa |

### B001: CNKI 接口问题 ✅ 已决策
**决策**: MCP 方案 (h-lu/cnki-mcp)
- MVP 阶段：仅 arXiv + Semantic Scholar + 本地上传
- Phase 2：集成 CNKI-MCP

### B002: Embedding 模型选择 ✅ 已决策
**决策**: C — 可切换（云端 OpenAI + 本地 sentence-transformers/bge-m3）
- 默认：OpenAI text-embedding-3-small
- `--offline` 模式：本地 bge-m3 / nomic-embed

### B003: RAG 引擎选择 ✅ 已决策
**决策**: A — 集成 paper-qa (future-house/paper-qa)
- MVP 使用 paper-qa 作为核心 RAG 引擎
- 后续可基于其 API 扩展自定义功能

---

## 6. 非功能需求

| 需求 | 目标值 | 验证方式 |
|------|--------|----------|
| 性能 - PDF 解析 | < 10s/篇 | 基准测试 |
| 性能 - RAG 查询 | < 5s | 基准测试 |
| 性能 - 端到端生成 | < 15min (云端) | 端到端测试 |
| 可用性 - 离线 | 100% 功能可用 (Ollama) | 离线测试 |
| 存储 - 向量库 | 支持 10000 文档 | 压力测试 |
| 兼容性 - Python | ≥ 3.11 | CI 测试 |
| 兼容性 - OS | macOS / Linux / Windows | CI 矩阵 |

---

## 7. 依赖变更清单

**新增依赖** (需 C5 确认):

| 依赖 | 版本 | 用途 | 优先级 |
|------|------|------|--------|
| chromadb | ≥0.4 | 向量数据库 | MVP |
| pymupdf4llm | ≥0.0.10 | PDF 解析 | MVP |
| arxiv | ≥2.0 | arXiv API | MVP |
| paper-qa | ≥5.0 | 科学文献 RAG 引擎 | MVP |
| sentence-transformers | ≥2.2 | 本地 Embedding (可选) | MVP |
| semanticscholar | ≥0.8 | Semantic Scholar API | MVP |

**Phase 2 依赖**:
| 依赖 | 版本 | 用途 |
|------|------|------|
| pyzotero | ≥1.5 | Zotero 同步 |
| cnki-mcp | - | CNKI MCP 服务 (Docker) |

---

## 8. 文件变更预览

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| pyproject.toml | 编辑 | 添加新依赖 |
| academic_agent_team/plugins/ | 新建目录 | 插件系统 |
| academic_agent_team/plugins/base.py | 新建 | 插件基类 |
| academic_agent_team/plugins/pdf_extract/ | 新建目录 | PDF 解析插件 |
| academic_agent_team/storage/vector_db.py | 新建 | Chroma 封装 |
| academic_agent_team/tools/search_literature.py | 新建 | 文献搜索 |
| academic_agent_team/tools/rag_query.py | 新建 | RAG 问答 |
| academic_agent_team/agents/researcher.py | 编辑 | 集成 RAG |
| academic_agent_team/contracts/agent_contracts.py | 编辑 | 新增合约 |
| academic_agent_team/cli/console.py | 编辑 | 默认 `v2`，支持 `db-migrate` 与引擎回退 |
| tests/test_pdf_parser.py | 新建 | PDF 测试 |
| tests/test_vector_db.py | 新建 | 向量库测试 |
| tests/test_rag.py | 新建 | RAG 测试 |

---

## 输出契约

| 项目 | 内容 |
|------|------|
| **Current Phase** | Phase 5: 稳定性与实现 |
| **What was completed** | 完整 PRD 文档，含功能清单、详细规格、Invariants、阻塞问题 |
| **Gate status** | ✅ 已完成（Phase 5 Gate 5 已确认） |
| **Risks** | 主要风险转为发布门禁执行一致性与 RC 交付验收闭环 |
| **Need human decision?** | No |
| **Next action** | 基于已批准的 `v1.1 RC` 进入正式发布与 v1.2 规划 |

---

> 注：本节为历史门禁输出模板，当前阶段状态以 `docs/ai/state.yaml` 为准。

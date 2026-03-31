# Academic Agent Team

多 Agent 学术论文写作系统，基于 Microsoft AutoGen 0.7 GraphFlow 编排 5 个专业化 Agent（选题顾问 → 文献研究员 → 论文写手 → 审稿人 → 润色师），自动完成从课题到终稿的全流程。

**状态**：v1.7 · In Development · 30/30 测试通过

---

## 架构

```
user input (CLI)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  build_academic_team()  ── AutoGen 0.7 GraphFlow         │
│                                                         │
│   advisor ──▶ researcher ──▶ writer ──▶ reviewer        │
│                                          │               │
│                              ┌───────────┴───────────┐  │
│                              │  handoff 驱动路由       │  │
│                              │  minor/accept → polisher  │
│                              │  major → writer (返工)  │  │
│                              └───────────────────────┘  │
└─────────────────────────────────────────────────────────┘
    │
    ▼
ModelClientAdapter (BaseModelClient → ChatCompletionClient)
    │
    ├── MockClient          （开发/测试）
    ├── AnthropicClient     （Claude）
    ├── DeepSeekClient      （DeepSeek V3）
    ├── OpenAIClient        （GPT-4）
    └── ZhipuClient         （GLM-4）
```

### Agent 流水线拓扑

| Agent | 职责 | 下一跳 |
|---|---|---|
| `advisor` | 选题分析，输出 `topic_done` | → `researcher` |
| `researcher` | 文献检索，输出 `literature_done` | → `writer` |
| `writer` | 撰写初稿，输出 `writing_done` | → `reviewer` |
| `reviewer` | 审稿判决 `verdict` | → `writer`（major） / `polisher`（minor） |
| `polisher` | 语言润色，输出 `polish_done` | → [终止] |

---

## 快速开始

```bash
# 1. 安装
git clone https://github.com/TabithaFanny/academic-agent-team.git
cd academic-agent-team
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Mock 模式（不消耗 API）
paper-team start --mock \
  --topic "大模型在学术写作中的应用" \
  --journal "中文核心"

# 3. 真实模式（AutoGen GraphFlow，默认引擎）
paper-team start --real \
  --topic "数字治理中的 AI 分流机制研究" \
  --journal "IEEE Trans" \
  --budget 50.0

# 4. 顺序引擎（备选，不依赖 AutoGen）
paper-team start --real --engine sequential \
  --topic "社区养老的 AI 辅助系统" \
  --journal "CCF-A"
```

---

## CLI 命令

| 命令 | 说明 |
|---|---|
| `paper-team start --mock` | Mock LLM，完整 pipeline |
| `paper-team start --real` | 真实 LLM，AutoGen GraphFlow（默认） |
| `paper-team start --real --engine sequential` | 顺序引擎（非 AutoGen） |
| `paper-team list` | 列出最近 session |
| `paper-team status <id>` | 查看 session 状态和费用 |
| `paper-team cost <id>` | 实时费用明细 |
| `paper-team debug <id>` | 调试日志 + summary |
| `paper-team export <id>` | 导出论文包 |

更多命令：`resume` `role` `mode` `goto` `rollback`

---

## 环境变量

```bash
# 模型 API Key（至少配置一个）
ANTHROPIC_AUTH_TOKEN=sk-ant-...   # Claude
DEEPSEEK_API_KEY=sk-...           # DeepSeek
OPENAI_API_KEY=sk-...             # GPT-4

# 可选
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-7
SESSION_DB=./session_store/sessions.db   # 覆盖默认路径
```

---

## 模型配置（按 Agent 角色）

| Agent | 默认模型 | 降级链 |
|---|---|---|
| advisor | anthropic/claude-sonnet-4-7 | → deepseek/deepseek-v3-250120 |
| researcher | deepseek/deepseek-v3-250120 | → openai/gpt-4o |
| writer | anthropic/claude-sonnet-4-7 | → deepseek/deepseek-v3 |
| reviewer | deepseek/deepseek-v3-250120 | → anthropic/claude-opus |
| polisher | anthropic/claude-haiku | → deepseek/deepseek-v3 |

---

## 持久化

每个 session 在 `session_store/sessions.db`（SQLite WAL）中记录：

- **messages**：Agent 间 handoff 的 JSON payload
- **artifacts**：各阶段输出（topic_report / literature_matrix / section_draft / review_report / polish_diff）
- **versions**：完整版本快照（论文文本）
- **costs**：按 Agent 分项的 token 用量和费用
- **raw_responses**：LLM 原始响应（SHA256 去重）

输出文件：`output/<session_id>/paper.md` + 各阶段 JSON

---

## 测试

```bash
# 全部测试（30/30 通过）
python3 -m pytest tests/ -v

# 单模块
python3 -m pytest tests/test_autogen_pipeline.py -v    # AutoGen 集成
python3 -m pytest tests/test_cli.py -v                # CLI 命令
python3 -m pytest tests/test_agent_contracts.py -v    # 契约校验
```

---

## 项目结构

```
academic_agent_team/
├── cli/console.py          # CLI 入口（paper-team 命令）
├── config/
│   ├── journals.py         # 期刊格式标准
│   ├── models.py           # 模型注册表 + 降级链
│   └── role_profiles.py    # Agent → 模型映射
├── contracts/
│   └── agent_contracts.py  # Pydantic 契约校验（5 阶段）
├── core/
│   ├── agents/
│   │   └── autogen_agents.py   # AutoGen AssistantAgent 工厂
│   ├── autogen_adapter.py      # ModelClientAdapter
│   ├── base_client.py          # BaseModelClient 接口
│   ├── clients/                # 各 Provider Client 实现
│   │   ├── anthropic_client.py
│   │   ├── deepseek_client.py
│   │   ├── mock_client.py
│   │   └── ...
│   └── team/
│       └── graph_flow_team.py  # AcademicTeam + build_academic_team()
├── pipeline.py             # Mock pipeline
├── pipeline_real.py        # Sequential + AutoGen pipeline
├── session_logger.py        # JSONL 日志
└── storage/
    └── db.py               # SQLite schema + 持久化函数
```

---

## PRD 对齐

| PRD Section | 状态 | 说明 |
|---|---|---|
| 7.5 Pipeline | ✅ | AutoGen 0.7 GraphFlow + 顺序引擎 |
| 7.6 Interface Contract | ✅ | Pydantic v2（topic_done / literature_done / writing_done / review_done / polish_done）|
| 7.7 Model Registry | ✅ | 6 providers，FALLBACK_ORDER 降级 |
| 7.8 Storage | ✅ | SQLite WAL，versions/messages/artifacts/costs |
| 7.9 Session Logger | ✅ | JSONL 结构化日志 |
| 7.10 Mock Mode | ✅ | MockClient，CLI `--mock` |
| T01 Trap | ✅ | `pip install "autogen-agentchat[0.4]>=0.4,<1.0"` 固化 |
| P0 AutoGen 0.4+ | ✅ | `ModelClientAdapter` + `GraphFlow` + `Handoff` |
| P1 CLI `--real` | ✅ | `paper-team start --real` 端到端测试通过 |
| P4 README | ✅ | 本文档 |

---

## 已知陷阱（T01）

AutoGen 0.4+ 必须从 `autogen-agentchat[0.4]` 安装：

```bash
# ❌ 错误：安装裸 autogen（版本不兼容）
pip install autogen

# ✅ 正确：指定 autogen-agentchat + 0.4 扩展
pip install "autogen-agentchat[0.4]>=0.4,<1.0"
```

其他常见问题：

- `create()` 必须是 `async def`（AutoGen 0.7 ChatCompletionClient 要求）
- `FinishReasons` 是 `Literal` 类型，不能 `FinishReasons("stop")`，直接用字符串字面量
- `SystemMessage` 没有 `source` 属性，先 `isinstance` 判断
- `UserProxyAgent` 默认读 stdin，pytest 中传 `input_func=lambda _: ""`
- DiGraph 不能有显式双向边（reviewer ↔ writer 循环由 handoff 驱动）

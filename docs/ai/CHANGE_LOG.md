# Change Log - 变更日志

## [Unreleased]

### 2026-04-13
- **FEATURE**: `pipeline_v2` Phase 3 改为真实 writer/reviewer 调用（按 `AGENT_MODEL_MAP` 路由，支持失败降级到 MockClient）
- **FEATURE**: `pipeline_v2` Phase 4 改为真实 polisher 调用，并接入 `AIDetector` + `PlagiarismChecker` 生成终审质量指标
- **FEATURE**: `pipeline_v2` Phase 1 改为真实 advisor 调用，支持 JSON 解析兜底与人工方向选择联动
- **FEATURE**: `pipeline_v2` Phase 2.5 改为真实 data_analyst 调用，新增数据文件概览构建与统计结果兜底
- **HARDENING**: 增加稳健 JSON 解析与字段归一化（Markdown code block/脏输出兜底），避免模型返回格式漂移导致流程崩溃
- **OBSERVABILITY**: `pipeline_v2` 阶段持久化改为记录真实 `model_id/input_tokens/output_tokens/cost_cny`
- **TEST**: `tests/test_pipeline_v2_persistence.py` 新增 3 个用例（真调用落库、脏 JSON 兜底、Phase 2.5 数据分析阶段），全量回归通过 `90 passed`
- **FEATURE**: 新增 CLI 子命令 `paper-team release-gate`，自动执行 schema preflight、v2/legacy mock smoke 与回归测试
- **FIX**: `release-gate` 对 DB 打开失败改为可读错误输出并阻断（移除 traceback 退出）
- **TEST**: 新增 `tests/test_cli_release_gate.py`，覆盖 preflight 失败、通过、回归失败阻断路径
- **VERIFY**: 全量测试刷新为 `90 passed`
- **VERIFY**: 实机执行 `release-gate --skip-regression`，schema preflight + v2/legacy smoke 均通过
- **VERIFY**: 在 Phase 1/2.5 改造后再次实机执行 `release-gate --skip-regression`，双引擎 smoke 持续通过
- **VERIFY**: 实机执行完整 `release-gate`（含回归）通过，`tests/test_pipeline_v2_persistence.py + tests/test_db_schema_migration.py + tests/test_cli_v2_engine.py` 共 `9 passed`
- **DOC**: 新增 `docs/ai/RELEASE_BASELINE_V1_1_RC.md` 作为 Gate 5 人类验收基线报告
- **GATE**: 人类确认 Gate 5 通过（Yes），`v1.1 RC` 发布基线状态更新为 `APPROVED`

### 2026-04-11
- **MIGRATION**: 新增显式 DB 迁移能力：`paper-team db-migrate --yes`（自动备份后补齐 `sessions.run_mode` / `sessions.budget_cap_cny`）
- **FIX**: 执行生产库迁移并生成备份 `session_store/sessions.db.bak.20260412011238`
- **VERIFY**: 迁移后完成双引擎 smoke：`start --engine v2 --mock` 与 `start --engine legacy --mock` 均可创建并完成会话
- **GATE HARDENING**: `pipeline_v2` 将引用验证 Gate、文献数量 Gate 改为硬阻断（失败即抛错）
- **TEST**: 新增 Gate 失败回归用例（`test_run_pipeline_v2_blocks_when_literature_gate_fails`），全量回归通过 `84 passed`
- **STATE**: 清空 BI-001 与 `pending_human_decisions`，新增决策 D13
- **DOC ALIGN**: 修正 `ARCH.md` 过期阶段口径（Phase 3 → Phase 5），移除已失效的门禁确认段落
- **DOC ALIGN**: 修正 `PRD.md` 中过期的 `--enable-rag` 与阶段输出契约，统一到当前 CLI/Phase 5 状态
- **DOC ALIGN**: 完成 `INVARIANTS.md` 正式化，替换模板为可执行不变量清单（含 Gate/迁移约束）

### 2026-04-10
- **DOC ALIGN**: 对齐 `PRD.md` 与 `state.yaml` 的阶段状态（标记为 Phase 5 进行中）
- **DOC ALIGN**: 在 PRD 的 MVP 清单补齐 F107-F112（与 state/product_overview 一致）
- **DECISION**: D12 - CLI 默认执行引擎切换为 `pipeline_v2`，`legacy` 作为回退
- **STATE**: `pending_human_decisions` 更新为数据迁移决策项（BI-001）
- **DOC ALIGN**: 更新 `PRODUCT_OVERVIEW.md`，明确 autopilot/manual 到 express/standard 的映射
- **EVIDENCE**: 补充 Phase 5 回归测试证据（3 passed；44 passed/1 failed，环境依赖阻塞异步与 LaTeX 测试）
- **ROLLBACK**: 完成 v2/legacy 回滚演练记录，发现统一受 `sessions.db` schema 保护门阻断
- **BLOCKER**: 新增 BI-001（sessions 表缺 `run_mode`/`budget_cap_cny`，需人类批准迁移策略）

### 2026-04-08
- **INIT**: 初始化 docs/ai/ 项目内存结构
- **INIT**: 创建 state.yaml 控制面
- **INIT**: 创建 GATES.md 门禁清单
- **INIT**: 创建 SESSION_NOTES.md 会话记录
- **PHASE 0**: 开始任务理解阶段
- **PHASE 0**: ✅ 完成，人类确认通过
- **DECISION**: D1 - AutoGen 为主，未来可混用 LangGraph
- **DECISION**: D2 - MVP 范围确认 (PDF+RAG+搜索+向量库)
- **DECISION**: D3 - 4 周开发周期确认
- **PHASE 1**: 开始人机协作协议阶段
- **PHASE 1**: ✅ 完成，人类确认协议正确
- **PHASE 2**: 开始 PRD 编写阶段
- **DECISION**: B001 - CNKI 用 MCP 方案 (h-lu/cnki-mcp)
- **DECISION**: B002 - Embedding 可切换 (云端 OpenAI + 本地 bge-m3)
- **DECISION**: B003 - RAG 引擎用 paper-qa
- **PHASE 2**: ✅ 完成，PRD 确认通过
- **PHASE 3**: 开始架构设计阶段
- **DECISION**: D4 - 采用 GroupChat 多 Agent 讨论模式 (writer ⟷ reviewer 迭代)
- **PHASE 3**: ✅ 完成，架构确认通过，编码禁令解除
- **PHASE 4**: 开始 Agent Operating System 设计
- **PHASE 4**: ✅ 完成，人类确认通过
- **DECISION**: D5 - 文献质量 Gate（< 30 篇返回 Phase 1）
- **DECISION**: D6 - 内容质量 Gate（Reviewer 评分 < 85 强制重写）
- **DECISION**: D7 - CNKI 降级策略（失败后切换 Semantic Scholar + OpenAlex）
- **PHASE 5**: 开始稳定性与回滚机制设计
- **PRD REVIEW**: 完成 PRD 全面审查，识别 C 刊/顶会差距
- **DECISION**: D8 - MVP 延长到 6 周
- **DECISION**: D9 - 自研语义查重 + paperyy API
- **DECISION**: D10 - ZeroGPT + GPTZero 双引擎
- **DECISION**: D11 - 高质量辅助写作 + 强后处理（非纯端到端）
- **MVP v1.1**: 追加 F107-F112（AI检测/引用验证/查重/DataAnalyst/LaTeX/CNKI）

---

## 变更类型说明
- **INIT**: 初始化
- **PHASE X**: 阶段性交付物
- **FIX**: 修复
- **DECISION**: 人类决策记录
- **ROLLBACK**: 回滚操作

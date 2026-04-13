# Session Notes - 会话记录

## 2026-04-08 Session 1

### 背景
- 用户提供 Grok 生成的 PRD v1.0（论文智造 Pro / PaperGenius Pro）
- 要求将其与现有 academic-agent-team 项目融合
- 启用 Governance Executor 模式进行严格分阶段交付

### 关键输入
1. **现有项目**: academic-agent-team（AutoGen + CLI 多 Agent 论文写作系统）
2. **目标愿景**: 集成 20+ GitHub 开源项目的端到端学术写作平台
3. **治理要求**: 6 阶段门禁流程，每阶段需人类确认

### 本轮进展
- 初始化 docs/ai/ 内存结构
- 创建 state.yaml 控制面
- 开始 Phase 0: 理解任务

### 待决事项
- 无

---

*Last updated: 2026-04-08T05:41:00Z*

---

## 2026-04-10 Session 2

### 目标
- 对齐 `PRD/state/overview` 文档状态，并补齐 Phase 5 门禁证据与回滚演练记录。

### 已完成
- 文档对齐：`PRD.md` 状态与 `state.yaml` 统一为 Phase 5 进行中。
- 决策更新：记录 D12（CLI 默认切换到 `pipeline_v2`，`legacy` 可回退）。
- 回归证据：
  - `tests/test_pipeline_v2_persistence.py + tests/test_cli_v2_engine.py` 通过（3 passed）。
  - `pytest -m "not asyncio"` 结果为 `44 passed, 1 failed`（失败为缺 `jinja2`）。
  - 异步用例受 `pytest-asyncio` 缺失影响无法执行。
- 回滚演练：
  - v2/legacy 启动均被 `sessions.db` 旧 schema 保护门阻断。
  - 已确认阻塞为数据迁移决策，不可隐式推进。

### 新阻塞
- BI-001: `session_store/sessions.db` 缺 `run_mode` / `budget_cap_cny` 列，需人类批准迁移方案。

### 待决策
- 方案 A：迁移现有 `sessions.db`（推荐）
- 方案 B：改用全新 DB 路径作为 v2 基线

---

## 2026-04-11 Session 3

### 目标
- 按 review 结论继续推进，解除 BI-001 运行阻塞并补齐可审计迁移路径。

### 已完成
- 新增显式迁移命令：`paper-team db-migrate --yes`（自动备份 + 补列）。
- 执行迁移并生成备份：`session_store/sessions.db.bak.20260412011238`。
- 收敛门禁行为：`pipeline_v2` 的引用验证 Gate、文献数量 Gate 由告警改为硬阻断。
- 迁移后 smoke 验证：
  - `paper-team start --engine v2 --mock --no-interactive` 成功。
  - `paper-team start --engine legacy --mock --no-interactive` 成功。
- 回归验证：`pytest -q -p no:cacheprovider` 全部通过（84 passed）。
- 控制面同步：`state.yaml` 清空 `blocking_issues` 与 `pending_human_decisions`，新增 D13。

### 当前状态
- BI-001 已解除，Phase 5 进入“实现质量与发布门禁收敛”阶段。

---

## 2026-04-11 Session 4

### 目标
- 继续收敛架构与治理文档，消除 `ARCH/PRD` 与控制面状态冲突。

### 已完成
- 修正 `ARCH.md`：阶段口径切到 Phase 5，更新默认执行栈（`pipeline_v2`）和过期条目。
- 修正 `PRD.md`：移除过期 `--enable-rag` 表述，输出契约同步到当前阶段。
- 正式化 `INVARIANTS.md`：由模板升级为可执行不变量清单（引用、合约、文献 Gate、迁移、CLI 兼容）。
- 回归验证：
  - `pytest -q -p no:cacheprovider tests/test_pipeline_v2_persistence.py tests/test_db_schema_migration.py` 通过。
  - `paper-team --help` 正常。

### 当前状态
- 文档控制面与实现口径已进一步对齐，下一步可聚焦 P5-001/P5-002 的真实能力接线与发布门禁自动化。

---

## 2026-04-13 Session 5

### 目标
- 推进 P5-001 主任务：移除 `pipeline_v2` Phase 3/4 骨架逻辑，替换为真实模型驱动流程并补齐回归证据。

### 已完成
- `pipeline_v2` Phase 3 接入真实 writer/reviewer 调用，基于 `PROMPT_TEMPLATES + *_SYSTEM` 运行。
- 新增稳健 JSON 解析与字段兜底，覆盖 code block、半结构化文本、字段缺失场景。
- `pipeline_v2` Phase 4 接入真实 polisher 调用，并串联 `AIDetector` 与 `PlagiarismChecker` 计算终审指标。
- 阶段入库增强：`_persist_stage` 记录真实 `model_id/input_tokens/output_tokens/cost_cny`。
- 测试新增：
  - `test_run_pipeline_v2_uses_llm_outputs_and_persists_cost`
  - `test_run_pipeline_v2_llm_json_fallbacks`
- 验证结果：
  - `pytest -q tests/test_pipeline_v2_persistence.py` -> 4 passed
  - `pytest -q tests -p no:cacheprovider` -> 86 passed

### 当前状态
- P5-001 进入尾段：Phase 3/4 已真调用落地，剩余 Phase 1 Advisor 与 Phase 2.5 Data Analyst 去骨架。

---

## 2026-04-13 Session 6

### 目标
- 推进 P5-002：交付可执行的发布门禁自动化链路（schema + smoke + regression）。

### 已完成
- 新增 CLI 命令：`paper-team release-gate`
  - schema preflight：检查 `sessions` 必需列，缺失则阻断并提示 `db-migrate`。
  - smoke：自动执行 v2 (`run_pipeline_v2`) 与 legacy (`run_mock_pipeline`) 双路径 mock 验证。
  - regression：内置核心 pytest targets，并支持 `--target` 追加。
- 新增测试：`tests/test_cli_release_gate.py`
  - preflight 失败阻断
  - smoke+regression 成功路径
  - regression 失败阻断
- 验证结果：
  - `pytest -q tests/test_cli_release_gate.py tests/test_cli_v2_engine.py -p no:cacheprovider` -> 5 passed
  - `pytest -q tests -p no:cacheprovider` -> 89 passed
  - `python3 -m academic_agent_team.cli.console release-gate --skip-regression` -> schema + 双引擎 smoke 通过

### 当前状态
- P5-002 已实现并具备测试覆盖；Phase 5 剩余核心项为 Gate 5 人类验收与 v1.1 RC 发布基线确认。

---

## 2026-04-13 Session 7

### 目标
- 完成 P5-001 收尾：将 `pipeline_v2` 的 Phase 1 与 Phase 2.5 从骨架替换为真实调用流程。

### 已完成
- `pipeline_v2` Phase 1:
  - 接入 advisor 模型调用（`PROMPT_TEMPLATES["advisor"] + ADVISOR_SYSTEM`）。
  - 增加 topic options 生成、方向分析字段兜底、人工 H1 选择边界保护。
- `pipeline_v2` Phase 2.5:
  - 接入 data_analyst 模型调用（新增 `DATA_ANALYST_SYSTEM`）。
  - 增加 `_profile_data_file`，支持 CSV/JSON/文本数据概览构建。
  - 分析输出新增 `analysis_type/interpretation/key_findings/statistics_results` 结构化结果与兜底。
- 持久化一致性：
  - `topic_done` 与 `analysis_done` 均记录真实 `model_response` 元数据。
  - Phase 2 文献检索查询改为优先使用 H1 选中方向。
- 测试新增与验证：
  - 新增 `test_run_pipeline_v2_executes_data_analysis_phase`
  - `pytest -q tests/test_pipeline_v2_persistence.py -p no:cacheprovider` -> 5 passed
  - `pytest -q tests -p no:cacheprovider` -> 90 passed
  - `python3 -m academic_agent_team.cli.console release-gate --skip-regression` -> schema + 双引擎 smoke 通过

### 当前状态
- P5-001 已完成；Phase 5 主线剩余 Gate 5 人类验收与 v1.1 RC 发布基线确认。

---

## 2026-04-13 Session 8

### 目标
- 形成 Gate 5 最终验收包，输出可审计的 v1.1 RC 发布基线并准备人类确认。

### 已完成
- 执行完整发布门禁：
  - `python3 -m academic_agent_team.cli.console release-gate`
  - 结果：schema preflight + v2/legacy smoke + regression 全通过（`9 passed`）。
- 生成 RC 基线报告：`docs/ai/RELEASE_BASELINE_V1_1_RC.md`。
- 更新门禁/回滚文档：
  - `docs/ai/GATES.md` 增补 Gate 5 验收证据。
  - `docs/ai/ROLLBACK.md` 更新最后验证日期并记录 2026-04-13 复核。
- 控制面更新：
  - `state.yaml` 写入待人类决策项（Gate 5 最终 Yes/No）。

### 当前状态
- Gate 5 前置证据齐全，等待人类最终确认以完成 Phase 5。

---

## 2026-04-13 Session 9

### 目标
- 完成 Gate 5 最终确认闭环并更新控制面状态。

### 已完成
- 人类给出最终确认：`Yes`。
- Gate 5 状态切换为 Completed：
  - `state.yaml`：`gates.phase_5.status=COMPLETED`，`human_confirmed=true`。
  - `GATES.md`：Phase 5 标记为“已完成”，写入确认日期与证据。
  - `TASK_BOARD.md`：Gate 5 验收项转入 Done。
- `v1.1 RC` 基线状态更新为 `APPROVED`（`RELEASE_BASELINE_V1_1_RC.md`）。

### 当前状态
- Phase 5 已正式关闭；项目进入“v1.1 正式发布准备 / v1.2 规划”阶段。

---

## 2026-04-13 Session 10

### 目标
- 在完成 `v1.1.0` 发布后，启动后续版本（v1.2）规划入口。

### 已完成
- 新增 `docs/ai/V1_2_PLAN.md`，定义 v1.2 目标、候选范围、里程碑、风险与验收标准。
- `TASK_BOARD.md` 更新为 v1.2 规划评审进行中（P6-001）。

### 当前状态
- 代码与治理基线已发布到 `v1.1.0`；后续工作转入 v1.2 规划与范围冻结。

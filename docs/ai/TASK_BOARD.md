# Task Board - 任务看板

## 📋 当前阶段: Phase 5 - 稳定性与实现

### 🔴 阻塞中 (Blocked)
- [ ] （当前无）

### 🟡 进行中 (In Progress)
- [ ] P6-001: v1.2 规划评审（见 `docs/ai/V1_2_PLAN.md`）

### 🟢 已完成 (Done)
- [x] P0-000: 初始化项目内存结构
- [x] P0-001: 完成任务理解并通过 Gate 0
- [x] P1-001: 完成人机协作协议并通过 Gate 1
- [x] P2-001: 完成 PRD 并通过 Gate 2
- [x] P3-001: 完成架构设计并通过 Gate 3
- [x] P4-001: 完成 Agent OS 设计并通过 Gate 4
- [x] P5-000: 启动稳定性与实现阶段
- [x] P5-003: CLI 默认入口切换到 `pipeline_v2`（`legacy` 保留回退）
- [x] DOC-001: 修复 `state.yaml` 控制面语法错误
- [x] DOC-002: 同步 PRD/概览文档与当前 CLI 命令口径
- [x] QA-001: 回归证据采集（v2 持久化/CLI 引擎测试）
- [x] P5-004: 执行 `sessions.db` schema 迁移（补齐 `run_mode` / `budget_cap_cny`）并完成 v2/legacy smoke 验证
- [x] P5-005: 将 `pipeline_v2` 文献/引用 Gate 从告警升级为硬阻断，并补充失败场景回归测试
- [x] P5-006: 将 `pipeline_v2` Phase 3/4 升级为真实 writer/reviewer/polisher 调用，移除对应骨架评分逻辑
- [x] QA-002: 新增 v2 Phase3/4 成功路径与 JSON 脏输出兜底回归测试，全量通过 `86 passed`
- [x] P5-002: 新增 `paper-team release-gate`（schema preflight + v2/legacy smoke + regression）
- [x] QA-003: `release-gate` 相关 CLI 回归测试新增并通过，全量回归 `89 passed`
- [x] P5-001: 完成 F107-F112 的真实 API 接线（Phase 1 Advisor / Phase 2.5 Data Analyst 已去骨架）
- [x] QA-004: 新增 Phase 2.5 数据分析阶段回归用例，全量回归 `90 passed`
- [x] DOC-003: 对齐 `ARCH.md` / `PRD.md` / `INVARIANTS.md` 与当前 Phase 5 实现状态
- [x] Gate 5 人类验收（已确认 Yes，`v1.1 RC` 基线批准）

### ⏳ 待办 (Pending - 后续阶段)
- v1.2 范围冻结与里程碑确认

---

## 任务依赖关系

```
Phase 0 ─────► Phase 1 ─────► Phase 2 ─────► Phase 3 ─────► Phase 4 ─────► Phase 5
  │              │              │              │              │              │
  ▼              ▼              ▼              ▼              ▼              ▼
 Gate 0        Gate 1        Gate 2        Gate 3        Gate 4        Gate 5
(确认)        (确认)        (确认)        (确认)        (确认)        (确认)
                                            │
                                            ▼
                                      [编码解禁]
```

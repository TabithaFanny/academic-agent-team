# Governance Gates 门禁清单

## Phase 0: 理解任务
- **状态**: ✅ 已完成
- **门禁条件**: 人类确认目标、复杂性分析、关键假设正确
- **确认日期**: 2026-04-08
- **决策记录**: D1 AutoGen为主 | D2 MVP范围确认 | D3 4周周期

## Phase 1: 人机协作协议
- **状态**: ✅ 已完成
- **门禁条件**: 人类确认决策边界、I/O 契约、风险控制措施
- **确认日期**: 2026-04-08

## Phase 2: PRD
- **状态**: ✅ 已完成
- **门禁条件**: 人类确认完整 PRD，所有模块标注 MVP/Optional，阻塞问题清零
- **确认日期**: 2026-04-08
- **决策记录**: B001 CNKI用MCP | B002 Embedding可切换 | B003 用paper-qa

## Phase 3: 架构
- **状态**: ✅ 已完成
- **门禁条件**: 人类确认技术栈、分层设计、数据流、禁止行为
- **确认日期**: 2026-04-08
- **决策记录**: D4 采用 GroupChat 多 Agent 讨论模式
- **🔓 编码禁令已解除**

## Phase 4: Agent Operating System
- **状态**: ✅ 已完成
- **门禁条件**: 人类确认 Agent 角色、执行顺序、记忆策略、错误闭环
- **确认日期**: 2026-04-08
- **补充建议**: 文献质量 Gate、内容质量 Gate (≥85分)、CNKI 降级策略

## Phase 5: 稳定性与回滚
- **状态**: ✅ 已完成
- **门禁条件**: 人类确认缺陷流程、回滚预案、发布门禁
- **确认日期**: 2026-04-13（人类明确回复：Yes）
- **阶段决策**: D8 MVP 延长到 6 周 | D12 CLI 默认引擎切换为 pipeline_v2（legacy 可回退）| D13 批准并执行 sessions.db 迁移策略 A
- **当前阻塞**: 无
- **验收证据**:
  - `pytest -q tests -p no:cacheprovider` → `90 passed`
  - `python3 -m academic_agent_team.cli.console release-gate` → schema + smoke + regression 通过（`9 passed`）
  - 发布基线文档: `docs/ai/RELEASE_BASELINE_V1_1_RC.md`

---

## 门禁规则

1. **顺序执行**: Phase N 必须在 Phase N-1 确认后才能开始
2. **人类确认**: 每个门禁必须获得明确的人类 "Yes" 确认
3. **状态不一致**: 若 artifacts 与 state.yaml 冲突，立即停止
4. **升级机制**: 不确定问题必须升级给人类决策

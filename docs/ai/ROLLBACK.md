# Rollback Plan - 回滚预案

> 本文件记录 Phase 5 的可执行回滚流程与实测结果。

## 状态

- 当前状态: ✅ `COMPLETED`
- 最后验证日期: `2026-04-13`
- 结论: 回滚路径可执行，数据库 schema 阻塞已解除（显式迁移 + 双引擎 smoke 已验证）。

---

## 1. 回滚目标

1. 当 `pipeline_v2` 出现不可接受故障时，能快速回退到 `legacy` 引擎。
2. 回滚后必须保证会话可创建、状态可查询、费用记录可追溯。

---

## 2. 回滚触发条件

- P0/P1 故障: `paper-team start --engine v2` 无法完成基本流程。
- 关键回归: v2 持久化/会话状态与基线行为不一致。
- 发布门禁失败: 回归测试未达发布阈值且 30 分钟内无法修复。

---

## 3. 回滚执行流程（命令级）

1. 切换引擎回退：
```bash
paper-team start --topic "<topic>" --journal "中文核心" --mode autopilot --engine legacy --mock --no-interactive
```
2. 验证会话可用：
```bash
paper-team sessions --limit 5
paper-team status <session_id>
```
3. 验证成本记录可读（若有）：
```bash
paper-team cost <session_id>
```
4. 记录回滚事件到 `docs/ai/CHANGE_LOG.md` 和 `docs/ai/SESSION_NOTES.md`。

---

## 4. 2026-04-10 实测结果

| 检查项 | 结果 | 备注 |
|--------|------|------|
| v2 启动演练 | ❌ 失败 | `Detected legacy sessions.db schema missing columns: ['budget_cap_cny','run_mode']` |
| legacy 启动演练 | ❌ 失败 | 同样被 schema 保护门阻断 |
| schema 取证 | ✅ 完成 | `sessions` 表缺 `run_mode` / `budget_cap_cny` |

结论：回滚命令路径存在，但当前 DB schema 未完成迁移，导致 v2/legacy 均不可创建新会话。

---

## 5. 2026-04-11 迁移与复测结果

| 检查项 | 结果 | 备注 |
|--------|------|------|
| `paper-team db-migrate --yes` | ✅ 成功 | 自动备份：`sessions.db.bak.20260412011238` |
| v2 启动演练 | ✅ 成功 | `start --engine v2 --mock --no-interactive` 完成到 export |
| legacy 启动演练 | ✅ 成功 | `start --engine legacy --mock --no-interactive` 完成到 export |
| sessions 查询 | ✅ 成功 | `paper-team sessions --limit 3` 可读取最新会话 |

---

## 6. 回归预防

- 将迁移脚本纳入 CI 前置检查，避免运行时才触发 schema 阻塞。
- 在发布门禁新增 “DB schema preflight” 步骤。
- 每次引擎切换前执行最小 smoke 流程（start/sessions/status）。

## 7. 2026-04-13 发布门禁复核

| 检查项 | 结果 | 备注 |
|--------|------|------|
| `paper-team release-gate` | ✅ 通过 | schema preflight + v2/legacy smoke + regression(`9 passed`) |
| v2 smoke session | ✅ 通过 | `dbe49a56-a9be-481b-a28c-f319dee8a747` |
| legacy smoke session | ✅ 通过 | `5d71c925-5124-410c-8622-f4dfa2f7c936` |

结论：回滚路径与发布门禁均可执行，满足 Gate 5 人类验收前置条件。

# Release Baseline - v1.1 RC

## 状态
- 基线版本: `v1.1 RC`
- 生成日期: `2026-04-13`
- 当前阶段: `Phase 5`
- 发布门禁: `APPROVED`
- 人类审批: `YES`（2026-04-13）

## 基线目标
1. 验证默认执行栈 `pipeline_v2` 全链路可用。
2. 验证 `legacy` 回退路径可用。
3. 验证 schema preflight + regression 自动门禁稳定。

## 验收证据

### 1) 全量回归
- 命令: `pytest -q tests -p no:cacheprovider`
- 结果: `90 passed`

### 2) 发布门禁（完整）
- 命令: `python3 -m academic_agent_team.cli.console release-gate`
- 结果:
  - schema preflight: passed
  - smoke(v2): passed, session_id=`dbe49a56-a9be-481b-a28c-f319dee8a747`
  - smoke(legacy): passed, session_id=`5d71c925-5124-410c-8622-f4dfa2f7c936`
  - regression: `9 passed`
  - gate summary: `Release gate passed`

### 3) 发布门禁（轻量 smoke）
- 命令: `python3 -m academic_agent_team.cli.console release-gate --skip-regression`
- 结果: schema + 双引擎 smoke 持续通过

## 当前不阻断告警
- `chromadb` 未安装时出现告警并自动降级，当前不阻断主流程（相似度查询返回空结果）。
- `MagicCNKI` 未安装时走 mock 搜索路径，当前 smoke 场景可接受。

## 已完成能力清单（P5）
- `pipeline_v2` Phase 1/2/2.5/3/4/5 均已接线，门禁可执行。
- `paper-team db-migrate --yes` 支持显式迁移 legacy schema。
- `paper-team release-gate` 提供发布前自动门禁闭环。

## 人类确认项（Gate 5）
- 是否批准以当前基线作为 `v1.1 RC` 发布候选。

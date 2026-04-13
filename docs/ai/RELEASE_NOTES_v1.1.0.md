# Release Notes - v1.1.0

发布日期：2026-04-13

## 版本概览
- 完成 Phase 5 稳定性与回滚收敛，Gate 5 已人工确认通过。
- 默认执行引擎为 `pipeline_v2`，`legacy` 保留回退路径。
- 发布门禁 `paper-team release-gate` 可执行 schema preflight + 双引擎 smoke + regression。

## 主要新增
- `pipeline_v2` 全阶段接线增强：
  - Phase 1: Advisor 真实调用 + H1 人工决策联动
  - Phase 2: 文献门禁硬阻断（引用验证/数量阈值）
  - Phase 2.5: Data Analyst 真实调用 + 数据概览兜底
  - Phase 3/4: Writer/Reviewer/Polisher 真实调用 + JSON 兜底
- 持久化增强：
  - `messages/cost_log` 记录真实 `model_id/input_tokens/output_tokens/cost_cny`
- 数据库治理：
  - `paper-team db-migrate --yes` 支持 legacy schema 显式迁移
- 发布治理：
  - `paper-team release-gate` 支持一键门禁验收

## 本次修复（稳定性关键）
- 收紧内容门禁：Reviewer 分数必须 `>= 85` 才通过迭代门。
- 移除真实模式静默降级 Mock：模型调用失败将显式报错阻断。
- 解耦 LLM Mock 与工具 Mock 开关，避免误触发整链路 Mock。
- `release-gate` 默认回归升级为全量 `tests`。

## 验收证据
- `pytest -q tests -p no:cacheprovider` -> `92 passed`
- `python3 -m academic_agent_team.cli.console release-gate` -> passed
  - schema preflight: passed
  - smoke(v2): passed
  - smoke(legacy): passed
  - regression: passed

## 已知事项
- 在未安装 `chromadb` 时，相似度查询会降级并输出告警（不阻断主流程）。
- 在未安装 `MagicCNKI` 时，检索会走 mock 路径（用于本地 smoke）。

# Academic Agent Team

面向论文写作场景的多 Agent 协作系统（CLI MVP）。

当前版本已对齐 PRD 的关键执行约束：
- Agent 合约校验（pydantic）
- 角色模型配置（可运行时切换）
- 会话持久化（SQLite）
- 成本追踪与日志审计
- 导出前四道门禁（contract/citation/format/ethics）

## 1. 功能概览

系统包含 5 个角色：
- `advisor` 选题顾问
- `researcher` 文献研究员
- `writer` 论文写手
- `reviewer` 审稿人
- `polisher` 润色 Agent

标准阶段流：
- `topic_done -> literature_done -> writing_done -> review_done -> polish_done -> export`

支持能力：
- 按角色配置不同 provider/model
- `role --set` 动态调整后续执行配置
- 费用记录与汇总查询
- rollback 标记后续产物 `stale`
- raw response 入库用于审计

## 2. 环境要求

- Python `>=3.11`
- 建议使用虚拟环境

## 3. 安装

```bash
cd academic-agent-team
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## 4. 快速开始

### 4.1 Mock 模式（本地快速验证）

```bash
paper-team start --mock --topic "测试课题" --journal "中文核心" --no-interactive
```

### 4.2 Real 模式（默认）

`start` 默认走 real 模式，至少需要可用 API key：

```bash
paper-team start --topic "社区治理中的智能分流" --journal "中文核心"
```

推荐在 `.env` 设置：
- `MINIMAX_API_KEY`（优先）
- 或 `ANTHROPIC_AUTH_TOKEN`

也可通过参数传入：

```bash
paper-team start \
  --topic "社区治理中的智能分流" \
  --journal "中文核心" \
  --api-key "<your-key>" \
  --base-url "https://api.minimaxi.com/anthropic" \
  --model "MiniMax-M2"
```

## 5. 常用命令

```bash
paper-team --help
```

当前 CLI 子命令：
- `start` 新建会话
- `sessions` 查看最近会话
- `status <session_id>` 查看进度与费用
- `cost <session_id>` 查看费用明细
- `role --show` 查看角色配置
- `role --set <agent> --to <provider/model> [--session-id <id>]` 切换角色模型
- `mode <session_id> <autopilot|manual>` 切换会话模式
- `rollback <session_id> --to-stage <stage>` 标记后续阶段为 stale
- `diff <session_id> <stage> <v1> <v2>` 对比版本
- `export <session_id> [--dest <dir>]` 导出产物目录
- `debug <session_id> [--tail N]` 查看会话摘要与日志尾部

## 6. 角色配置与运行时切换

运行时角色配置会持久化到：
- `session_store/role_profile.json`

示例：

```bash
paper-team role --show
paper-team role --set reviewer --to openai/gpt4o
paper-team role --set writer --to anthropic/sonnet --session-id <session_id>
```

说明：
- 切换后主要影响后续执行/新会话
- 传 `--session-id` 时会同步更新该会话的 `model_config` 快照

## 7. 输出与数据目录

执行后会生成：
- `session_store/sessions.db`：会话数据库
- `session_store/logs/<session_id>.log`：事件日志
- `session_store/role_profile.json`：运行时角色配置
- `output/<session_id>/`：阶段产物 JSON、`paper.md`、`raw_responses.json`

## 8. 测试

```bash
pytest -q -p no:cacheprovider
```

## 9. 已知限制与排障

### 9.1 旧数据库 schema 不兼容

如果出现类似错误：
- `Detected legacy sessions.db schema missing columns: ...`

说明当前 `sessions.db` 是旧结构。当前策略是显式阻断（不自动迁移）。

解决方式：
- 使用新的工作目录重新运行，或
- 删除旧 `session_store/sessions.db` 后重建（仅在你确认不保留旧数据时）。

### 9.2 `diff` 依赖版本快照

`diff` 读取 `versions` 表，若当前会话没有版本快照，会提示版本不足。

## 10. 开发说明

建议流程：

```bash
git checkout -b feat/<your-topic>
pytest -q -p no:cacheprovider
```

提交前至少确认：
- 合约校验可运行
- CLI `--help` 可用
- mock 流程可完整落库

## 11. 许可证

暂未声明（如需开源发布，请补充 `LICENSE` 文件）。

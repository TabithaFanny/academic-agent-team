# Invariants - 不可妥协约束

> 本文件记录项目中不可违反的核心约束，任何实现都必须遵守。

## 状态: 已启用（与 PRD Section 4 同步）

---

### INV-001: 引用必须可溯源
- **描述**: 文献引用必须具备 DOI 或 CNKI 可验证链接，且验证率达到门禁要求。
- **违反后果**: 学术诚信风险、投稿被拒。
- **验证方式**: `citation_verification_gate` + 回归测试。
- **关联 PRD 段落**: `PRD.md` Section 4 / Section 5。

### INV-002: 合约校验不可绕过
- **描述**: 各阶段 payload 必须通过 Pydantic 合约校验，失败即阻断阶段推进。
- **违反后果**: 数据污染、阶段状态错乱。
- **验证方式**: `contracts/agent_contracts.py` + `tests/test_agent_contracts.py`。
- **关联 PRD 段落**: `PRD.md` Section 4。

### INV-003: 文献质量 Gate 必须硬阻断
- **描述**: 文献数量不足（当前阈值 `<30`）不得继续后续写作阶段。
- **违反后果**: 低质量语料导致后续产出失真。
- **验证方式**: `pipeline_v2.py` 门禁抛错 + `tests/test_pipeline_v2_persistence.py`。
- **关联 PRD 段落**: `PRD.md` Section 2.3 / Section 4。

### INV-004: 数据库 schema 变更必须可审计迁移
- **描述**: 任何 `sessions` 表结构升级必须通过显式迁移命令和备份策略执行。
- **违反后果**: 历史会话不可读、运行阻断。
- **验证方式**: `paper-team db-migrate --yes` + `tests/test_db_schema_migration.py`。
- **关联 PRD 段落**: `PRD.md` Section 4。

### INV-005: CLI 向后兼容
- **描述**: `paper-team` 的核心命令语义（start/status/sessions/export/rollback）不可破坏。
- **违反后果**: 现有自动化脚本与用户流程中断。
- **验证方式**: CLI 回归测试与 smoke。
- **关联 PRD 段落**: `PRD.md` Section 6。

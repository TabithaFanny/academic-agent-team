# Phase 5: 稳定性与回滚机制

> **状态**: 🔄 IN_PROGRESS  
> **依赖**: Phase 4 已通过 (Agent OS 设计完成)  
> **门禁**: 等待人类确认后进入实现阶段

---

## 1. 缺陷定位流程

### 1.1 缺陷分类体系

| 级别 | 名称 | 定义 | SLA | 示例 |
|------|------|------|-----|------|
| P0 | 阻断 | 核心流程完全不可用 | 立即 | Agent 崩溃、数据丢失 |
| P1 | 严重 | 主要功能受损 | 4h | RAG 检索失败、生成乱码 |
| P2 | 一般 | 次要功能异常 | 24h | 格式错误、引用缺失 |
| P3 | 轻微 | 体验问题 | 7d | 响应慢、提示不友好 |

### 1.2 缺陷定位决策树

```
[用户报告问题]
    ↓
[Agent 层面检查]
    ├── GroupChat 日志完整？
    │   ├── 否 → 检查 AutoGen 版本兼容性
    │   └── 是 → 继续
    ├── 哪个 Agent 出错？
    │   ├── Researcher → 跳到 RAG 层
    │   ├── Writer/Polisher → 跳到 LLM 层
    │   └── Reviewer → 检查评分逻辑
    ↓
[RAG 层面检查] (如涉及文献)
    ├── 文献搜索返回结果？
    │   ├── 否 → 检查 API 连通性 (arXiv/CNKI)
    │   └── 是 → 继续
    ├── Chroma 查询返回？
    │   ├── 否 → 检查 Embedding 模型
    │   └── 是 → 检查 top_k / 相关性阈值
    ↓
[LLM 层面检查]
    ├── API 调用成功？
    │   ├── 否 → 检查 key / quota / rate limit
    │   └── 是 → 继续
    ├── 响应格式正确？
    │   ├── 否 → 检查 prompt 模板
    │   └── 是 → 检查 Pydantic 合约
    ↓
[存储层检查]
    ├── SQLite 写入成功？
    ├── 项目文件完整？
    └── 向量库一致性？
```

### 1.3 自动诊断脚本

```bash
# scripts/diagnose.sh <project_id>
# 自动收集:
# - 最近 100 条 GroupChat 消息
# - 最近 5 次 LLM 调用及响应
# - Chroma collection 状态
# - SQLite 项目记录
# 输出: diagnostics/<timestamp>/report.json
```

---

## 2. 回滚预案

### 2.1 回滚触发条件

| 触发条件 | 自动/手动 | 回滚目标 |
|----------|----------|----------|
| 测试覆盖率下降 > 5% | 自动 | 上一个稳定 commit |
| CI 红超过 30 分钟 | 自动 | 上一个绿色 commit |
| P0 Bug 上线 | 手动 | 上一个发布 tag |
| Embedding 模型更换后召回率下降 | 手动 | 上一个模型版本 |

### 2.2 数据回滚策略

#### 代码回滚
```bash
# 标准回滚流程
git revert --no-commit HEAD~<n>..HEAD
git commit -m "revert: rollback to <stable_tag>"
git push origin main
```

#### 向量库回滚 (Chroma)
```python
# 方案 1: Collection 快照
# 每次发布前自动执行
chroma_client.backup_collection(
    collection_name="literature",
    backup_path=f"backups/chroma_{timestamp}.tar.gz"
)

# 回滚
chroma_client.restore_collection(
    backup_path="backups/chroma_<target_timestamp>.tar.gz"
)
```

#### SQLite 回滚
```bash
# 自动备份 (每日 + 发布前)
cp data/papers.db backups/papers_$(date +%Y%m%d).db

# 回滚
cp backups/papers_<target_date>.db data/papers.db
```

### 2.3 回滚验证清单

- [ ] 核心 API 端点健康检查通过
- [ ] 基础 RAG 查询返回预期结果
- [ ] GroupChat 能完成一次完整对话
- [ ] 无新增 P0/P1 告警

---

## 3. 回归预防策略

### 3.1 测试金字塔

```
                    ╭─────────────╮
                    │  E2E 测试   │  5 个关键场景
                    │  (慢、贵)    │
                ╭───┴─────────────┴───╮
                │   集成测试           │  Agent 间协作、RAG 流程
                │   (分钟级)           │
            ╭───┴─────────────────────┴───╮
            │       单元测试               │  合约、工具函数、解析器
            │       (秒级)                 │
            ╰─────────────────────────────╯
```

### 3.2 关键测试场景 (必须 100% 通过)

| ID | 场景 | 覆盖模块 | 预期结果 |
|----|------|----------|----------|
| E2E-01 | 完整论文生成流程 | 全链路 | 5 分钟内生成完整论文 |
| E2E-02 | RAG 文献检索 | Researcher + Chroma | 返回 ≥10 篇相关论文 |
| E2E-03 | CNKI 降级测试 | Researcher + Fallback | CNKI 失败后切换 Semantic Scholar |
| E2E-04 | Writer-Reviewer 循环 | GroupChat | 最多 5 轮后达成 accept |
| E2E-05 | 离线模式 | 全链路 (--offline) | 使用本地模型完成生成 |

### 3.3 回归检测机制

#### 黄金测试用例 (Golden Tests)
```python
# tests/golden/test_rag_recall.py
def test_rag_recall_rate():
    """确保 RAG 召回率不低于 baseline"""
    baseline_recall = 0.85
    current_recall = measure_recall(golden_queries)
    assert current_recall >= baseline_recall, \
        f"RAG 召回率下降: {current_recall} < {baseline_recall}"
```

#### 自动回归检测 CI Job
```yaml
# .github/workflows/regression.yml
regression-test:
  runs-on: ubuntu-latest
  steps:
    - name: Run golden tests
      run: pytest tests/golden/ -v --tb=short
    - name: Compare metrics
      run: |
        python scripts/compare_metrics.py \
          --baseline .metrics/baseline.json \
          --current .metrics/current.json \
          --threshold 0.05
```

---

## 4. 测试与快照策略

### 4.1 快照类型

| 快照类型 | 频率 | 保留期 | 内容 |
|----------|------|--------|------|
| 代码快照 | 每次 commit | 永久 | Git history |
| 向量库快照 | 每日 + 发布前 | 30 天 | Chroma collection |
| SQLite 快照 | 每日 + 发布前 | 30 天 | 项目数据库 |
| 配置快照 | 每次变更 | 90 天 | config/*.yaml |
| Prompt 快照 | 每次变更 | 永久 | prompts/*.md |

### 4.2 快照自动化

```python
# academic_agent_team/storage/snapshot.py

class SnapshotManager:
    def create_release_snapshot(self, version: str):
        """发布前创建完整快照"""
        timestamp = datetime.now().isoformat()
        snapshot_dir = f"backups/{version}_{timestamp}"
        
        # 1. Chroma 备份
        self.backup_chroma(snapshot_dir)
        
        # 2. SQLite 备份
        self.backup_sqlite(snapshot_dir)
        
        # 3. 配置备份
        self.backup_configs(snapshot_dir)
        
        # 4. Prompt 模板备份
        self.backup_prompts(snapshot_dir)
        
        # 5. 记录元数据
        self.write_manifest(snapshot_dir, {
            "version": version,
            "timestamp": timestamp,
            "git_sha": self.get_git_sha(),
        })
        
        return snapshot_dir
```

### 4.3 测试隔离策略

```python
# tests/conftest.py

@pytest.fixture(scope="function")
def isolated_chroma(tmp_path):
    """每个测试使用独立的向量库"""
    client = chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory=str(tmp_path / "chroma"),
        anonymized_telemetry=False
    ))
    yield client
    client.reset()

@pytest.fixture(scope="function")
def isolated_sqlite(tmp_path):
    """每个测试使用独立的 SQLite"""
    db_path = tmp_path / "test.db"
    yield str(db_path)
    db_path.unlink(missing_ok=True)
```

---

## 5. 发布门禁 (Release Gates)

### 5.1 发布门禁清单

```yaml
# .github/workflows/release-gate.yml
release-gate:
  jobs:
    unit-tests:
      - name: 单元测试 100% 通过
        threshold: 100%
        
    integration-tests:
      - name: 集成测试 100% 通过
        threshold: 100%
        
    e2e-tests:
      - name: E2E 关键场景全部通过
        scenarios: [E2E-01, E2E-02, E2E-03, E2E-04, E2E-05]
        
    coverage:
      - name: 代码覆盖率
        min_line_coverage: 80%
        min_branch_coverage: 70%
        
    golden-tests:
      - name: 黄金测试无回归
        baseline: .metrics/baseline.json
        max_degradation: 5%
        
    security:
      - name: 无高危漏洞
        tools: [safety, bandit]
        
    docs:
      - name: CHANGELOG 已更新
        path: docs/CHANGELOG.md
```

### 5.2 发布流程

```
[开发完成]
    ↓
[创建 Release PR]
    ↓
[自动运行发布门禁] ─────────────────────────────────────────┐
    │                                                        │
    ├── 单元测试 ──── 失败 → 拒绝合并，标记失败 Case ────────→ 退出
    ├── 集成测试 ──── 失败 → 拒绝合并，标记失败 Case ────────→ 退出
    ├── E2E 测试 ──── 失败 → 拒绝合并，标记失败场景 ─────────→ 退出
    ├── 覆盖率检查 ── < 80% → 拒绝合并，显示差距 ────────────→ 退出
    ├── 黄金测试 ──── 回归 > 5% → 拒绝合并，需 P0 审批 ─────→ 退出
    └── 安全扫描 ──── 高危 → 拒绝合并，需安全团队审批 ──────→ 退出
    │
    ↓ (全部通过)
[创建发布快照]
    ↓
[人工确认] ← 必须，不可自动合并
    ↓
[合并 + 打 Tag]
    ↓
[发布完成]
```

### 5.3 紧急发布流程

```
[P0 Bug 需紧急修复]
    ↓
[创建 hotfix 分支]
    ↓
[最小化修复 + 最小化测试]
    │
    ├── 受影响模块测试 100% 通过
    ├── E2E 关键场景通过
    └── 双人 Code Review
    ↓
[紧急发布审批 (2 人)]
    ↓
[发布 + 标记为 hotfix]
    ↓
[24h 内补充完整测试]
```

---

## 6. 稳定性保证计划

### 6.1 SLA 承诺

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| 论文生成成功率 | ≥ 95% | 成功生成 / 总请求 |
| RAG 召回率 | ≥ 85% | 相关文献 / 查询文献 |
| 平均生成时间 | ≤ 5 分钟 | 端到端耗时 |
| P0 Bug 修复时间 | ≤ 4 小时 | 发现到修复 |
| 回归率 | ≤ 2% | 回归 Bug / 总发布 |

### 6.2 监控与告警

```python
# academic_agent_team/monitoring/alerts.py

class AlertManager:
    def check_generation_success_rate(self):
        """每小时检查生成成功率"""
        rate = self.metrics.get_success_rate(hours=1)
        if rate < 0.90:  # 预警阈值
            self.send_alert(
                level="warning",
                message=f"生成成功率下降: {rate:.2%}"
            )
        if rate < 0.80:  # 严重阈值
            self.send_alert(
                level="critical",
                message=f"生成成功率严重下降: {rate:.2%}",
                auto_rollback=True
            )
```

### 6.3 健康检查端点

```python
# academic_agent_team/api/health.py

@app.get("/health")
async def health_check():
    """综合健康检查"""
    checks = {
        "sqlite": check_sqlite_connection(),
        "chroma": check_chroma_connection(),
        "llm_api": check_llm_api(),
        "disk_space": check_disk_space(),
    }
    
    healthy = all(c["status"] == "ok" for c in checks.values())
    return {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }
```

---

## 7. 用户确认建议整合

根据 Phase 4 验收时的补充建议：

### 7.1 文献质量 Gate
```python
# 在 Phase 2 (文献调研) 结束后检查
def check_literature_quality_gate(papers: list[Paper]) -> GateResult:
    if len(papers) < 30:
        return GateResult(
            passed=False,
            reason=f"文献数量不足: {len(papers)} < 30",
            action="返回 Phase 1 扩大搜索范围"
        )
    return GateResult(passed=True)
```

### 7.2 内容质量 Gate
```python
# Reviewer 评分低于 85 强制重写
def check_content_quality_gate(review_result: ReviewResult) -> GateResult:
    if review_result.overall_score < 85:
        return GateResult(
            passed=False,
            reason=f"内容质量不足: {review_result.overall_score} < 85",
            action="返回 Writer 重写",
            max_retries=3
        )
    return GateResult(passed=True)
```

### 7.3 CNKI 降级策略
```python
# CNKI 失败时自动切换
async def search_with_fallback(query: str) -> list[Paper]:
    try:
        return await search_cnki(query)
    except (CnkiRateLimitError, CnkiBlockedError) as e:
        logger.warning(f"CNKI 搜索失败: {e}, 切换到备用源")
        # 并行查询备用源
        results = await asyncio.gather(
            search_semantic_scholar(query),
            search_openalex(query)
        )
        return merge_and_dedupe(results)
```

---

## 8. 2026-04-10 实测门禁证据

### 8.1 回归测试结果（本地 .venv）

| 命令 | 结果 | 结论 |
|------|------|------|
| `pytest tests/test_pipeline_v2_persistence.py tests/test_cli_v2_engine.py -q -p no:cacheprovider` | `3 passed` | ✅ v2 持久化与 CLI 引擎切换主路径可用 |
| `pytest tests -q -m "not asyncio" -p no:cacheprovider` | `44 passed, 1 failed, 36 deselected` | ⚠️ 大部分同步用例通过，`test_e2e` 中 LaTeX 用例因缺 `jinja2` 失败 |
| `pytest tests/test_pipeline_v2_persistence.py tests/test_cli_v2_engine.py tests/test_ai_detection.py tests/test_citation_verifier.py -q -p no:cacheprovider` | `3 passed, 21 failed` | ⚠️ 失败原因为环境缺 `pytest-asyncio`，并非业务逻辑回归 |

### 8.2 环境阻塞证据

- `pytest-asyncio` 缺失，导致 `@pytest.mark.asyncio` 用例无法执行。
- `jinja2` 缺失，导致 LaTeX 导出相关用例失败。
- 当前网络受限，无法通过 `pip install pytest-asyncio` 在线补齐依赖。

### 8.3 回滚演练结果（CLI 引擎）

| 演练命令 | 结果 | 说明 |
|----------|------|------|
| `paper-team start ... --engine v2 --mock` | 失败 | 触发 schema 保护门：`sessions.db` 缺 `run_mode/budget_cap_cny` |
| `paper-team start ... --engine legacy --mock` | 失败 | 同样触发 schema 保护门（统一存储层校验） |

SQLite 实测 schema（`session_store/sessions.db`）显示 `sessions` 表确实缺少 `run_mode` 与 `budget_cap_cny`，符合阻塞判断。

### 8.4 Gate 5 当前判定

- 结论：**Gate 5 暂不满足放行条件**。
- 原因：
  - 数据迁移策略未获人类批准（高风险，涉及历史会话库）。
  - 测试环境依赖不完整，异步与 LaTeX 路径无法完成全量回归。
- 处置：升级为人类决策项并写入 `state.yaml`。

---

## 输出契约

- **Current Phase**: Phase 5 - 稳定性与回滚
- **What was completed**: 
  - 缺陷分类体系与定位决策树
  - 代码/向量库/SQLite 回滚预案
  - 回归预防策略与测试金字塔
  - 快照策略与自动化脚本
  - 发布门禁清单与流程
  - SLA 承诺与监控方案
  - 用户补充建议整合 (文献质量 Gate、内容质量 Gate、CNKI 降级)
- **Gate status**: 🟡 等待人类确认
- **Risks**: 
  - CNKI MCP 可能因反爬虫策略频繁失效
  - 快照策略增加存储成本
- **Need human decision?**: Yes
- **Next action**: 确认后进入实现阶段 (Implementation)

---

**请确认是否进入实现阶段（Yes/No）**

确认后将开始：
1. 完整多代理实现框架代码 (AutoGen GroupChat)
2. 每个 Agent 的 System Prompt 模板
3. 记忆层实现 (Chroma + SQLite Schema)
4. 错误处理与 Gate 机制代码
5. 最小可运行 Demo (主题: "人工智能对新闻传播伦理的影响")

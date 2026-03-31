# PRD: 学术研究 Agent Team

## 学术论文写作 AI 多智能体协作系统

---

## 1. Executive Summary

### 一句话概述
基于 Microsoft AutoGen 框架，构建由选题顾问、文献研究员、论文写手、审稿人、润色 Agent 组成的 5-Agent Team（v1.0），覆盖从**选题到投稿包导出**的完整学术研究流程；图表师 Agent 在 v1.1 引入。

### 核心价值
- **效率提升**: 自动化文献调研、论文撰写、润色审稿
- **质量保证**: 内置 30+ Prompt 模板，对标顶刊标准
- **灵活介入**: 默认自动推进，用户可随时插话、重定向、回溯
- **多模型支持**: 每个 Agent 可独立配置 provider/model，并支持会话中切换角色配置

### 目标用户
- 研究生（写第一篇论文）
- 高校教师（指导学生/投稿顶刊）
- 科研人员（申请基金/研究报告）
- 学术团队（协作研究）

### 关键指标
| 指标 | 当前 | 目标 | 时间线 |
|------|------|------|--------|
| 文献调研效率 | 3-5天 | ≤4小时 | v1.0 |
| 论文初稿完成 | 2-4周 | 3-7天 | v1.0 |
| 审稿反馈轮次 | 3-5轮 | 1-2轮 | v2.0 |
| 格式错误率 | 30% | <5% | v1.0 |

---

## 1.5 产品最终形态 (Product Vision)

### 产品定位

> **「学术写作 AI 导师 + 协作搭档」**
> 不是论文代写器，而是一个带你写论文的 AI 团队——教你为什么这样写，帮你写得更好。

### 三个版本的实现形式

| 版本 | 交付形态 | 界面技术 | 核心特性 | 目标用户 |
|------|---------|----------|---------|---------|
| **v1.0 MVP** | 终端 TUI 应用 | Rich + Textual 分栏界面 | 分栏布局：左栏 Agent 对话 / 右栏论文 Markdown 实时预览 / 底部命令栏 / 顶部进度条+费用显示 | 技术型研究生、熟悉命令行的科研人员 |
| **v1.5** | 桌面应用 | Tauri (Rust + WebView) | 可视化拖拽论文结构，所见即所得编辑，内置文献管理 | 文科研究者、不熟悉命令行的用户 |
| **v2.0** | Web SaaS 平台 | React + FastAPI | 浏览器访问，导师/学生协作，实时同步编辑，权限管理 | 实验室、课题组、学术团队 |

### v1.0 TUI 界面原型

```
┌────────────────────────────────┬──────────────────────────┐
│  💬 Agent 对话区               │  📄 论文实时预览          │
│                                │                          │
│  🎯 选题顾问：                 │  # 社区治理AI智能分流     │
│  "你的课题方向有3个切入点：     │                          │
│   1. 技术路线（NLP分流模型）    │  ## 1. 引言              │
│   2. 制度视角（政策+AI融合）    │  随着人工智能技术的发展...│
│   3. 比较研究（中美社区治理）   │                          │
│                                │  ## 2. 文献综述           │
│   推荐方向2，创新性评分 8.5/10" │  [生成中...]             │
│                                │                          │
│  你：选方向2，但想加入案例分析  │                          │
│                                │                          │
├────────────────────────────────┤                          │
│ ⏱️ 进度: ████░░░░ 选题→文献    │  💰 已用: ¥0.8 / 预估¥3 │
│ 📌 输入命令 / 回复 Agent...    │  📊 AI味: --             │
└────────────────────────────────┴──────────────────────────┘
```

### 差异化竞争力

| 竞争维度 | ChatGPT / Kimi 等通用AI | 本产品 |
|---------|------------------------|--------|
| **文献真实性** | ❌ LLM 幻觉编造文献 | ✅ Semantic Scholar 真实检索，可点击查看原文 |
| **流程覆盖** | ❌ 单点辅助（润色一段话） | ✅ 选题→文献→撰写→审稿→去AI味→投稿 全流程 |
| **成本** | ❌ ChatGPT Plus ¥140/月 | ✅ DeepSeek 单篇 ¥0.4，混合方案 ¥2-5 |
| **期刊适配** | ❌ 不了解期刊格式要求 | ✅ 内置中文核心/CSSCI/IEEE/CCF-A 模板 |
| **人类控制** | ❌ 一次性输出，不可干预 | ✅ 默认自动推进 + 随时插话 + 可回退 |
| **去AI味** | ❌ 无此功能 | ✅ 内置可读性与重复表达指标实时显示 |

### 最终交付物愿景

用户走完全流程后，系统交付：

```
📦 最终输出包
├── 📄 paper_final.tex           # LaTeX 格式论文
├── 📄 paper_final.docx          # Word 格式论文
├── 📚 references.bib            # 参考文献（全部已验证 ✓）
├── 📁 figures/                  # 图表文件（v1.1 默认开启，v1.0 可选）
│   ├── architecture.png
│   ├── experiment_results.png
│   └── comparison_table.png
├── 📝 cover_letter.md           # 投稿信
├── 📊 quality_report.md         # 质量报告
│   ├── 创新性评分:   8.5/10
│   ├── 可读性评分:   4.3/5 (已优化 ✅)
│   ├── 格式合规:     100% ✅
│   └── 文献真实性:   28/28 已验证 ✅
└── 💰 cost_summary.md           # 费用明细（¥3.2）
```

---

## 2. Problem Statement

### Jobs-to-be-Done

| When... | I want to... | So I can... |
|---------|--------------|-------------|
| 研究初期 | 快速了解领域研究空白 | 确定有价值的选题方向 |
| 文献阅读 | 从海量文献中提取关键信息 | 高效完成文献综述 |
| 论文写作 | 快速产出结构完整的初稿 | 缩短投稿周期 |
| 润色修改 | 消除AI生成痕迹，达到顶刊标准 | 提高录用率 |
| 投稿准备 | 对标目标期刊格式要求 | 避免因格式问题被退稿 |

### 当前痛点

```
┌────────────────────────────────────────────────────────────────┐
│  学术论文写作痛点分析                                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  📚 文献调研 (3-5天)                                           │
│     ├── 找不到相关文献                                         │
│     ├── 阅读效率低，难以提取关键信息                           │
│     └── 文献管理混乱，难以复用                                 │
│                                                                │
│  ✍️ 论文撰写 (2-4周)                                           │
│     ├── 不知道如何组织论文结构                                 │
│     ├── 表达不专业，逻辑不清晰                                 │
│     └── 缺乏学术写作规范知识                                   │
│                                                                │
│  🔧 润色修改 (1-2周)                                           │
│     ├── AI生成痕迹明显，易被识别                              │
│     ├── 语言表达不够地道                                       │
│     └── 反复修改，效率低下                                     │
│                                                                │
│  📄 投稿准备 (3-5天)                                           │
│     ├── 格式不统一，引用不规范                                 │
│     ├── 图表不规范，不符合期刊要求                             │
│     └── 审稿意见回复不专业                                     │
│                                                                │
│  ⏰ 总耗时: 1-3个月                                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 用户研究总结

- 研究生平均写一篇论文花费 **3-6 个月**
- 50% 时间花在文献调研和整理
- 30% 时间花在反复润色修改
- 主要障碍：缺乏系统方法论、工具分散、效率低下

---

## 3. Opportunity Sizing

### 市场分析

| 层级 | 规模（人数） | 说明 |
|------|-------------|------|
| **TAM** (Total Addressable Market) | ~5000万人 | 全球在读研究生 (~4000万) + 高校科研人员 (~1000万)；原写"2.4亿"已修正，实际数据来源：UNESCO 2023 |
| **SAM** (Serviceable Addressable Market) | 1200万人 | 中国研究生 + 高校教师 |
| **SOM** (Serviceable Obtainable Market) | 50万人 | 愿意使用AI工具的学术用户 |

### 目标用户细分

| 用户群 | 规模（中国） | 痛点 | 付费意愿 |
|--------|-------------|------|----------|
| 在读硕士/博士 | 300万+ | 论文写作、时间压力 | 中 |
| 高校教师 | 180万+ | 指导学生、投稿顶刊 | 高 |
| 科研院所研究员 | 50万+ | 基金申请、论文产出 | 高 |
| 学术团队 | 1万+ | 协作效率、标准化 | 高 |

### RICE 计算

| 指标 | 数值 | 说明 |
|------|------|------|
| **Reach** (触达用户/季度) | 10,000 | 首季度目标用户量 |
| **Impact** (影响程度) | 3 (massive) | 标准 RICE 评分: 0.25/0.5/1/2/3 |
| **Confidence** (信心度) | 80% | 基于用户调研和市场分析 |
| **Effort** (人月) | 3 人月 | 1人 × 3个月 |
| **RICE Score** | **8,000** | = (10000 × 3 × 0.8) / 3 |

> 口径说明:
> - Reach 按首季度目标激活用户数计算（以试点渠道导入量为准）
> - Confidence 由用户访谈 + 小规模内测结果估算，每次版本发布后复盘更新
> - Effort 仅计核心研发人月，不含外部协作和市场投入

---

## 4. Success Metrics

### 核心 KPI

| Metric | Baseline | Target | Timeline | Measurement |
|--------|----------|--------|----------|-------------|
| 论文初稿完成周期 | 4周 | 1周 | v1.0 GA | 用户反馈统计 |
| 文献调研效率 | 5天 | 4小时 | v1.0 GA | 任务计时 |
| 导出门禁通过率（contract/citation/format/ethics） | N/A | >90% | v1.0 GA | 系统自动统计 |
| 会话恢复成功率（resume） | N/A | >95% | v1.0 GA | 恢复任务日志 |
| 用户满意度 (NPS) | N/A | >50 | v1.0 GA | 问卷调查 |
| 格式错误率 | 30% | <5% | v1.0 | 自动检查 |

### 功能验收标准

| 功能 | 验收条件 | 优先级 |
|------|----------|--------|
| 选题推荐 | 生成3-5个方向，每个含创新点分析 | Must |
| 文献调研 | 15分钟内完成20篇核心文献总结 | Must |
| 论文大纲 | 生成符合目标期刊结构的完整大纲 | Must |
| 摘要撰写 | 人工盲评平均分 ≥4.0/5（结构完整、结论清晰） | Should |
| 润色优化 | 可读性评分提升 ≥20%，并输出可追溯 diff 报告 | Should |
| 格式输出 | 通过期刊格式自动检查 | Must |
| 会话恢复 | 程序异常退出后可 `resume` 恢复到最近快照 | Must |
| 角色切换 | 运行时支持 `role set`，后续阶段按新配置执行 | Must |

---

## 5. User Stories

### 核心场景

```gherkin
Feature: 学术论文 AI 协作写作

  Scenario: 研究生快速完成论文初稿
    Given 我是一名在读硕士
    When 我输入研究课题"社区治理AI智能分流"
    And 我设定期刊目标为"中文核心期刊"
    Then 选题顾问在2分钟内推荐3个研究方向
    And 文献研究员在15分钟内完成20篇文献调研
    And 论文写手在2小时内产出完整初稿
    And 审稿人给出具体修改建议
    And 我可以选择性采纳或让AI修改

  Scenario: 研究者对标顶刊润色
    Given 我有一篇初稿
    When 我选择"IEEE Trans"目标期刊
    And 我启动"去AI味"润色流程
    Then 系统自动应用IEEE格式模板
    And 生成规范的参考文献格式
    And 输出符合顶刊标准的论文版本
    And 生成Cover Letter草稿

  Scenario: 人类全程介入控制
    Given AI正在执行某个阶段
    When 我说"停"或"重新来"
    Then AI立即暂停等待指令
    When 我说"重写引言"
    Then AI重新生成引言部分
    And 其他部分保持不变
```

### 用户故事详细版

| As a... | I want... | So I can... | Acceptance Criteria |
|---------|-----------|-------------|---------------------|
| 研究生 | 快速找到研究空白 | 确定有价值的选题 | 输出3-5个方向，含gap分析 |
| 研究生 | AI帮我读文献 | 快速提取关键信息 | 15分钟内总结20篇核心文献 |
| 研究生 | 自动生成论文框架 | 不用从零开始 | 输出符合期刊格式的大纲 |
| 研究生 | 提升文本自然度 | 减少机械化表达 | 人工可读性盲评 ≥4/5，且修改可追溯 |
| 导师 | 一键生成审稿意见 | 指导学生修改 | 输出结构化修改建议 |
| 研究者 | 对标目标期刊格式 | 形成可投稿草案包 | 自动应用引用/图表规范并输出人工复核清单 |

---

## 6. Functional Requirements

### MoSCoW 分类

#### Must Have (v1.0)

| ID | 功能 | 描述 | Acceptance Criteria |
|----|------|------|---------------------|
| M1 | Agent Team 框架 | 基于 AutoGen 的多 Agent 协作 | **5个** Agent 正常通信，共享 context（v1.0：选题顾问/文献研究员/论文写手/审稿人/润色 Agent；图表师 Agent 在 v1.1 加入） |
| M2 | 选题顾问 | 研究方向推荐和创新点分析 | 输出3-5个方向，含创新性/可行性评分 |
| M3 | 文献研究员 | 文献搜索、总结、对比分析 | 支持中英文文献，15分钟内完成调研 |
| M4 | 论文写手 | 基于模板生成论文各章节 | 内置30个 Prompt 模板，覆盖全流程 |
| M5 | 人类介入机制 | 默认自动推进，用户可随时审核/修改/重写 | 支持插话、暂停、重写指定章节、回退 |
| M6 | 格式输出 | LaTeX/Word 格式导出 | 内置 **4种** 期刊模板（中文核心/CSSCI/IEEE Trans/CCF-A），自动应用格式；v1.1 扩展到更多垂直模板 |
| M7 | 多模型支持 | 每个 Agent 可独立配置模型 | Claude/GPT-4/Gemini/DeepSeek/GLM/MiniMax/Ollama |
| M8 | 审稿人 Agent | 模拟顶刊审稿意见 | 输出结构化评审，含修改优先级 |
| M9 | 语言自然度润色 | 优化表达自然性和多样性 | 输出可读性指标报告 + diff，可回退 |

#### Should Have (v1.1)

| ID | 功能 | 描述 | Acceptance Criteria |
|----|------|------|---------------------|
| S1 | 图表师 Agent | 生成架构图/数据可视化 | 支持架构图、实验图、表格 |
| S2 | 对话历史导出 | 完整记录协作过程 | 支持txt/md格式导出 |

#### Could Have (v2.0)

| ID | 功能 | 描述 |
|----|------|------|
| C1 | Zotero MCP 集成 | 文献自动同步 |
| C2 | ResearchRabbit 集成 | 智能文献推荐图谱 |
| C3 | 基金申请书模块 | 国自然等基金申请 |
| C4 | 多语言翻译 | 中英日德互译 |

#### Won't Have (v1.0)

| ID | 功能 | 原因 |
|----|------|------|
| W1 | 完整API服务化 | 预计v2.0 |
| W2 | 团队协作功能 | 需要重新设计权限系统 |

---

## 7. Technical Requirements

### 架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Academic Agent Team                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      AutoGen Core Framework                      │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐      │   │
│  │  │  选题顾问  │  │ 文献研究员 │  │  论文写手  │  │   审稿人   │      │   │
│  │  │  Agent   │←→│   Agent   │←→│   Agent   │←→│   Agent   │      │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘      │   │
│  │                              ↕                                    │   │
│  │                        ┌───────────┐                              │   │
│  │                        │   润色     │                              │   │
│  │                        │   Agent   │                              │   │
│  │                        └───────────┘                              │   │
│  │         ↑                                       ↑                │   │
│  │         └────────────── 人类 (Team Lead) ───────┘                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Mission / Policy Layer                     │   │
│  │  用户目标、约束、预算、伦理边界、角色配置（可运行时切换）       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Skill Layer                                │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │ research-       │  │ academic-       │  │ scientific-     │  │   │
│  │  │ writing-skill   │  │ forge           │  │ visualization   │  │   │
│  │  │ (30 prompts)    │  │ (300+ skills)   │  │ (图表制作)       │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Tool Layer (v1.0 可用)                         │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │   │
│  │  │ Semantic  │  │ Skill     │  │ CrossRef  │  │ chatpaper │    │   │
│  │  │ Scholar   │  │ (免费搜索) │  │ API       │  │            │    │   │
│  │  │ API (免费) │  │           │  │           │  │            │    │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │   │
│  │                                                                   │   │
│  │                   Tool Layer (v2.0 扩展)                         │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐                    │   │
│  │  │ Zotero   │  │Research   │  │ Elicit/   │                    │   │
│  │  │ MCP      │  │ Rabbit     │  │ paper-qa  │                    │   │
│  │  └───────────┘  └───────────┘  └───────────┘                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       Model Layer                                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│  │  │Anthropic│ │ OpenAI  │ │DeepSeek │ │  GLM    │ │ MiniMax │  │   │
│  │  │ Claude  │ │ GPT-4   │ │  V3/R1  │ │ (智谱)  │ │         │  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│  │  ┌─────────┐ ┌─────────┐                                       │   │
│  │  │ Google  │ │ Ollama  │                                       │   │
│  │  │ Gemini  │ │ (本地)   │                                       │   │
│  │  └─────────┘ └─────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Agent 框架 | AutoGen 0.7+ | Microsoft 开源，多 Agent 协作，支持 GroupChat + 可中断调度器 |
| 编程语言 | Python 3.11+ | AutoGen 依赖 |
| CLI 界面 | Rich / Textual | 终端交互美化 |
| 模型客户端 | autogen-core | 支持多模型 |
| 技能加载 | Claude Code Skills | 复用现有 Skill |
| 输出格式 | LaTeX / Word | python-docx, pylatex |

### API 依赖

| Service | 用途 | Required | 备注 |
|---------|------|----------|------|
| Semantic Scholar API | 文献搜索（v1.0 核心数据源） | **Yes** | 免费开放 API，无需密钥即可基础查询 |
| GitHub Code Search API | 代码/文档搜索（用于 Skill 检索） | No (可选) | 不应阻断论文主流程 |
| CrossRef API | DOI 解析和引用数据 | **Yes** | 免费开放 API |
| chatpaper | PDF 全文解析（用户上传文献时使用） | No (可选) | 开源工具，github.com/kaixindelele/ChatPaper，本地部署，无 API 费用 |
| Anthropic API | Claude 模型 | Yes (任选其一) | 付费 |
| OpenAI API | GPT-4 模型 | Yes (任选其一) | 付费 |
| DeepSeek API | DeepSeek V3/R1 模型 | No (可选) | 性价比极高 |
| 智谱 GLM API | GLM-4 模型 | No (可选) | 国产模型 |
| MiniMax API | MiniMax 模型 | No (可选) | 国产多模态模型 |
| Google AI | Gemini 模型 | No (可选) | 付费 |
| Ollama | 本地模型 | No (可选) | 免费，本地部署 |

### 项目结构

```
academic-agent-team/
├── academic_agent_team/
│   ├── cli/console.py                 # 命令入口（start/resume/debug/status）
│   ├── pipeline.py                    # mock pipeline
│   ├── pipeline_real.py               # real pipeline (agent-first 执行器)
│   ├── contracts/                     # pydantic 契约模型与校验
│   ├── core/
│   │   ├── agent_prompts.py
│   │   ├── base_client.py
│   │   └── clients/                   # provider 实现
│   ├── config/
│   │   ├── models.py                  # MODEL_REGISTRY / FALLBACK_ORDER
│   │   ├── role_profiles.py           # 角色配置（支持会话中切换）
│   │   └── journals.py
│   ├── storage/db.py
│   └── session_logger.py
├── tools/
├── tests/
├── output/
├── session_store/
├── pyproject.toml
└── .env.example
```

### 7.5 详细技术路径 (Technical Roadmap)

#### 核心执行流（Agent First，v1.0 固定规范）

```
用户输入 Mission Card（课题、期刊、预算、禁区） 
    │
    ├─ 默认模式：autopilot（自动推进）
    └─ 可切换：manual（阶段确认）
    ▼
advisor(topic) -> researcher(literature) -> writer(writing) -> reviewer(review) -> polisher(polish) -> export
```

执行约束：
- 阶段推进由状态机驱动，不允许 Agent 私自跳阶段。
- 任一阶段可被 `interrupt/rewrite/goto/rollback` 打断并触发 stale 传播。
- `export` 前必须通过四道 gate：`contract_ok`、`citation_ok`、`format_ok`、`ethics_ok`。

#### Agent 间通信协议（可执行结构）

```python
class AgentMessage:
    sender: str          # advisor|researcher|writer|reviewer|polisher|human
    receiver: str        # 目标 agent 或 broadcast
    stage: str           # topic|literature|writing|review|polish|export
    content: str         # markdown/json 文本
    metadata: dict       # tokens/cost/model/latency/version_id
```

消息规则：
- 每条消息必须绑定 `session_id`、`stage`、`version_id`。
- human 插话默认 `broadcast=true`；支持 `@agent` 私聊模式。
- 冲突插话按“最新明确指令 > 已确认决策 > 历史上下文”优先级裁决。

#### 会话持久化（强一致最小要求）

- SQLite 保存：`sessions/messages/artifacts/versions/cost_log`。
- `approve/rewrite/rollback/goto` 必须写入 `versions` 快照。
- 恢复策略：`resume` 前执行 schema 校验与快照一致性校验，失败进入 `failed`。

#### 模型路由策略（支持角色配置热切换）

```python
MODEL_ROUTER = {
    "mode": "role-based",  # 按角色配置模型
    "auto_switch": True,   # 主模型异常自动切备选
    "cost_limit_per_paper_cny": 35.0,
}

ROLE_PROFILE = {
    "advisor":    {"provider": "anthropic", "model": "sonnet"},
    "researcher": {"provider": "deepseek",  "model": "v3"},
    "writer":     {"provider": "anthropic", "model": "sonnet"},
    "reviewer":   {"provider": "openai",    "model": "gpt4o"},
    "polisher":   {"provider": "deepseek",  "model": "v3"},
}
```

切换规则：
- 支持命令：`role set <agent> <provider>/<model>`。
- 切换仅影响后续阶段，不回写已完成阶段。
- 切换动作强制落日志和 `sessions.model_config` 快照。

#### 关键技术实现要点（v1.0 交付要求）

| 技术点 | 实现方案 | 验收要求 |
|-------|---------|---------|
| 多 Agent 协作 | AutoGen GroupChat + 可中断调度器 | 5 Agent 全链路可跑通 |
| Human-in-the-loop | 默认 autopilot + 命令式介入 | 插话延迟 < 1s（本地） |
| 文献真实检索 | Semantic Scholar + CrossRef 双检验 | 未验证文献必须标记 `[需验证]` |
| 契约校验 | pydantic 模型 + schema 版本 | 非法 payload 不得入库 |
| 持久化恢复 | SQLite + versions 快照 | 意外退出后可 resume |
| 成本追踪 | provider 原生 usage 计费 | `cost` 命令实时可查 |
| 导出 | tex/docx/bib + quality_report | export gate 全部通过 |

---

## 7.6 接口契约（Interface Contract）

> **工程强制要求**：7.6 是“可执行规范”，不是示例文本。  
> 运行时必须由 `pydantic` 进行严格校验；校验失败立即中断并记录错误码。

### 契约版本策略

- 当前版本：`contract_version = "1.0.0"`。
- 兼容策略：仅允许向后兼容新增字段；删字段/改类型必须升 major。
- 所有 payload 必须包含：`stage`、`session_id`、`contract_version`。

### pydantic 契约定义（最小集）

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

Stage = Literal["topic_done", "literature_done", "writing_done", "review_done", "polish_done"]

class BasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Stage
    session_id: str
    contract_version: Literal["1.0.0"] = "1.0.0"

class TopicDone(BasePayload):
    stage: Literal["topic_done"]
    selected_direction: str = Field(min_length=5)
    direction_analysis: dict
    journal_type: Literal["中文核心", "CSSCI", "IEEE Trans", "CCF-A"]
    language: Literal["zh", "en"]

class LiteratureDone(BasePayload):
    stage: Literal["literature_done"]
    papers: list[dict]
    literature_matrix: str
    verified_count: int = Field(ge=0)
    total_found: int = Field(ge=0)

class WritingDone(BasePayload):
    stage: Literal["writing_done"]
    sections: dict
    word_count: int = Field(ge=1000, le=50000)
    version_id: str

class Issue(BaseModel):
    issue_id: str
    section: str
    problem: str
    priority: Literal["high", "medium", "low"]
    suggestion: str

class ReviewDone(BasePayload):
    stage: Literal["review_done"]
    verdict: Literal["accept", "minor_revision", "major_revision", "reject"]
    overall_score: float = Field(ge=0, le=10)
    major_issues: list[Issue]
    minor_issues: list[Issue]
    adopted_issues: list[str]

class PolishDone(BasePayload):
    stage: Literal["polish_done"]
    polished_sections: dict
    readability_before: float = Field(ge=1, le=5)
    readability_after: float = Field(ge=1, le=5)
    diff_report: str
    scorer_json: dict
```

### 错误状态码定义（执行级）

| 代码 | 含义 | 触发条件 | 处理策略 |
|------|------|----------|----------|
| `E001` | API 超时 | 单次请求超时阈值 | 指数退避重试，最多 3 次 |
| `E002` | Rate Limit | HTTP 429 | 按 `retry-after` 等待后切换备选 |
| `E003` | 上下文超长 | 超过模型 max_tokens | 压缩历史并保留关键快照 |
| `E004` | 文献验证失败 | DOI 不存在或校验失败 | 标注 `[需验证]`，不中断 |
| `E005` | 插话冲突 | 与已确认决策冲突 | 进入冲突确认流程 |
| `E006` | 会话损坏 | SQLite/快照读取异常 | 自动恢复最近有效快照 |
| `E007` | 契约校验失败 | pydantic 校验失败 | 阻断阶段推进并落 error 事件 |
| `E008` | 鉴权失败 | API key 缺失/401/403 | 终止当前 provider，尝试备选 |
| `E009` | Provider 不可达 | DNS/网络不可达 | 标记 provider down，切备选 |
| `E010` | 导出门禁失败 | citation/format/ethics 任一失败 | 禁止 export，输出修复清单 |

### 模型降级顺序（按角色）

```python
ROLE_FALLBACK = {
    "advisor":    [("anthropic", "sonnet"), ("openai", "gpt4o"), ("deepseek", "v3"), ("ollama", "llama3")],
    "researcher": [("deepseek", "v3"), ("openai", "gpt4o"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
    "writer":     [("anthropic", "sonnet"), ("deepseek", "v3"), ("openai", "gpt4o"), ("ollama", "llama3")],
    "reviewer":   [("openai", "gpt4o"), ("anthropic", "sonnet"), ("deepseek", "v3"), ("ollama", "llama3")],
    "polisher":   [("deepseek", "v3"), ("openai", "gpt4o"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
}
```

---

## 7.7 模型注册表设计（新模型接入接口）

> **设计原则**：新模型接入 = 加一个 registry 条目 + 实现一个 client 类，Agent 代码零修改。

### BaseModelClient 接口（所有模型 client 必须实现）

```python
# core/base_client.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ModelResponse:
    content: str
    input_tokens: int
    output_tokens: int
    cost_cny: float
    model_id: str
    latency_ms: int

class BaseModelClient(ABC):
    """所有 LLM provider 必须继承此类"""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """同步调用，返回标准 ModelResponse"""
        ...

    @abstractmethod
    async def complete_async(self, *args, **kwargs) -> ModelResponse:
        """异步调用，供 TUI 流式显示使用"""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """检查该 provider 是否可用（用于降级判断）"""
        ...
```

### 模型注册表（config/models.py）

```python
# config/models.py
# 新增模型：只需在此添加条目，不改任何 Agent 代码

MODEL_REGISTRY = {
    "anthropic": {
        "client_class": "AnthropicClient",      # core/clients/anthropic_client.py
        "models": {
            "opus":   {"id": "claude-opus-4-5",   "input_cny_per_1m": 36.0,  "output_cny_per_1m": 180.0},
            "sonnet": {"id": "claude-sonnet-4-5", "input_cny_per_1m": 21.6,  "output_cny_per_1m": 108.0},
            "haiku":  {"id": "claude-haiku-3-5",  "input_cny_per_1m": 7.2,   "output_cny_per_1m": 36.0},
        }
    },
    "openai": {
        "client_class": "OpenAIClient",
        "models": {
            "gpt4o":     {"id": "gpt-4o",            "input_cny_per_1m": 18.0,  "output_cny_per_1m": 72.0},
            "gpt4turbo": {"id": "gpt-4-turbo-preview","input_cny_per_1m": 72.0,  "output_cny_per_1m": 216.0},
        }
    },
    "deepseek": {
        "client_class": "DeepSeekClient",
        "models": {
            "v3": {"id": "deepseek-chat", "input_cny_per_1m": 2.02, "output_cny_per_1m": 3.02},
        }
    },
    "zhipu": {
        "client_class": "ZhipuClient",
        "models": {
            "glm4flash":    {"id": "glm-4-flash",     "input_cny_per_1m": 1.0,   "output_cny_per_1m": 1.0},
            "glm4flagship": {"id": "glm-4",           "input_cny_per_1m": 100.0, "output_cny_per_1m": 100.0},
        }
    },
    "ollama": {
        "client_class": "OllamaClient",          # 本地模型，cost 为 0
        "models": {
            "llama3": {"id": "llama3:8b", "input_cny_per_1m": 0.0, "output_cny_per_1m": 0.0},
        }
    },
    # ── 新模型接入示例 ──────────────────────────────────
    # "qwen": {
    #     "client_class": "QwenClient",           # 新建 core/clients/qwen_client.py，继承 BaseModelClient
    #     "models": {
    #         "max": {"id": "qwen-max", "input_cny_per_1m": 24.0, "output_cny_per_1m": 72.0},
    #     }
    # },
}

# 各 Agent 默认模型分配（可被 role profile 覆盖）
AGENT_MODEL_MAP = {
    "advisor":    ("anthropic", "opus"),
    "researcher": ("deepseek",  "v3"),
    "writer":     ("anthropic", "sonnet"),
    "reviewer":   ("openai",    "gpt4turbo"),
    "polisher":   ("deepseek",  "v3"),
    "visualizer": ("openai",    "gpt4o"),      # v1.1
}

# 会话级角色配置（运行时可切换）
ROLE_PROFILE = {
    "advisor":    {"provider": "anthropic", "model": "sonnet"},
    "researcher": {"provider": "deepseek",  "model": "v3"},
    "writer":     {"provider": "anthropic", "model": "sonnet"},
    "reviewer":   {"provider": "openai",    "model": "gpt4o"},
    "polisher":   {"provider": "deepseek",  "model": "v3"},
}

# 角色级降级顺序（推荐）；如未配置则回退到全局 FALLBACK_ORDER
ROLE_FALLBACK = {
    "advisor":    [("anthropic", "sonnet"), ("openai", "gpt4o"), ("deepseek", "v3"), ("ollama", "llama3")],
    "researcher": [("deepseek", "v3"), ("openai", "gpt4o"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
    "writer":     [("anthropic", "sonnet"), ("deepseek", "v3"), ("openai", "gpt4o"), ("ollama", "llama3")],
    "reviewer":   [("openai", "gpt4o"), ("anthropic", "sonnet"), ("deepseek", "v3"), ("ollama", "llama3")],
    "polisher":   [("deepseek", "v3"), ("openai", "gpt4o"), ("zhipu", "glm4flash"), ("ollama", "llama3")],
}

FALLBACK_ORDER = [("openai", "gpt4o"), ("deepseek", "v3"), ("ollama", "llama3")]
```

---

## 7.8 数据库 Schema（SQLite）

```sql
-- 创建时机：首次 `paper-team start` 时自动初始化

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,      -- UUID v4
    topic        TEXT NOT NULL,
    journal_type TEXT NOT NULL DEFAULT '中文核心',
    language     TEXT NOT NULL DEFAULT 'zh',
    model_config TEXT,                  -- JSON: ROLE_PROFILE 的当次快照
    run_mode     TEXT NOT NULL DEFAULT 'autopilot', -- autopilot|manual
    stage        TEXT NOT NULL DEFAULT 'topic',  -- topic|literature|writing|review|polish|export
    status       TEXT NOT NULL DEFAULT 'active', -- active|paused|completed|failed
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,      -- UUID v4
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    sender       TEXT NOT NULL,         -- advisor|researcher|writer|reviewer|polisher|human
    receiver     TEXT NOT NULL,         -- 接收方 agent 名称，或 "broadcast"
    stage        TEXT NOT NULL,
    content      TEXT NOT NULL,         -- Markdown 格式消息体
    metadata     TEXT,                  -- JSON: {tokens, cost_cny, model_id, latency_ms}
    is_human_interrupt BOOLEAN DEFAULT 0,  -- 是否为用户插话
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id           TEXT PRIMARY KEY,      -- UUID v4
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    stage        TEXT NOT NULL,         -- 产物所属阶段
    artifact_type TEXT NOT NULL,        -- topic_report|literature_matrix|section_draft|review_report|polish_diff
    content      TEXT NOT NULL,         -- Markdown 或 JSON 字符串
    is_stale     BOOLEAN DEFAULT 0,     -- goto/rollback 后标记为过期
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS versions (
    id           TEXT PRIMARY KEY,      -- UUID v4
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    stage        TEXT NOT NULL,
    version_num  INTEGER NOT NULL,      -- 从 1 开始自增
    full_content TEXT NOT NULL,         -- 当前阶段论文全文快照（Markdown）
    metadata     TEXT,                  -- JSON: {word_count, total_cost_cny, model_used_map}
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_versions_stage
ON versions(session_id, stage, version_num);

CREATE TABLE IF NOT EXISTS raw_responses (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    agent        TEXT NOT NULL,
    content      TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cost_log (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    agent        TEXT NOT NULL,
    model_id     TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_cny     REAL NOT NULL,
    stage        TEXT NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引（提升查询性能）
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_versions_session ON versions(session_id, version_num);
CREATE INDEX IF NOT EXISTS idx_cost_session ON cost_log(session_id);
```

---

## 7.9 日志策略

> 日志文件路径：`session_store/logs/<session_id>.log`
> 格式：结构化 JSON Lines（每行一条事件），便于 `grep` 和后续分析

### 必须记录的事件

```json
// 每次 API 调用
{"event": "api_call",     "ts": "ISO8601", "session_id": "...", "agent": "writer",
 "model_id": "deepseek-chat", "prompt_preview": "前100字...", "input_tokens": 2500,
 "output_tokens": 800, "latency_ms": 3200, "status": "ok|timeout|rate_limit|error"}

// Agent 交接
{"event": "handoff",      "ts": "...", "session_id": "...",
 "from": "researcher", "to": "writer", "stage": "literature_done", "version_id": "v1"}

// 用户插话
{"event": "human_interrupt", "ts": "...", "session_id": "...",
 "stage": "writing", "current_agent": "writer",
 "message": "引言要加入2023年的政策数据", "broadcast": true}

// 阶段完成 / 版本快照
{"event": "version_snapshot", "ts": "...", "session_id": "...",
 "stage": "writing", "version_num": 2, "word_count": 8432, "cost_cny_cumulative": 1.82}

// 错误事件
{"event": "error", "ts": "...", "session_id": "...",
 "error_code": "E001", "agent": "advisor", "retry_count": 2, "fallback_to": "openai/gpt4o"}

// 状态变更（stale 标记）
{"event": "stale_marked", "ts": "...", "session_id": "...",
 "trigger": "goto writing", "affected_stages": ["review", "polish"]}

// 角色配置切换
{"event": "role_switched", "ts": "...", "session_id": "...",
 "agent": "reviewer", "from": "openai/gpt4o", "to": "anthropic/sonnet"}

// 模式切换
{"event": "mode_changed", "ts": "...", "session_id": "...",
 "from": "autopilot", "to": "manual"}
```

### 日志轮转规则
- 单个 session 日志 > 10MB 时自动压缩为 `.log.gz`
- session 完成后日志保留 30 天
- `paper-team debug <session_id>` 命令可展示该 session 的日志摘要
- `prompt_preview` 默认脱敏（PII/邮箱/手机号/ID）后写入
- `raw_responses` 默认保留 30 天，可配置关闭或立即清理

---

## 7.10 本地开发环境 & Mock 模式

### 快速启动（不需要真实 API Key）

```bash
# 1. 克隆并安装
git clone <repo>
cd academic-agent-team
pip install -e ".[dev]"         # 含开发依赖（pytest, rich, textual）

# 2. 复制环境变量模板
cp .env.example .env
# .env 最小配置（Mock 模式不需要真实 Key）：
# MOCK_MODE=true
# DEFAULT_MODEL=mock

# 3. Mock 模式启动（所有 LLM 调用返回预设假数据，不消耗 API 费用）
paper-team start --mock

# 4. 跑最小可验证流程（30秒内跑完）
paper-team start --mock --topic "测试课题" --journal "中文核心" --no-interactive
# 验证输出目录 output/ 下是否生成了完整文件结构
```

### Mock Client 设计

```python
# core/clients/mock_client.py
class MockClient(BaseModelClient):
    """本地开发专用，返回固定格式的假数据，完整实现 BaseModelClient 接口"""

    MOCK_RESPONSES = {
        "advisor":    "【方向1】测试方向A\n创新性：8/10\n...",
        "researcher": "## 文献矩阵\n| 标题 | 作者 | 年份 |\n...",
        "writer":     "# 引言\n这是一篇关于...的研究。\n",
        "reviewer":   "总体评定：小修后录用\n主要问题：...",
        "polisher":   "润色后文本...",
    }

    def complete(self, prompt, system="", temperature=0.5, max_tokens=4096):
        agent = self._detect_agent_from_prompt(prompt)
        return ModelResponse(
            content=self.MOCK_RESPONSES.get(agent, "Mock 响应"),
            input_tokens=100, output_tokens=50,
            cost_cny=0.0, model_id="mock", latency_ms=200
        )
```

### 单元测试最小集

```bash
# 运行全部测试
pytest tests/

# 关键测试文件（v1.0 必须全部通过）
tests/
├── test_model_registry.py     # 所有 client 能正确初始化
├── test_agent_contracts.py    # Agent 输入输出符合 JSON Schema
├── test_session_persistence.py # save/resume 流程
├── test_readability_scorer.py  # 评分工具准确性
└── test_cost_tracking.py      # 费用累计逻辑
```

---

## 8. AI/ML Specifications

### 模型配置（对齐 Section 7.7 ROLE_PROFILE 默认值）

| Agent | Model | Temperature | Max Tokens | 理由 |
|-------|-------|-------------|------------|------|
| 选题顾问 | `claude-sonnet-4-5`（`sonnet`，ROLE_PROFILE 默认） | 0.7 | 4096 | 创意分析能力强；经费充足时可选 `opus` |
| 文献研究员 | `gpt-4o`（`gpt4turbo` 备选） | 0.3 | 8192 | 事实总结准确；DeepSeek V3 亦可（成本更低） |
| 论文写手 | `claude-sonnet-4-5`（`sonnet`，ROLE_PROFILE 默认） | 0.5 | 8192 | 写作质量高 |
| 审稿人 | `gpt-4o`（`gpt4turbo` 备选） | 0.2 | 4096 | 严谨批评 |
| 图表师 (v1.1) | `gpt-4o` | 0.4 | 4096 | 支持 Vision |

> ⚠️ **实现注意**：
> - **Section 7.7 的 `ROLE_PROFILE` 为权威默认值**，Section 8 的上表供参考（标注温度/max_tokens）；
> - **Section 7.7 与 Section 8 的冲突（v1.5 遗留）已在本版本统一为 sonnet/gpt4o 配置**；
> - 模型 ID 通过 `config/models.py` 中的 `MODEL_REGISTRY` 配置，**禁止硬编码**；
> - 运行时可通过 `role set` 热切换（见 Section 9.2），不影响已完成阶段。

### Prompt 模板整合

```python
RESEARCH_WRITING_PROMPTS = {
    # 文献调研
    "literature_summary": "#18 文献总结与笔记",
    "literature_comparison": "#19 文献对比分析",
    "research_gap": "#20 找到研究空白",

    # 论文写作
    "outline_generator": "#21 论文大纲生成",
    "chapter_expansion": "#22 章节内容扩展",
    "abstract_writer": "#23 摘要写作",
    "introduction_writer": "#24 引言写作",
    "method_writer": "#25 方法章节写作",

    # 润色修改
    "zh_to_en": "#1 中译英",
    "en_to_zh": "#2 英译中",
    "chinese_polish": "#3 中文润色",
    "english_polish": "#6 英文润色",
    "remove_ai_zh": "#7 中文去AI味",
    "remove_ai_en": "#8 英文去AI味",
    "logic_check": "#9 逻辑检查",

    # 图表制作
    "architecture_diagram": "#11 绘制架构图",
    "chart_recommender": "#12 实验图推荐",
    "figure_caption": "#13 图片标题说明",
    "table_caption": "#14 表格标题说明",
    "result_analysis": "#15 实验结果分析",

    # 审稿回复
    "peer_review": "#16 模拟审稿人",
    "rebuttal": "#26 回复审稿人",
    "cover_letter": "#27 Cover Letter",
}
```

### 期刊标准配置

```python
JOURNAL_STANDARDS = {
    "中文核心": {
        "citation": "GB/T 7714-2015",
        "word_limit": "8000-15000",
        "ai_detection": "<20%",
        "template": "chinese_journal.cls"
    },
    "CSSCI": {
        "citation": "GB/T 7714-2015",
        "word_limit": "10000-20000",
        "plagiarism": "<10%",
        "ai_detection": "<15%"
    },
    "IEEE Trans": {
        "citation": "IEEE",
        "word_limit": "8000-10000",
        "format": "double-column",
        "template": "IEEEtran.cls"
    },
    "CCF-A": {
        "citation": "IEEE/ACM",
        "page_limit": "10-12",
        "novelty": "30%+",
        "template": "acmart.cls"
    }
}
```

---

## 9. User Experience

### 9.0 核心交互理念：可观察流 + 随时插话（2026-03-27 新增）

#### 交互主张（冻结为执行规范）

- 默认模式：`autopilot`（不强制阶段确认，自动推进到 export）。
- 人类控制：任何时刻允许 `interrupt/rewrite/goto/rollback/pause`。
- 双模式并存：`autopilot` 与 `manual` 可运行时切换，默认 `autopilot`。

#### 介入级别（定义完成）

| 级别 | 触发方式 | 系统行为 | 一致性动作 |
|------|---------|---------|------------|
| 轻量插话 | 直接输入自然语言 | 当前 Agent 在下一个可中断点读取并调整 | 写入 `human_interrupt` 消息 |
| 强制重定向 | `rewrite <target>` / `goto <stage>` | 中断当前执行并跳转 | 目标阶段后的 artifacts 标记 `is_stale=1` |
| 版本回溯 | `rollback <version_id>` | 恢复快照并重建上下文 | 回溯点后版本全部失效 |

#### 多次插话与冲突处理（补齐）

1. 同一阶段多次插话：按时间戳后写覆盖前写。  
2. 插话与已确认决策冲突：进入 `E005`，显示冲突摘要，要求用户二次确认。  
3. 私聊与广播：默认广播；`@agent` 前缀为私聊，仅目标 Agent 可见。  
4. 自动/手动切换：`mode autopilot` 与 `mode manual` 即时生效并写入日志。  

#### 技术实现要点（执行级）

| 要点 | 方案 |
|------|------|
| 对话可观察 | GroupChat 事件流实时推送到 TUI 左栏 |
| 插话注入 | `asyncio.Queue` + 周期性轮询（<=50ms） |
| 中断点 | token 流式输出间隙 + 阶段边界 |
| stale 可见性 | 右栏章节显示 `[已过期]`，导出按钮硬禁用 |
| 命令优先级 | 命令解析优先于自然语言（带前缀 `/`） |

---

### 9.1 六阶段使用流程

整个论文写作流程分为 **六个阶段**，默认自动推进，人类可随时介入：

#### 阶段一：启动与配置

```bash
paper-team start --config --mode autopilot
```

最小必填：
- `topic`
- `journal`
- `budget_cap_cny`
- `role_profile`（可后续切换）

#### 阶段二：选题分析（topic）

- 产物：`topic_done.json`、选题报告。
- gate：方向评分、研究空白、关键词齐全。
- 介入示例：`rewrite topic` 或自然语言插话补约束。

#### 阶段三：文献调研（literature）

- 产物：`literature_done.json`、文献矩阵。
- gate：`verified_count <= total_found` 且 DOI 可追溯。
- 规则：未验证文献必须标记 `[需验证]`。

#### 阶段四：论文撰写（writing）

- 产物：`writing_done.json`、章节草稿。
- gate：章节齐全、字数达标、术语一致。
- 介入示例：`rewrite introduction`、`@writer 增加2023政策数据`。

#### 阶段五：审稿与修改（review）

- 产物：`review_done.json`、采纳列表。
- gate：每个 issue 必须有 `issue_id` 与优先级。
- 规则：`adopted_issues` 仅可引用存在的 `issue_id`。

#### 阶段六：润色与导出（polish/export）

- 产物：`polish_done.json`、`paper_final.tex/.docx`、`references.bib`、`quality_report.md`、`cost_summary.md`。
- 导出前 gate：contract/citation/format/ethics 必须全通过。
- 失败处理：任一 gate 失败则阻断导出并输出修复清单。

### 9.2 增强命令系统

| 命令 | 行为 | 示例 |
|------|------|------|
| `/mode autopilot|manual` | 切换执行模式 | `/mode manual` |
| `/role show` | 查看当前角色配置 | `/role show` |
| `/role set <agent> <provider>/<model>` | 运行时切换角色模型 | `/role set reviewer openai/gpt4o` |
| `y` / `n` | 确认/拒绝当前建议 | `y` |
| `1-5` | 选择选项 | `2` |
| `重写 <章节>` | 指定重写某章节 | `重写 引言` |
| `goto <阶段>` | 跳转到任意阶段 | `goto 文献` |
| `rollback <版本ID>` | 回退到指定版本快照 | `rollback v3` |
| `diff [v1] [v2]` | 对比两个版本差异 | `diff v1 v2` |
| `edit <章节>` | 在外部编辑器中打开 | `edit 方法` |
| `status` | 查看当前进度和费用 | `status` |
| `save` | 手动保存当前进度 | `save` |
| `resume` | 恢复上次保存的进度 | `paper-team resume session_abc` |
| `cost` | 查看实时费用明细 | `cost` |
| `export` | 导出中间结果 | `export 文献综述` |
| `停` / `pause` | 暂停等待指令 | `停` |
| `quit` | 退出程序（自动保存） | `quit` |

### 9.3 启动参数

```bash
# 基本启动
paper-team start --real

# 带配置启动
paper-team start --config

# 恢复上次进度
paper-team resume <session_id>

# 指定默认执行模式
paper-team start --mode autopilot

# 指定主模型（会作为 role profile 初始值）
paper-team start --model openai/gpt4o

# 从已有初稿开始（跳过 topic/literature）
paper-team start --draft ./my_draft.md --stage writing
```

### 9.4 流程状态机（支持迭代回退）

#### 状态定义

| 状态 | 含义 | 输出产物 |
|------|------|----------|
| `topic` | 选题分析 | 选题报告 |
| `literature` | 文献调研 | 文献矩阵、引用草案 |
| `writing` | 章节撰写 | 分章节草稿 |
| `review` | 审稿修改 | 评审意见、修改记录 |
| `polish` | 润色优化 | 润色版、质量报告 |
| `export` | 导出交付 | tex/docx/bib/报告 |
| `failed` | 异常终止待恢复 | 错误快照 |

#### 事件与转移规则

| 事件 | 允许状态 | 转移结果 |
|------|----------|----------|
| `approve` | 任意阶段 | 进入下一阶段并创建版本快照 |
| `rewrite` | `topic/literature/writing/review/polish` | 当前阶段重算，版本号 +1 |
| `goto <阶段>` | 任意阶段 | 跳转到目标阶段，后续产物标记为 `stale` |
| `rollback <版本ID>` | 任意阶段 | 恢复到指定版本，对应后续产物失效 |
| `pause` / `resume` | 任意阶段 | 暂停/恢复，不改变当前状态 |
| `error(E007-E010)` | 任意阶段 | 进入 `failed`，等待修复或 resume |

#### 回退执行约束

- 从 `review/polish/export` 回退到 `writing` 时，评审报告与润色报告全部失效并需重生。
- 从 `writing` 回退到 `literature/topic` 时，章节草稿全部标记为过期，禁止直接导出。
- 每次 `approve/rewrite/rollback` 都写入 `versions` 表，确保可追踪和可比对。
- 已发生的模型调用费用保留在 `cost_summary`，重算部分单独追加，不做覆盖。

---

## 10. Risk Assessment

### 风险矩阵

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API Key 暴露 | **Medium** | Critical | 使用 .env 文件，安装脚本自动将 `.env` 写入 `.gitignore`；README 首屏醒目警告；非开发者用户（文科研究生）误操作上传风险不低 |
| 模型幻觉 | Medium | Medium | 人类审核每个输出 |
| AI检测器拦截 | Medium | High | 去AI味 Prompt 优化 |
| 文献版权 | Low | Medium | 仅输出摘要，不爬取全文 |
| 格式错误 | Medium | Low | 自动格式检查 + 模板 |
| **API 超时/断网** | **Medium** | **High** | **自动重试 3 次（指数退避）；Rate limit 时降级到备选模型；失败后自动保存 session 快照，恢复后可续跑** |

### 备选方案

| 如果... | 那么... |
|---------|---------|
| Anthropic API 不可用 | 切换到 GPT-4 作为备选 |
| 输出质量不达标 | 提供"重新生成"选项 |
| 用户不满意 | 支持导出对话，发给人工优化 |

---

## 10.5 学术伦理声明

### 定位声明

> **本系统定位为「学术写作辅助工具」，而非「论文代写工具」。**
> 所有 AI 生成内容均需人类用户审核、修改和确认，最终学术责任由用户本人承担。

### 伦理边界

| 允许 ✅ | 禁止 ❌ |
|---------|---------|
| 辅助文献检索和总结 | 完全替代人类进行原创研究 |
| 提供写作框架和结构建议 | 伪造实验数据或研究结果 |
| 语法润色和格式规范化 | 直接提交 AI 生成内容作为原创论文 |
| 模拟审稿反馈，帮助改进论文 | 绕过学术诚信检测机制 |
| 帮助用户学习学术写作规范 | 代替用户进行学术决策 |

### 用户责任

1. **内容审核义务**: 用户必须审核所有 AI 生成内容的准确性和原创性
2. **引用规范**: AI 提供的文献信息必须经人工验证后才可引用
3. **学术诚信**: 用户需遵守所在机构的学术诚信政策
4. **署名声明**: 建议在论文致谢中说明使用了 AI 辅助工具

### 系统内置保障

- 每次输出附带「**⚠️ 此内容由AI辅助生成，请审核后使用**」水印
- 文献引用自动标注「**[需验证]**」标记，提醒用户人工核实
- 默认仅本地存储用户论文内容（SQLite + 本地文件）；不上传云端，支持一键清理
- 内置可读性指标实时显示，帮助用户持续优化写作表达

---

## 10.6 成本估算

### 计费口径说明

- 主货币统一为人民币（CNY）
- 外币换算使用固定估算汇率：`1 USD = 7.2 CNY`（仅用于预算）
- 实际扣费以各模型平台账单为准

### 各模型定价对比（统一人民币口径）

| 模型 | 提供商 | 输入价格 (¥/1M tokens) | 输出价格 (¥/1M tokens) | 备注 |
|------|--------|-----------------------|------------------------|------|
| **Claude Opus 4.x** | Anthropic | ¥36.0 | ¥180.0 | 最强创意分析（实际 ID 以官方文档为准） |
| **Claude Sonnet 4.x** | Anthropic | ¥21.6 | ¥108.0 | 性价比之选（实际 ID 以官方文档为准） |
| **Claude Haiku 3.5** | Anthropic | ¥7.2 | ¥36.0 | 轻量任务 |
| **GPT-4o** | OpenAI | ¥18.0 | ¥72.0 | 多模态能力强 |
| **GPT-4-turbo** | OpenAI | ¥72.0 | ¥216.0 | 长上下文 |
| **o1** | OpenAI | ¥108.0 | ¥432.0 | 推理能力强 |
| **DeepSeek V3** | DeepSeek | ¥2.02 (miss) / ¥0.20 (R1-hit) | ¥3.02 | 极致性价比；R1 适合推理任务 |
| **GLM-4-Flash** | 智谱AI | ¥1.0 | ¥1.0 | 轻量/免费额度内可用 |
| **GLM-4（旗舰）** | 智谱AI | ¥100.0 | ¥100.0 | 旗舰版（¥100/百万tokens，与表中 ¥100/1M 一致） |
| **MiniMax** | MiniMax | 按官方实时计费 | 按官方实时计费 | 多模态，语音资源包另计 |
| **Ollama (本地)** | 用户自建 | 免费 | 免费 | 需要 GPU 硬件 |

### 单篇论文预估成本（统一人民币）

以一篇中文核心期刊论文（约 8000 字）为基准，采用三档配置：

| 方案 | 模型组合 | 预估单篇成本（CNY） | 适用场景 |
|------|----------|---------------------|----------|
| 经济档 | DeepSeek 全流程 | ¥0.3 - ¥0.8 | 快速打底稿、预算敏感 |
| 平衡档（推荐） | DeepSeek 主力 + Claude/GPT 关键章节 | ¥2 - ¥5 | 常规论文写作与润色 |
| 质量档 | Claude/GPT 主力 + 多轮审稿润色 | ¥6 - ¥12 | 高要求投稿前打磨 |

> 💡 推荐默认采用平衡档，并在配置页明确显示「当前档位 + 实时累计费用」。

### 免费工具汇总

| 工具 | 用途 | 费用 |
|------|------|------|
| Semantic Scholar API | 文献搜索、引用图谱 | 免费 |
| CrossRef API | DOI 解析 | 免费 |
| Skill 搜索工具 | 代码/文档搜索 | 免费 |
| Ollama | 本地模型推理 | 免费（需硬件） |

---

## 11. Launch Plan

### Phase 1: MVP (v1.0) - Week 1-5

**目标**: 最小可用版本，支持完整论文写作流程

| Week | 技术任务 | 交付物 | 验证标准 |
|------|---------|--------|---------|
| W1 | 搭建 AutoGen 框架，实现 GroupChat + UserProxyAgent | Agent 框架骨架 | **5个** Agent 能互相发消息（选题顾问/文献研究员/论文写手/审稿人/润色Agent） |
| W1 | 集成 Semantic Scholar API + CrossRef API | 文献搜索模块 | 输入关键词返回 20 篇真实论文 |
| W2 | 实现选题顾问 Agent（含 Prompt 模板） | 选题报告生成 | 输入课题→输出 3 个方向 + 评分 |
| W2 | 实现文献研究员 Agent（接入 Semantic Scholar） | 文献综述矩阵 | 15分钟内完成 20 篇文献总结 |
| W3 | 实现论文写手 Agent（整合 30 个 Prompt 模板） | 逐章节论文生成 | 生成符合期刊格式的完整初稿 |
| W3 | 实现审稿人 Agent + 润色 Agent | 评审报告 + 润色 | 结构化评审意见 + 可读性报告可导出 |
| W4 | Rich/Textual TUI 界面实现（分栏布局） | 可交互终端界面 | 左栏对话 + 右栏预览 + 底部输入 |
| W4 | 模型路由（支持按角色切换） | 多模型配置 | `role set` 与 profile 切换可用 |
| W4 | SQLite 会话持久化（save/resume） | 进度保存恢复 | 关掉程序重开能恢复到之前阶段 |
| **W5** | **LaTeX/Word 输出 + 4种期刊模板** | **格式化论文输出** | **中文核心/CSSCI/IEEE/CCF-A 格式正确** |
| **W5** | **端到端测试 + README + 安装文档** | **可发布 v1.0** | **新用户 15 分钟内跑通完整流程** |

### Phase 2: Enhancement (v1.1) - Week 6-9

**目标**: 提升输出质量，增加图表能力，完善持久化

| Week | 技术任务 | 交付物 | 验证标准 |
|------|---------|--------|---------|
| W6 | 图表师 Agent（Mermaid/Matplotlib 生成） | 架构图 + 数据图 | 自动生成 ≥ 3 种图表类型 |
| W7 | 润色效果持续优化（多轮策略） | 更高文本可读性 | 人工盲评平均分提升 ≥0.8（5分制） |
| W7 | 格式自动检查（引用格式/图表编号/字数） | 格式检查报告 | 自动发现 > 90% 格式问题 |
| W8 | 对话历史导出（txt/md/JSON） | 完整协作记录 | 一键导出全部 Agent 对话 |
| W8 | Zotero MCP 集成（文献同步） | 文献自动导入 | 从 Zotero 库直接加载文献 |
| W9 | 版本对比功能（diff v1 v2） | 版本管理 | 可视化对比两版论文差异 |
| W9 | 费用实时追踪 + 费用报告 | 成本透明化 | `cost` 命令显示实时费用明细 |

### Phase 3: Scale (v2.0) - Week 10-14

**目标**: API 服务化，支持团队协作，桌面/Web 多端

| Week | 技术任务 | 交付物 | 验证标准 |
|------|---------|--------|---------|
| W10 | FastAPI 后端 REST API 封装 | API 服务 | 所有 Agent 能力 API 化 |
| W10 | WebSocket 实时通信（Agent 对话流式推送） | 实时交互 | 前端实时显示 Agent 对话 |
| W11 | React Web Dashboard 前端 | Web 界面 | 浏览器中完成完整写作流程 |
| W11 | 用户认证 + 权限管理（导师/学生角色） | 团队协作 | 导师可查看学生论文进度 |
| W12 | Tauri 桌面应用封装（可选） | 桌面应用 | 双击打开，无需命令行 |
| W12 | 基金申请书模块（国自然等模板） | 申请书生成 | 支持国自然/社科基金格式 |
| W13 | 多语言支持（中/英/日） | 国际化 | 自动切换语言 |
| W14 | 性能优化 + 压力测试 + 上线部署 | 生产环境 | 支持 100 并发用户 |

### 技术里程碑甘特图

```
Week:    1    2    3    4    5    6    7    8    9   10   11   12   13   14
         ├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
框架搭建  ████
Agent开发      ████████
TUI界面              ████
文献API   ████
输出格式                  ████
                              ┃ v1.0 发布 (W5末)
图表Agent                     ████
持久化                        ████
质量优化                           ████████
工具集成                                ████
                                            ┃ v1.1 发布 (W9末)
API服务化                                    ████
Web前端                                          ████
团队协作                                          ████
桌面应用                                               ████
部署上线                                                    ████
                                                                ┃ v2.0 发布 (W14末)
```

---

### 11.5 v1.0 执行任务卡（可直接派工）

> 说明：以下任务卡为 v1.0 发布阻断项（P0/P1）。每张卡都必须满足输入、输出、验收、测试四项才能 Done。

| ID | 优先级 | 任务 | 输入 | 输出 | 验收标准 | 最小测试 |
|----|--------|------|------|------|----------|----------|
| TSK-001 | P0 | 角色配置热切换 | `ROLE_PROFILE`、当前 session | `role set` 命令可用，写入 `sessions.model_config` 快照 | 切换后仅影响后续阶段；日志有 `role_switched` | 单测：切换 reviewer 模型后后续调用生效 |
| TSK-002 | P0 | 契约引擎 pydantic 化 | 7.6 契约模型 | `contracts/` 模块 + schema 版本 | 非法 payload 阻断入库并报 `E007` | 单测：字段缺失/类型错误/枚举错误 |
| TSK-003 | P0 | 状态机完整实现 | 9.4 事件表 | `approve/rewrite/goto/rollback/pause/resume` | stale 传播正确，状态转移可追踪 | 集成测：`goto writing` 后 review/polish stale |
| TSK-004 | P0 | 异常收敛与恢复 | 错误码 E001-E010 | 用户可读错误 + `failed` 状态 + `resume` | 失败不丢 session，恢复后可继续 | 集成测：模拟 API 超时后恢复 |
| TSK-005 | P0 | 导出门禁 | 四道 gate 规则 | export gate 检查器 | 任一 gate 失败禁止导出并出修复清单 | 集成测：citation 失败时 export 被拒 |
| TSK-006 | P1 | 成本追踪统一 | provider usage | `cost_summary` 与 `cost` 命令一致 | 成本误差 < 3%（对账账单） | 单测：多阶段累计与回退追加 |
| TSK-007 | P1 | 文献双检验 | Semantic Scholar + CrossRef | `verified_count/total_found` 真实一致 | 未验证项必须 `[需验证]` | 集成测：无效 DOI 流程不中断 |
| TSK-008 | P1 | 本地数据治理 | 日志与 raw responses | TTL、脱敏、清理命令 | 默认本地保存，支持一键清理 | 集成测：清理后文件与索引同步 |
| TSK-009 | P1 | CLI 命令补齐 | 9.2 命令表 | `status/cost/save/resume/diff/export` | 命令行为与状态机一致 | e2e：完整跑一篇并回退重生 |
| TSK-010 | P1 | 新用户上手路径 | README + .env.example | 15 分钟跑通脚本 | 新机器从零可启动并生成产物 | 安装验收脚本全绿 |

### 11.6 发布门禁（Definition of Done, v1.0）

发布前必须同时满足：

1. 全量测试通过：`unit + integration + e2e`。
2. 契约校验通过率 100%，无 `E007` 残留会话。
3. `resume` 成功率 >= 95%（故障注入样本 >= 50）。
4. 导出门禁通过率 >= 90%，且失败可给出可执行修复建议。
5. 文档一致性通过：README、CLI `--help`、PRD 参数命名一致。
6. 安全检查通过：日志脱敏、API Key 不入日志、支持一键本地清理。

---

## 12. Stakeholder Matrix

### RACI Matrix

| Task | Product | Engineering | Research | QA |
|------|---------|-------------|----------|-----|
| PRD Review | A | C | I | - |
| Agent 开发 | A | R | C | - |
| Prompt 优化 | C | C | R | - |
| 格式模板 | C | R | C | - |
| 用户测试 | I | C | R | - |
| 质量验收 | A | C | C | R |

---

## 13. Appendix

### A. Skill 来源

| Skill | 来源 | 链接 | License |
|-------|------|------|---------|
| research-writing-skill | alfonso0512 | github.com/alfonso0512/research-writing-skill | MIT |
| AcademicForge | HughYau | github.com/HughYau/AcademicForge | MIT |
| claude-scientific-skills | K-Dense-AI | github.com/K-Dense-AI/claude-scientific-skills | MIT |
| paper-polish-workflow-skill | Lylll9436 | github.com/Lylll9436/Paper-Polish-Workflow-skill | MIT |
| humanizer | blader | (AcademicForge子模块) | MIT |
| scientific-visualization | (AcademicForge子模块) | - | MIT |

---

### B. 参考资料

- AutoGen 官方文档: microsoft.github.io/autogen
- Semantic Scholar API: api.semanticscholar.org（免费学术文献搜索 API）
- CrossRef API: api.crossref.org（免费 DOI 解析）
- GitHub Code Search API: docs.github.com/en/rest/search（需 PAT）
- Zotero MCP: github.com/cookjohn/zotero-mcp (v2.0)
- ResearchRabbit: researchrabbit.ai (v2.0)
- DeepSeek API: platform.deepseek.com
- 智谱 AI (GLM): open.bigmodel.cn
- MiniMax: platform.minimaxi.com

---

### C. 术语表

| 术语 | 定义 |
|------|------|
| Agent | AI 代理，可执行特定任务的 AI 组件 |
| Team Lead | 人类用户，作为最终决策者 |
| Prompt Template | 预设的 Prompt 模式，确保输出质量 |
| Skill | Claude Code 的任务分解能力集合 |
| Semantic Scholar | Allen AI 提供的免费学术文献搜索引擎 |
| 去AI味 | 消除 AI 生成文本的典型特征，使其更接近人类写作风格 |
| RICE | Reach × Impact × Confidence / Effort 的优先级评估框架 |
| BaseModelClient | 所有 LLM provider 的统一抽象基类，定义 `complete()` / `complete_async()` / `health_check()` 接口 |
| Interface Contract | Agent 间数据传递的 JSON Schema 规范，所有 Agent 必须遵守 |
| E00X | 错误状态码，用于系统内错误分类与降级处理 |

---

### D. 补充 Prompt 库（v1.3 新增，填补四个缺口）

> 以下 Prompt #31–#34 均为本项目新增，覆盖 SKILL.md 原版未包含的场景。
> #32 审稿人 Prompt 核心结构改编自 `ppw-reviewer-simulation`（MIT License，Lylll9436/Paper-Polish-Workflow-skill）。

---

#### Prompt #31 — 选题顾问（原创）

````markdown
## 角色
你是一位专注于中国学术生态的研究选题顾问，熟悉中文核心期刊、CSSCI、IEEE/CCF-A 等各类期刊的选题偏好与发文趋势。

## 变量
- 研究想法：{{RESEARCH_IDEA}}
- 目标期刊类型：{{JOURNAL_TYPE}}（中文核心 / CSSCI / IEEE Trans / CCF-A / 不限）
- 用户背景：{{USER_BACKGROUND}}（硕士生 / 博士生 / 高校教师 / 研究员）

## 执行步骤

**Step 1 — 拆解**：识别核心概念、研究对象、潜在问题域。

**Step 2 — 发散三个方向**（各从不同维度切入）：
1. 技术路线：聚焦方法或模型创新
2. 制度/理论视角：聚焦政策、机制、理论框架构建
3. 比较/实证研究：通过对比案例或数据验证命题

**Step 3 — 评估每个方向**：

| 评估项 | 说明 |
|--------|------|
| 研究空白 | 该方向目前缺少什么（描述趋势，不编造具体数字） |
| 创新性评分 | 1-10分，并说明评分依据 |
| 可行性 | 数据获取难度、研究周期、所需专业知识 |
| 期刊契合度 | 与 {{JOURNAL_TYPE}} 的匹配程度及理由 |

**Step 4 — 推荐**：明确推荐一个方向，说明理由；对用户修改意见给出具体调整方案。

## 输出格式
```
【方向1】[名称]
核心角度：...
研究空白：...
创新性：X/10，理由：...
可行性：高/中/低，原因：...
期刊契合度：...

【方向2】...（同上）
【方向3】...（同上）

⭐ 推荐方向：[X]
推荐理由：...
调整建议：...
```

## 约束
- 不编造具体文献数据或引用量，只描述趋势
- 对文科/理科背景用户使用不同深度的专业术语
- 不过度承诺录用率
````

---

#### Prompt #32 — 中文期刊专项审稿人（改编自 ppw-reviewer-simulation，MIT License）

````markdown
## 角色
你是一位拥有丰富审稿经验的中文学术期刊匿名审稿专家，熟悉北大核心、CSSCI 录用标准。
审稿态度：挑剔但建设性。指出问题要具体，不说"文献综述不够"，要说"缺少对XX领域近5年的国内文献综述"。

## 变量
- 论文全文：{{PAPER_CONTENT}}
- 目标期刊类型：{{JOURNAL_TYPE}}（中文核心 / CSSCI）
- 学科领域：{{FIELD}}

## 评审维度（中文期刊专项，5维度评分）

| 维度 | 权重 | 评分要点 |
|------|------|----------|
| 选题创新性 | 25% | 研究问题是否新颖？是否填补国内研究空白？ |
| 理论基础 | 20% | 理论框架是否清晰？文献支撑是否充分？ |
| 研究方法 | 20% | 方法是否科学严谨？数据来源是否可靠？论证逻辑是否完整？ |
| 中文表达质量 | 15% | 表达是否规范流畅？术语是否统一？是否有 AI 生成痕迹？ |
| 政策/实践价值 | 10% | 是否有明确政策建议或实践意义？（社科类期刊尤为重要） |
| 格式规范 | 10% | 引用格式（GB/T 7714-2015）是否正确？摘要/关键词是否规范？ |

## 执行检查（输出前自查）
1. 语气是否太温和？重新审视模糊的论证，提出尖锐质疑。
2. 指出的问题是否具体？不要说"实验不够"，要说"缺少对XX数据集的验证"。

## 输出格式
```
# 审稿意见

**论文题目**：[标题]
**目标期刊**：{{JOURNAL_TYPE}}
**总体评定**：录用 / 小修后录用 / 大修后再审 / 退稿

## 评分总览
| 维度 | 得分 | 简评 |
|------|------|------|
| 选题创新性 | X/10 | ... |
...

## 主要问题（必须修改）
### 问题1：[描述性标题]
- 位置：[第几节第几段]
- 问题：[具体描述]
- 影响：[为什么这是问题]
- 建议：[具体修改方向]

## 次要问题（建议修改）
...

## 亮点
...
```
````

---

#### Prompt #33 — 中文期刊大纲生成（原创，弥补 #21 缺失的中文期刊适配）

````markdown
## 角色
你是熟悉中国学术出版规范的论文结构设计专家，根据目标期刊偏好设计论文框架。

## 变量
- 研究课题：{{TOPIC}}
- 目标期刊：{{JOURNAL_TYPE}}（中文核心 / CSSCI / IEEE / CCF-A）
- 核心研究方法：{{METHOD}}（定性 / 定量 / 混合 / 案例研究 / 实验）
- 预计字数：{{WORD_COUNT}}

## 期刊结构模板

### 中文核心 / CSSCI（社科类）
```
1. 引言（问题提出与研究意义）
2. 理论基础与文献综述
   2.1 理论框架
   2.2 国内外研究现状
   2.3 研究空白与本文贡献
3. 研究设计
   3.1 研究思路
   3.2 数据来源与处理
   3.3 分析方法
4. 实证分析 / 案例分析
   4.1 核心发现1
   4.2 核心发现2
   4.3 稳健性检验（定量研究必须）
5. 讨论
   5.1 主要结论
   5.2 理论贡献
   5.3 政策建议
6. 结论与展望
参考文献（GB/T 7714-2015格式）
```

### IEEE Trans / CCF-A（工程/计算机类）
```
Abstract
1. Introduction
2. Related Work
3. Methodology
   3.1 Problem Formulation
   3.2 Core Component 1
   3.3 Core Component 2
4. Experiments
   4.1 Experimental Setup
   4.2 Main Results
   4.3 Ablation Study
5. Conclusion
References
```

## 输出格式
```
# 论文大纲：[课题名称]

**期刊类型**：... | **研究方法**：... | **目标字数**：...

## 推荐题目（3个选项）
1. ...  2. ...  3. ...

## 详细大纲
[按模板展开，每节包含：建议字数 + 3-5个写作要点]

## 摘要关键词建议
词1 / 词2 / 词3 / 词4 / 词5
```
````

---

#### Prompt #34 — 量化可读性评分（原创，配合 Python 脚本使用）

````markdown
## 角色
你是中文学术文本质量分析器，专门识别 AI 生成痕迹并定位具体位置。

## 说明
量化统计部分（字数、比率）由 tools/readability_scorer.py 完成。
你的任务是：接收脚本输出的 JSON 结果，结合原文，给出可操作的改写建议。

## 输入
脚本输出的 JSON 指标：{{SCORER_JSON_OUTPUT}}
原文片段：{{ORIGINAL_TEXT}}

## 任务
1. 解读各项指标含义（用非技术语言解释给用户）
2. 对脚本标注的每处套话，给出1-2种具体替换方案
3. 对句式单调的段落，示范改写一个例句
4. 整体优先级排序：哪3处改了收益最大

## 输出格式
```
## 指标解读
[用一句话解释每个指标的意思]

## 套话替换建议
原句：「...」
方案A：...
方案B：...

## 句式改写示例
原句：...
改写：...

## 本次最值得改的3处
1. ...
2. ...
3. ...
```

## 约束
- 所有建议必须保持学术语体，不能改成口语
- 替换方案必须与原文语境一致，不引入新观点
````

---

### E. tools/ 目录说明

| 文件 | 用途 | 依赖 |
|------|------|------|
| `tools/readability_scorer.py` | 中文学术文本量化评分（套话率/句式多样性/连接词密度/综合评分） | Python 3.11+，无第三方依赖 |

**使用方式：**
```bash
# 分析文本文件
python tools/readability_scorer.py my_paper.txt

# 分析剪贴板文字
python tools/readability_scorer.py --text "随着人工智能的深入发展，本文旨在..."

# 输出 JSON 供 Prompt #34 使用
python tools/readability_scorer.py my_paper.txt --json > scorer_result.json
```

---

### F. Prompt 版本管理规范（v1.4 新增）

> **目的**：随着项目迭代，Prompt 内容会不断修改。建立版本管理制度，确保每次修改可追溯、可回滚、可评估效果。

#### 目录结构

```
skills/
├── research-writing/
│   └── SKILL.md              # 原始 Prompt #1-30（来自 alfonso0512，MIT License）
│
├── supplemental/             # 本项目新增/改编的 Prompt
│   ├── prompt_31_topic_advisor_v1.0.md
│   ├── prompt_31_topic_advisor_v1.1.md   ← 迭代版本
│   ├── prompt_32_cn_reviewer_v1.0.md
│   ├── prompt_33_cn_outline_v1.0.md
│   └── prompt_34_readability_v1.0.md
│
└── registry.csv             # 所有 Prompt 的版本索引（见下方格式）
```

#### registry.csv 格式

```csv
prompt_id,name,file,version,date,blind_test_score,test_count,notes
31,选题顾问,prompt_31_topic_advisor_v1.1.md,v1.1,2026-03-28,4.2/5,8,我调整了发散方向的比例权重
32,中文审稿人,prompt_32_cn_reviewer_v1.0.md,v1.0,2026-03-28,3.9/5,12,改编自ppw-reviewer-simulation
18,文献总结,#18（SKILL.md 内嵌）,v2.0,2026-03-18,N/A,N/A,来自research-writing-skill原作者
...
```

#### 迭代规则

| 场景 | 操作 |
|------|------|
| 修改现有 Prompt | 新建 `prompt_XX_name_v<X+1>.md`，旧版保留，更新 registry.csv |
| 新增 Prompt | 在 `supplemental/` 下新建 `prompt_XX_name_v1.0.md`，在 registry.csv 添加条目 |
| 删除 Prompt | 不物理删除文件，registry.csv 中标记 `deprecated: true` |
| 效果验证 | 每次迭代后需有至少 5 次内测盲评，低于 3.5/5 的版本不允许合入主分支 |

---

## 14. 开发陷阱 & 已知问题清单（v1.4 新增）

> 本节由 AI 模拟开发者视角穷举开发过程中可能遇到的问题，供调试时快速定位。
> 随着开发推进，本节持续更新。

### 🔴 会导致系统无法启动的问题

| # | 陷阱 | 触发条件 | 症状 | 解决方案 |
|---|------|----------|------|----------|
| T01 | AutoGen 版本不对 | `pip install autogen` 安装了旧版 | `ImportError: cannot import name 'GroupChat'` 或 API 不兼容 | 必须 `pip install autogen-agentchat[ollama]>=0.7`，参见 Section 7.5 |
| T02 | `.env` 里有空格导致 Key 读取失败 | `.env` 文件 `ANTHROPIC_API_KEY = sk-ant-...`（等号两边有空格） | API 返回 `authentication_error` | 用 `strip()` 读取 env 值，install 时检查格式 |
| T03 | SQLite 并发写入冲突 | 两个 AutoGen Worker 同时写 session DB | `sqlite3.OperationalError: database is locked` | 使用 `check_same_thread=False` + WAL 模式 + 写锁队列 |
| T04 | macOS 中文路径导致文件写入失败 | 用户名是中文，`~/Library/Application Support/` 路径含中文 | `FileNotFoundError` 在 `session_store/` | 所有路径处理加 `pathlib.Path.expanduser()` + UTF-8 编码测试 |
| T05 | Mock 模式忘记开，耗尽真实 API 额度 | 开发时没设置 `MOCK_MODE=true` | 测试跑完账单爆炸 | CI 强制要求 `MOCK_MODE=true` 跑测试 |

### 🟠 功能性 bug（能跑但结果错误）

| # | 陷阱 | 触发条件 | 症状 | 根因 | 解决方案 |
|---|------|----------|------|------|----------|
| T06 | Token 计算错误导致费用超上限 | DeepSeek V3 的 token 计费有 hit/miss 区别 | 实际费用是预估的 3-5 倍 | 直接用字符数估算 token 不准 | 必须用`tiktoken`库对每个 provider 单独计算 |
| T07 | 用户插话丢失在流式输出过程中 | 用户在 LLM streaming 途中输入文字 | 插话内容没有被 Agent 看到 | asyncio.Queue 在流式输出时没有被检查 | 在 stream yield 间隙周期性检查 Queue（每 50ms） |
| T08 | Context 压缩误删关键信息 | `E003` 触发后压缩历史消息 | 早期确定的选题方向在后续章书中消失 | 压缩时错误地只保留了 system prompt | 压缩时显式保留 `sessions.context_snapshot` 中的选题结论和文献矩阵 |
| T09 | `is_stale` 标记传播方向错误 | `goto` 触发后，只标记了同阶段后续产物，漏了前一阶段的版本记录 | 回滚后还是拿到的是新产物 | 逻辑只处理了单向传播 | 增加单元测试覆盖所有 `goto` 路径 |
| T10 | DOI 验证失败但仍然被引用 | Semantic Scholar 返回的 DOI 在 CrossRef 查不到（数据质量问题） | 论文里出现了虚假引用 | 只打印了 warning 没有阻断 | E004 应在输出中标注 `[需验证]`，并在最终质量报告里单独列出一张"可疑文献表" |
| T11 | Prompt #7 中文去AI味后改变了原意 | 机械替换套话时，误将学术术语当作套话替换 | 论文核心概念被改成了另一个词 | LLM 改写没有加"保持原意"约束 | Prompt #7 改写前先提取术语表，要求严格保留术语表中的词 |
| T12 | 流式输出导致 Markdown 渲染闪烁 | TUI 每收到一个 token 就刷新右栏 | 右栏内容不断跳动无法阅读 | 刷新频率太高 | 右栏 Markdown 渲染做 200ms debounce，累计 5 个 token 或 200ms 后刷新一次 |

### 🟡 边界情况（概率低但后果严重）

| # | 陷阱 | 触发条件 | 后果 | 建议 |
|---|------|----------|------|------|
| T13 | Session 恢复时选了错误的版本快照 | 用户在 `v2` 和 `v3` 之间犹豫，恢复时选错 | 后续所有工作基于错误版本，浪费用户时间 | 恢复前展示版本 diff 摘要，让用户确认 |
| T14 | 某期刊格式模板不存在 | 用户指定了 `Nature` 或其他未收录的期刊 | 格式输出直接失败 | 在启动时检查期刊模板是否存在，不存在则提前报错并列出可用模板 |
| T15 | DeepSeek API 响应速度慢导致 TUI 超时 | DeepSeek V3 在高峰期响应 >60s | TUI 认为请求失败，触发重试，但 LLM 实际还在生成 | 增加流式 `last_event_time` 心跳检测，超过 90s 才视为超时 |
| T16 | 文献研究员被 PDF 解析结果误导 | chatpaper 解析中文 PDF 出现乱码 | 文献摘要包含乱码，影响后续写作 | 解析前先检测编码，对乱码率 >5% 的文献标注 `[解析可疑]` |

---

**Version**: 1.7
**Author**: Academic Agent Team
**Date**: 2026-03-31
**Status**: In Development (活跃迭代中)
**Changelog**:
- v1.7: P3 PRD 内部矛盾修复：
  - ✅ §10.6 DeepSeek V3.2 → 统一为 DeepSeek V3（R1 推理任务另注）
  - ✅ §10.6 GLM-4 旗舰版定价描述统一为 ¥100/百万tokens（与表中数值一致）
  - ✅ §7.5 技术栈 AutoGen 0.4+ → AutoGen 0.7+（对齐 v1.6 代码骨架）
  - ✅ §14 T01 陷阱描述更新：AutoGen 版本检测陷阱
  - ✅ §8 与 §7.7 模型配置冲突已统一：sonnet（默认）/ gpt4o 为推荐配置；opus 为可选升级路径；§8 新增说明禁止硬编码、引用 ROLE_PROFILE 为权威默认值
  - ℹ️ Status: Draft → In Development
- v1.6: 代码层重大重构（与 PRD 7.x 对齐）：
  - ✅ DB Schema 升级：补 `run_mode`/`versions`/`raw_responses` 表 + 6条索引
  - ✅ pydantic 契约模型：实现 `BasePayload`/`TopicDone` 等 + E007/E010 错误码
  - ✅ AutoGen 0.7 骨架：5个 Agent 类（Advisor/Researcher/Writer/Reviewer/Polisher）+ `GraphFlow` 流水线编排器
  - ✅ 补全 Client：AnthropicClient / DeepSeekClient / ZhipuClient / OllamaClient
  - ✅ MODEL_REGISTRY 升级：统一 ROLE_PROFILE / ROLE_FALLBACK / FALLBACK_ORDER（PRD 7.7 规格）
  - ✅ CLI 全命令补齐：sessions/status/cost/role/mode/rollback/diff/export（PRD 9.2 规格）
  - ✅ Semantic Scholar + CrossRef 文献检索工具（PRD M3）
  - ✅ 导出门禁四 gate（contract/citation/format/ethics）+ 修复清单输出
  - ✅ 预算超限中断逻辑（E010，`budget_cap_cny` 参数）
  - ✅ 补全 `config/role_profiles.py` / `config/journals.py`
  - ✅ PRD Section 7.7 vs 8 模型配置矛盾：代码采用 7.7 规格（v1.7 统一 PRD 文本）
  - ✅ PRD Section 10.6 DeepSeek 名称："DeepSeek V3.2" → "DeepSeek V3"（v1.7 修）
- v1.5: 新增 Section 7.6（接口契约 JSON Schema）、7.7（模型注册表+BaseModelClient）、7.8（SQLite Schema）、7.9（日志策略）、7.10（Mock模式）；补录 Appendix F（Prompt版本管理）；新增 Section 14（开发陷阱清单）；修复甘特图周序号（W5→W14连续）；Phase 2 改为 W6-9，Phase 3 改为 W10-14；W1 验收标准改为"5个Agent（含润色）"；修复 Section 9.0 插话注入 API 写法（inject_message→asyncio.Queue）；修正 Appendix A-D 顺序（B/C/D/E/F）；补全 GitHub Code Search API 链接至 Appendix B
- v1.4: 新增 Appendix D（Prompt #31–#34 补充 Prompt 库）、Appendix E（tools/ 目录说明）；更新 Appendix A Skill 来源表，补全 K-Dense 和 Paper-Polish-Workflow 真实仓库地址及 License
- v1.3: PRD Review 修复 14 个问题（Agent数量矛盾、期刊模板数量矛盾、文献调研目标不一致、模型名称不合规、TAM数字修正、AutoGen代码注释修正、chatpaper说明补充、"Skill搜索工具"明确为GitHub Code Search API、API Key风险等级提升为Medium、W4时间线拆分到W5、GLM-4定价分层、新增Section 9.0可观察流+随时插话交互模型、新增API失败处理策略、补充stale状态UI说明）
- v1.2: 新增产品最终形态章节 (Section 1.5)、详细技术路径 (Section 7.5)、完整六阶段用户体验流程 (Section 9)、Launch Plan 细化到每周技术任务、甘特图
- v1.1: 修复 RICE 计算错误、统一 Agent 数量为5、审稿人和去AI味提升为 Must Have、新增学术伦理声明、新增成本估算、Tool Layer 增加 Semantic Scholar/Skill/CrossRef、Model Layer 增加 DeepSeek/GLM/MiniMax

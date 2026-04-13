# Phase 5 实现方案 — MVP v1.1 (C 刊/顶会投稿级)

> **版本**: 1.1  
> **状态**: 🔄 实现中  
> **创建时间**: 2026-04-08  
> **目标**: 输出可辅助投稿 C 刊/CSSCI/顶会的论文

---

## 1. 更新后的完整 Agent 角色定义

### 1.1 核心 Agent 团队 (6 个角色)

| 角色 | 职责 | 工具 | 参与 GroupChat |
|------|------|------|----------------|
| **Advisor** | 选题分析、研究空白识别 | topic_analyzer, gap_finder | 选题讨论 |
| **Researcher** | 文献搜索 (CNKI 优先)、RAG 综述 | search_cnki, search_arxiv, rag_query | 选题讨论 |
| **Data Analyst** | 数据分析、统计检验、图表生成 | run_statistics, generate_chart | 数据分析 |
| **Writer** | 章节撰写、引用注入 | write_section, inject_citations | 写作-审稿 |
| **Reviewer** | 审稿、质量评分、修改意见 | review_section, score_quality | 写作-审稿 + 终审 |
| **Polisher** | 语言润色、降重、格式化 | polish_text, reduce_similarity | 润色终审 |

### 1.2 辅助 Agent (按需调用)

| 角色 | 职责 | 触发条件 |
|------|------|----------|
| **Citation Verifier** | DOI/CNKI 链接验证 | 每次引用生成后 |
| **Plagiarism Checker** | 查重检测 | 每章节完成后 |
| **AI Detector** | AI 生成检测 | 每章节完成后 |
| **LaTeX Exporter** | LaTeX 编译 + 模板适配 | 最终导出时 |

### 1.3 Data Analyst Agent 详细定义

```python
DATA_ANALYST_SYSTEM_PROMPT = """你是一位专业的数据分析师，负责学术论文的数据处理和可视化。

## 可用工具
- run_statistics(data_path, analysis_type): 执行统计分析
  - analysis_type: "descriptive" | "correlation" | "regression" | "ttest" | "anova" | "chi2"
- generate_chart(data, chart_type, config): 生成图表
  - chart_type: "bar" | "line" | "scatter" | "heatmap" | "boxplot"
- validate_data(data_path): 数据质量检查

## 输出要求
严格输出 JSON 格式（AnalysisDone）：
- statistics_results: dict  # 统计结果
- figures: list[FigureRef]  # 图表引用
- interpretation: str  # 结果解读
- methodology_text: str  # 可直接插入论文的方法描述

## 学术规范
- 报告效应量 (Cohen's d, η²)
- 报告置信区间
- 使用 APA 格式表述统计结果
- 图表符合期刊规范 (300 DPI, 矢量格式优先)

## 禁止动作
- ❌ 编造数据
- ❌ p-hacking（选择性报告显著结果）
- ❌ 忽略异常值而不说明
"""

class AnalysisDone(BaseModel):
    statistics_results: dict
    figures: list[FigureRef]
    interpretation: str
    methodology_text: str
    data_source: str  # 必须追溯
    sample_size: int
```

---

## 2. F107~F112 详细实现方案

### 2.1 F107: AI 生成检测 + 改写建议

**技术选型**:
- **主引擎**: ZeroGPT API (稳定性好)
- **备用引擎**: GPTZero API (作为交叉验证)
- **自研补充**: 风格一致性检测 (perplexity + burstiness 计算)

**实现方案**:
```python
# academic_agent_team/tools/ai_detection.py

class AIDetector:
    """AI 生成检测工具"""
    
    def __init__(self):
        self.zerogpt_api = ZeroGPTClient(os.getenv("ZEROGPT_API_KEY"))
        self.gptdetector = GPTZeroClient(os.getenv("GPTZERO_API_KEY"))
    
    async def detect(self, text: str) -> AIDetectionResult:
        """双引擎检测"""
        results = await asyncio.gather(
            self.zerogpt_api.detect(text),
            self.gptdetector.detect(text),
        )
        
        # 取最高值作为保守估计
        ai_score = max(r.ai_probability for r in results)
        
        return AIDetectionResult(
            ai_probability=ai_score,
            flagged_sentences=self._merge_flagged(results),
            rewrite_suggestions=self._generate_suggestions(results) if ai_score > 0.3 else [],
            engines_used=["zerogpt", "gptzero"]
        )
    
    def _generate_suggestions(self, results) -> list[RewriteSuggestion]:
        """为高 AI 概率句子生成人类化改写建议"""
        suggestions = []
        for sentence in results[0].flagged_sentences:
            suggestions.append(RewriteSuggestion(
                original=sentence,
                suggestion="请人工改写此句：增加个人观点、具体案例或领域术语",
                ai_score=sentence.score
            ))
        return suggestions

class AIDetectionResult(BaseModel):
    ai_probability: float  # 0-1
    flagged_sentences: list[FlaggedSentence]
    rewrite_suggestions: list[RewriteSuggestion]
    engines_used: list[str]
    
    @property
    def needs_human_rewrite(self) -> bool:
        return self.ai_probability > 0.3  # 30% 阈值
```

**集成方式**: 作为 Gate 插入每个章节完成后
```
Writer 输出章节
    ↓
AI Detector 检测
    ├── ai_score < 30% → 通过
    └── ai_score ≥ 30% → 标记 + 返回改写建议 + 要求人工润色
```

---

### 2.2 F108: 引用 DOI / CNKI 验证

**技术选型**:
- **DOI 验证**: CrossRef API (免费, 可靠)
- **CNKI 验证**: 知网链接格式校验 + 元数据抓取

**实现方案**:
```python
# academic_agent_team/tools/citation_verifier.py

class CitationVerifier:
    """引用真实性验证"""
    
    def __init__(self):
        self.crossref = CrossRefClient()
        self.cnki = CNKIVerifier()
    
    async def verify_citation(self, citation: Citation) -> VerificationResult:
        """验证单条引用"""
        if citation.doi:
            return await self._verify_doi(citation.doi)
        elif citation.cnki_url:
            return await self._verify_cnki(citation.cnki_url)
        else:
            return VerificationResult(
                verified=False,
                reason="缺少 DOI 或知网链接",
                action="REMOVE_OR_FIND_SOURCE"
            )
    
    async def _verify_doi(self, doi: str) -> VerificationResult:
        """CrossRef DOI 验证"""
        try:
            metadata = await self.crossref.get_work(doi)
            return VerificationResult(
                verified=True,
                metadata=CitationMetadata(
                    title=metadata["title"][0],
                    authors=[a["family"] for a in metadata["author"]],
                    year=metadata["published"]["date-parts"][0][0],
                    journal=metadata.get("container-title", [""])[0],
                    doi=doi
                )
            )
        except DoiNotFoundError:
            return VerificationResult(verified=False, reason="DOI 不存在")
    
    async def verify_all(self, citations: list[Citation]) -> BatchVerificationResult:
        """批量验证"""
        results = await asyncio.gather(*[
            self.verify_citation(c) for c in citations
        ])
        
        verified = [c for c, r in zip(citations, results) if r.verified]
        failed = [c for c, r in zip(citations, results) if not r.verified]
        
        return BatchVerificationResult(
            verified_citations=verified,
            failed_citations=failed,
            verification_rate=len(verified) / len(citations) if citations else 0
        )
```

**Invariant 强制执行**:
```python
# INV-007: 所有引用必须通过验证
async def post_literature_gate(literature_done: LiteratureDone) -> GateResult:
    verifier = CitationVerifier()
    result = await verifier.verify_all(literature_done.citations)
    
    if result.verification_rate < 1.0:
        # 移除未验证引用
        literature_done.citations = result.verified_citations
        
        if result.verification_rate < 0.8:
            return GateResult(
                passed=False,
                reason=f"引用验证率过低: {result.verification_rate:.0%}",
                action="扩大文献搜索范围"
            )
    
    return GateResult(passed=True)
```

---

### 2.3 F109: 查重 + 智能降重

**技术选型**:
- **自研语义查重**: sentence-transformers (all-MiniLM-L6-v2) + 相似度计算
- **备用服务**: paperyy API (知网兼容格式)

**实现方案**:
```python
# academic_agent_team/tools/plagiarism_checker.py

class PlagiarismChecker:
    """查重检测"""
    
    def __init__(self, literature_db: VectorStore):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.literature_db = literature_db
        self.paperyy = PaperyyClient(os.getenv("PAPERYY_API_KEY"))
    
    async def check_similarity(self, text: str, threshold: float = 0.85) -> SimilarityResult:
        """语义相似度检测"""
        sentences = self._split_sentences(text)
        embeddings = self.embedder.encode(sentences)
        
        similar_pairs = []
        for i, (sent, emb) in enumerate(zip(sentences, embeddings)):
            # 在文献库中搜索相似段落
            matches = self.literature_db.query_by_embedding(emb, k=3)
            for match in matches:
                if match.similarity > threshold:
                    similar_pairs.append(SimilarPair(
                        original_sentence=sent,
                        matched_text=match.text,
                        source=match.metadata["source"],
                        similarity=match.similarity
                    ))
        
        similarity_rate = len(similar_pairs) / len(sentences)
        
        return SimilarityResult(
            overall_similarity=similarity_rate,
            similar_pairs=similar_pairs,
            needs_reduction=similarity_rate > 0.20  # 20% 阈值
        )
    
    def generate_reduction_suggestions(self, similar_pairs: list[SimilarPair]) -> list[ReductionSuggestion]:
        """生成降重建议"""
        suggestions = []
        for pair in similar_pairs:
            suggestions.append(ReductionSuggestion(
                original=pair.original_sentence,
                suggestion_type="paraphrase",
                hint=f"此句与《{pair.source}》相似度 {pair.similarity:.0%}，建议换词改写"
            ))
        return suggestions

# Polisher Agent 集成降重能力
POLISHER_REDUCTION_PROMPT = """当发现高相似度段落时：
1. 理解原文核心含义
2. 用完全不同的句式重新表达
3. 添加自己的分析和见解
4. 确保引用标注正确

禁止：简单同义词替换、调换语序
"""
```

---

### 2.4 F110: Data Analyst Agent

**技术选型**:
- **统计分析**: scipy, statsmodels, pingouin
- **可视化**: matplotlib, seaborn (学术风格)
- **执行环境**: RestrictedPython 沙箱

**实现方案**:
```python
# academic_agent_team/agents/data_analyst.py

class DataAnalystAgent(AssistantAgent):
    """数据分析 Agent"""
    
    def __init__(self, model_client):
        super().__init__(
            name="DataAnalyst",
            system_message=DATA_ANALYST_SYSTEM_PROMPT,
            model_client=model_client,
            tools=[
                self.run_statistics,
                self.generate_chart,
                self.validate_data
            ]
        )
    
    @tool
    async def run_statistics(
        self,
        data_path: str,
        analysis_type: Literal["descriptive", "correlation", "regression", "ttest", "anova", "chi2"],
        variables: list[str]
    ) -> StatisticsResult:
        """在沙箱中执行统计分析"""
        sandbox = StatisticsSandbox()
        
        code = self._generate_analysis_code(analysis_type, variables)
        result = await sandbox.execute(code, data_path)
        
        return StatisticsResult(
            analysis_type=analysis_type,
            results=result.output,
            apa_format=self._format_apa(result),  # APA 格式输出
            code_used=code  # 可复现性
        )
    
    @tool
    async def generate_chart(
        self,
        data_path: str,
        chart_type: str,
        config: ChartConfig
    ) -> FigureRef:
        """生成学术规范图表"""
        # 设置学术样式
        plt.style.use("seaborn-v0_8-paper")
        plt.rcParams["figure.dpi"] = 300
        
        fig = self._create_chart(chart_type, data_path, config)
        
        # 保存多格式
        figure_id = str(uuid.uuid4())[:8]
        paths = {
            "png": f"figures/{figure_id}.png",
            "pdf": f"figures/{figure_id}.pdf",  # 矢量格式
            "svg": f"figures/{figure_id}.svg"
        }
        
        for fmt, path in paths.items():
            fig.savefig(path, format=fmt, bbox_inches="tight")
        
        return FigureRef(
            figure_id=figure_id,
            caption=config.caption,
            paths=paths,
            latex_ref=f"\\ref{{fig:{figure_id}}}"
        )
```

---

### 2.5 F111: LaTeX 导出 + 期刊模板库

**技术选型**:
- **模板引擎**: Jinja2 + 自定义 LaTeX 过滤器
- **编译**: pdflatex / xelatex (中文支持)
- **模板来源**: 复制 pmichaillat/latex-paper + CSSCI 常用模板

**模板目录结构**:
```
templates/latex/
├── cssci/
│   ├── journalism.cls      # 新闻传播类
│   ├── sociology.cls       # 社会学类
│   └── management.cls      # 管理学类
├── conferences/
│   ├── acl2025.sty
│   ├── neurips2025.sty
│   ├── chi2025.cls
│   └── ieee.cls
├── common/
│   ├── gbt7714-2015.bst    # 国标引用格式
│   ├── apa7.bst
│   └── ieee.bst
└── base/
    └── paper_genius.cls    # 通用基础模板
```

**实现方案**:
```python
# academic_agent_team/tools/latex_exporter.py

class LaTeXExporter:
    """LaTeX 导出引擎"""
    
    TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "latex"
    
    def __init__(self):
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.TEMPLATE_DIR),
            block_start_string='\\BLOCK{',
            block_end_string='}',
            variable_start_string='\\VAR{',
            variable_end_string='}',
        )
        self.jinja_env.filters["escape_latex"] = self._escape_latex
    
    def export(
        self,
        paper: PaperContent,
        template: str = "cssci/journalism",
        bibliography_style: str = "gbt7714-2015"
    ) -> LaTeXOutput:
        """导出 LaTeX 源文件"""
        
        template = self.jinja_env.get_template(f"{template}.tex.jinja")
        
        latex_content = template.render(
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            keywords=paper.keywords,
            sections=paper.sections,
            references=paper.references,
            figures=paper.figures,
            tables=paper.tables,
            bibliography_style=bibliography_style
        )
        
        # 生成 .bib 文件
        bib_content = self._generate_bibtex(paper.references)
        
        return LaTeXOutput(
            main_tex=latex_content,
            bib_file=bib_content,
            template_used=template
        )
    
    async def compile(self, latex_output: LaTeXOutput, output_dir: Path) -> CompileResult:
        """编译 LaTeX 到 PDF"""
        # 写入文件
        (output_dir / "main.tex").write_text(latex_output.main_tex)
        (output_dir / "references.bib").write_text(latex_output.bib_file)
        
        # 复制模板依赖
        self._copy_template_deps(latex_output.template_used, output_dir)
        
        # 编译 (xelatex 支持中文)
        for _ in range(2):  # 两次编译确保引用正确
            proc = await asyncio.create_subprocess_exec(
                "xelatex", "-interaction=nonstopmode", "main.tex",
                cwd=output_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
        
        # biber/bibtex
        await asyncio.create_subprocess_exec(
            "bibtex", "main",
            cwd=output_dir
        )
        
        # 最终编译
        await asyncio.create_subprocess_exec(
            "xelatex", "-interaction=nonstopmode", "main.tex",
            cwd=output_dir
        )
        
        pdf_path = output_dir / "main.pdf"
        if pdf_path.exists():
            return CompileResult(success=True, pdf_path=pdf_path)
        else:
            return CompileResult(success=False, error=stderr.decode())
```

---

### 2.6 F112: CNKI 搜索 (MVP 最高优先级)

**技术选型**:
- **主方案**: 集成 MagicCNKI (1049451037/MagicCNKI)
- **备用方案**: h-lu/cnki-mcp (MCP 服务器)

**实现方案**:
```python
# academic_agent_team/tools/search_cnki.py

# 直接集成 MagicCNKI
from magiccnki import CNKISearcher

class CNKISearchTool:
    """CNKI 搜索工具 - Researcher Agent 专用"""
    
    def __init__(self):
        self.searcher = CNKISearcher()
        self.rate_limiter = RateLimiter(requests_per_minute=10)
    
    @tool
    async def search_cnki(
        self,
        query: str,
        search_type: Literal["主题", "关键词", "作者", "篇名"] = "主题",
        source_filter: list[str] | None = None,  # ["CSSCI", "北大核心", "SCI"]
        year_range: tuple[int, int] | None = None,
        max_results: int = 50
    ) -> list[CNKIPaper]:
        """搜索知网文献"""
        
        await self.rate_limiter.wait()
        
        try:
            results = self.searcher.search(
                query=query,
                search_type=search_type,
                source=source_filter,
                year_from=year_range[0] if year_range else None,
                year_to=year_range[1] if year_range else None,
                limit=max_results
            )
            
            papers = []
            for r in results:
                papers.append(CNKIPaper(
                    title=r["title"],
                    authors=r["authors"],
                    journal=r["journal"],
                    year=r["year"],
                    abstract=r.get("abstract", ""),
                    keywords=r.get("keywords", []),
                    cnki_url=r["url"],
                    source_type=self._classify_source(r["journal"]),
                    doi=r.get("doi")  # 可能为空
                ))
            
            return papers
            
        except CNKIRateLimitError:
            logger.warning("CNKI 限流，切换到备用源")
            return await self._fallback_search(query, max_results)
    
    async def _fallback_search(self, query: str, max_results: int) -> list[CNKIPaper]:
        """降级到 Semantic Scholar + OpenAlex"""
        ss_results = await search_semantic_scholar(query, max_results // 2)
        oa_results = await search_openalex(query, max_results // 2)
        return self._merge_and_dedupe(ss_results + oa_results)
```

**Researcher Agent CNKI 专用 Prompt**:
```python
RESEARCHER_CNKI_SYSTEM_PROMPT = """你是一位专业的中文学术文献检索专家，擅长使用知网(CNKI)进行文献调研。

## 可用工具
- search_cnki(query, search_type, source_filter, year_range, max_results): 搜索知网
- search_arxiv(query, max_results): 搜索英文预印本
- search_semantic_scholar(query, max_results): 搜索英文学术文献
- pdf_parse(url): 解析 PDF
- rag_query(question, collection): 基于已入库文献问答
- add_to_library(paper): 添加文献到向量库

## 搜索优先级
1. **CNKI (知网)** - 中文社科论文首选
2. **Semantic Scholar** - 英文补充
3. **arXiv** - 计算机/数学领域预印本

## 文献筛选标准
- 优先 CSSCI 来源期刊、北大核心
- 优先近 5 年文献 (≥ 2021)
- 排除学位论文（除非高度相关）
- 中英文比例建议 6:4 (社科) 或 3:7 (CS)

## 输出要求
严格输出 JSON 格式（LiteratureDone）：
- papers: list[Paper]  # 必须包含 cnki_url 或 doi
- literature_matrix: str  # Markdown 表格，含来源类型
- verified_count: int  # 已验证引用数
- cnki_count: int  # CNKI 文献数
- international_count: int  # 国际文献数

## 质量门禁
- 总文献数 ≥ 30 篇
- CNKI 文献 ≥ 15 篇 (社科项目)
- 所有文献必须有 cnki_url 或 doi

## 禁止动作
- ❌ 编造知网链接
- ❌ 跳过 CNKI 直接用英文文献
- ❌ 返回无法验证的文献
"""
```

---

## 3. 引用验证 + 查重 + AI 检测闭环流程

```
论文生成流程（含质量 Gate）
════════════════════════════════════════════════════════════════

                    [用户输入主题]
                          │
                          ▼
                ┌─────────────────┐
                │ Phase 1: 选题   │
                │ Advisor ⟷ Researcher │
                └─────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │ Phase 2: 文献调研 │
                │ Researcher + CNKI │
                └─────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │       引用验证 Gate (F108)      │
         │  ┌─────────────────────────┐   │
         │  │ CrossRef 验证 DOI        │   │
         │  │ CNKI 链接格式校验        │   │
         │  │ 验证率 < 80% → 返回搜索  │   │
         │  └─────────────────────────┘   │
         └────────────────────────────────┘
                          │ 通过
                          ▼
         ┌────────────────────────────────┐
         │       文献质量 Gate (D5)        │
         │  文献 < 30 篇 → 返回 Phase 1   │
         │  CNKI < 15 篇 → 扩大搜索       │
         └────────────────────────────────┘
                          │ 通过
                          ▼
                ┌─────────────────┐
                │ Phase 2.5: 数据分析 │  ← 新增
                │ Data Analyst      │
                └─────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │ Phase 3: 写作-审稿 │
                │ Writer ⟷ Reviewer │
                │ (章节循环)        │
                └─────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
    ┌─────────────────┐     ┌─────────────────┐
    │ 每章节完成后:    │     │                 │
    │                 │     │                 │
    │ ① AI 检测 Gate  │     │ ② 查重 Gate     │
    │   (F107)        │     │   (F109)        │
    │                 │     │                 │
    │ ai_score ≥ 30%  │     │ similarity ≥ 20%│
    │     ↓           │     │     ↓           │
    │ 标记 + 改写建议  │     │ 降重建议        │
    │ 要求人工润色    │     │ → Polisher 改写 │
    └─────────────────┘     └─────────────────┘
              │                       │
              └───────────┬───────────┘
                          ▼
         ┌────────────────────────────────┐
         │       内容质量 Gate (D6)        │
         │  Reviewer 评分 < 85 → 返回重写  │
         └────────────────────────────────┘
                          │ 通过
                          ▼
                ┌─────────────────┐
                │ Phase 4: 润色终审 │
                │ Polisher ⟷ Reviewer │
                └─────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │      最终 AI + 查重检测         │
         │  整篇论文综合检测              │
         │  ai_score < 30% AND sim < 20% │
         │  否则 → 人工修改清单           │
         └────────────────────────────────┘
                          │ 通过
                          ▼
                ┌─────────────────┐
                │ Phase 5: 导出   │
                │ LaTeX Exporter  │
                └─────────────────┘
                          │
                          ▼
         ┌────────────────────────────────┐
         │         最终输出                │
         │                                │
         │  📄 paper.pdf (期刊格式)       │
         │  📄 paper.tex (LaTeX 源码)     │
         │  📚 references.bib             │
         │  📊 figures/ (图表)            │
         │  📋 AI 辅助声明模板            │
         │  📝 人类修改建议报告           │
         │                                │
         └────────────────────────────────┘
```

---

## 4. 更新后的 Phase 执行顺序

### 4.1 论文生成 Pipeline (6 Phase)

| Phase | 名称 | 参与 Agent | 产出 | Gate |
|-------|------|------------|------|------|
| 1 | 选题讨论 | Advisor + Researcher | TopicDone | 双方确认 |
| 2 | 文献调研 | Researcher (CNKI 优先) | LiteratureDone | 引用验证 + 文献数量 |
| **2.5** | **数据分析** | **Data Analyst** | **AnalysisDone** | 统计方法合理性 |
| 3 | 写作-审稿 | Writer + Reviewer | WritingDone + ReviewDone | AI 检测 + 查重 + 评分 |
| 4 | 润色终审 | Polisher + Reviewer | PolishDone | 最终质量检查 |
| 5 | 导出 | LaTeX Exporter | PDF + LaTeX | 编译成功 |

### 4.2 代码实现周计划 (6 周)

| 周 | 任务 | 交付物 |
|---|------|--------|
| W1 | CNKI 集成 + 引用验证 | search_cnki.py, citation_verifier.py |
| W2 | PDF 解析 + RAG | pdf_extract plugin, rag plugin |
| W3 | AI 检测 + 查重 | ai_detection.py, plagiarism_checker.py |
| W4 | Data Analyst Agent | data_analyst.py, statistics_sandbox.py |
| W5 | LaTeX 导出 | latex_exporter.py, templates/ |
| W6 | 集成测试 + 稳定性 | E2E tests, demo |

---

## 5. 强制输出内容

### 5.1 AI 辅助生成声明模板

```latex
\section*{AI 辅助声明}

本论文在撰写过程中使用了 AI 辅助工具（PaperGenius Pro）进行：
\begin{itemize}
    \item 文献检索与综述生成
    \item 初稿撰写与结构组织
    \item 语言润色与格式规范
\end{itemize}

所有核心观点、研究设计、数据分析及结论均由作者独立完成并经过人工审核修改。
AI 生成内容比例约为 \_\_\_\%（经 ZeroGPT/GPTZero 检测）。

全文引用均已通过 DOI/知网链接验证真实有效。
```

### 5.2 人类修改建议报告模板

```markdown
# 人类修改建议报告

## 概览
- 论文标题: {{title}}
- 生成时间: {{timestamp}}
- AI 检测得分: {{ai_score}}% (需 < 30%)
- 查重相似度: {{similarity}}% (需 < 20%)

## 🔴 必须人工修改的段落

### 高 AI 概率段落 (ai_score > 50%)
1. **第 2 章第 3 段** (ai_score: 72%)
   > 原文: "人工智能技术的快速发展..."
   > 建议: 添加具体案例、个人见解或领域专业术语

2. ...

### 高相似度段落 (similarity > 30%)
1. **第 3 章第 1 段** (与《XXX》相似度: 45%)
   > 原文: "..."
   > 建议: 换用完全不同的表述方式

## 🟡 建议人工润色的部分
- Introduction 段落 3
- Discussion 全节

## ✅ 可直接使用的部分
- Abstract
- Methodology (数据分析部分)
- Conclusion

## 检查清单
- [ ] 核心创新点是否清晰？
- [ ] 所有引用是否已确认来源？
- [ ] 统计结果是否已复核？
- [ ] 是否符合目标期刊格式？
```

---

## 6. 可复用 GitHub 项目集成计划

### 6.1 直接集成 (Week 1)

| 项目 | 集成方式 | 目标模块 |
|------|----------|----------|
| **1049451037/MagicCNKI** | pip install | F112 CNKI 搜索 |
| **pmichaillat/latex-paper** | 复制 .cls/.sty | F111 LaTeX 模板 |

### 6.2 参考集成 (Week 2-3)

| 项目 | 复制部分 | 目标模块 |
|------|----------|----------|
| **assafelovic/gpt-researcher** | multi_agents/ 目录 | Pipeline 参考 |
| **RUC-NLPIR/FlashRAG** | retrieval 模块 | RAG 优化 |

---

## 输出契约

| 项目 | 内容 |
|------|------|
| **Current Phase** | Phase 5 - 实现中 |
| **What was completed** | 6 Agent 角色定义、F107-F112 方案、CNKI Prompt、闭环流程、执行顺序 |
| **Gate status** | 🟢 设计完成，准备编码 |
| **Risks** | ZeroGPT/GPTZero API 稳定性；CNKI 反爬虫 |
| **Need human decision?** | No |
| **Next action** | 开始 Week 1 编码：CNKI 集成 + 引用验证 |

---

**确认后开始编码实现。**

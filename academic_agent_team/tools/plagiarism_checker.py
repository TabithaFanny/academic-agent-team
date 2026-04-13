"""
查重工具 — 检测文本的语义相似度并提供降重建议。

功能：
  - check_similarity(text): 异步检测文本的相似度
  - 在向量库中搜索相似片段
  - 计算整体相似度
  - 生成降重建议

相似度阈值：
  - >= 0.85: 高相似度（红色警告）
  - >= 0.70: 中等相似度（黄色警告）
  - < 0.70: 低相似度（通过）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field

from ..storage.vector_db import VectorStore, SearchResult, get_vector_store

logger = logging.getLogger(__name__)


# ── 常量定义 ─────────────────────────────────────────────────────────────────

HIGH_SIMILARITY_THRESHOLD = 0.85   # 高相似度阈值
MEDIUM_SIMILARITY_THRESHOLD = 0.70  # 中等相似度阈值


# ── 数据模型 ─────────────────────────────────────────────────────────────────

class SimilarityLevel(str, Enum):
    """相似度级别"""
    HIGH = "high"      # >= 0.85
    MEDIUM = "medium"  # >= 0.70
    LOW = "low"        # < 0.70


class SimilarPair(BaseModel):
    """相似文本对"""
    original_sentence: str = Field(description="原始句子")
    matched_text: str = Field(description="匹配到的相似文本")
    source: str = Field(default="unknown", description="来源（如文献标题、URL等）")
    similarity: float = Field(ge=0.0, le=1.0, description="相似度分数 (0-1)")
    
    @property
    def level(self) -> SimilarityLevel:
        """获取相似度级别"""
        if self.similarity >= HIGH_SIMILARITY_THRESHOLD:
            return SimilarityLevel.HIGH
        elif self.similarity >= MEDIUM_SIMILARITY_THRESHOLD:
            return SimilarityLevel.MEDIUM
        return SimilarityLevel.LOW
    
    @property
    def is_high(self) -> bool:
        return self.similarity >= HIGH_SIMILARITY_THRESHOLD
    
    @property
    def is_medium(self) -> bool:
        return MEDIUM_SIMILARITY_THRESHOLD <= self.similarity < HIGH_SIMILARITY_THRESHOLD


class ReductionSuggestion(BaseModel):
    """降重建议"""
    original: str = Field(description="原始文本")
    suggestion_type: Literal["rephrase", "cite", "restructure", "combine"] = Field(
        description="建议类型：rephrase=改写, cite=添加引用, restructure=调整结构, combine=合并句子"
    )
    hint: str = Field(description="降重提示")


class SimilarityResult(BaseModel):
    """查重结果"""
    overall_similarity: float = Field(ge=0.0, le=1.0, description="整体相似度")
    similar_pairs: List[SimilarPair] = Field(default_factory=list, description="相似文本对列表")
    needs_reduction: bool = Field(default=False, description="是否需要降重")
    reduction_suggestions: List[ReductionSuggestion] = Field(
        default_factory=list, description="降重建议列表"
    )
    
    @property
    def level(self) -> SimilarityLevel:
        """获取整体相似度级别"""
        if self.overall_similarity >= HIGH_SIMILARITY_THRESHOLD:
            return SimilarityLevel.HIGH
        elif self.overall_similarity >= MEDIUM_SIMILARITY_THRESHOLD:
            return SimilarityLevel.MEDIUM
        return SimilarityLevel.LOW
    
    @property
    def high_similarity_count(self) -> int:
        """高相似度句子数量"""
        return sum(1 for p in self.similar_pairs if p.is_high)
    
    @property
    def medium_similarity_count(self) -> int:
        """中等相似度句子数量"""
        return sum(1 for p in self.similar_pairs if p.is_medium)


# ── 查重器 ─────────────────────────────────────────────────────────────────

class PlagiarismChecker:
    """
    查重检测器。
    
    使用向量数据库进行语义相似度检测，
    支持分句检测和整体相似度计算。
    """
    
    # 降重建议模板
    REDUCTION_HINTS = {
        "rephrase": [
            "尝试用自己的话重新表述这个观点",
            "替换关键词汇，使用同义词或近义词",
            "调整句子结构，改变主被动语态",
            "将长句拆分为多个短句",
            "将多个短句合并为一个复杂句",
        ],
        "cite": [
            "添加引用标注，注明原始出处",
            "使用直接引用格式，并标注页码",
            "将此内容作为引文处理",
        ],
        "restructure": [
            "调整段落结构，重新组织论述逻辑",
            "改变论述顺序，先结论后论据",
            "添加过渡句，使上下文更连贯",
        ],
        "combine": [
            "将相似的观点合并表述",
            "整合多个来源的观点，形成综述",
            "用对比分析的方式呈现不同观点",
        ],
    }
    
    def __init__(
        self,
        vector_store: VectorStore | None = None,
        high_threshold: float = HIGH_SIMILARITY_THRESHOLD,
        medium_threshold: float = MEDIUM_SIMILARITY_THRESHOLD,
        top_k: int = 5,
    ):
        """
        初始化查重检测器。
        
        Args:
            vector_store: 向量数据库实例，如果为 None 则使用默认实例
            high_threshold: 高相似度阈值（默认 0.85）
            medium_threshold: 中等相似度阈值（默认 0.70）
            top_k: 每个句子检索的相似文本数量
        """
        self._vector_store = vector_store
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.top_k = top_k
    
    @property
    def vector_store(self) -> VectorStore:
        """获取向量数据库实例（延迟初始化）"""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store
    
    async def check_similarity(self, text: str) -> SimilarityResult:
        """
        检测文本的相似度。
        
        Args:
            text: 待检测的文本
            
        Returns:
            SimilarityResult 包含相似度结果和降重建议
        """
        if not text or not text.strip():
            return SimilarityResult(
                overall_similarity=0.0,
                similar_pairs=[],
                needs_reduction=False,
                reduction_suggestions=[],
            )
        
        # 分句
        sentences = self._split_sentences(text)
        if not sentences:
            return SimilarityResult(
                overall_similarity=0.0,
                similar_pairs=[],
                needs_reduction=False,
                reduction_suggestions=[],
            )
        
        # 检测每个句子的相似度
        similar_pairs: List[SimilarPair] = []
        total_max_similarity = 0.0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # 跳过过短的句子
                continue
            
            # 在向量库中搜索相似文本
            search_results = await self._search_similar(sentence)
            
            if search_results:
                # 取最高相似度
                best_match = search_results[0]
                total_max_similarity += best_match.similarity
                
                # 只记录超过中等阈值的相似对
                if best_match.similarity >= self.medium_threshold:
                    similar_pairs.append(SimilarPair(
                        original_sentence=sentence,
                        matched_text=best_match.content,
                        source=best_match.source,
                        similarity=round(best_match.similarity, 4),
                    ))
            else:
                # 未找到相似内容，相似度为 0
                total_max_similarity += 0.0
        
        # 计算整体相似度
        checked_count = sum(1 for s in sentences if len(s.strip()) >= 10)
        overall_similarity = (
            total_max_similarity / checked_count if checked_count > 0 else 0.0
        )
        
        # 判断是否需要降重
        needs_reduction = (
            overall_similarity >= self.medium_threshold
            or any(p.is_high for p in similar_pairs)
        )
        
        # 生成降重建议
        reduction_suggestions = self._generate_reduction_suggestions(similar_pairs)
        
        return SimilarityResult(
            overall_similarity=round(overall_similarity, 4),
            similar_pairs=similar_pairs,
            needs_reduction=needs_reduction,
            reduction_suggestions=reduction_suggestions,
        )
    
    async def _search_similar(self, text: str) -> List[SearchResult]:
        """
        在向量库中搜索相似文本。
        
        Args:
            text: 查询文本
            
        Returns:
            按相似度降序排列的搜索结果
        """
        try:
            results = await self.vector_store.query(
                query=text,
                k=self.top_k,
            )
            # 过滤掉完全相同的文本（可能是同一文档）
            return [r for r in results if r.content.strip() != text.strip()]
        except Exception as e:
            logger.warning(f"向量库搜索失败: {e}")
            return []
    
    def _split_sentences(self, text: str) -> List[str]:
        """
        分割文本为句子列表。
        
        支持中英文标点。
        """
        # 中英文句子分割
        pattern = r'(?<=[。！？.!?])\s*'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _generate_reduction_suggestions(
        self, 
        similar_pairs: List[SimilarPair],
    ) -> List[ReductionSuggestion]:
        """
        根据相似对生成降重建议。
        
        Args:
            similar_pairs: 相似文本对列表
            
        Returns:
            降重建议列表
        """
        suggestions: List[ReductionSuggestion] = []
        
        for pair in similar_pairs:
            if pair.similarity >= self.high_threshold:
                # 高相似度：建议改写或添加引用
                suggestion_type = "rephrase" if pair.similarity < 0.95 else "cite"
                hint_pool = self.REDUCTION_HINTS[suggestion_type]
                hint = hint_pool[len(suggestions) % len(hint_pool)]
                
                suggestions.append(ReductionSuggestion(
                    original=pair.original_sentence,
                    suggestion_type=suggestion_type,
                    hint=f"{hint}（来源: {pair.source}）",
                ))
            elif pair.similarity >= self.medium_threshold:
                # 中等相似度：建议调整结构
                suggestion_type = "restructure"
                hint_pool = self.REDUCTION_HINTS[suggestion_type]
                hint = hint_pool[len(suggestions) % len(hint_pool)]
                
                suggestions.append(ReductionSuggestion(
                    original=pair.original_sentence,
                    suggestion_type=suggestion_type,
                    hint=hint,
                ))
        
        return suggestions


# ── 便捷函数 ─────────────────────────────────────────────────────────────────

async def check_plagiarism(
    text: str,
    vector_store: VectorStore | None = None,
) -> SimilarityResult:
    """
    便捷函数：检测文本的相似度。
    
    Args:
        text: 待检测的文本
        vector_store: 向量数据库实例（可选）
        
    Returns:
        SimilarityResult
    """
    checker = PlagiarismChecker(vector_store=vector_store)
    return await checker.check_similarity(text)


def format_plagiarism_report(result: SimilarityResult) -> str:
    """
    格式化查重结果为可读报告。
    
    Args:
        result: 查重结果
        
    Returns:
        Markdown 格式的报告
    """
    lines = [
        "# 📝 查重检测报告",
        "",
        f"## 整体相似度: {result.overall_similarity * 100:.1f}%",
        "",
    ]
    
    # 风险等级
    if result.level == SimilarityLevel.HIGH:
        risk = "🔴 高相似度 - 需要大幅修改"
    elif result.level == SimilarityLevel.MEDIUM:
        risk = "🟡 中等相似度 - 建议适当修改"
    else:
        risk = "🟢 低相似度 - 通过"
    
    lines.append(f"**风险等级**: {risk}")
    lines.append("")
    
    # 统计信息
    lines.append("## 📊 统计")
    lines.append(f"- 高相似度句子: {result.high_similarity_count} 个")
    lines.append(f"- 中等相似度句子: {result.medium_similarity_count} 个")
    lines.append(f"- 需要降重: {'是' if result.needs_reduction else '否'}")
    lines.append("")
    
    # 相似文本对
    if result.similar_pairs:
        lines.append("## 🔍 相似内容详情")
        lines.append("")
        
        for i, pair in enumerate(result.similar_pairs, 1):
            level_icon = "🔴" if pair.is_high else "🟡"
            lines.append(f"### {level_icon} 第 {i} 处 (相似度: {pair.similarity * 100:.1f}%)")
            lines.append("")
            lines.append("**原文:**")
            lines.append(f"> {pair.original_sentence}")
            lines.append("")
            lines.append("**相似来源:**")
            lines.append(f"> {pair.matched_text}")
            lines.append(f"")
            lines.append(f"*来源: {pair.source}*")
            lines.append("")
    else:
        lines.append("## ✅ 未发现高相似度内容")
        lines.append("")
    
    # 降重建议
    if result.reduction_suggestions:
        lines.append("## ✏️ 降重建议")
        lines.append("")
        
        for i, suggestion in enumerate(result.reduction_suggestions, 1):
            type_names = {
                "rephrase": "改写",
                "cite": "添加引用",
                "restructure": "调整结构",
                "combine": "合并表述",
            }
            type_name = type_names.get(suggestion.suggestion_type, suggestion.suggestion_type)
            
            lines.append(f"### 建议 {i}: {type_name}")
            lines.append(f"**原句:** {suggestion.original}")
            lines.append(f"**建议:** {suggestion.hint}")
            lines.append("")
    
    return "\n".join(lines)

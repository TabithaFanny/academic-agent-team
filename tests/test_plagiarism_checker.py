"""
测试查重检测模块。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from academic_agent_team.tools.plagiarism_checker import (
    PlagiarismChecker,
    SimilarityResult,
    SimilarPair,
    ReductionSuggestion,
    SimilarityLevel,
    check_plagiarism,
    format_plagiarism_report,
    HIGH_SIMILARITY_THRESHOLD,
    MEDIUM_SIMILARITY_THRESHOLD,
)
from academic_agent_team.storage.vector_db import SearchResult


# ── 数据模型测试 ─────────────────────────────────────────────────────────────

class TestSimilarPair:
    """测试 SimilarPair 模型"""
    
    def test_high_similarity_level(self):
        """高相似度应该返回 HIGH 级别"""
        pair = SimilarPair(
            original_sentence="这是原始句子。",
            matched_text="这是匹配的文本。",
            source="测试来源",
            similarity=0.90,
        )
        assert pair.level == SimilarityLevel.HIGH
        assert pair.is_high is True
        assert pair.is_medium is False
    
    def test_medium_similarity_level(self):
        """中等相似度应该返回 MEDIUM 级别"""
        pair = SimilarPair(
            original_sentence="这是原始句子。",
            matched_text="这是匹配的文本。",
            source="测试来源",
            similarity=0.75,
        )
        assert pair.level == SimilarityLevel.MEDIUM
        assert pair.is_high is False
        assert pair.is_medium is True
    
    def test_low_similarity_level(self):
        """低相似度应该返回 LOW 级别"""
        pair = SimilarPair(
            original_sentence="这是原始句子。",
            matched_text="这是匹配的文本。",
            source="测试来源",
            similarity=0.50,
        )
        assert pair.level == SimilarityLevel.LOW
        assert pair.is_high is False
        assert pair.is_medium is False


class TestSimilarityResult:
    """测试 SimilarityResult 模型"""
    
    def test_overall_level_high(self):
        """整体高相似度级别测试"""
        result = SimilarityResult(
            overall_similarity=0.88,
            similar_pairs=[],
            needs_reduction=True,
        )
        assert result.level == SimilarityLevel.HIGH
    
    def test_overall_level_medium(self):
        """整体中等相似度级别测试"""
        result = SimilarityResult(
            overall_similarity=0.72,
            similar_pairs=[],
            needs_reduction=True,
        )
        assert result.level == SimilarityLevel.MEDIUM
    
    def test_overall_level_low(self):
        """整体低相似度级别测试"""
        result = SimilarityResult(
            overall_similarity=0.50,
            similar_pairs=[],
            needs_reduction=False,
        )
        assert result.level == SimilarityLevel.LOW
    
    def test_similarity_counts(self):
        """测试相似度计数"""
        pairs = [
            SimilarPair(
                original_sentence="句子1",
                matched_text="匹配1",
                source="来源1",
                similarity=0.90,  # HIGH
            ),
            SimilarPair(
                original_sentence="句子2",
                matched_text="匹配2",
                source="来源2",
                similarity=0.88,  # HIGH
            ),
            SimilarPair(
                original_sentence="句子3",
                matched_text="匹配3",
                source="来源3",
                similarity=0.75,  # MEDIUM
            ),
        ]
        result = SimilarityResult(
            overall_similarity=0.85,
            similar_pairs=pairs,
            needs_reduction=True,
        )
        assert result.high_similarity_count == 2
        assert result.medium_similarity_count == 1


class TestReductionSuggestion:
    """测试 ReductionSuggestion 模型"""
    
    def test_rephrase_suggestion(self):
        """测试改写建议"""
        suggestion = ReductionSuggestion(
            original="这是需要改写的句子。",
            suggestion_type="rephrase",
            hint="尝试用自己的话重新表述这个观点",
        )
        assert suggestion.suggestion_type == "rephrase"
    
    def test_cite_suggestion(self):
        """测试引用建议"""
        suggestion = ReductionSuggestion(
            original="这是需要引用的句子。",
            suggestion_type="cite",
            hint="添加引用标注，注明原始出处",
        )
        assert suggestion.suggestion_type == "cite"


# ── PlagiarismChecker 测试 ─────────────────────────────────────────────────

class TestPlagiarismChecker:
    """测试 PlagiarismChecker 类"""
    
    @pytest.fixture
    def mock_vector_store(self):
        """创建模拟的向量数据库"""
        store = MagicMock()
        store.query = AsyncMock(return_value=[])
        return store
    
    @pytest.fixture
    def checker(self, mock_vector_store):
        """创建查重检测器"""
        return PlagiarismChecker(vector_store=mock_vector_store)
    
    @pytest.mark.asyncio
    async def test_empty_text_returns_zero_similarity(self, checker):
        """空文本应返回零相似度"""
        result = await checker.check_similarity("")
        assert result.overall_similarity == 0.0
        assert result.similar_pairs == []
        assert result.needs_reduction is False
    
    @pytest.mark.asyncio
    async def test_whitespace_text_returns_zero_similarity(self, checker):
        """纯空白文本应返回零相似度"""
        result = await checker.check_similarity("   \n\t  ")
        assert result.overall_similarity == 0.0
        assert result.similar_pairs == []
    
    @pytest.mark.asyncio
    async def test_short_sentences_skipped(self, checker):
        """过短的句子应被跳过"""
        result = await checker.check_similarity("短句。")
        assert result.overall_similarity == 0.0
    
    @pytest.mark.asyncio
    async def test_high_similarity_detection(self, mock_vector_store):
        """高相似度检测测试"""
        # 模拟搜索结果返回高相似度
        mock_vector_store.query = AsyncMock(return_value=[
            SearchResult(
                id="doc1",
                content="这是一段非常相似的文本内容。",
                metadata={"source": "论文A"},
                similarity=0.92,
            )
        ])
        
        checker = PlagiarismChecker(vector_store=mock_vector_store)
        result = await checker.check_similarity("这是一段需要检测的文本内容。")
        
        assert result.overall_similarity >= 0.0
        assert result.needs_reduction is True
        assert len(result.similar_pairs) > 0
        assert result.similar_pairs[0].similarity == 0.92
    
    @pytest.mark.asyncio
    async def test_medium_similarity_detection(self, mock_vector_store):
        """中等相似度检测测试"""
        mock_vector_store.query = AsyncMock(return_value=[
            SearchResult(
                id="doc1",
                content="这是一段中等相似度的文本。",
                metadata={"source": "论文B"},
                similarity=0.75,
            )
        ])
        
        checker = PlagiarismChecker(vector_store=mock_vector_store)
        result = await checker.check_similarity("这是一段需要检测的文本内容。")
        
        assert len(result.similar_pairs) > 0
        assert result.similar_pairs[0].is_medium is True
    
    @pytest.mark.asyncio
    async def test_low_similarity_not_recorded(self, mock_vector_store):
        """低相似度不应被记录"""
        mock_vector_store.query = AsyncMock(return_value=[
            SearchResult(
                id="doc1",
                content="完全不相关的文本。",
                metadata={"source": "其他来源"},
                similarity=0.50,
            )
        ])
        
        checker = PlagiarismChecker(vector_store=mock_vector_store)
        result = await checker.check_similarity("这是一段需要检测的文本内容。")
        
        # 低于中等阈值的不应被记录
        assert len(result.similar_pairs) == 0
        assert result.needs_reduction is False
    
    @pytest.mark.asyncio
    async def test_multiple_sentences(self, mock_vector_store):
        """多句子文本检测测试"""
        call_count = 0
        
        async def mock_query(query, k):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [SearchResult(
                    id="doc1",
                    content="第一句的相似内容。",
                    metadata={"source": "来源1"},
                    similarity=0.88,
                )]
            else:
                return [SearchResult(
                    id="doc2",
                    content="第二句的相似内容。",
                    metadata={"source": "来源2"},
                    similarity=0.72,
                )]
        
        mock_vector_store.query = mock_query
        
        checker = PlagiarismChecker(vector_store=mock_vector_store)
        text = "这是第一个需要检测的句子。这是第二个需要检测的句子。"
        result = await checker.check_similarity(text)
        
        assert len(result.similar_pairs) == 2
    
    def test_sentence_splitting(self, checker):
        """测试句子分割"""
        text = "第一句。第二句！第三句？Fourth sentence."
        sentences = checker._split_sentences(text)
        
        assert len(sentences) == 4
        assert "第一句" in sentences[0]
        assert "第二句" in sentences[1]
    
    def test_reduction_suggestions_generation(self, checker):
        """测试降重建议生成"""
        pairs = [
            SimilarPair(
                original_sentence="这是一个高相似度的句子。",
                matched_text="这是匹配的内容。",
                source="测试来源",
                similarity=0.92,
            ),
            SimilarPair(
                original_sentence="这是一个中等相似度的句子。",
                matched_text="这是另一个匹配。",
                source="另一个来源",
                similarity=0.75,
            ),
        ]
        
        suggestions = checker._generate_reduction_suggestions(pairs)
        
        assert len(suggestions) == 2
        # 高相似度应该建议改写
        assert suggestions[0].suggestion_type == "rephrase"
        # 中等相似度应该建议调整结构
        assert suggestions[1].suggestion_type == "restructure"
    
    @pytest.mark.asyncio
    async def test_search_error_handling(self, mock_vector_store):
        """搜索错误处理测试"""
        mock_vector_store.query = AsyncMock(side_effect=Exception("搜索失败"))
        
        checker = PlagiarismChecker(vector_store=mock_vector_store)
        result = await checker.check_similarity("这是需要检测的文本。")
        
        # 搜索失败应该返回空结果而不是抛出异常
        assert result.overall_similarity == 0.0
        assert result.similar_pairs == []


# ── 便捷函数测试 ─────────────────────────────────────────────────────────────

class TestConvenienceFunctions:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_check_plagiarism_function(self):
        """测试 check_plagiarism 便捷函数"""
        with patch('academic_agent_team.tools.plagiarism_checker.get_vector_store') as mock_get:
            mock_store = MagicMock()
            mock_store.query = AsyncMock(return_value=[])
            mock_get.return_value = mock_store
            
            result = await check_plagiarism("测试文本。")
            
            assert isinstance(result, SimilarityResult)
    
    def test_format_plagiarism_report_low_similarity(self):
        """测试低相似度报告格式化"""
        result = SimilarityResult(
            overall_similarity=0.30,
            similar_pairs=[],
            needs_reduction=False,
        )
        
        report = format_plagiarism_report(result)
        
        assert "查重检测报告" in report
        assert "30.0%" in report
        assert "🟢" in report
        assert "低相似度" in report
    
    def test_format_plagiarism_report_high_similarity(self):
        """测试高相似度报告格式化"""
        result = SimilarityResult(
            overall_similarity=0.90,
            similar_pairs=[
                SimilarPair(
                    original_sentence="原始句子。",
                    matched_text="匹配文本。",
                    source="论文来源",
                    similarity=0.90,
                )
            ],
            needs_reduction=True,
            reduction_suggestions=[
                ReductionSuggestion(
                    original="原始句子。",
                    suggestion_type="rephrase",
                    hint="建议改写",
                )
            ],
        )
        
        report = format_plagiarism_report(result)
        
        assert "90.0%" in report
        assert "🔴" in report
        assert "高相似度" in report
        assert "降重建议" in report
        assert "改写" in report


# ── 阈值测试 ─────────────────────────────────────────────────────────────────

class TestThresholds:
    """测试相似度阈值"""
    
    def test_high_threshold_value(self):
        """高阈值应为 0.85"""
        assert HIGH_SIMILARITY_THRESHOLD == 0.85
    
    def test_medium_threshold_value(self):
        """中等阈值应为 0.70"""
        assert MEDIUM_SIMILARITY_THRESHOLD == 0.70
    
    def test_custom_thresholds(self):
        """测试自定义阈值"""
        checker = PlagiarismChecker(
            high_threshold=0.90,
            medium_threshold=0.75,
        )
        
        assert checker.high_threshold == 0.90
        assert checker.medium_threshold == 0.75

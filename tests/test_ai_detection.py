"""
AI 检测工具测试。
"""

import asyncio
import os
import pytest

from academic_agent_team.tools.ai_detection import (
    AIDetector,
    AIDetectionResult,
    FlaggedSentence,
    RewriteSuggestion,
    detect_ai_content,
    format_detection_report,
)


# ── 测试数据 ─────────────────────────────────────────────────────────────────

SAMPLE_TEXT_ZH = """
值得注意的是，本研究采用了创新的方法论。首先，我们收集了大量数据。
其次，我们进行了深入的分析。综上所述，研究表明该方法具有显著优势。
此外，实验结果显示了良好的可重复性。
"""

SAMPLE_TEXT_EN = """
It is worth noting that this study employs an innovative methodology.
Furthermore, we collected extensive data for analysis.
Moreover, the experimental results demonstrate significant improvements.
In conclusion, our findings suggest promising applications.
"""

SAMPLE_TEXT_NORMAL = """
我们用Python写了一个程序。这个程序可以处理图片。运行速度还行。
"""


# ── Mock 模式测试 ────────────────────────────────────────────────────────────

class TestMockMode:
    """测试 Mock 模式。"""
    
    @pytest.fixture(autouse=True)
    def setup_mock_mode(self):
        """启用 Mock 模式。"""
        os.environ['AI_DETECT_MOCK'] = 'true'
        yield
        os.environ.pop('AI_DETECT_MOCK', None)
    
    @pytest.mark.asyncio
    async def test_mock_mode_enabled(self):
        """验证 Mock 模式已启用。"""
        detector = AIDetector()
        assert detector.is_mock_mode is True
    
    @pytest.mark.asyncio
    async def test_detect_returns_result(self):
        """检测应返回 AIDetectionResult。"""
        detector = AIDetector()
        result = await detector.detect(SAMPLE_TEXT_ZH)
        
        assert isinstance(result, AIDetectionResult)
        assert 0 <= result.ai_probability <= 1
        assert isinstance(result.flagged_sentences, list)
        assert isinstance(result.rewrite_suggestions, list)
    
    @pytest.mark.asyncio
    async def test_flagged_sentence_structure(self):
        """验证 FlaggedSentence 结构。"""
        detector = AIDetector()
        result = await detector.detect(SAMPLE_TEXT_ZH)
        
        for fs in result.flagged_sentences:
            assert isinstance(fs, FlaggedSentence)
            assert isinstance(fs.text, str)
            assert 0 <= fs.score <= 1
            assert isinstance(fs.position, tuple)
            assert len(fs.position) == 2
    
    @pytest.mark.asyncio
    async def test_rewrite_suggestion_structure(self):
        """验证 RewriteSuggestion 结构。"""
        detector = AIDetector()
        result = await detector.detect(SAMPLE_TEXT_ZH)
        
        for rs in result.rewrite_suggestions:
            assert isinstance(rs, RewriteSuggestion)
            assert isinstance(rs.original, str)
            assert isinstance(rs.suggestion, str)
            assert 0 <= rs.ai_score <= 1
    
    @pytest.mark.asyncio
    async def test_deterministic_mock_results(self):
        """相同输入应产生相同 Mock 结果。"""
        detector = AIDetector()
        result1 = await detector.detect(SAMPLE_TEXT_ZH)
        result2 = await detector.detect(SAMPLE_TEXT_ZH)
        
        assert result1.ai_probability == result2.ai_probability
        assert len(result1.flagged_sentences) == len(result2.flagged_sentences)
    
    @pytest.mark.asyncio
    async def test_ai_text_higher_probability(self):
        """AI 特征明显的文本应有更高的检测概率。"""
        detector = AIDetector()
        
        ai_result = await detector.detect(SAMPLE_TEXT_ZH)
        normal_result = await detector.detect(SAMPLE_TEXT_NORMAL)
        
        # AI 特征文本应有更高概率
        assert ai_result.ai_probability > normal_result.ai_probability
    
    @pytest.mark.asyncio
    async def test_english_text_detection(self):
        """测试英文文本检测。"""
        detector = AIDetector()
        result = await detector.detect(SAMPLE_TEXT_EN)
        
        assert isinstance(result, AIDetectionResult)
        assert result.ai_probability > 0.3  # 应检测到 AI 特征
        assert len(result.flagged_sentences) > 0


# ── 非 Mock 模式测试 ─────────────────────────────────────────────────────────

class TestNonMockMode:
    """测试非 Mock 模式（启发式检测）。"""
    
    @pytest.fixture(autouse=True)
    def disable_mock_mode(self):
        """禁用 Mock 模式。"""
        os.environ.pop('AI_DETECT_MOCK', None)
        yield
    
    @pytest.mark.asyncio
    async def test_mock_mode_disabled(self):
        """验证 Mock 模式已禁用。"""
        detector = AIDetector()
        assert detector.is_mock_mode is False
    
    @pytest.mark.asyncio
    async def test_heuristic_detection(self):
        """测试启发式检测。"""
        detector = AIDetector()
        result = await detector.detect(SAMPLE_TEXT_ZH)
        
        assert isinstance(result, AIDetectionResult)
        assert 0 <= result.ai_probability <= 1

    @pytest.mark.asyncio
    async def test_real_detect_uses_provider_score(self, monkeypatch):
        """有供应商分数时应采用保守融合（取最高值）。"""
        monkeypatch.setenv("ZEROGPT_API_KEY", "k")
        detector = AIDetector()
        detector.provider_mode = "zerogpt"

        async def fake_heuristic(_text):
            return AIDetectionResult(ai_probability=0.35, flagged_sentences=[], rewrite_suggestions=[])

        async def fake_zerogpt(_text):
            return 0.91

        monkeypatch.setattr(detector, "_heuristic_detect", fake_heuristic)
        monkeypatch.setattr(detector, "_detect_with_zerogpt", fake_zerogpt)

        result = await detector.detect(SAMPLE_TEXT_ZH)
        assert result.ai_probability == 0.91

    @pytest.mark.asyncio
    async def test_real_detect_falls_back_on_provider_error(self, monkeypatch):
        """供应商调用异常时应回退启发式结果。"""
        monkeypatch.setenv("ZEROGPT_API_KEY", "k")
        detector = AIDetector()
        detector.provider_mode = "zerogpt"

        async def fake_heuristic(_text):
            return AIDetectionResult(ai_probability=0.42, flagged_sentences=[], rewrite_suggestions=[])

        async def boom(_text):
            raise RuntimeError("api down")

        monkeypatch.setattr(detector, "_heuristic_detect", fake_heuristic)
        monkeypatch.setattr(detector, "_detect_with_zerogpt", boom)

        result = await detector.detect(SAMPLE_TEXT_ZH)
        assert result.ai_probability == 0.42


# ── 便捷函数测试 ─────────────────────────────────────────────────────────────

class TestConvenienceFunctions:
    """测试便捷函数。"""
    
    @pytest.fixture(autouse=True)
    def setup_mock_mode(self):
        """启用 Mock 模式。"""
        os.environ['AI_DETECT_MOCK'] = 'true'
        yield
        os.environ.pop('AI_DETECT_MOCK', None)
    
    @pytest.mark.asyncio
    async def test_detect_ai_content_function(self):
        """测试 detect_ai_content 便捷函数。"""
        result = await detect_ai_content(SAMPLE_TEXT_ZH)
        assert isinstance(result, AIDetectionResult)
    
    @pytest.mark.asyncio
    async def test_format_detection_report(self):
        """测试报告格式化。"""
        result = await detect_ai_content(SAMPLE_TEXT_ZH)
        report = format_detection_report(result)
        
        assert isinstance(report, str)
        assert "AI 内容检测报告" in report
        assert "总体 AI 概率" in report
        assert "%" in report


# ── 边界情况测试 ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    """测试边界情况。"""
    
    @pytest.fixture(autouse=True)
    def setup_mock_mode(self):
        os.environ['AI_DETECT_MOCK'] = 'true'
        yield
        os.environ.pop('AI_DETECT_MOCK', None)
    
    @pytest.mark.asyncio
    async def test_empty_text(self):
        """测试空文本。"""
        detector = AIDetector()
        result = await detector.detect("")
        
        assert result.ai_probability == 0.0
        assert result.flagged_sentences == []
        assert result.rewrite_suggestions == []
    
    @pytest.mark.asyncio
    async def test_single_sentence(self):
        """测试单句文本。"""
        detector = AIDetector()
        result = await detector.detect("这是一个简单的句子。")
        
        assert isinstance(result, AIDetectionResult)
    
    @pytest.mark.asyncio
    async def test_very_long_text(self):
        """测试长文本。"""
        detector = AIDetector()
        long_text = SAMPLE_TEXT_ZH * 10
        result = await detector.detect(long_text)
        
        assert isinstance(result, AIDetectionResult)
        # 改写建议应限制在5条以内
        assert len(result.rewrite_suggestions) <= 5


# ── 运行测试 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

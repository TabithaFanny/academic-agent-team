"""
AI 检测工具 — 检测文本的 AI 生成概率并提供改写建议。

功能：
  - detect(text): 异步检测文本的 AI 概率
  - 标记高概率 AI 生成的句子 (> 0.5)
  - 生成改写建议降低 AI 检测率

Mock 模式：
  设置环境变量 AI_DETECT_MOCK=true 启用 Mock 模式，
  用于测试时返回随机但合理的结果。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import random
import re
from dataclasses import dataclass
from typing import List

import httpx

logger = logging.getLogger(__name__)


# ── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass
class FlaggedSentence:
    """被标记的高 AI 概率句子。"""
    text: str                 # 句子文本
    score: float              # AI 概率分数 (0-1)
    position: tuple[int, int] # (start, end) 在原文中的位置


@dataclass
class RewriteSuggestion:
    """改写建议。"""
    original: str    # 原句
    suggestion: str  # 改写后的句子
    ai_score: float  # 改写后预估的 AI 分数


@dataclass
class AIDetectionResult:
    """AI 检测结果。"""
    ai_probability: float                        # 整体 AI 概率 (0-1)
    flagged_sentences: List[FlaggedSentence]     # 被标记的句子列表
    rewrite_suggestions: List[RewriteSuggestion] # 改写建议列表


# ── AI 检测器 ─────────────────────────────────────────────────────────────────

class AIDetector:
    """
    AI 内容检测器。
    
    支持 Mock 模式用于测试：设置环境变量 AI_DETECT_MOCK=true
    """
    
    # 常见 AI 生成文本的特征词/短语（用于启发式检测）
    AI_PATTERNS = [
        r'\b(值得注意的是|需要指出的是|综上所述|总而言之)\b',
        r'\b(It is worth noting|It should be noted|In conclusion|To summarize)\b',
        r'\b(此外|另外|与此同时|因此|从而|进而)\b',
        r'\b(Furthermore|Moreover|Additionally|Consequently|Therefore|Thus)\b',
        r'\b(研究表明|实验结果显示|数据表明)\b',
        r'\b(Studies have shown|Research indicates|Data suggests)\b',
        r'(首先|其次|最后|第一|第二|第三)',
        r'(Firstly|Secondly|Lastly|First|Second|Third)',
    ]
    
    # 改写模板 - 用于降低 AI 检测率
    REWRITE_TEMPLATES = {
        '值得注意的是': ['值得关注', '我们注意到', '有趣的是'],
        '需要指出的是': ['应当说明', '需要强调', '这里要说的是'],
        '综上所述': ['总的来看', '从以上分析来看', '概括来说'],
        'It is worth noting': ['We noticed that', 'Interestingly', 'Of note'],
        'Furthermore': ['Also', 'In addition', 'Beyond this'],
        'Moreover': ['What\'s more', 'Additionally', 'On top of that'],
        'In conclusion': ['To wrap up', 'In summary', 'All in all'],
    }
    
    def __init__(self, api_key: str | None = None):
        """
        初始化 AI 检测器。
        
        Args:
            api_key: API 密钥（Mock 模式下不需要）
        """
        self.api_key = api_key
        self._mock_mode = os.getenv('AI_DETECT_MOCK', '').lower() == 'true'
        self.zerogpt_api_key = os.getenv("ZEROGPT_API_KEY", api_key or "")
        self.gptzero_api_key = os.getenv("GPTZERO_API_KEY", api_key or "")
        self.zerogpt_api_url = os.getenv(
            "ZEROGPT_API_URL",
            "https://api.zerogpt.com/api/detectText",
        )
        self.gptzero_api_url = os.getenv(
            "GPTZERO_API_URL",
            "https://api.gptzero.me/v2/predict/text",
        )
        self.provider_mode = os.getenv("AI_DETECT_PROVIDER", "both").lower()
        self.timeout = float(os.getenv("AI_DETECT_TIMEOUT", "12"))
    
    @property
    def is_mock_mode(self) -> bool:
        """是否处于 Mock 模式。"""
        return self._mock_mode
    
    async def detect(self, text: str) -> AIDetectionResult:
        """
        检测文本的 AI 生成概率。
        
        Args:
            text: 待检测的文本
            
        Returns:
            AIDetectionResult 包含检测结果、标记句子和改写建议
        """
        if self._mock_mode:
            return await self._mock_detect(text)
        return await self._real_detect(text)
    
    async def _mock_detect(self, text: str) -> AIDetectionResult:
        """
        Mock 模式检测 — 返回基于文本特征的模拟结果。
        
        使用文本哈希确保相同输入返回一致结果。
        """
        # 模拟网络延迟
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 使用文本哈希生成可重复的随机种子
        text_hash = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = random.Random(text_hash)
        
        # 分割句子
        sentences = self._split_sentences(text)
        
        # 计算每个句子的 AI 分数
        flagged: List[FlaggedSentence] = []
        suggestions: List[RewriteSuggestion] = []
        total_score = 0.0
        current_pos = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                current_pos += 1
                continue
            
            # 基于特征词计算分数
            base_score = self._calculate_heuristic_score(sentence)
            # 添加随机波动
            noise = rng.uniform(-0.15, 0.15)
            score = max(0.0, min(1.0, base_score + noise))
            total_score += score
            
            # 找到句子在原文中的位置
            start = text.find(sentence, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(sentence)
            current_pos = end
            
            # 标记高概率句子
            if score > 0.5:
                flagged.append(FlaggedSentence(
                    text=sentence,
                    score=round(score, 3),
                    position=(start, end)
                ))
                
                # 生成改写建议
                rewritten = self._generate_rewrite(sentence, rng)
                if rewritten != sentence:
                    new_score = max(0.1, score - rng.uniform(0.2, 0.4))
                    suggestions.append(RewriteSuggestion(
                        original=sentence,
                        suggestion=rewritten,
                        ai_score=round(new_score, 3)
                    ))
        
        # 计算整体概率
        if sentences:
            ai_probability = total_score / len(sentences)
        else:
            ai_probability = 0.0
        
        # 根据整体概率调整
        if ai_probability > 0.7:
            ai_probability = min(1.0, ai_probability + rng.uniform(0, 0.1))
        
        return AIDetectionResult(
            ai_probability=round(ai_probability, 3),
            flagged_sentences=flagged,
            rewrite_suggestions=suggestions[:5]  # 最多返回5条建议
        )
    
    async def _real_detect(self, text: str) -> AIDetectionResult:
        """
        真实 API 检测。

        策略：
        1. 使用 ZeroGPT / GPTZero（按配置）获取整体概率
        2. 保留启发式分句标注和改写建议
        3. 若 API 不可用则自动降级为启发式
        """
        heuristic = await self._heuristic_detect(text)
        provider_scores: list[float] = []

        tasks = []
        if self.provider_mode in ("both", "zerogpt"):
            tasks.append(self._detect_with_zerogpt(text))
        if self.provider_mode in ("both", "gptzero"):
            tasks.append(self._detect_with_gptzero(text))

        if not tasks:
            return heuristic

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                logger.warning("AI 检测 API 调用失败，降级启发式: %s", res)
                continue
            if res is None:
                continue
            provider_scores.append(res)

        if not provider_scores:
            return heuristic

        # 保守策略：取最高值，避免漏检
        fused_probability = max([heuristic.ai_probability, *provider_scores])
        return AIDetectionResult(
            ai_probability=round(fused_probability, 3),
            flagged_sentences=heuristic.flagged_sentences,
            rewrite_suggestions=heuristic.rewrite_suggestions,
        )

    async def _detect_with_zerogpt(self, text: str) -> float | None:
        """调用 ZeroGPT API，返回 0-1 概率。"""
        if not self.zerogpt_api_key:
            return None

        headers = {
            "Authorization": f"Bearer {self.zerogpt_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input_text": text}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.zerogpt_api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return self._extract_probability(data)

    async def _detect_with_gptzero(self, text: str) -> float | None:
        """调用 GPTZero API，返回 0-1 概率。"""
        if not self.gptzero_api_key:
            return None

        headers = {
            "x-api-key": self.gptzero_api_key,
            "Content-Type": "application/json",
        }
        payload = {"document": text}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.gptzero_api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return self._extract_probability(data)

    def _extract_probability(self, data: object) -> float | None:
        """
        从不同供应商返回中提取 AI 概率（0-1）。
        支持常见字段并对 0-100 值自动归一化。
        """
        candidate_keys = {
            "ai_probability",
            "ai_score",
            "score",
            "generated_probability",
            "average_generated_prob",
            "completely_generated_prob",
            "fakePercentage",
            "average_generated",
        }

        def normalize(v: object) -> float | None:
            if isinstance(v, bool):
                return None
            if not isinstance(v, (int, float)):
                return None
            val = float(v)
            if 0.0 <= val <= 1.0:
                return val
            if 1.0 < val <= 100.0:
                return val / 100.0
            return None

        def visit(obj: object) -> list[float]:
            found: list[float] = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in candidate_keys:
                        n = normalize(v)
                        if n is not None:
                            found.append(n)
                    found.extend(visit(v))
            elif isinstance(obj, list):
                for item in obj:
                    found.extend(visit(item))
            return found

        values = visit(data)
        if not values:
            return None
        return max(values)
    
    async def _heuristic_detect(self, text: str) -> AIDetectionResult:
        """
        启发式检测 — 基于文本特征分析。
        
        用于无 API 时的降级检测。
        """
        sentences = self._split_sentences(text)
        flagged: List[FlaggedSentence] = []
        suggestions: List[RewriteSuggestion] = []
        total_score = 0.0
        current_pos = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                current_pos += 1
                continue
            
            score = self._calculate_heuristic_score(sentence)
            total_score += score
            
            start = text.find(sentence, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(sentence)
            current_pos = end
            
            if score > 0.5:
                flagged.append(FlaggedSentence(
                    text=sentence,
                    score=round(score, 3),
                    position=(start, end)
                ))
                
                rewritten = self._generate_rewrite(sentence)
                if rewritten != sentence:
                    new_score = max(0.1, score - 0.25)
                    suggestions.append(RewriteSuggestion(
                        original=sentence,
                        suggestion=rewritten,
                        ai_score=round(new_score, 3)
                    ))
        
        ai_probability = total_score / len(sentences) if sentences else 0.0
        
        return AIDetectionResult(
            ai_probability=round(ai_probability, 3),
            flagged_sentences=flagged,
            rewrite_suggestions=suggestions[:5]
        )
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割文本为句子列表。"""
        # 支持中英文标点
        pattern = r'(?<=[。！？.!?])\s*'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _calculate_heuristic_score(self, sentence: str) -> float:
        """
        基于启发式规则计算句子的 AI 概率分数。
        
        考虑因素：
        - AI 特征词/短语出现
        - 句子长度（AI 倾向于生成中等长度的句子）
        - 标点使用模式
        - 词汇多样性
        """
        score = 0.3  # 基础分数
        
        # 检测 AI 特征模式
        for pattern in self.AI_PATTERNS:
            if re.search(pattern, sentence, re.IGNORECASE):
                score += 0.15
        
        # 句子长度分析（AI 倾向于 50-150 字符）
        length = len(sentence)
        if 50 <= length <= 150:
            score += 0.1
        elif length > 200:
            score -= 0.1  # 过长句子 AI 特征减弱
        
        # 检测过度使用的连接词
        connectives = len(re.findall(r'[，,；;]', sentence))
        if connectives >= 3:
            score += 0.1
        
        # 检测列举模式
        if re.search(r'(第[一二三四五六七八九十]|[①②③④⑤]|[1-9][.、)])', sentence):
            score += 0.1
        
        return min(1.0, max(0.0, score))
    
    def _generate_rewrite(self, sentence: str, rng: random.Random | None = None) -> str:
        """
        生成改写建议，降低 AI 检测率。
        
        策略：
        - 替换 AI 特征词汇
        - 调整句式结构
        - 增加口语化表达
        """
        rewritten = sentence
        
        for original, replacements in self.REWRITE_TEMPLATES.items():
            if original in rewritten:
                if rng:
                    replacement = rng.choice(replacements)
                else:
                    replacement = replacements[0]
                rewritten = rewritten.replace(original, replacement, 1)
        
        return rewritten


# ── 便捷函数 ─────────────────────────────────────────────────────────────────

async def detect_ai_content(text: str, api_key: str | None = None) -> AIDetectionResult:
    """
    便捷函数：检测文本的 AI 生成概率。
    
    Args:
        text: 待检测的文本
        api_key: API 密钥（可选，Mock 模式下不需要）
        
    Returns:
        AIDetectionResult
    """
    detector = AIDetector(api_key=api_key)
    return await detector.detect(text)


def format_detection_report(result: AIDetectionResult) -> str:
    """
    格式化检测结果为可读报告。
    
    Args:
        result: AI 检测结果
        
    Returns:
        Markdown 格式的报告
    """
    lines = [
        "# AI 内容检测报告",
        "",
        f"## 总体 AI 概率: {result.ai_probability * 100:.1f}%",
        "",
    ]
    
    # 风险等级
    if result.ai_probability < 0.3:
        risk = "🟢 低风险"
    elif result.ai_probability < 0.6:
        risk = "🟡 中等风险"
    else:
        risk = "🔴 高风险"
    lines.append(f"**风险等级**: {risk}")
    lines.append("")
    
    # 标记的句子
    if result.flagged_sentences:
        lines.append("## 🚩 标记的高风险句子")
        lines.append("")
        for i, fs in enumerate(result.flagged_sentences, 1):
            lines.append(f"{i}. (AI 概率: {fs.score * 100:.1f}%)")
            lines.append(f"   > {fs.text}")
            lines.append("")
    else:
        lines.append("## ✅ 未发现高风险句子")
        lines.append("")
    
    # 改写建议
    if result.rewrite_suggestions:
        lines.append("## ✏️ 改写建议")
        lines.append("")
        for i, rs in enumerate(result.rewrite_suggestions, 1):
            lines.append(f"### 建议 {i}")
            lines.append(f"- **原句**: {rs.original}")
            lines.append(f"- **建议**: {rs.suggestion}")
            lines.append(f"- **预估降低至**: {rs.ai_score * 100:.1f}%")
            lines.append("")
    
    return "\n".join(lines)

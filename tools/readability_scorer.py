#!/usr/bin/env python3
"""
readability_scorer.py
中文学术文本可读性量化评分工具（对应 PRD Prompt #34）

用法：
    python readability_scorer.py input.txt
    python readability_scorer.py --text "要分析的段落文字"

输出：量化指标报告 + diff 标注位置
"""

import re
import sys
import argparse
import statistics
from collections import Counter
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# 1. 套话词库（持续维护，可外部扩展）
# ─────────────────────────────────────────────

CLICHE_PATTERNS_A = [
    # 结构类套话
    r"随着.{1,10}的.{0,4}(深入|不断|持续|快速)(发展|推进|推广|普及|演进)",
    r"不仅如此",
    r"值得注意的是",
    r"首先.{0,50}其次.{0,50}(再次|然后|最后)",
    r"综上所述",
    r"由此可见",
    r"不难发现",
    r"毋庸置疑",
    r"不言而喻",
    r"众所周知",
    r"总而言之",
    r"简言之",
]

CLICHE_PATTERNS_B = [
    # 表达类套话
    r"具有重要(意义|价值|作用)",
    r"发挥(着|了)重要作用",
    r"日益凸显",
    r"亟(需|待)",
    r"有效推进",
    r"深入推进",
    r"全面提升",
    r"显著提高",
    r"大力推进",
    r"积极探索",
    r"切实加强",
    r"稳步推进",
    r"持续优化",
]

CONNECTIVE_WORDS = [
    "因此", "然而", "此外", "同时", "由于", "从而", "进而",
    "但是", "而且", "并且", "不过", "尽管", "虽然", "即使",
    "对此", "为此", "基于此", "综上", "另外", "相比之下",
    "与此同时", "在此基础上", "从这一角度来看",
]


# ─────────────────────────────────────────────
# 2. 数据结构
# ─────────────────────────────────────────────

@dataclass
class ScoreResult:
    # 原始统计
    total_chars: int = 0
    total_sentences: int = 0
    cliche_hits: list = field(default_factory=list)      # [(pattern, match, position)]
    connective_count: int = 0
    sentence_lengths: list = field(default_factory=list)
    paragraph_lengths: list = field(default_factory=list)

    # 衍生指标
    cliche_rate: float = 0.0           # 重复套话率（%）
    diversity_index: float = 0.0       # 句式多样性指数（0-1）
    connective_density: float = 0.0    # 连接词密度（%）
    paragraph_std: float = 0.0         # 段落长度标准差

    # 综合评分
    readability_score: float = 0.0     # 1-5 分


# ─────────────────────────────────────────────
# 3. 分析器
# ─────────────────────────────────────────────

def split_sentences(text: str) -> list[str]:
    """按中文句末标点切分句子"""
    sentences = re.split(r'[。！？!?]', text)
    return [s.strip() for s in sentences if len(s.strip()) >= 4]


def split_paragraphs(text: str) -> list[str]:
    """按换行切分段落"""
    paras = re.split(r'\n\s*\n|\n', text)
    return [p.strip() for p in paras if len(p.strip()) >= 10]


def detect_cliches(text: str) -> list[tuple]:
    """检测套话，返回 (label, matched_text, char_position)"""
    hits = []
    all_patterns = (
        [(p, "结构类") for p in CLICHE_PATTERNS_A] +
        [(p, "表达类") for p in CLICHE_PATTERNS_B]
    )
    for pattern, label in all_patterns:
        for m in re.finditer(pattern, text):
            hits.append((label, m.group(), m.start()))
    # 按位置排序
    hits.sort(key=lambda x: x[2])
    return hits


def count_connectives(text: str) -> tuple[int, list[str]]:
    """统计连接词出现次数"""
    found = []
    for word in CONNECTIVE_WORDS:
        count = text.count(word)
        if count > 0:
            found.extend([word] * count)
    return len(found), found


def sentence_diversity_index(sentences: list[str]) -> float:
    """
    句式多样性指数 = 1 - (最高频句型比例)
    句型按字数分档：短(<15) / 中(15-40) / 长(>40)
    """
    if not sentences:
        return 0.0
    buckets = {"short": 0, "medium": 0, "long": 0}
    for s in sentences:
        n = len(s)
        if n < 15:
            buckets["short"] += 1
        elif n <= 40:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total = len(sentences)
    max_ratio = max(v / total for v in buckets.values())
    return round(1 - max_ratio, 3)


def compute_readability(result: ScoreResult) -> float:
    """
    综合可读性评分（1-5）
    = (1 - 套话率×10) × 0.35
    + 句式多样性指数    × 0.30
    + (1 - 连接词密度×5) × 0.20
    + 段落均匀度惩罚项  × 0.15
    """
    cliche_component = max(0, 1 - result.cliche_rate / 100 * 10) * 0.35
    diversity_component = result.diversity_index * 0.30
    connective_component = max(0, 1 - result.connective_density / 100 * 5) * 0.20

    # 段落均匀度：std < 30 → 满分，std > 100 → 0分
    std = result.paragraph_std
    para_component = max(0, 1 - (std - 30) / 70) * 0.15 if std > 30 else 0.15

    raw = cliche_component + diversity_component + connective_component + para_component
    return round(raw * 5, 2)   # 映射到 1-5，最低按 1 封底


def analyze(text: str) -> ScoreResult:
    result = ScoreResult()

    # 基础统计
    result.total_chars = len(re.sub(r'\s', '', text))
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)
    result.total_sentences = len(sentences)
    result.sentence_lengths = [len(s) for s in sentences]
    result.paragraph_lengths = [len(p) for p in paragraphs]

    # 套话
    result.cliche_hits = detect_cliches(text)
    cliche_chars = sum(len(h[1]) for h in result.cliche_hits)
    result.cliche_rate = round(cliche_chars / max(result.total_chars, 1) * 100, 2)

    # 连接词密度
    result.connective_count, _ = count_connectives(text)
    result.connective_density = round(
        result.connective_count / max(len(sentences), 1) * 100, 2
    )

    # 多样性
    result.diversity_index = sentence_diversity_index(sentences)

    # 段落标准差
    if len(result.paragraph_lengths) >= 2:
        result.paragraph_std = round(statistics.stdev(result.paragraph_lengths), 1)
    else:
        result.paragraph_std = 0.0

    # 综合分
    result.readability_score = max(1.0, compute_readability(result))

    return result


# ─────────────────────────────────────────────
# 4. 报告生成
# ─────────────────────────────────────────────

def status_icon(value, good, warn):
    """根据阈值返回状态图标"""
    if value <= good:
        return "✅"
    elif value <= warn:
        return "⚠️"
    return "❌"


def score_icon(score):
    if score >= 4.0:
        return "✅"
    elif score >= 3.0:
        return "⚠️"
    return "❌"


def build_report(text: str, result: ScoreResult) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  中文学术文本可读性分析报告 (Prompt #34)")
    lines.append("=" * 60)

    lines.append("\n## 量化指标")
    lines.append(f"{'指标':<18} {'当前值':>8} {'目标值':>8} {'状态':>4}")
    lines.append("-" * 44)

    cr_icon = status_icon(result.cliche_rate, 5, 10)
    lines.append(f"{'重复套话率':<16} {result.cliche_rate:>7.1f}% {'<5%':>8} {cr_icon}")

    di_icon = "✅" if result.diversity_index >= 0.65 else ("⚠️" if result.diversity_index >= 0.45 else "❌")
    lines.append(f"{'句式多样性指数':<14} {result.diversity_index:>8.3f} {'>0.65':>8} {di_icon}")

    ps_icon = status_icon(result.paragraph_std, 30, 60)
    lines.append(f"{'段落均匀度标准差':<12} {result.paragraph_std:>7.1f}字 {'<30字':>8} {ps_icon}")

    cd_icon = status_icon(result.connective_density, 8, 15)
    lines.append(f"{'连接词密度':<16} {result.connective_density:>7.1f}% {'<8%':>8} {cd_icon}")

    si = score_icon(result.readability_score)
    lines.append("-" * 44)
    lines.append(f"{'可读性综合评分':<14} {result.readability_score:>7.1f}/5 {'>4.0':>8} {si}")

    lines.append(f"\n  总字数：{result.total_chars}  总句数：{result.total_sentences}"
                 f"  段落数：{len(result.paragraph_lengths)}")

    # ── 套话明细 ──
    lines.append("\n## 检测到的具体问题")

    if result.cliche_hits:
        lines.append("\n### 套话 / 高频模板词（建议修改）")
        counter = Counter((h[0], h[1]) for h in result.cliche_hits)
        for (label, phrase), cnt in counter.most_common():
            # 找出在文中的位置
            positions = [
                _char_to_approx_line(text, h[2])
                for h in result.cliche_hits if h[1] == phrase
            ]
            pos_str = "、".join(f"第{p}行附近" for p in positions[:3])
            lines.append(f"  🔴 [{label}] 「{phrase}」× {cnt}次 → {pos_str}")
    else:
        lines.append("\n### 套话检测：未发现明显套话 ✅")

    # ── 修改优先级 ──
    lines.append("\n## 修改优先级")

    must_fix = []
    suggest_fix = []

    if result.cliche_rate > 5:
        must_fix.append(f"套话率 {result.cliche_rate}% 超标 → 逐一替换上方红色标注词组")
    if result.diversity_index < 0.45:
        must_fix.append("句式单调，连续多句长度相似 → 拆分长句或合并短句")
    if result.connective_density > 15:
        must_fix.append(f"连接词堆叠（密度 {result.connective_density}%）→ 删除“因此/此外/同时”等多余衔接词")

    if 5 <= result.cliche_rate <= 10:
        suggest_fix.append("套话率略高，建议替换其中出现≥2次的词组")
    if result.paragraph_std > 30:
        suggest_fix.append(f"段落长度不均（标准差 {result.paragraph_std}字）→ 适当拆分超长段落")
    if 8 <= result.connective_density <= 15:
        suggest_fix.append("连接词偏多，可削减 1/3 的“然而/此外”类词")

    if must_fix:
        lines.append("🔴 必须改：")
        for item in must_fix:
            lines.append(f"   - {item}")
    if suggest_fix:
        lines.append("🟡 建议改：")
        for item in suggest_fix:
            lines.append(f"   - {item}")
    if not must_fix and not suggest_fix:
        lines.append("🟢 文本质量良好，无须强制修改。")

    lines.append("\n" + "=" * 60)
    lines.append("⚠️  本工具仅做统计分析，最终修改决策请人工判断。")
    lines.append("=" * 60)

    return "\n".join(lines)


def _char_to_approx_line(text: str, char_pos: int) -> int:
    """将字符位置转换为近似行号"""
    return text[:char_pos].count('\n') + 1


# ─────────────────────────────────────────────
# 5. CLI 入口
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="中文学术文本可读性量化评分工具 (Prompt #34)"
    )
    parser.add_argument("file", nargs="?", help="输入文本文件路径")
    parser.add_argument("--text", help="直接传入文本字符串")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出指标")
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"错误：找不到文件 {args.file}", file=sys.stderr)
            sys.exit(1)
    else:
        print("用法：python readability_scorer.py <文件路径>")
        print("   或：python readability_scorer.py --text '要分析的文字'")
        sys.exit(0)

    result = analyze(text)

    if args.json:
        import json
        print(json.dumps({
            "total_chars": result.total_chars,
            "total_sentences": result.total_sentences,
            "cliche_rate_pct": result.cliche_rate,
            "diversity_index": result.diversity_index,
            "connective_density_pct": result.connective_density,
            "paragraph_std": result.paragraph_std,
            "readability_score": result.readability_score,
            "cliche_hits": [(h[0], h[1], h[2]) for h in result.cliche_hits],
        }, ensure_ascii=False, indent=2))
    else:
        print(build_report(text, result))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""PaperGenius Pro - 最小可运行 Demo

使用方法:
    python demo.py "人工智能对新闻传播伦理的影响"
    python demo.py "人工智能对新闻传播伦理的影响" --mode express
"""

import asyncio
import os
import sys
from pathlib import Path

# 启用 Mock 模式（无需真实 API）
os.environ['AI_DETECT_MOCK'] = 'true'
os.environ['CNKI_MOCK'] = 'true'


def print_banner():
    """打印 Banner。"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    📚 PaperGenius Pro                        ║
║              AI 辅助学术论文写作系统 v1.0                     ║
║                                                              ║
║  支持模式:                                                   ║
║    • 标准模式 (standard): 4 个人工干预点，30-60 分钟         ║
║    • 极速模式 (express): 2 个干预点，10-15 分钟              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def simulate_phase_1(topic: str) -> list[str]:
    """Phase 1: 选题讨论 - Advisor 生成聚焦方向。"""
    print("\n" + "="*60)
    print("📌 Phase 1: 选题讨论")
    print("="*60)
    
    # 模拟 Advisor Agent 输出
    directions = [
        f"【方向 A】{topic}的理论框架构建",
        f"【方向 B】{topic}的实证研究：以主流媒体为例",
        f"【方向 C】{topic}：国际比较与本土化路径",
    ]
    
    print(f"\n🎯 研究主题: {topic}")
    print("\n💡 Advisor 建议的聚焦方向:\n")
    for i, d in enumerate(directions, 1):
        print(f"  {i}. {d}")
    
    return directions


def human_intervention_h1(directions: list[str], auto_select: bool = False) -> str:
    """H1 干预点: 用户选择研究方向。"""
    print("\n" + "-"*40)
    print("🔔 [H1 干预点] 请选择研究方向")
    print("-"*40)
    
    if auto_select:
        print("(极速模式: 自动选择方向 1)")
        return directions[0]
    
    while True:
        try:
            choice = input("\n请输入方向编号 (1-3): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(directions):
                selected = directions[idx]
                print(f"\n✅ 已选择: {selected}")
                return selected
        except (ValueError, IndexError):
            pass
        print("❌ 无效输入，请重试")


def simulate_phase_2(direction: str) -> dict:
    """Phase 2: 文献调研 - CNKI + 国际文献搜索。"""
    print("\n" + "="*60)
    print("📚 Phase 2: 文献调研")
    print("="*60)
    
    print("\n🔍 正在搜索 CNKI 中文文献...")
    cnki_papers = [
        {"title": "人工智能时代新闻传播伦理的挑战与应对", "source": "cnki", "year": 2023},
        {"title": "算法推荐与新闻伦理：技术理性批判", "source": "cnki", "year": 2024},
        {"title": "深度伪造技术的传播伦理问题研究", "source": "cnki", "year": 2023},
    ]
    print(f"  ✓ 找到 {len(cnki_papers)} 篇 CNKI 文献")
    
    print("\n🔍 正在搜索国际文献 (Semantic Scholar)...")
    intl_papers = [
        {"title": "AI Ethics in Journalism: A Systematic Review", "source": "semanticscholar", "year": 2024},
        {"title": "The Impact of Generative AI on Media Ethics", "source": "arxiv", "year": 2024},
    ]
    print(f"  ✓ 找到 {len(intl_papers)} 篇国际文献")
    
    all_papers = cnki_papers + intl_papers
    total = len(all_papers)
    
    # 文献质量门检查
    print(f"\n📊 文献统计: 共 {total} 篇")
    if total < 30:
        print(f"  ⚠️ 警告: 文献数量 ({total}) 低于推荐值 (30)")
        print("  💡 建议: 扩大搜索范围或放宽关键词")
    else:
        print(f"  ✅ 文献数量充足")
    
    return {
        "papers": all_papers,
        "cnki_count": len(cnki_papers),
        "intl_count": len(intl_papers),
    }


def simulate_phase_3(direction: str) -> dict:
    """Phase 3: 写作-审稿循环。"""
    print("\n" + "="*60)
    print("✍️ Phase 3: 写作-审稿循环")
    print("="*60)
    
    max_rounds = 5
    target_score = 85
    
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- 第 {round_num} 轮 ---")
        
        # 模拟 Writer 生成
        print("📝 Writer Agent 正在生成稿件...")
        
        # 模拟 Reviewer 打分
        if round_num == 1:
            score = 72
        elif round_num == 2:
            score = 81
        else:
            score = 88
        
        print(f"📋 Reviewer Agent 评分: {score}/100")
        
        if score >= target_score:
            print(f"\n✅ 达到质量门标准 (≥{target_score})，进入下一阶段")
            return {"score": score, "rounds": round_num}
        else:
            print(f"   ↩️ 低于 {target_score} 分，继续迭代...")
    
    print(f"\n⚠️ 达到最大迭代次数 ({max_rounds})，强制进入下一阶段")
    return {"score": score, "rounds": max_rounds}


def simulate_phase_4() -> dict:
    """Phase 4: 润色终审。"""
    print("\n" + "="*60)
    print("💎 Phase 4: 润色终审")
    print("="*60)
    
    print("\n🔧 Polisher Agent 正在润色...")
    print("  • 语言流畅性优化")
    print("  • 学术规范检查")
    print("  • 格式统一调整")
    
    print("\n🔍 执行 AI 检测...")
    ai_score = 28  # 模拟
    print(f"  AI 生成概率: {ai_score}% (目标 < 30%)")
    
    print("\n🔍 执行查重检测...")
    similarity = 15  # 模拟
    print(f"  相似度: {similarity}% (目标 < 20%)")
    
    return {
        "ai_score": ai_score,
        "similarity": similarity,
        "passed": ai_score < 30 and similarity < 20,
    }


def human_intervention_h4(phase4_result: dict) -> bool:
    """H4 干预点: 最终预览确认。"""
    print("\n" + "-"*40)
    print("🔔 [H4 干预点] 最终预览确认")
    print("-"*40)
    
    print("\n📄 论文预览:")
    print("  标题: 人工智能对新闻传播伦理的影响：理论框架构建")
    print("  字数: 约 8,000 字")
    print("  章节: 引言 / 文献综述 / 研究方法 / 结果分析 / 结论")
    
    print(f"\n✅ AI 检测: {phase4_result['ai_score']}%")
    print(f"✅ 查重率: {phase4_result['similarity']}%")
    
    confirm = input("\n确认导出? (y/n): ").strip().lower()
    return confirm in ('y', 'yes', '')


def simulate_phase_5(topic: str) -> Path:
    """Phase 5: 导出。"""
    print("\n" + "="*60)
    print("📦 Phase 5: 导出论文包")
    print("="*60)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # 生成文件
    files = []
    
    # 1. LaTeX 文件
    tex_path = output_dir / "paper.tex"
    tex_path.write_text(f"% PaperGenius Pro 生成\n% 主题: {topic}\n\\documentclass{{article}}\n...", encoding='utf-8')
    files.append(tex_path)
    print(f"  ✓ {tex_path}")
    
    # 2. BibTeX 文件
    bib_path = output_dir / "references.bib"
    bib_path.write_text("@article{ref1, title={示例引用}}", encoding='utf-8')
    files.append(bib_path)
    print(f"  ✓ {bib_path}")
    
    # 3. AI 声明
    disclosure_path = output_dir / "AI_DISCLOSURE.md"
    disclosure_path.write_text("""# AI 辅助声明

本论文在撰写过程中使用了 AI 辅助工具 (PaperGenius Pro)，具体包括：
- 文献检索与整理
- 初稿生成
- 语言润色

所有核心观点、研究设计和结论均由作者独立完成并审核。
""", encoding='utf-8')
    files.append(disclosure_path)
    print(f"  ✓ {disclosure_path}")
    
    # 4. 人工修改指南
    guide_path = output_dir / "HUMAN_EDIT_GUIDE.md"
    guide_path.write_text("""# 人工修改建议

## 需重点关注的段落
1. 引言第 2 段 - 建议增加研究背景说明
2. 结论部分 - 需要补充实践建议

## 引用核查
- 请核实参考文献 [3] 的 DOI 链接
- 建议补充 2-3 篇 2024 年最新文献

## 格式检查
- 确认参考文献格式符合目标期刊要求
- 检查图表编号是否连续
""", encoding='utf-8')
    files.append(guide_path)
    print(f"  ✓ {guide_path}")
    
    print(f"\n📁 输出目录: {output_dir.absolute()}")
    return output_dir


def run_demo(topic: str, mode: str = "standard"):
    """运行完整 Demo。"""
    print_banner()
    print(f"\n🚀 启动模式: {'标准模式' if mode == 'standard' else '极速模式'}")
    print(f"📝 研究主题: {topic}")
    
    auto_select = (mode == "express")
    
    # Phase 1: 选题
    directions = simulate_phase_1(topic)
    selected = human_intervention_h1(directions, auto_select=auto_select)
    
    # Phase 2: 文献调研
    lit_result = simulate_phase_2(selected)
    
    # Phase 3: 写作-审稿
    write_result = simulate_phase_3(selected)
    
    # Phase 4: 润色终审
    polish_result = simulate_phase_4()
    
    # H4: 最终确认
    if auto_select or human_intervention_h4(polish_result):
        # Phase 5: 导出
        output_dir = simulate_phase_5(topic)
        
        print("\n" + "="*60)
        print("🎉 论文生成完成！")
        print("="*60)
        print(f"\n📊 最终统计:")
        print(f"  • 文献数量: {lit_result['cnki_count']} CNKI + {lit_result['intl_count']} 国际")
        print(f"  • 写作迭代: {write_result['rounds']} 轮")
        print(f"  • Reviewer 评分: {write_result['score']}/100")
        print(f"  • AI 检测: {polish_result['ai_score']}%")
        print(f"  • 查重率: {polish_result['similarity']}%")
        print(f"\n📁 请在 {output_dir.absolute()} 查看输出文件")
        print("\n⚠️ 重要提示: 请务必进行人工审核后再投稿！")
    else:
        print("\n❌ 用户取消导出")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PaperGenius Pro Demo")
    parser.add_argument("topic", nargs="?", default="人工智能对新闻传播伦理的影响",
                        help="研究主题")
    parser.add_argument("--mode", choices=["standard", "express"], default="standard",
                        help="运行模式 (standard/express)")
    
    args = parser.parse_args()
    run_demo(args.topic, args.mode)

import asyncio
import importlib
import sqlite3

import pytest

from academic_agent_team.core.base_client import ModelResponse
from academic_agent_team.pipeline_v2 import PipelineOrchestrator, run_pipeline
from academic_agent_team.storage.db import get_session_summary


def test_run_pipeline_v2_persists_session(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_TEAM_LLM_MOCK", "true")
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    context = asyncio.run(
        run_pipeline(
            base_dir=tmp_path,
            topic="v2 持久化测试",
            journal="中文核心",
            run_mode="express",
        )
    )

    db_path = tmp_path / "session_store" / "sessions.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    summary = get_session_summary(conn, context.session_id)
    conn.close()

    assert summary["status"] == "completed"
    assert summary["stage"] == "export"
    assert summary["run_mode"] == "autopilot"
    assert summary["artifact_count"] >= 6
    assert summary["message_count"] >= 6
    assert summary["total_cost_cny"] == 0.0


def test_run_pipeline_v2_blocks_when_literature_gate_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_TEAM_LLM_MOCK", "true")
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    async def _small_cnki_result(*args, **kwargs):
        del args, kwargs
        from academic_agent_team.tools.search_cnki import (
            CNKIPaper,
            CNKISearchResult,
            SourceType,
        )

        papers = [
            CNKIPaper(
                title=f"测试文献{i}",
                authors=["张三"],
                journal="新闻与传播研究",
                year=2024,
                cnki_url=f"https://kns.cnki.net/kcms2/article/abstract?v=mock_{i}",
                source_type=SourceType.CSSCI,
                doi=f"10.1234/mock.{i}",
            )
            for i in range(5)
        ]
        return CNKISearchResult(
            papers=papers,
            total_found=len(papers),
            query="q",
            search_type="主题",
        )

    search_cnki_module = importlib.import_module("academic_agent_team.tools.search_cnki")
    monkeypatch.setattr(search_cnki_module, "search_cnki", _small_cnki_result)

    with pytest.raises(RuntimeError, match="文献质量 Gate 失败"):
        asyncio.run(
            run_pipeline(
                base_dir=tmp_path,
                topic="v2 文献门禁失败测试",
                journal="中文核心",
                run_mode="express",
            )
        )


def test_run_pipeline_v2_uses_llm_outputs_and_persists_cost(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_TEAM_LLM_MOCK", "true")
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    async def _fake_llm_complete(self, role, prompt, system, max_tokens=4096, use_mock=False):
        del self, prompt, system, max_tokens, use_mock
        payload_by_role = {
            "advisor": """{
                "selected_direction": "平台治理与内容可信度协同机制",
                "alternative_directions": ["平台审核机制比较研究", "生成式 AI 风险传播链条"],
                "direction_analysis": {
                    "innovation_score": 8.8,
                    "feasibility": "high",
                    "research_gap": "缺少治理协同视角",
                    "recommended_keywords": ["平台治理", "内容可信度", "协同机制"]
                }
            }""",
            "writer": """{
                "sections": {
                    "abstract": "这是测试摘要",
                    "introduction": "这是测试引言",
                    "literature_review": "这是测试文献综述",
                    "methodology": "这是测试方法",
                    "results": "这是测试结果",
                    "discussion": "这是测试讨论",
                    "conclusion": "这是测试结论"
                },
                "word_count": 4567
            }""",
            "reviewer": """{
                "verdict": "accept",
                "overall_score": 9.2,
                "major_issues": [],
                "minor_issues": []
            }""",
            "polisher": """{
                "polished_sections": {
                    "abstract": "润色后摘要",
                    "introduction": "润色后引言",
                    "literature_review": "润色后综述",
                    "methodology": "润色后方法",
                    "results": "润色后结果",
                    "discussion": "润色后讨论",
                    "conclusion": "润色后结论"
                },
                "readability_before": 2.8,
                "readability_after": 4.3,
                "diff_report": "完成润色"
            }""",
        }
        cost_by_role = {"advisor": 0.05, "writer": 0.12, "reviewer": 0.08, "polisher": 0.06}
        return ModelResponse(
            content=payload_by_role[role],
            input_tokens=123,
            output_tokens=456,
            cost_cny=cost_by_role[role],
            model_id=f"unit/{role}",
            latency_ms=10,
        )

    pipeline_v2_module = importlib.import_module("academic_agent_team.pipeline_v2")
    monkeypatch.setattr(pipeline_v2_module.PipelineOrchestrator, "_llm_complete", _fake_llm_complete)

    context = asyncio.run(
        run_pipeline(
            base_dir=tmp_path,
            topic="v2 LLM 输出落库测试",
            journal="中文核心",
            run_mode="express",
        )
    )

    assert context.writing_done["sections"]["abstract"] == "这是测试摘要"
    assert context.reviewer_score == 92.0
    assert context.polish_done["polished_sections"]["abstract"] == "润色后摘要"

    conn = sqlite3.connect(tmp_path / "session_store" / "sessions.db")
    summary = get_session_summary(conn, context.session_id)
    cost_rows = conn.execute(
        """
        SELECT stage, agent, model_id, input_tokens, output_tokens, cost_cny
        FROM cost_log
        WHERE session_id = ?
          AND stage IN ('writing_done', 'review_done', 'polish_done')
        ORDER BY stage
        """,
        (context.session_id,),
    ).fetchall()
    conn.close()

    assert len(cost_rows) == 3
    assert all(r[2].startswith("unit/") for r in cost_rows)
    assert all(r[3] == 123 and r[4] == 456 for r in cost_rows)
    assert summary["total_cost_cny"] > 0.25


def test_run_pipeline_v2_llm_json_fallbacks(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_TEAM_LLM_MOCK", "true")
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    async def _invalid_llm_complete(self, role, prompt, system, max_tokens=4096, use_mock=False):
        del self, prompt, system, max_tokens, use_mock
        payload = {
            "advisor": "```json\ninvalid\n```",
            "writer": "这不是 JSON，只有纯文本草稿",
            "reviewer": "```json\ninvalid\n```",
            "polisher": "[]",
        }[role]
        return ModelResponse(
            content=payload,
            input_tokens=1,
            output_tokens=1,
            cost_cny=0.0,
            model_id="unit/invalid",
            latency_ms=5,
        )

    pipeline_v2_module = importlib.import_module("academic_agent_team.pipeline_v2")
    monkeypatch.setattr(pipeline_v2_module.PipelineOrchestrator, "_llm_complete", _invalid_llm_complete)

    context = asyncio.run(
        run_pipeline(
            base_dir=tmp_path,
            topic="v2 JSON 兜底测试",
            journal="中文核心",
            run_mode="express",
        )
    )

    assert isinstance(context.writing_done["sections"], dict)
    assert context.writing_done["sections"]["abstract"]
    assert context.review_done["verdict"] == "minor_revision"
    assert context.review_done["overall_score"] == 85.0
    assert context.polish_done["polished_sections"] == context.writing_done["sections"]


def test_run_pipeline_v2_executes_data_analysis_phase(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_TEAM_LLM_MOCK", "true")
    monkeypatch.setenv("AI_DETECT_MOCK", "true")
    monkeypatch.setenv("CNKI_MOCK", "true")
    monkeypatch.setenv("CITATION_MOCK", "true")

    data_file = tmp_path / "sample.csv"
    data_file.write_text(
        "user_id,score,group\n1,85,A\n2,91,A\n3,77,B\n4,88,B\n",
        encoding="utf-8",
    )

    async def _fake_llm_complete(self, role, prompt, system, max_tokens=4096, use_mock=False):
        del self, prompt, system, max_tokens, use_mock
        payload_by_role = {
            "advisor": """{"selected_direction":"数据驱动的治理绩效评估"}""",
            "data_analyst": """{
                "analysis_type": "descriptive",
                "interpretation": "A组均值略高于B组，整体分布稳定。",
                "key_findings": ["样本量4", "分数组均值在80以上"],
                "statistics_results": {"mean_score": 85.25},
                "figures": [{"path":"output/fig1.png","caption":"分组均值","type":"bar"}]
            }""",
            "writer": """{"sections":{"abstract":"摘要"}}""",
            "reviewer": """{"verdict":"accept","overall_score":9.0}""",
            "polisher": """{"polished_sections":{"abstract":"润色摘要"}}""",
        }
        return ModelResponse(
            content=payload_by_role[role],
            input_tokens=50,
            output_tokens=50,
            cost_cny=0.01,
            model_id=f"unit/{role}",
            latency_ms=5,
        )

    pipeline_v2_module = importlib.import_module("academic_agent_team.pipeline_v2")
    monkeypatch.setattr(pipeline_v2_module.PipelineOrchestrator, "_llm_complete", _fake_llm_complete)

    context = asyncio.run(
        run_pipeline(
            base_dir=tmp_path,
            topic="v2 数据分析阶段测试",
            journal="中文核心",
            run_mode="express",
            data_file=data_file,
        )
    )

    assert context.analysis_done is not None
    assert context.analysis_done["analysis_type"] == "descriptive"
    assert context.analysis_done["statistics_results"]["mean_score"] == 85.25
    assert context.analysis_done["statistics_results"]["data_profile"]["column_count"] == 3

    conn = sqlite3.connect(tmp_path / "session_store" / "sessions.db")
    rows = conn.execute(
        """
        SELECT model_id, cost_cny
        FROM cost_log
        WHERE session_id = ? AND stage = 'analysis_done'
        """,
        (context.session_id,),
    ).fetchall()
    conn.close()
    assert rows and rows[0][0] == "unit/data_analyst"


def test_review_gate_requires_score_threshold(tmp_path):
    orchestrator = PipelineOrchestrator(base_dir=tmp_path)
    assert orchestrator._review_passed("accept", 85.0) is True
    assert orchestrator._review_passed("minor_revision", 84.9) is False


def test_llm_complete_raises_when_real_client_fails(tmp_path, monkeypatch):
    pipeline_v2_module = importlib.import_module("academic_agent_team.pipeline_v2")

    class _BrokenClient:
        def complete(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("provider down")

    monkeypatch.setattr(pipeline_v2_module, "_client_for_role", lambda role: _BrokenClient())
    orchestrator = PipelineOrchestrator(base_dir=tmp_path)

    with pytest.raises(RuntimeError, match="模型调用失败"):
        asyncio.run(
            orchestrator._llm_complete(
                role="writer",
                prompt="p",
                system="s",
                use_mock=False,
            )
        )

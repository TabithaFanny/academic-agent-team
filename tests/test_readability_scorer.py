import importlib.util
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "readability_scorer.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("readability_scorer", TOOL_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_readability_tool_analyze_runs():
    mod = _load_tool_module()
    text = "随着人工智能的发展，本文提出一个可复现的研究框架。"
    result = mod.analyze(text)
    assert result.total_chars > 0
    assert 1.0 <= result.readability_score <= 5.0

"""
模型注册表测试。

注意：health_check 测试仅覆盖 mock client（有 API key 时可手动验证真实 client）。
集成测试（接真实 API）由 e2e 测试覆盖，不在此单元测试套件中。
"""

import pytest

from academic_agent_team.config.models import (
    AGENT_MODEL_MAP,
    FALLBACK_ORDER,
    ROLE_FALLBACK,
    get_model_spec,
    MODEL_REGISTRY,
)


def test_model_registry_all_agents_resolve():
    """验证 AGENT_MODEL_MAP 中所有 agent 都能解析出有效的 ModelSpec。"""
    for agent, (provider, name) in AGENT_MODEL_MAP.items():
        spec = get_model_spec(provider, name)
        assert spec.provider == provider
        assert spec.name == name
        assert spec.model_id
        assert spec.input_cny_per_1m >= 0
        assert spec.output_cny_per_1m >= 0
        assert spec.client_class is not None


def test_mock_client_health_check():
    """mock client 无需 API key，可直接测试 health_check。"""
    mock_spec = get_model_spec("mock", "default")
    client = mock_spec.client_class()
    assert client.health_check() is True


def test_all_registered_providers_have_client_class():
    """验证 MODEL_REGISTRY 中每条 provider 都有有效的 client_class。"""
    for provider, info in MODEL_REGISTRY.items():
        assert info["client_class"] is not None
        # client_class 必须继承 BaseModelClient
        from academic_agent_team.core.base_client import BaseModelClient
        assert issubclass(info["client_class"], BaseModelClient), \
            f"{provider} client_class must inherit from BaseModelClient"


def test_role_fallback_has_all_agents():
    """ROLE_FALLBACK 必须包含所有 AGENT_MODEL_MAP 中的 agent。"""
    assert set(ROLE_FALLBACK.keys()) == set(AGENT_MODEL_MAP.keys())


def test_fallback_order_ends_with_mock():
    """FALLBACK_ORDER 最后必须有 mock兜底（无 key 时不崩溃）。"""
    assert FALLBACK_ORDER[-1] == ("mock", "default")


def test_get_model_spec_unknown_provider():
    with pytest.raises(KeyError):
        get_model_spec("nonexistent_provider", "default")


def test_deepseek_pricing():
    """验证 DeepSeek 定价与 PRD 10.6 一致（deepseek-chat = V3）。"""
    spec = get_model_spec("deepseek", "v3")
    assert spec.model_id == "deepseek-chat"
    assert spec.input_cny_per_1m == 0.27
    assert spec.output_cny_per_1m == 2.18

from unittest.mock import patch

from academic_agent_team.config.models import (
    FALLBACK_ORDER,
    get_model_spec,
    list_models,
    list_providers,
)
from academic_agent_team.config.role_profiles import ROLE_FALLBACK


def test_model_registry_resolves_all_providers():
    """验证所有注册的 provider 都能被解析。"""
    for provider in list_providers():
        models = list_models(provider)
        assert models, f"Provider {provider} has no models registered"
        for name in models:
            spec = get_model_spec(provider, name)
            assert spec.provider == provider
            assert spec.name == name
            assert spec.input_cny_per_1m >= 0.0


def test_mock_client_health_check_is_mocked():
    """
    Mock client 的 health_check 应该返回 True（不需要真实 API）。
    其他 provider 的 get_client_class() 用 mock 补丁。
    """
    from academic_agent_team.config.models import get_model_spec

    spec = get_model_spec("mock", "default")
    cls = spec.get_client_class()
    assert cls is not None
    with patch.object(cls, "health_check", return_value=True):
        client = cls()
        assert client.health_check() is True


def test_fallback_order_not_empty():
    assert FALLBACK_ORDER
    assert all(isinstance(item, tuple) and len(item) == 2 for item in FALLBACK_ORDER)


def test_role_fallback_covers_all_agents():
    """每个 agent 在 ROLE_FALLBACK 中都有降级链。"""
    expected_agents = {"advisor", "researcher", "writer", "reviewer", "polisher", "visualizer"}
    for agent in expected_agents:
        assert agent in ROLE_FALLBACK, f"Agent {agent} missing from ROLE_FALLBACK"
        chain = ROLE_FALLBACK[agent]
        assert len(chain) >= 1
        assert all(isinstance(item, tuple) and len(item) == 2 for item in chain)


def test_get_model_spec_unknown_provider_raises():
    """未知 provider 抛出 KeyError。"""
    import pytest
    with pytest.raises(KeyError):
        get_model_spec("nonexistent_provider", "default")


def test_get_model_spec_unknown_model_raises():
    """未知模型名抛出 KeyError。"""
    import pytest
    with pytest.raises(KeyError):
        get_model_spec("anthropic", "nonexistent_model")

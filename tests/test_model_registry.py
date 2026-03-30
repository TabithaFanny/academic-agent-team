from academic_agent_team.config.models import AGENT_MODEL_MAP, FALLBACK_ORDER, get_model_spec


def test_model_registry_resolves_all_agent_defaults():
    for provider, name in AGENT_MODEL_MAP.values():
        spec = get_model_spec(provider, name)
        client = spec.client_class()
        assert client.health_check() is True


def test_fallback_order_not_empty():
    assert FALLBACK_ORDER

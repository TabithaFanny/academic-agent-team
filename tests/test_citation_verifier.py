import pytest

from academic_agent_team.tools.citation_verifier import (
    CNKIVerifier,
    VerificationStatus,
)


VALID_CNKI_URL = "https://kns.cnki.net/kcms2/article/abstract?v=abc123"


@pytest.mark.asyncio
async def test_cnki_verify_invalid_format():
    verifier = CNKIVerifier()
    result = await verifier.verify("https://example.com/paper")
    assert result.verified is False
    assert result.status == VerificationStatus.INVALID_FORMAT


@pytest.mark.asyncio
async def test_cnki_verify_format_only_mode(monkeypatch):
    monkeypatch.setenv("CNKI_VERIFY_HTTP", "false")
    verifier = CNKIVerifier()
    result = await verifier.verify(VALID_CNKI_URL)
    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_cnki_verify_strict_http_reachable(monkeypatch):
    monkeypatch.setenv("CNKI_VERIFY_HTTP", "true")
    verifier = CNKIVerifier()

    async def fake_reachable(_url):
        return True, "CNKI 链接可达"

    monkeypatch.setattr(verifier, "_check_url_reachable", fake_reachable)
    result = await verifier.verify(VALID_CNKI_URL)
    assert result.verified is True
    assert result.status == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_cnki_verify_strict_http_not_found(monkeypatch):
    monkeypatch.setenv("CNKI_VERIFY_HTTP", "true")
    verifier = CNKIVerifier()

    async def fake_unreachable(_url):
        return False, "CNKI 链接不可达: HTTP 404"

    monkeypatch.setattr(verifier, "_check_url_reachable", fake_unreachable)
    result = await verifier.verify(VALID_CNKI_URL)
    assert result.verified is False
    assert result.status == VerificationStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_cnki_verify_strict_http_network_error(monkeypatch):
    monkeypatch.setenv("CNKI_VERIFY_HTTP", "true")
    verifier = CNKIVerifier()

    async def fake_network_error(_url):
        return False, "CNKI 链接验证网络错误: timeout"

    monkeypatch.setattr(verifier, "_check_url_reachable", fake_network_error)
    result = await verifier.verify(VALID_CNKI_URL)
    assert result.verified is False
    assert result.status == VerificationStatus.NETWORK_ERROR

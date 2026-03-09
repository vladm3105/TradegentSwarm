"""Tests for shared LiteLLM gateway client routing and fallback behavior."""

from __future__ import annotations

import pytest

from llm_gateway.client import LiteLLMGatewayClient


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeResponse:
    def __init__(self, *, content: str, response_id: str = "resp-1") -> None:
        self.id = response_id
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(prompt_tokens=11, completion_tokens=7)


@pytest.mark.asyncio
async def test_gateway_uses_role_route_and_fallback(monkeypatch) -> None:
    calls: list[str] = []
    flush_calls: list[str] = []

    async def _fake_acompletion(**kwargs):
        model = kwargs["model"]
        calls.append(model)
        if model == "openrouter/fail-model":
            raise RuntimeError("provider down")
        return _FakeResponse(content='{"ok": true}')

    import llm_gateway.client as client_mod

    monkeypatch.setattr(client_mod.litellm, "acompletion", _fake_acompletion)

    async def _fake_flush() -> None:
        flush_calls.append("flush")

    monkeypatch.setattr(client_mod, "_flush_litellm_logging_worker", _fake_flush)

    gateway = LiteLLMGatewayClient(
        routes={
            "summarizer_fast": ["openrouter/fail-model", "openai/gpt-4o-mini"],
        },
        timeout=15.0,
        max_retries=1,
    )

    result = await gateway.chat_json(
        role_alias="summarizer_fast",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.2,
    )

    assert calls == ["openrouter/fail-model", "openai/gpt-4o-mini"]
    assert result.model == "openai/gpt-4o-mini"
    assert result.provider == "openai"
    assert result.model_alias == "summarizer_fast"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert flush_calls == ["flush"]


@pytest.mark.asyncio
async def test_gateway_raises_when_fallback_chain_exhausted(monkeypatch) -> None:
    async def _always_fail(**kwargs):
        raise RuntimeError(f"fail:{kwargs['model']}")

    import llm_gateway.client as client_mod

    monkeypatch.setattr(client_mod.litellm, "acompletion", _always_fail)

    gateway = LiteLLMGatewayClient(
        routes={"summarizer_fast": ["openrouter/f1", "openrouter/f2"]},
        timeout=5.0,
        max_retries=0,
    )

    with pytest.raises(RuntimeError, match="fallback chain exhausted"):
        await gateway.chat_text(
            role_alias="summarizer_fast",
            messages=[{"role": "user", "content": "test"}],
        )

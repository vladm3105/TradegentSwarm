"""Shared LiteLLM gateway client with role-based routing and deterministic fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import litellm  # type: ignore[import-untyped]

try:
    from tradegent.adk_runtime.env import load_runtime_env
except ImportError:  # pragma: no cover - fallback for local test/import context
    from adk_runtime.env import load_runtime_env


_ROLE_ALIASES = {
    "reasoning_premium",
    "reasoning_standard",
    "extraction_fast",
    "critic_model",
    "summarizer_fast",
}


@dataclass(slots=True)
class LLMChatResult:
    """Normalized LiteLLM chat result."""

    content: str
    model_alias: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    response_id: str | None


class LiteLLMGatewayClient:
    """Role-aware gateway that routes through ordered model fallback chains."""

    def __init__(
        self,
        *,
        routes: dict[str, list[str]],
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.routes = {alias: self._dedupe(models) for alias, models in routes.items()}
        self.timeout = timeout
        self.max_retries = max_retries

    def get_route_candidates(self, role_alias: str) -> list[str]:
        """Return ordered model candidates for a role alias."""
        return list(self.routes.get(role_alias) or self.routes.get("summarizer_fast") or [])

    @classmethod
    def from_env(cls, *, timeout: float = 120.0, max_retries: int = 2) -> "LiteLLMGatewayClient":
        """Load routes from runtime env (single shared source) and build client."""
        load_runtime_env()
        default_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        routes: dict[str, list[str]] = {}
        for alias in _ROLE_ALIASES:
            env_key = f"LITELLM_ROUTE_{alias.upper()}"
            raw = os.getenv(env_key, "").strip()
            if raw:
                routes[alias] = [m.strip() for m in raw.split(",") if m.strip()]
            else:
                routes[alias] = [default_model]

        # Optional shared fallback chain appended to each alias route.
        global_fallback = [
            m.strip() for m in os.getenv("LITELLM_FALLBACK_MODELS", "").split(",") if m.strip()
        ]
        if global_fallback:
            for alias in routes:
                routes[alias] = cls._dedupe(routes[alias] + global_fallback)

        return cls(routes=routes, timeout=timeout, max_retries=max_retries)

    async def chat_json(
        self,
        *,
        role_alias: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMChatResult:
        """Request JSON object response with deterministic fallback."""
        return await self._chat(
            role_alias=role_alias,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

    async def chat_text(
        self,
        *,
        role_alias: str,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMChatResult:
        """Request free-form text response with deterministic fallback."""
        return await self._chat(
            role_alias=role_alias,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=None,
        )

    async def _chat(
        self,
        *,
        role_alias: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None,
    ) -> LLMChatResult:
        candidates = self.get_route_candidates(role_alias)
        if not candidates:
            raise RuntimeError(f"No models configured for role_alias={role_alias}")

        last_error: Exception | None = None
        for model in candidates:
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "timeout": self.timeout,
                    "num_retries": self.max_retries,
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens
                if response_format is not None:
                    kwargs["response_format"] = response_format

                response = await litellm.acompletion(**kwargs)
                content = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                provider = self._provider_from_model(model)

                return LLMChatResult(
                    content=content,
                    model_alias=role_alias,
                    model=model,
                    provider=provider,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    response_id=getattr(response, "id", None),
                )
            except Exception as exc:
                last_error = exc

        raise RuntimeError(
            f"LiteLLM fallback chain exhausted for role_alias={role_alias}: {last_error}"
        ) from last_error

    @staticmethod
    def _provider_from_model(model: str) -> str:
        if "/" in model:
            return model.split("/", 1)[0]
        return "unknown"

    @staticmethod
    def _dedupe(models: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for model in models:
            token = model.strip()
            if token and token not in seen:
                seen.add(token)
                out.append(token)
        return out

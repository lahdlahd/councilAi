"""LLM client — Qwen primary, OpenAI fallback, OpenAI-compatible chat API.

Both Qwen (DashScope compatible mode) and OpenAI expose the same
`POST {base}/chat/completions` shape, so a single code path serves both with
different base_url / key / model.

Provider selection at construction time:
  1. Qwen        if QWEN_API_KEY is set        (primary)
  2. OpenAI      if OPENAI_API_KEY is set       (fallback)
  3. OFFLINE     otherwise                      (is_offline=True)

In OFFLINE mode `complete()` raises — agents must use their deterministic,
data-driven `_offline()` path instead (see agents/base.py). This keeps the whole
council runnable and demoable with zero API keys, reasoning over REAL market data.

Token streaming (`astream`) is defined here but wired into the WebSocket transport
in Step 3; Step 2 uses full `complete()` calls for orchestration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.utils.logging import get_logger

log = get_logger("llm")


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


class LLMUnavailable(RuntimeError):
    """Raised when no live provider is configured (offline mode)."""


class LLMClient:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._providers: list[Provider] = []

        if settings.qwen_api_key:
            self._providers.append(
                Provider("qwen", settings.qwen_base_url, settings.qwen_api_key, settings.qwen_model)
            )
        if settings.openai_api_key:
            self._providers.append(
                Provider("openai", settings.openai_base_url, settings.openai_api_key, settings.openai_model)
            )

        if self._providers:
            log.info("LLM providers: %s", " -> ".join(p.name for p in self._providers))
        else:
            log.warning("No LLM key configured — council runs in OFFLINE (data-driven) mode")

    @property
    def is_offline(self) -> bool:
        return not self._providers

    # ---- Full completion (Step 2 orchestration) ----------------------------
    async def complete(self, *, system: str, user: str, json_mode: bool = False) -> str:
        if self.is_offline:
            raise LLMUnavailable("no live LLM provider configured")

        last_exc: Exception | None = None
        for provider in self._providers:
            try:
                return await self._call(provider, system, user, json_mode)
            except Exception as exc:  # noqa: BLE001 - fall through to next provider
                last_exc = exc
                log.warning("provider %s failed: %s", provider.name, exc)
        assert last_exc is not None
        raise last_exc

    async def _call(self, provider: Provider, system: str, user: str, json_mode: bool) -> str:
        payload: dict = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = await self._client.post(
            f"{provider.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json=payload,
            timeout=self._settings.llm_timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ---- Token streaming (used by Step 3 transport) ------------------------
    async def astream(self, *, system: str, user: str) -> AsyncIterator[str]:
        if self.is_offline:
            raise LLMUnavailable("no live LLM provider configured")
        provider = self._providers[0]
        payload = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
            "stream": True,
        }
        async with self._client.stream(
            "POST",
            f"{provider.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json=payload,
            timeout=self._settings.llm_timeout_sec,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[len("data: "):].strip()
                if chunk == "[DONE]":
                    break
                import json as _json

                try:
                    delta = _json.loads(chunk)["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, ValueError):
                    continue
                if delta:
                    yield delta

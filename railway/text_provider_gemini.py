"""Text generation providers for the Nova AI Orchestrator.

Two interchangeable adapters behind a common shape:
  - OpenAIProvider: OpenAI Responses API (OPENAI_API_KEY).
  - GeminiProvider: Google Gemini REST API (GEMINI_API_KEY or GOOGLE_API_KEY).

Providers never silently fall back to another credential.
"""
import os
from collections.abc import AsyncIterator
from typing import Optional

import json
import httpx


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else None


class OpenAIProvider:
    key = "openai"
    label = "OpenAI"

    def __init__(self):
        self._api_key = _env("OPENAI_API_KEY")
        self.model = _env("OPENAI_MODEL") or "gpt-5.4"

    @property
    def configured(self):
        return bool(self._api_key)

    async def stream(self, session_id, system_message, user_text):
        if not self.configured:
            raise RuntimeError("OpenAI não configurado")
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream(
                "POST", "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self.model, "instructions": system_message,
                      "input": user_text, "stream": True, "store": False},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    event = json.loads(raw)
                    kind = event.get("type")
                    if kind == "response.output_text.delta":
                        yield event["delta"]
                    elif kind == "response.completed":
                        return
                    elif kind in ("error", "response.failed", "response.incomplete"):
                        raise RuntimeError("Falha no provedor de IA")
                raise RuntimeError("Resposta de IA interrompida")


class GeminiProvider:
    """Google Gemini provider using the official REST API."""

    key = "gemini"
    label = "Google Gemini"

    def __init__(self) -> None:
        self._api_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
        self.model = _env("GEMINI_MODEL") or "gemini-3.5-flash-lite"

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def stream(self, session_id: str, system_message: str, user_text: str) -> AsyncIterator[str]:
        if not self._api_key:
            raise RuntimeError("Gemini não configurado")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_message}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"maxOutputTokens": 2048},
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f"Falha no Gemini ({response.status_code})")
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini não retornou resposta")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise RuntimeError("Gemini retornou resposta vazia")

        step = 160
        for i in range(0, len(text), step):
            yield text[i:i + step]


_openai = OpenAIProvider()
_gemini = GeminiProvider()

TEXT_PROVIDERS = {p.key: p for p in (_openai, _gemini)}
DEFAULT_TEXT_PROVIDER = _env("NOVA_TEXT_PROVIDER") or "openai"


def get_text_provider(name: Optional[str] = None):
    key = name or DEFAULT_TEXT_PROVIDER
    if key not in TEXT_PROVIDERS:
        raise ValueError("Provedor de IA desconhecido")
    return TEXT_PROVIDERS[key]

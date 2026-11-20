"""LLM backends. The engine only needs `complete(messages) -> str`.

- Gemini (free tier, no credit card): set GEMINI_API_KEY  -> https://aistudio.google.com/apikey
  Called through Gemini's native REST endpoint, which accepts both the new "AQ." keys and the
  older "AIza" keys (the OpenAI-compatible endpoint rejects AQ. keys).
- Groq (free tier, no credit card): set GROQ_API_KEY  -> https://console.groq.com/keys
- OpenAI (paid): set OPENAI_API_KEY
Priority when several keys are set: Groq, then Gemini, then OpenAI. Override the model with LLM_MODEL.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Protocol

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-3-flash-preview",
                  "openai": "gpt-4o-mini"}
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
RETRYABLE = {429, 500, 502, 503, 504}


class LLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class LLMError(RuntimeError):
    """A clear, user-facing error from the model provider."""


def _backoff(attempt: int) -> int:
    wait = min(60, 5 * 2 ** attempt)  # free tiers allow only a few requests per minute
    print(f"  rate limited - waiting {wait}s and retrying...")
    return wait


class GeminiLLM:
    """Google Gemini via the native generateContent REST API (standard library only)."""

    provider = "gemini"

    def __init__(self, api_key: str, model: str | None = None, max_retries: int = 5):
        self.api_key = api_key.strip().strip('"').strip("'")
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS["gemini"]
        self.max_retries = max_retries
        self.total_tokens = 0

    @staticmethod
    def _to_gemini(messages: list[dict]) -> dict:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"]
        body = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    def complete(self, messages: list[dict]) -> str:
        data = json.dumps(self._to_gemini(messages)).encode()
        req = urllib.request.Request(
            GEMINI_URL.format(model=self.model), data=data, method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key})
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    out = json.load(r)
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in RETRYABLE and attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                if e.code in (400, 401, 403):
                    raise LLMError(f"Gemini rejected the request ({e.code}). Check GEMINI_API_KEY in .env "
                                   f"and the model name '{self.model}'. Details: {detail}") from e
                raise LLMError(f"Gemini error {e.code}: {detail}") from e
            except urllib.error.URLError as e:
                if attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    continue
                raise LLMError(f"Could not reach Gemini: {e.reason}") from e

        self.total_tokens += out.get("usageMetadata", {}).get("totalTokenCount", 0)
        cands = out.get("candidates") or []
        if not cands:
            raise LLMError(f"Gemini returned no answer: {str(out.get('promptFeedback', out))[:200]}")
        parts = cands[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))


class OpenAIChatLLM:
    """OpenAI chat models (paid) or any OpenAI-compatible provider such as Groq (free)."""

    def __init__(self, api_key: str, model: str | None = None, temperature: float = 0.0,
                 max_retries: int = 5, provider: str = "openai", base_url: str | None = None):
        from openai import OpenAI  # imported here so tests and Gemini users don't need it

        self.provider = provider
        self.client = OpenAI(api_key=api_key.strip().strip('"').strip("'"), base_url=base_url)
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider]
        self.temperature = temperature
        self.max_retries = max_retries
        self.total_tokens = 0

    def complete(self, messages: list[dict]) -> str:
        from openai import APIConnectionError, APIStatusError, RateLimitError

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model, messages=messages, temperature=self.temperature)
                break
            except (RateLimitError, APIConnectionError):
                if attempt == self.max_retries:
                    raise
                time.sleep(_backoff(attempt))
            except APIStatusError as e:
                raise LLMError(f"{self.provider} error {e.status_code}: {e.message} "
                               f"(check the API key in .env and the model '{self.model}')") from e
        if resp.usage:
            self.total_tokens += resp.usage.total_tokens or 0
        return resp.choices[0].message.content or ""


def ChatLLM(provider: str | None = None, model: str | None = None):
    """Pick the provider from whichever API key is configured."""
    groq, gemini, openai_key = (os.getenv("GROQ_API_KEY"), os.getenv("GEMINI_API_KEY"),
                                os.getenv("OPENAI_API_KEY"))
    provider = provider or ("groq" if groq else "gemini" if gemini else "openai" if openai_key else None)
    if provider == "groq" and groq:
        return OpenAIChatLLM(groq, model, provider="groq", base_url=GROQ_BASE_URL)
    if provider == "gemini" and gemini:
        return GeminiLLM(gemini, model)
    if provider == "openai" and openai_key:
        return OpenAIChatLLM(openai_key, model)
    raise LLMError("No API key found. Put GROQ_API_KEY (free), GEMINI_API_KEY (free) or OPENAI_API_KEY "
                   "in a .env file - see README.")


# backwards-compatible name
OpenAILLM = ChatLLM

"""LLM backends. The engine only needs `complete(messages) -> str`.

Two providers, both called through the `openai` Python library:
- Gemini (free tier, no credit card): set GEMINI_API_KEY  -> https://aistudio.google.com/apikey
- OpenAI (paid):                      set OPENAI_API_KEY
If both are set, Gemini is used. Override the model with LLM_MODEL.
"""
from __future__ import annotations

import os
import time
from typing import Protocol

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODELS = {"gemini": "gemini-3-flash-preview", "openai": "gpt-4o-mini"}


class LLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class ChatLLM:
    """OpenAI-compatible chat model (Gemini or OpenAI), with retries on rate limits."""

    def __init__(self, provider: str | None = None, model: str | None = None,
                 temperature: float = 0.0, max_retries: int = 5):
        from openai import OpenAI  # imported here so tests run without the package

        provider = provider or ("gemini" if os.getenv("GEMINI_API_KEY") else
                                "openai" if os.getenv("OPENAI_API_KEY") else None)
        if provider is None:
            raise RuntimeError("No API key found. Put GEMINI_API_KEY (free) or OPENAI_API_KEY "
                               "in a .env file - see README.")
        if provider == "gemini":
            self.client = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=GEMINI_BASE_URL)
        else:
            self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.provider = provider
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider]
        self.temperature = temperature
        self.max_retries = max_retries
        self.total_tokens = 0

    def complete(self, messages: list[dict]) -> str:
        from openai import APIConnectionError, RateLimitError

        for attempt in range(self.max_retries + 1):
            try:
                kwargs = {"model": self.model, "messages": messages}
                if self.provider == "openai":  # Gemini 3 models are tuned for their default temperature
                    kwargs["temperature"] = self.temperature
                resp = self.client.chat.completions.create(**kwargs)
                break
            except (RateLimitError, APIConnectionError):
                if attempt == self.max_retries:
                    raise
                wait = min(60, 5 * 2 ** attempt)  # free tiers allow only a few requests per minute
                print(f"  rate limited - waiting {wait}s and retrying...")
                time.sleep(wait)
        if resp.usage:
            self.total_tokens += resp.usage.total_tokens or 0
        return resp.choices[0].message.content or ""


# backwards-compatible name
OpenAILLM = ChatLLM

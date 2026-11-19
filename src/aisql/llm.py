"""LLM backends. The engine only needs `complete(messages) -> str`."""
from __future__ import annotations

import os
from typing import Protocol


class LLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class OpenAILLM:
    """OpenAI chat model. Reads OPENAI_API_KEY (and optional OPENAI_MODEL) from the environment."""

    def __init__(self, model: str | None = None, temperature: float = 0.0):
        from openai import OpenAI  # imported here so tests run without the package

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set - put it in a .env file (see README)")
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature
        self.total_tokens = 0

    def complete(self, messages: list[dict]) -> str:
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=self.temperature)
        if resp.usage:
            self.total_tokens += resp.usage.total_tokens
        return resp.choices[0].message.content or ""

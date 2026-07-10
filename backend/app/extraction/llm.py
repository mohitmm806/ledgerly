"""LLM access behind a small interface.

Everything the extractor needs from a model is: given a prompt, return text
(which we expect to be JSON). Hiding that behind a Protocol means:
  - tests run with a deterministic FakeLLM, no network, no API key, and can
    script a bad-then-good sequence to exercise the self-correction loop;
  - swapping providers is a one-file change.

The real client is intentionally thin. Provider SDKs change; this keeps the
surface we depend on tiny.
"""

from __future__ import annotations

import os
from typing import Protocol


class LLM(Protocol):
    name: str

    def complete(self, prompt: str) -> str:
        """Return the model's text response to a single prompt."""
        ...


class FakeLLM:
    """Deterministic model for tests. Returns queued responses in order; once
    exhausted, repeats the last one. Lets a test say "first answer is wrong,
    second is right" and assert the loop recovered.
    """

    name = "fake"

    def __init__(self, responses: list[str]):
        if not responses:
            raise ValueError("FakeLLM needs at least one response")
        self._responses = responses
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[idx]


class AnthropicLLM:
    """Thin wrapper over the Anthropic Messages API.

    Kept optional: the SDK is imported lazily so the app runs (and tests pass)
    without it installed. Configure with LLM_API_KEY.
    """

    # Default to Haiku: cheapest Claude model and plenty for invoice extraction.
    # Override with the LLM_MODEL env var (e.g. a Sonnet model) if you want more
    # headroom on the messiest documents.
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.name = model or os.getenv("LLM_MODEL", self.DEFAULT_MODEL)
        self._api_key = api_key or os.getenv("LLM_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                "No LLM_API_KEY set. Set it, or use FakeLLM in tests."
            )

    def complete(self, prompt: str) -> str:
        import anthropic  # imported here so it's only required when actually used

        client = anthropic.Anthropic(api_key=self._api_key)
        try:
            msg = client.messages.create(
                model=self.name,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            # Turn provider errors (billing, auth, rate limit, outage) into a
            # domain error the API layer can present cleanly, instead of a 500.
            raise LLMError(_friendly_llm_error(exc)) from exc
        return "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )


class LLMError(Exception):
    """A call to the language model failed (billing, auth, rate limit, outage)."""


def _friendly_llm_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "credit balance" in text or "billing" in text:
        return (
            "The language model is unavailable: the Anthropic account has no "
            "credit balance. Add credits in the Anthropic console to enable "
            "extraction and natural-language query."
        )
    if "authentication" in text or "api key" in text or "401" in text:
        return "The language model rejected the API key. Check LLM_API_KEY."
    if "rate limit" in text or "429" in text:
        return "The language model is rate limited right now. Try again shortly."
    return f"The language model call failed: {exc}"


class GroqLLM:
    """Groq's OpenAI-compatible chat API.

    Groq has a real free tier (no credit card), which makes it a good default
    for a free deployment. Uses httpx directly so there's no extra SDK to pull
    in. Configure with GROQ_API_KEY, override the model with LLM_MODEL.
    """

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.name = model or os.getenv("LLM_MODEL", self.DEFAULT_MODEL)
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("No GROQ_API_KEY set. Set it, or use FakeLLM in tests.")

    def complete(self, prompt: str) -> str:
        import httpx

        try:
            resp = httpx.post(
                self.URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.name,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMError(_friendly_llm_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach the language model: {exc}") from exc
        return resp.json()["choices"][0]["message"]["content"]


def default_llm() -> LLM:
    """Pick a real client based on LLM_PROVIDER, else fail loudly.

    LLM_PROVIDER = "groq" (free tier) or "anthropic" (default). Each provider
    reads its own key. Routes construct their own LLM, so this is mainly a
    convenience for the seed and eval scripts.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "groq":
        return GroqLLM()
    if provider == "anthropic":
        if os.getenv("LLM_API_KEY"):
            return AnthropicLLM()
        raise RuntimeError("No LLM_API_KEY set for provider 'anthropic'.")
    raise RuntimeError(f"Unknown LLM_PROVIDER {provider!r}. Use 'groq' or 'anthropic'.")

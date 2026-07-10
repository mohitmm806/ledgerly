"""Shared FastAPI dependencies.

The LLM is a dependency so tests can override it with a deterministic FakeLLM
via app.dependency_overrides, exactly like the database session.
"""

from fastapi import HTTPException

from .extraction.llm import LLM, default_llm


def get_llm() -> LLM:
    try:
        return default_llm()
    except RuntimeError as exc:
        # No model configured: a 503 is the honest status (the service can't do
        # this right now), with a message that says how to fix it.
        raise HTTPException(status_code=503, detail=str(exc))

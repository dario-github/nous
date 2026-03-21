"""OpenAI-based LLM Provider for Nous Semantic Gate.

Provides a simple provider function that calls OpenAI's chat completions API.
Used for benchmark evaluation with real LLM.
"""
import json
import os
from typing import Optional


def create_openai_provider(
    model: str = "DeepSeek-V3.1",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_retries: int = 2,
) -> callable:
    """Create an OpenAI-compatible LLM provider for semantic_gate.

    Args:
        model: Model name (default: MiniMax-M2.7)
        api_key: API key (defaults to NOUS_API_KEY → OPENAI_API_KEY env var)
        base_url: API base URL (defaults to NOUS_BASE_URL env var, then OpenAI default)
        max_retries: Number of retries on transient errors (default: 2)

    Returns:
        Callable matching LLMProvider protocol: (prompt, timeout_ms, model) -> str

    Raises on API errors instead of returning fake verdicts.
    The semantic_gate caller handles exceptions → returns None → FAIL_OPEN
    (falls back to Datalog verdict, which is the conservative path).
    """
    try:
        import openai
    except ImportError:
        raise ImportError("openai package required: pip install openai")

    key = api_key or os.environ.get("NOUS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("No API key provided (set NOUS_API_KEY or OPENAI_API_KEY)")

    url = base_url or os.environ.get("NOUS_BASE_URL")
    client_kwargs = {"api_key": key}
    if url:
        client_kwargs["base_url"] = url

    client = openai.OpenAI(**client_kwargs)

    def provider(prompt: str, timeout_ms: int, model_override: str) -> str:
        """Call OpenAI-compatible chat completions.

        Raises on failure — caller (semantic_gate) catches and returns None.
        This is correct: API failure → no semantic verdict → Datalog verdict stands.
        """
        import time as _time

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=600,
                    temperature=0.0,
                    timeout=max(timeout_ms / 1000, 10.0),
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise ValueError("Empty response from LLM")
                return content
            except Exception as e:
                last_err = e
                # Retry on transient errors (rate limit, timeout, 5xx)
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in [
                    "rate_limit", "timeout", "503", "502", "429",
                    "connection", "temporary",
                ])
                if is_transient and attempt < max_retries:
                    _time.sleep(1.0 * (attempt + 1))  # Linear backoff
                    continue
                raise  # Non-transient or exhausted retries

        raise last_err  # Should not reach here, but safety net

    return provider

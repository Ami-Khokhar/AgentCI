"""Shared Gemini rate gate for RECORD mode (no effect on replay — that path is cached).

Fresh GCP projects have low Vertex per-minute/token quota. Phoenix runs the target task and the
four judges over all cases concurrently, which bursts past the quota; Phoenix's own adaptive
limiter then throttles to ~zero and never recovers. Instead we serialize every live Gemini call
to a safe minimum interval across all worker threads, and back off on the 429s that still slip
through. Both the target (ADK) and the judges (genai) route through here so neither phase bursts.
"""
import os
import threading
import time

_LOCK = threading.Lock()
_LAST = [0.0]
_MIN_INTERVAL = float(os.environ.get("AGENTCI_GEMINI_MIN_INTERVAL", "1.0"))  # seconds between calls
_MAX_RETRIES = int(os.environ.get("AGENTCI_GEMINI_MAX_RETRIES", "10"))


def is_rate_limit(exc: BaseException) -> bool:
    """True for Vertex/AI-Studio 429 RESOURCE_EXHAUSTED — covers both the genai ClientError and
    ADK's google_llm._ResourceExhaustedError wrapper."""
    return getattr(exc, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc)


def pace() -> None:
    """Block until at least _MIN_INTERVAL has elapsed since the last paced call (thread-safe)."""
    with _LOCK:
        wait = _MIN_INTERVAL - (time.monotonic() - _LAST[0])
        if wait > 0:
            time.sleep(wait)
        _LAST[0] = time.monotonic()


def call_with_backoff(fn):
    """Run fn() paced + with exponential backoff on 429. fn must be a no-arg callable."""
    delay = 4.0
    for attempt in range(_MAX_RETRIES):
        pace()
        try:
            return fn()
        except Exception as exc:
            if attempt == _MAX_RETRIES - 1 or not is_rate_limit(exc):
                raise
            time.sleep(delay)
            delay = min(delay * 1.7, 60.0)

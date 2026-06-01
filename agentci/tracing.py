"""Phoenix tracing init. Mirrors the Arize reference repo's phoenix.otel.register usage."""
import os
from phoenix.otel import register

_PROVIDER = None


def init_tracing():
    """Idempotently register the Phoenix tracer; auto-instruments installed OI deps (ADK)."""
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = register(
            project_name=os.environ.get("PHOENIX_PROJECT_NAME", "agentci"),
            auto_instrument=True,
        )
    return _PROVIDER

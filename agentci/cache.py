"""Record/replay cache: makes LLM-touching code deterministic for tests and demo replay."""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable


class CacheMissError(RuntimeError):
    """Raised in replay mode when no recording exists for the key."""


def _mode() -> str:
    return os.environ.get("AGENTCI_CACHE_MODE", "replay")


def _dir() -> Path:
    d = Path(os.environ.get("AGENTCI_CACHE_DIR", ".agentci_cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(namespace: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return f"{namespace}-{digest}"


def cached(namespace: str, payload: Any, live_fn: Callable[[], Any]) -> Any:
    """Return live_fn() result, recording/replaying per AGENTCI_CACHE_MODE."""
    mode = _mode()
    if mode == "live":
        return live_fn()

    path = _dir() / f"{_key(namespace, payload)}.json"
    if mode == "replay":
        if not path.exists():
            raise CacheMissError(f"no recording for {namespace} key {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    if mode == "record":
        result = live_fn()
        path.write_text(json.dumps(result, default=str), encoding="utf-8")
        return result

    raise ValueError(f"unknown AGENTCI_CACHE_MODE: {mode}")

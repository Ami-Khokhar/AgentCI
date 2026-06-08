"""Quality Memory: the self-improving institutional-memory layer (read on diagnose, write on approval)."""
# Public surface = the read helpers + the SINGLE human-gated writer (record_approval).
# `append_entry`/`build_entry` are intentionally NOT re-exported here so the only advertised
# write path is record_approval (D20); reach them via `agentci.memory.memory` if ever needed.
from agentci.memory.memory import (  # noqa: F401
    find_relevant,
    format_for_prompt,
    load_memory,
    record_approval,
)

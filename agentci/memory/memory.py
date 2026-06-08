"""Quality Memory (self-improving layer): a persistent, git-tracked archive of past regressions.

The investigator READS relevant entries before diagnosing (D11 amendment, 2026-06-08); entries are
WRITTEN only on human approval (D12). Pure functions — no LLM calls, no network."""
import json
import os
from pathlib import Path

from agentci.data.dataset import load_tickets

_DEFAULT_PATH = Path(__file__).resolve().parent / "quality_memory.json"

# Deterministic, templated lessons keyed by the diagnosis taxonomy (config.FAILURE_TAXONOMY).
# No LLM call — the surfaced "pattern" is a stable string the investigator can reuse.
_LESSON_TEMPLATES = {
    "factual_omission": "Making prompts more concise often removes required citation/policy detail "
                        "from answers.",
    "over_refusal": "Cautious or restrictive wording can make the agent over-refuse tickets the "
                    "knowledge base actually covers.",
    "policy_miscite": "Loosening citation instructions can cause the agent to cite the wrong policy.",
    "hallucination": "Removing grounding constraints invites fabricated answers.",
    "format_regression": "Changing tone/format instructions can break required output structure.",
}

_CATEGORY_DIM = {
    "factual_omission": "completeness/correctness",
    "over_refusal": "correctness",
    "policy_miscite": "policy_reference",
    "hallucination": "groundedness",
    "format_regression": "completeness",
}


def _path() -> Path:
    return Path(os.environ.get("AGENTCI_MEMORY_PATH", str(_DEFAULT_PATH)))


def load_memory() -> list[dict]:
    """Return all entries (oldest first). Empty list if the store does not exist.

    Invariant: the store is always a JSON list (seeded as `[]`, every write goes through
    `append_entry`). We deliberately do NOT guard against a corrupt/non-list file — a silent
    fallback would mask data loss; a malformed store should fail loudly.
    """
    p = _path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def append_entry(entry: dict) -> None:
    """Append one entry to the store, creating it if needed.

    Non-atomic read-modify-write by design: the only writer is `record_approval`, reached
    synchronously through a single human approval. Do not add a second concurrent writer
    without introducing a file lock.
    """
    entries = load_memory()
    entries.append(entry)
    _path().write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _policy_by_case() -> dict:
    """Map every frozen ticket id to its policy_id (the cross-failure matching key)."""
    return {t["id"]: t["policy_id"] for t in load_tickets()}


def _policies_for(case_ids: list[str], policy_by_case: dict) -> set:
    return {policy_by_case[c] for c in case_ids if c in policy_by_case}


def find_relevant(flipped_case_ids: list[str]) -> list[dict]:
    """Past entries whose affected policies intersect the flipped cases' policies.

    Policy id is the matching key because it is available BEFORE diagnosis runs.
    """
    if not flipped_case_ids:
        return []
    flipped_policies = _policies_for(flipped_case_ids, _policy_by_case())
    if not flipped_policies:
        return []
    return [e for e in load_memory()
            if set(e.get("affected_policies") or []) & flipped_policies]


def format_for_prompt(entries: list[dict]) -> str:
    """Render matched lessons for injection into the diagnose prompt. Stable + deterministic.

    Returns "" for the empty case so an empty memory does not perturb the cache key.
    """
    if not entries:
        return ""
    lines = [f"- [{e.get('failure_type', '?')}] {e.get('lesson', '')} "
             f"(past fix: {e.get('successful_fix', '')})" for e in entries]
    return "Prior lessons from past regressions (apply if relevant):\n" + "\n".join(lines)


def _lesson(failure_type: str) -> str:
    return _LESSON_TEMPLATES.get(failure_type, "A prompt change reintroduced a known failure mode.")


def build_entry(report: dict, timestamp: str) -> dict:
    """Construct one Quality Memory entry from an approved run report."""
    inv = report.get("investigation") or {}
    rc = inv.get("root_cause") or {}
    fix = report.get("proposed_fix") or {}
    flips = report.get("flips") or {}
    mint = report.get("proposed_mint") or {}

    affected = list(flips.get("pass_to_fail") or [])
    policies = _policies_for(affected, _policy_by_case())
    if rc.get("policy_id"):
        policies.add(rc["policy_id"])
    failure_type = rc.get("category") or "unknown"

    try:
        guard_slug = json.loads(mint.get("guard") or "{}").get("slug")
    except (ValueError, TypeError):
        guard_slug = None

    return {
        "failure_type": failure_type,
        "triggering_prompt_change": report.get("candidate_label"),
        "root_cause": rc.get("summary"),
        "lesson": _lesson(failure_type),
        "successful_fix": fix.get("rationale"),
        "failed_fixes": [],
        "affected_cases": affected,
        "affected_policies": sorted(p for p in policies if p),
        "evaluator_notes": f"{_CATEGORY_DIM.get(failure_type, 'correctness')} regressed on "
                           f"{len(affected)} case(s).",
        "new_eval_cases": {"id": mint.get("id"), "guard_slug": guard_slug},
        "approval_status": "approved",
        "timestamp": timestamp,
    }


def record_approval(report: dict, timestamp: str) -> dict:
    """Build + append a memory entry for an approved run. The ONLY write path (human-gated, D12)."""
    entry = build_entry(report, timestamp)
    append_entry(entry)
    return entry

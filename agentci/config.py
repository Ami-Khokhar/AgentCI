"""Single source of truth for model IDs, determinism, thresholds (frozen decisions)."""

# --- Models (pinned for determinism, D7) ---
TARGET_MODEL = "gemini-2.5-flash"   # D7 (original); recorded via Vertex AI (real quota, no free-tier 20/day cap)
ENGINEER_MODEL = "gemini-2.5-flash"  # D7 amendment 2026-06-08: pro-tier 429s immediately on the fresh project; flash@us-central1 has real quota
JUDGE_MODEL = "gemini-2.5-flash"    # D7 amendment 2026-06-08: flash judges run in us-central1 (high quota); pro 429-stalls on the global endpoint
TEMPERATURE = 0.0

# --- Rubric thresholds (D9) ---
PASS_THRESHOLD = 0.7          # per-dimension score >= this => "pass"

# --- Promotion gate (D8, amended 2026-06-09: recovery-correct criterion) ---
# A fix is a regression RECOVERY — its goal is to restore baseline behaviour, so its realistic best
# is parity (lift ~0), not a strict improvement. The original +0.05 bar suited the curated demo but
# structurally reds real recoveries. The promotion test is therefore "the fix is no worse than
# baseline (lift >= 0) AND introduces zero new held-out regressions" — the actual safe-to-ship test.
# Amended 2026-06-10 (noise-calibrated flip leg): the flip threshold is the MEASURED sampling-noise
# floor, not zero. scripts/calibrate_gate.py re-samples the unchanged baseline prompt on held-out
# and gates it against its own recorded answers: lift 0.0 but 2 pass->fail flips (Vertex temp-0 is
# not reproducible; judge scores wobble; knife-edge cases sit at exactly 0.70). A zero-flip gate
# reds a literal no-op, so it cannot pass any real recovery. Re-measure the floor (re-run the
# script with a cleared .agentci_cache_calib) whenever target/judge/ruler models change.
MIN_HELDOUT_LIFT = 0.0        # fixed mean correctness must be >= baseline (no worse than production)
MAX_HELDOUT_REGRESSIONS = 2   # measured baseline-vs-baseline noise floor (2/16 held-out, 2026-06-10)

# --- Phoenix dataset naming ---
DATASET_NAME = "agentci-support-suite"
RUBRIC_DIMENSIONS = ("correctness", "groundedness", "completeness", "policy_reference")

# --- Baseline target-agent system prompt ---
BASELINE_SUPPORT_PROMPT = """You are a customer-support agent for a SaaS billing product.
Use ONLY the knowledge base returned by the `lookup_kb` tool to answer.
Always cite the exact policy section you relied on. If the knowledge base does not
cover the question, say you will route the ticket to a human and name the team.
For refund questions, state the refund window and any eligibility conditions explicitly."""

# --- Cross-family independence (D17/D18): the ruler must not share a brain with the optimizer ---
IMPROVEMENT_JUDGE_MODEL = "claude-haiku-4-5-20251001"   # frozen held-out correctness ruler
GUARD_REVIEWER_MODEL = "claude-haiku-4-5-20251001"      # adversarial rubric reviewer
FREE_RULER_MODEL = "llama-3.3-70b-versatile"            # D17 amendment: Groq free tier, used when GROQ_API_KEY is set
RULER_VERTEX_MODEL = "claude-haiku-4-5@20251001"        # D17: Claude Haiku on Vertex AI (billed to GCP), used when ANTHROPIC_USE_VERTEX=true
# D17 deviation escape-hatch (AGENTCI_RULER=gemini): when NO non-Gemini endpoint has quota
# (Claude-on-Vertex defaults to ~0 quota on fresh projects), fall back to a Gemini ruler.
# Amended 2026-06-09: flash-lite, NOT flash — a distinct checkpoint from ENGINEER_MODEL (different
# weights, separate quota pool), so the fix-author never grades its own output with its own weights.
# Checkpoint separation is still weaker than cross-family — opt-in only, never the default.
RULER_GEMINI_MODEL = "gemini-2.5-flash-lite"

# --- Guard authoring/admission (D15/D18) ---
FAILURE_TAXONOMY = (
    "factual_omission", "over_refusal", "policy_miscite",
    "hallucination", "format_regression",
)
GUARD_REVIEW_THRESHOLD = 0.7    # rubric reviewer score >= this to admit
GUARD_REFINE_ATTEMPTS = 2       # how many times the agent may refine a rejected guard

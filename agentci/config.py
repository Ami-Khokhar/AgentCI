"""Single source of truth for model IDs, determinism, thresholds (frozen decisions)."""

# --- Models (pinned for determinism, D7) ---
TARGET_MODEL = "gemini-2.5-flash"
ENGINEER_MODEL = "gemini-2.5-pro"
JUDGE_MODEL = "gemini-2.5-pro"
TEMPERATURE = 0.0

# --- Rubric thresholds (D9) ---
PASS_THRESHOLD = 0.7          # per-dimension score >= this => "pass"

# --- Promotion gate (D8) ---
MIN_HELDOUT_LIFT = 0.05       # candidate mean correctness must beat baseline by >= this
MAX_HELDOUT_REGRESSIONS = 0   # zero held-out pass->fail flips allowed

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

# --- Guard authoring/admission (D15/D18) ---
FAILURE_TAXONOMY = (
    "factual_omission", "over_refusal", "policy_miscite",
    "hallucination", "format_regression",
)
GUARD_REVIEW_THRESHOLD = 0.7    # rubric reviewer score >= this to admit
GUARD_REFINE_ATTEMPTS = 2       # how many times the agent may refine a rejected guard

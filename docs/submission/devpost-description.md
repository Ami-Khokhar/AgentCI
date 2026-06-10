# Devpost submission — text description (Arize track)

Paste-ready sections for the Devpost form. Fill the bracketed URLs before submitting.

---

## Inspiration

A one-line prompt edit — "keep answers short" — can make a support agent silently drop
the refund window a policy requires, while still producing fluent, policy-citing answers
a human reviewer would approve. Code has CI; agents mostly have vibes. We built the CI.

## What it does

**AgentCI is regression CI for AI agents.** On every candidate prompt change to an
instrumented Google ADK support agent, it:

1. Runs the candidate against a frozen 40-ticket eval suite (24 tune / 16 held-out) as
   Phoenix experiments, scored by four LLM-as-judge dimensions.
2. If tune-set cases flip pass→fail, the gate goes **red** and a Gemini **Regression
   Investigator agent** autonomously root-causes the failure through the **Phoenix MCP
   server** — a genuine reason-act loop (hypothesis → pull experiments/traces → verify →
   refine), not a scripted query.
3. A separate fix-author agent writes one corrective edit, which is **proved on the
   held-out split** the candidate never touched, scored by an independent judge the
   fix-author doesn't control, behind a **noise-calibrated promotion gate**.
4. A human approves on the dashboard. Approval **mints the failure as a permanent eval
   case** and writes the lesson to **Quality Memory**, which the investigator reads
   before its next diagnosis — every caught regression makes the CI permanently
   stronger. Nothing auto-merges.

## How we built it

- **Agents:** Google ADK + Gemini 2.5 Flash on Vertex AI (target agent, investigator,
  fix-author — all temperature 0, pinned model IDs).
- **Arize Phoenix:** datasets (the frozen suite), experiments (every candidate run),
  LLM-as-judge evals, OpenInference tracing (google-adk + google-genai instrumentors),
  and the **Phoenix MCP server mounted as an ADK McpToolset** — the investigator's
  runtime window into its own eval history.
- **Determinism layer:** every LLM/judge/MCP call flows through a record/replay cache,
  so the full pipeline (including the investigator's real MCP trajectory) is replayable
  offline — 103 pytest tests run with no network and no keys.
- **Surface:** a CLI (`agentci check`) and a FastAPI dashboard (deployed on Cloud Run)
  with the human approve/reject decision.

## Data sources

Synthetic SaaS-billing knowledge base + 40 support tickets with gold resolutions,
generated once with Gemini, hand-checked, and frozen into the repo (no live PII, fully
reproducible). Uploaded to Phoenix as the canonical dataset.

## Challenges and what we learned

**The judge kept failing our best fix — and it was right.** Our fix-author originally
saw only the broken prompt and the root cause, so it authored fixes blind to the
production baseline it was graded against. Giving it the baseline (recovery framing)
took held-out lift positive.

**Then we discovered our gate was impossible to pass.** The promotion gate required
zero held-out pass→fail flips. We re-sampled the *unchanged production prompt* against
its own recorded answers: lift 0.0, but 2 flips — temperature-0 on Vertex is not
reproducible, judge scores wobble ±0.1–0.2, and knife-edge cases sit at exactly the
pass threshold. **A no-op change could not pass our own gate.** So we calibrated it:
the flip budget is now the measured baseline-vs-baseline noise floor
(`scripts/calibrate_gate.py`), re-measured whenever models change. The gate's guarantee
became honest: "no more regressions than re-running production unchanged produces."
Our green run is real, live-recorded, and uncurated: lift +0.019, flips at the floor.

**Determinism is a feature.** Wrapping every model touchpoint in a record/replay cache
made a non-deterministic multi-agent system testable, demo-able, and debuggable — we
found and fixed a cache-keying bug (the prompt template wasn't part of the key) because
the discipline made it visible.

## What's next

Guard packs per failure taxonomy, PR-comment integration (gate verdicts on prompt-change
PRs), and noise-floor auto-recalibration as a scheduled job.

## Links

- Hosted demo: [CLOUD RUN URL]
- Repo: https://github.com/Ami-Khokhar/AgentCI (MIT)
- Video: [YOUTUBE URL]

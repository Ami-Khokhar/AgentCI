# Demo video script (≤ 3:00, YouTube, English)

**Recording setup:** screen-record the hosted dashboard + one terminal + one Phoenix tab.
Rehearse once; the cut that matters is the side-by-side at 0:05. Speak plainly, no music
needed. Devpost evaluates only the first 3 minutes.

---

## 0:00–0:20 — The hook (D14 beat, part 1)

*Screen: dashboard step 1, the side-by-side answers.*

> "One of these refund answers is from production. The other shipped after a one-line
> prompt edit — 'keep answers short'. It reads fine. It cites a policy. A reviewer
> skimming five outputs would approve it. It's wrong — it silently dropped the 14-day
> refund window the policy requires."

## 0:20–0:40 — The problem

*Screen: the candidate prompt diff (two lines added).*

> "Prompt changes regress AI agents silently. There's no compiler error, no failing
> unit test — the agent just gets confidently worse. AgentCI is regression CI for
> agents: every prompt change runs against a frozen eval suite before it ships."

## 0:40–1:30 — The catch + the investigator (D14 beat, part 2)

*Screen: terminal `agentci check --candidate candidates/reg_refund.txt` output (gate RED),
then dashboard step 2, then the Phoenix trace tree.*

> "The gate goes red: ten tune-set cases flipped pass-to-fail. Then a Gemini-powered
> investigator takes over — not a script. It forms a hypothesis, pulls the baseline and
> candidate experiments through the Phoenix MCP server, checks the pattern across cases,
> and names the root cause in plain English: the brevity instruction is suppressing
> required policy citations."

*Point at the Phoenix trace: the agent's `get-experiment-by-id` MCP tool spans.*

> "This is the agent introspecting its own eval history at runtime — every MCP call is
> traced in Phoenix via OpenInference."

## 1:30–2:15 — The fix and the proof

*Screen: dashboard step 3.*

> "A separate fix-author agent writes one corrective edit — it restores the full
> production contract and drops the harmful brevity constraint. Then AgentCI proves it:
> on a held-out split the candidate never trained on, scored by an independent judge the
> fix-author doesn't control. Lift is positive, and held-out flips are within the
> measured noise floor — we calibrated the gate by re-sampling unchanged production
> against itself, so the bar is 'no worse than re-running prod'. The gate goes green."

## 2:15–2:50 — Human oversight + compounding immunity

*Screen: dashboard step 4, click **Approve & mint guard case**.*

> "Nothing auto-merges. A human approves — and approval does two things: it mints this
> exact failure as a permanent eval case, and writes the lesson to Quality Memory. The
> next time any prompt change touches refund policy, the investigator starts with this
> lesson, and the minted case makes this regression structurally impossible to re-ship.
> Every caught failure makes the CI stronger."

## 2:50–3:00 — Close

*Screen: architecture diagram (architecture.html).*

> "AgentCI: Gemini and Google ADK on Vertex AI for the agents, Phoenix for datasets,
> experiments, tracing, and the MCP server the investigator thinks with. Regression CI
> that improves itself — under your oversight."

---

**Upload checklist:** YouTube (public or unlisted), English audio ✓, ≤3:00 ✓, no
third-party logos/music, paste URL into the Devpost form.

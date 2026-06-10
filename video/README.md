# AgentCI demo video (Remotion)

A ~92s Remotion video for the hackathon submission: 6 beats (intro → gotcha →
investigation → proof → oversight → outro), Google Cloud TTS narration, captions, and
dashboard-matched styling. Each content beat is a fully **animated step-scene** that shows
how the agent works — the prompt-diff gotcha, the investigator's reason-act loop querying
Phoenix over MCP (case dots flip red → investigator → MCP queries → root cause types in),
the held-out proof (bars + lift count-up + gate flips green), and the compounding-memory
loop. It renders complete with **no footage required**.

Optional: to overlay a real screen-capture clip on a beat instead of its animation, drop
footage at `public/clips/<id>.mp4` and set `CLIP_AVAILABLE.<id> = true` in `src/AgentCI.tsx`.

## Render it

```bash
cd video
npm install
npm run render        # -> out/agentci.mp4
npm run dev           # live preview in Remotion Studio
```

## Add the real footage (4 clips)

Record these at 1920×1080, drop them in `public/clips/`, then flip the matching flag in
`src/AgentCI.tsx` (`CLIP_AVAILABLE`) to `true` and re-render:

| File | Shot |
|------|------|
| `clips/a.mp4` | Dashboard step 1 — wrong vs. correct refund answer, side by side |
| `clips/b.mp4` | Terminal `agentci check` → `gate: RED` (or dashboard step 2 header) |
| `clips/d.mp4` | Dashboard step 3 — +0.0188 lift, 2 flips ≤ noise floor, gate GREEN |
| `clips/e.mp4` | Dashboard step 4 — clicking Approve & mint guard case |

(The investigation beat reuses clip B's slot; if you capture the live "Run this
investigation live" flow, use that as `b.mp4` instead.)

## Regenerate narration

Narration MP3s in `public/audio/` are produced from `narration.json` by
`video/gen_narration.py` (Google Cloud TTS, Studio voice — needs gcloud auth + the
Text-to-Speech API). Edit the script text there and re-run to change wording or voice;
it rewrites `src/narration-manifest.json` (the per-beat durations the composition reads).

```bash
uv run python video/gen_narration.py
```

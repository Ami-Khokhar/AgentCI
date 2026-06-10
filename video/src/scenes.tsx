import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AMBER, GREEN, GREEN_SOFT, HAIR, INK, INK_SOFT, MONO, PANEL, RED, RED_SOFT, SERIF } from "./theme";
import { Node, Typewriter, useCountUp, useEnter } from "./anim";

const SceneTitle: React.FC<{ children: React.ReactNode; accent?: string }> = ({ children, accent = INK }) => {
  const e = useEnter(2);
  return (
    <div style={{ ...e, fontFamily: SERIF, fontSize: 46, fontWeight: 700, color: accent, marginBottom: 36 }}>
      {children}
    </div>
  );
};

const Stage: React.FC<{ children: React.ReactNode; align?: string }> = ({ children, align = "center" }) => (
  <AbsoluteFill style={{ padding: "70px 110px 0", alignItems: align as "center", justifyContent: "flex-start" }}>
    <div style={{ width: "100%", maxWidth: 1500 }}>{children}</div>
  </AbsoluteFill>
);

// 1 — GOTCHA: prompt diff + two answers, the wrong one drops a required detail.
export const GotchaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const diff = useEnter(4);
  const candEnter = useEnter(20);
  const baseEnter = useEnter(38);
  const flash = interpolate(frame, [70, 80, 120, 130], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Stage>
      <div style={{ ...diff, fontFamily: MONO, fontSize: 24, background: PANEL, border: `1px solid ${HAIR}`, borderRadius: 10, padding: "16px 22px", marginBottom: 30 }}>
        <span style={{ color: INK_SOFT }}>system prompt&nbsp;&nbsp;</span>
        <span style={{ color: RED, fontWeight: 700 }}>+ "Answer briefly. Keep answers short."</span>
      </div>
      <div style={{ display: "flex", gap: 28 }}>
        <div style={{ ...candEnter, flex: 1, background: RED_SOFT, border: `2px solid ${RED}`, borderRadius: 12, padding: "22px 26px" }}>
          <div style={{ fontFamily: MONO, fontSize: 18, color: RED, fontWeight: 700, letterSpacing: 1 }}>✗ CANDIDATE — shipped</div>
          <div style={{ fontFamily: SERIF, fontSize: 27, color: INK, marginTop: 14, lineHeight: 1.35 }}>
            "Please refer to policy SUB-001 for refund details."
          </div>
          <div style={{ marginTop: 16, height: 30 }}>
            <span style={{ fontFamily: MONO, fontSize: 18, color: RED, background: "#fff", padding: "4px 10px", borderRadius: 6, opacity: flash, border: `1px solid ${RED}` }}>
              ✗ dropped: the 14-day refund window
            </span>
          </div>
        </div>
        <div style={{ ...baseEnter, flex: 1, background: GREEN_SOFT, border: `2px solid ${GREEN}`, borderRadius: 12, padding: "22px 26px" }}>
          <div style={{ fontFamily: MONO, fontSize: 18, color: GREEN, fontWeight: 700, letterSpacing: 1 }}>✓ BASELINE — correct</div>
          <div style={{ fontFamily: SERIF, fontSize: 27, color: INK, marginTop: 14, lineHeight: 1.35 }}>
            "Refunds are available within 14 days of purchase. (Refund Policy, SUB-001)"
          </div>
          <div style={{ marginTop: 16, height: 30, fontFamily: MONO, fontSize: 18, color: GREEN }}>✓ states the window the policy requires</div>
        </div>
      </div>
    </Stage>
  );
};

// 2 — INVESTIGATION (centerpiece): gate flips red, investigator queries Phoenix via MCP, names cause.
export const InvestigationScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 24 case dots; ~10 flip green->red between frames 20..70.
  const flippedSet = new Set([2, 5, 6, 9, 12, 14, 15, 17, 20, 21]);
  const dotsEnter = useEnter(6);

  const invEnter = useEnter(95, 0);
  const invPulse = 0.5 + 0.5 * Math.sin(frame / 6);

  // MCP query arrows fire at ~140 and ~175; counter tracks them.
  const q1 = spring({ frame: frame - 140, fps, config: { damping: 200 }, durationInFrames: 16 });
  const q2 = spring({ frame: frame - 175, fps, config: { damping: 200 }, durationInFrames: 16 });
  const mcpCount = (frame >= 150 ? 1 : 0) + (frame >= 185 ? 1 : 0);
  const phoenixEnter = useEnter(120, 0);

  return (
    <Stage align="stretch">
      <SceneTitle accent={RED}>The gate goes red — the investigator takes over.</SceneTitle>

      {/* case dots */}
      <div style={{ ...dotsEnter, display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
        {Array.from({ length: 24 }).map((_, i) => {
          const flip = flippedSet.has(i);
          const t = interpolate(frame, [20 + i * 1.5, 34 + i * 1.5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const color = flip ? `rgb(${interpolate(t, [0, 1], [63, 179])}, ${interpolate(t, [0, 1], [125, 38])}, ${interpolate(t, [0, 1], [78, 30])})` : GREEN;
          return <div key={i} style={{ width: 34, height: 34, borderRadius: 8, background: color }} />;
        })}
      </div>
      <div style={{ fontFamily: MONO, fontSize: 20, color: RED, marginBottom: 26 }}>10 / 24 cases flipped pass → fail</div>

      {/* investigator -> MCP -> Phoenix flow */}
      <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 26 }}>
        <div style={{ ...invEnter }}>
          <Node title="Regression Investigator" sub="Gemini · reason-act loop" accent={GREEN} style={{ boxShadow: `0 0 ${20 * invPulse}px ${GREEN}55, 5px 5px 0 -1px ${GREEN}22` }} />
        </div>
        {/* arrows + query labels */}
        <div style={{ flex: 1, position: "relative", height: 120, margin: "0 18px" }}>
          {[{ y: 30, s: q1, label: "get-experiment-by-id · candidate" }, { y: 78, s: q2, label: "get-experiment-by-id · baseline" }].map((a, i) => (
            <div key={i} style={{ position: "absolute", top: a.y, left: 0, right: 0 }}>
              <div style={{ height: 3, background: GREEN, width: `${a.s * 100}%`, opacity: a.s }} />
              <div style={{ fontFamily: MONO, fontSize: 15, color: INK_SOFT, marginTop: 4, opacity: a.s }}>↳ MCP · {a.label}</div>
            </div>
          ))}
        </div>
        <div style={{ ...phoenixEnter }}>
          <Node title="Phoenix" sub="experiments · traces · MCP" accent={AMBER} />
        </div>
      </div>

      <div style={{ fontFamily: MONO, fontSize: 20, color: GREEN, marginBottom: 20 }}>● MCP calls: {mcpCount}</div>

      {/* root cause types in */}
      <div style={{ background: PANEL, borderLeft: `4px solid ${INK}`, padding: "18px 24px", borderRadius: 8, minHeight: 80 }}>
        <div style={{ fontFamily: MONO, fontSize: 16, color: INK_SOFT, marginBottom: 8 }}>ROOT CAUSE</div>
        <Typewriter
          text="The 'keep answers short' instruction suppresses the policy citations correct answers require."
          delay={205}
          dur={70}
          style={{ fontFamily: SERIF, fontSize: 30, color: INK, lineHeight: 1.35 }}
        />
      </div>
    </Stage>
  );
};

// 3 — PROOF: held-out lift counts up, flips within noise floor, gate flips green.
export const ProofScene: React.FC = () => {
  const frame = useCurrentFrame();
  const lift = useCountUp(0.0188, 40, 50);
  const baseBar = interpolate(frame, [20, 50], [0, 0.62], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fixBar = interpolate(frame, [55, 90], [0, 0.64], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const gateFlip = frame > 300;
  const gatePulse = interpolate(frame, [300, 320], [0.6, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const e1 = useEnter(6);
  const e2 = useEnter(120);
  const e3 = useEnter(170);
  return (
    <Stage>
      <div style={{ ...e1, fontFamily: SERIF, fontSize: 44, fontWeight: 700, color: INK, marginBottom: 30 }}>
        Proven on the held-out split — by an independent judge.
      </div>
      <div style={{ display: "flex", gap: 60, alignItems: "flex-end" }}>
        {/* bars */}
        <div style={{ display: "flex", gap: 40, alignItems: "flex-end", height: 230 }}>
          {[{ h: baseBar, c: INK_SOFT, l: "baseline" }, { h: fixBar, c: GREEN, l: "fixed" }].map((b, i) => (
            <div key={i} style={{ textAlign: "center" }}>
              <div style={{ width: 120, height: 230, display: "flex", alignItems: "flex-end" }}>
                <div style={{ width: "100%", height: `${b.h * 100}%`, background: b.c, borderRadius: "6px 6px 0 0" }} />
              </div>
              <div style={{ fontFamily: MONO, fontSize: 18, color: INK_SOFT, marginTop: 10 }}>{b.l}</div>
            </div>
          ))}
        </div>
        {/* metrics */}
        <div style={{ flex: 1 }}>
          <div style={{ ...e2 }}>
            <div style={{ fontFamily: MONO, fontSize: 18, color: INK_SOFT }}>HELD-OUT CORRECTNESS LIFT</div>
            <div style={{ fontFamily: SERIF, fontSize: 76, fontWeight: 700, color: GREEN }}>+{lift.toFixed(4)}</div>
          </div>
          <div style={{ ...e3, marginTop: 18, fontFamily: MONO, fontSize: 22, color: INK }}>
            held-out regressions: <b>2</b> ≤ noise floor <b>2</b>
            <div style={{ fontSize: 16, color: INK_SOFT, marginTop: 6 }}>(measured by re-sampling production against itself)</div>
          </div>
        </div>
      </div>
      {/* gate flip */}
      <div style={{ marginTop: 40, display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ fontFamily: MONO, fontSize: 22, color: INK_SOFT }}>GATE</div>
        <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 700, padding: "10px 26px", borderRadius: 8, transform: `scale(${gateFlip ? gatePulse : 1})`, color: "#fff", background: gateFlip ? GREEN : RED }}>
          {gateFlip ? "● GREEN — promotable" : "● RED"}
        </div>
      </div>
    </Stage>
  );
};

// 4 — OVERSIGHT: human approves -> mint case + write memory -> loop feeds the next investigation.
export const OversightScene: React.FC = () => {
  const frame = useCurrentFrame();
  const approve = useEnter(6);
  const press = interpolate(frame, [40, 52], [1, 0.94], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pressBack = interpolate(frame, [52, 64], [0.94, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const check = frame > 60;
  const mintEnter = useEnter(90);
  const memEnter = useEnter(140);
  const loop = interpolate(frame, [200, 250], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Stage>
      <div style={{ ...approve, marginBottom: 30 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 16, transform: `scale(${frame < 52 ? press : pressBack})` }}>
          <div style={{ fontFamily: MONO, fontSize: 24, fontWeight: 700, color: "#fff", background: GREEN, padding: "14px 30px", borderRadius: 8 }}>
            Approve &amp; mint guard case
          </div>
          {check ? <div style={{ fontFamily: SERIF, fontSize: 30, color: GREEN }}>✓ human-approved</div> : null}
        </div>
      </div>
      <div style={{ display: "flex", gap: 26, alignItems: "center" }}>
        <div style={{ ...mintEnter }}>
          <Node title="Minted eval case" sub="tune partition · guarded forever" accent={GREEN} />
        </div>
        <div style={{ fontFamily: SERIF, fontSize: 34, color: INK_SOFT, opacity: memEnter.opacity }}>→</div>
        <div style={{ ...memEnter }}>
          <Node title="Quality Memory" sub="failure · root cause · lesson · fix" accent={AMBER} />
        </div>
      </div>
      {/* loop back */}
      <div style={{ marginTop: 34, opacity: loop, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ height: 3, width: 60 * loop, background: INK }} />
        <div style={{ fontFamily: SERIF, fontSize: 28, color: INK }}>
          ↺ the next investigation <i>starts</i> from this lesson — the regression can't silently return.
        </div>
      </div>
    </Stage>
  );
};

export const SCENES: Record<string, React.FC> = {
  gotcha: GotchaScene,
  investigation: InvestigationScene,
  proof: ProofScene,
  oversight: OversightScene,
};

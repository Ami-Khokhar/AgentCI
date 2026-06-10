// Small animation primitives shared across scenes.
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { INK } from "./theme";

// Spring-eased entrance: returns {opacity, translateY} for a delayed fade+rise.
export const useEnter = (delay = 0, rise = 22) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 200 }, durationInFrames: 18 });
  return { opacity: s, transform: `translateY(${(1 - s) * rise}px)` };
};

// Count a number up from 0 -> value over [delay, delay+dur] frames.
export const useCountUp = (value: number, delay: number, dur: number) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [delay, delay + dur], [0, value], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

// Reveal characters of `text` over [delay, delay+dur].
export const Typewriter: React.FC<{
  text: string;
  delay: number;
  dur: number;
  style?: React.CSSProperties;
}> = ({ text, delay, dur, style }) => {
  const frame = useCurrentFrame();
  const n = Math.round(
    interpolate(frame, [delay, delay + dur], [0, text.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const showCaret = frame > delay && frame < delay + dur;
  return (
    <span style={style}>
      {text.slice(0, n)}
      {showCaret ? <span style={{ opacity: frame % 16 < 8 ? 1 : 0, color: INK }}>▍</span> : null}
    </span>
  );
};

// A node box (agent / data store) with a label.
export const Node: React.FC<{
  title: string;
  sub?: string;
  accent: string;
  style?: React.CSSProperties;
}> = ({ title, sub, accent, style }) => (
  <div
    style={{
      background: "#FBF8F1",
      border: `2px solid ${accent}`,
      borderRadius: 12,
      padding: "18px 26px",
      boxShadow: `5px 5px 0 -1px ${accent}22`,
      textAlign: "center",
      ...style,
    }}
  >
    <div style={{ fontFamily: "Georgia, serif", fontSize: 30, fontWeight: 700, color: "#2A2722" }}>
      {title}
    </div>
    {sub ? (
      <div style={{ fontFamily: "'SF Mono', Menlo, monospace", fontSize: 16, color: "#6B6358", marginTop: 6 }}>
        {sub}
      </div>
    ) : null}
  </div>
);

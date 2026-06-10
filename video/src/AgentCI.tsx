import {
  AbsoluteFill,
  Audio,
  interpolate,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";
import manifest from "./narration-manifest.json";
import { SCENES } from "./scenes";

export const FPS = 30;

// --- Palette (matches the dashboard) ---
const CREAM = "#F4EFE6";
const INK = "#2A2722";
const INK_SOFT = "#6B6358";
const GREEN = "#3F7D4E";
const RED = "#B3261E";
const HAIR = "rgba(42,39,34,0.14)";
const SERIF = "Georgia, 'Times New Roman', serif";
const MONO = "'SF Mono', 'Menlo', monospace";

// Per-beat tail padding (seconds) so the clip/caption lingers a touch after narration.
const PAD: Record<string, number> = {
  intro: 0.7, gotcha: 1.0, investigation: 1.0, proof: 1.0, oversight: 1.0, outro: 1.2,
};

// Flip a clip to true once its footage is dropped into public/clips/<id>.mp4 (a|b|d|e).
// Until then the beat renders a labelled placeholder card, so the video is complete without footage.
const CLIP_AVAILABLE: Record<string, boolean> = {
  a: false, b: false, d: false, e: false,
};

// Per-clip placeholder copy: tells you exactly what to record for that slot.
const CLIP_LABEL: Record<string, { tag: string; shot: string }> = {
  a: { tag: "CLIP A", shot: "Dashboard step 1 — the wrong vs. correct refund answer, side by side" },
  b: { tag: "CLIP B", shot: "Terminal `agentci check` → gate: RED  (or dashboard step 2 header)" },
  d: { tag: "CLIP D", shot: "Dashboard step 3 — +0.0188 lift, 2 flips ≤ noise floor, gate GREEN" },
  e: { tag: "CLIP E", shot: "Dashboard step 4 — clicking Approve & mint guard case" },
};

type Beat = { id: string; clip: string | null; text: string; audio_sec: number };
const BEATS = manifest as Beat[];

const beatFrames = (b: Beat) => Math.ceil((b.audio_sec + (PAD[b.id] ?? 0.8)) * FPS);

export const totalDurationInFrames = () =>
  BEATS.reduce((sum, b) => sum + beatFrames(b), 0);

// Fade opacity in over `inF` frames and out over the last `outF` frames of a beat.
const useFade = (durationInFrames: number, inF = 12, outF = 14) => {
  const f = useCurrentFrame();
  return interpolate(
    f,
    [0, inF, durationInFrames - outF, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
};

const TitleCard: React.FC<{ beat: Beat; durationInFrames: number; outro?: boolean }> = ({
  beat, durationInFrames, outro,
}) => {
  const opacity = useFade(durationInFrames, 14, 16);
  const f = useCurrentFrame();
  const rise = interpolate(f, [0, 20], [18, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: CREAM, justifyContent: "center", alignItems: "center" }}>
      <div style={{ opacity, transform: `translateY(${rise}px)`, textAlign: "center", padding: "0 12%" }}>
        <div style={{ fontFamily: MONO, fontSize: 26, letterSpacing: 6, color: GREEN, marginBottom: 26 }}>
          {outro ? "● UNDER YOUR OVERSIGHT" : "● REGRESSION CI FOR AI AGENTS"}
        </div>
        <div style={{ fontFamily: SERIF, fontSize: outro ? 64 : 110, fontWeight: 700, color: INK, lineHeight: 1.08 }}>
          {outro ? beat.text.replace(/^AgentCI\.\s*/, "") : "AgentCI"}
        </div>
        {!outro && (
          <div style={{ fontFamily: SERIF, fontSize: 34, color: INK_SOFT, marginTop: 22, fontStyle: "italic" }}>
            it catches the regression a human would have approved.
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const ClipFrame: React.FC<{ beat: Beat }> = ({ beat }) => {
  const clip = beat.clip!;
  if (CLIP_AVAILABLE[clip]) {
    return (
      <OffthreadVideo
        src={staticFile(`clips/${clip}.mp4`)}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
        muted
      />
    );
  }
  const label = CLIP_LABEL[clip];
  return (
    <AbsoluteFill
      style={{
        background: `repeating-linear-gradient(135deg, #ECE5D8, #ECE5D8 22px, #E7DFD0 22px, #E7DFD0 44px)`,
        justifyContent: "center", alignItems: "center",
      }}
    >
      <div style={{ textAlign: "center", border: `2px dashed ${INK_SOFT}`, borderRadius: 10, padding: "44px 64px", background: "rgba(255,255,255,0.45)" }}>
        <div style={{ fontFamily: MONO, fontSize: 30, letterSpacing: 5, color: RED, fontWeight: 700 }}>{label.tag}</div>
        <div style={{ fontFamily: SERIF, fontSize: 30, color: INK, marginTop: 18, maxWidth: 1100 }}>{label.shot}</div>
        <div style={{ fontFamily: MONO, fontSize: 18, color: INK_SOFT, marginTop: 16 }}>drop footage at public/clips/{clip}.mp4 → set CLIP_AVAILABLE.{clip} = true</div>
      </div>
    </AbsoluteFill>
  );
};

const ContentBeat: React.FC<{ beat: Beat; durationInFrames: number }> = ({ beat, durationInFrames }) => {
  const opacity = useFade(durationInFrames);
  const Scene = SCENES[beat.id];
  // Animated step-scene fills the frame above the caption band. A real screen-capture clip,
  // when present, overlays the scene (set CLIP_AVAILABLE.<clip> = true to use footage instead).
  const useClip = beat.clip !== null && CLIP_AVAILABLE[beat.clip];
  return (
    <AbsoluteFill style={{ backgroundColor: CREAM, opacity }}>
      <AbsoluteFill style={{ bottom: 230 }}>
        {useClip ? <ClipFrame beat={beat} /> : Scene ? <Scene /> : <ClipFrame beat={beat} />}
      </AbsoluteFill>
      <AbsoluteFill style={{ top: undefined, height: 230, bottom: 0, backgroundColor: INK }}>
        <div
          style={{
            fontFamily: SERIF, fontSize: 32, lineHeight: 1.4, color: "#F4EFE6",
            padding: "30px 90px", display: "flex", alignItems: "center", height: "100%",
          }}
        >
          <span style={{ borderLeft: `4px solid ${GREEN}`, paddingLeft: 26 }}>{beat.text}</span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const AgentCI: React.FC = () => {
  let offset = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: CREAM }}>
      {BEATS.map((beat) => {
        const dur = beatFrames(beat);
        const from = offset;
        offset += dur;
        const isCard = beat.clip === null;
        return (
          <Sequence key={beat.id} from={from} durationInFrames={dur} name={beat.id}>
            <Audio src={staticFile(`audio/${beat.id}.mp3`)} />
            {isCard ? (
              <TitleCard beat={beat} durationInFrames={dur} outro={beat.id === "outro"} />
            ) : (
              <ContentBeat beat={beat} durationInFrames={dur} />
            )}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

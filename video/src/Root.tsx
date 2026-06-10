import { Composition } from "remotion";
import { AgentCI, FPS, totalDurationInFrames } from "./AgentCI";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="AgentCI"
      component={AgentCI}
      durationInFrames={totalDurationInFrames()}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};

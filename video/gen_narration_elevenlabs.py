"""Synthesize per-beat narration via ElevenLabs (free tier), write MP3s + the duration manifest the
Remotion composition reads. Drop-in alternative to gen_narration.py (Google TTS).

Setup (free):
  1. Create a free account at https://elevenlabs.io and copy your API key
     (Profile -> API Keys).
  2. (optional) Pick a voice from https://elevenlabs.io/app/voice-library and copy its Voice ID.
  3. Run from the repo root:
       export ELEVENLABS_API_KEY=sk_...
       export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM   # optional; default = Rachel
       uv run python video/gen_narration_elevenlabs.py

Then re-render:  cd video && npm run render
The composition re-times itself from the regenerated src/narration-manifest.json.
"""
import json
import os
import subprocess
from pathlib import Path

import httpx

# A few stable ElevenLabs preset voice IDs (override with ELEVENLABS_VOICE_ID):
#   Rachel  21m00Tcm4TlvDq8ikWAM (clear female narrator)
#   Adam    pNInz6obpgDQGcFmaJgB (male narrator)
#   Antoni  ErXwobaYiN019PkySvjV (warm male)
_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
_HERE = Path(__file__).resolve().parent
_AUDIO = _HERE / "public" / "audio"
_SPEC = json.loads((_HERE / "narration.json").read_text())


def _duration_seconds(mp3: Path) -> float:
    out = subprocess.run(["afinfo", str(mp3)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "estimated duration" in line:
            return round(float(line.split(":")[1].strip().split()[0]), 3)
    raise RuntimeError(f"no duration from afinfo for {mp3}")


def main():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("set ELEVENLABS_API_KEY (free key from https://elevenlabs.io)")
    _AUDIO.mkdir(parents=True, exist_ok=True)
    manifest = []
    for beat in _SPEC["beats"]:
        resp = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{_VOICE}",
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            json={
                "text": beat["text"],
                "model_id": _MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        mp3 = _AUDIO / f"{beat['id']}.mp3"
        mp3.write_bytes(resp.content)
        dur = _duration_seconds(mp3)
        manifest.append({"id": beat["id"], "clip": beat["clip"], "text": beat["text"], "audio_sec": dur})
        print(f"{beat['id']:14} {dur:6.2f}s  {mp3.name}")

    total = sum(b["audio_sec"] for b in manifest)
    (_HERE / "src" / "narration-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\ntotal narration: {total:.1f}s  (budget 180s)")


if __name__ == "__main__":
    main()

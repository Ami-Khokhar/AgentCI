"""Synthesize per-beat narration via Google Cloud Text-to-Speech (Studio voice), write MP3s +
a durations manifest the Remotion composition reads. Auth via gcloud ADC access token.

Run from repo root:  uv run python video/gen_narration.py   (needs gcloud auth + TTS API enabled)
"""
import base64
import json
import os
import subprocess
from pathlib import Path

import httpx

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-0ef442b6-21ba-4553-b28")
_HERE = Path(__file__).resolve().parent
_AUDIO = _HERE / "public" / "audio"
_SPEC = json.loads((_HERE / "narration.json").read_text())


def _token() -> str:
    return subprocess.run(["gcloud", "auth", "print-access-token"],
                          capture_output=True, text=True, check=True).stdout.strip()


def _duration_seconds(mp3: Path) -> float:
    """afinfo (macOS) — 'estimated duration: 3.456 sec'."""
    out = subprocess.run(["afinfo", str(mp3)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "estimated duration" in line:
            return round(float(line.split(":")[1].strip().split()[0]), 3)
    raise RuntimeError(f"no duration from afinfo for {mp3}")


def main():
    _AUDIO.mkdir(parents=True, exist_ok=True)
    token = _token()
    manifest = []
    for beat in _SPEC["beats"]:
        resp = httpx.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     "x-goog-user-project": _PROJECT},  # bill ADC user-cred calls to the project
            json={
                "input": {"text": beat["text"]},
                "voice": {"languageCode": "en-US", "name": _SPEC["voice"]},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0},
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        mp3 = _AUDIO / f"{beat['id']}.mp3"
        mp3.write_bytes(base64.b64decode(resp.json()["audioContent"]))
        dur = _duration_seconds(mp3)
        manifest.append({"id": beat["id"], "clip": beat["clip"], "text": beat["text"], "audio_sec": dur})
        print(f"{beat['id']:14} {dur:6.2f}s  {mp3.name}")

    total = sum(b["audio_sec"] for b in manifest)
    (_HERE / "src" / "narration-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\ntotal narration: {total:.1f}s  (budget 180s)")


if __name__ == "__main__":
    main()

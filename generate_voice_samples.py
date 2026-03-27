"""
Pre-generate sample MP3 files for all Edge TTS Indian/regional voices.
Output → static/voice_samples/<voice-name>.mp3

Run once:
    python generate_voice_samples.py

Or from the Settings page via the "Generate All Samples" button.
"""

import asyncio
import os
import sys

SAMPLE_TEXT = "Hello! I am your learning assistant. Let's explore this topic together."

VOICES = [
    # Indian English
    "en-IN-NeerjaNeural",
    "en-IN-NeerjaExpressiveNeural",
    "en-IN-PrabhatNeural",
    "en-IN-AaravNeural",
    "en-IN-AnanyaNeural",
    "en-IN-KavyaNeural",
    "en-IN-KunalNeural",
    "en-IN-RehaanNeural",
    # Hindi
    "hi-IN-SwaraNeural",
    "hi-IN-MadhurNeural",
    # Tamil
    "ta-IN-PallaviNeural",
    "ta-IN-ValluvarNeural",
    # Telugu
    "te-IN-ShrutiNeural",
    "te-IN-MohanNeural",
    # Marathi
    "mr-IN-AarohiNeural",
    "mr-IN-ManoharNeural",
    # Bengali
    "bn-IN-TanishaaNeural",
    "bn-IN-BashkarNeural",
    # Gujarati
    "gu-IN-DhwaniNeural",
    "gu-IN-NiranjanNeural",
    # Kannada
    "kn-IN-SapnaNeural",
    "kn-IN-GaganNeural",
    # Malayalam
    "ml-IN-SobhanaNeural",
    "ml-IN-MidhunNeural",
    # International
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "static", "voice_samples")


async def generate_one(voice: str, out_path: str) -> tuple[str, bool, str]:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(SAMPLE_TEXT, voice)
        await communicate.save(out_path)
        return voice, True, ""
    except Exception as e:
        return voice, False, str(e)


async def generate_all(force: bool = False):
    os.makedirs(OUT_DIR, exist_ok=True)
    tasks = []
    skipped = []
    for voice in VOICES:
        out_path = os.path.join(OUT_DIR, f"{voice}.mp3")
        if not force and os.path.exists(out_path):
            skipped.append(voice)
            continue
        tasks.append(generate_one(voice, out_path))

    results = await asyncio.gather(*tasks)

    ok, fail = [], []
    for voice, success, err in results:
        (ok if success else fail).append((voice, err))

    return {"ok": ok, "fail": fail, "skipped": skipped}


def run(force: bool = False):
    result = asyncio.run(generate_all(force=force))
    for v, _ in result["ok"]:
        print(f"  [OK]      {v}")
    for v in result["skipped"]:
        print(f"  [SKIP]    {v}  (already exists)")
    for v, e in result["fail"]:
        print(f"  [FAILED]  {v}  — {e}")
    print(f"\nDone: {len(result['ok'])} generated, "
          f"{len(result['skipped'])} skipped, {len(result['fail'])} failed.")
    return result


if __name__ == "__main__":
    force = "--force" in sys.argv
    print(f"Generating voice samples → {OUT_DIR}")
    run(force=force)

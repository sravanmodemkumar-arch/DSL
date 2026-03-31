"""TTS audio generation with word-level timestamp mapping.

Generates full-sentence TTS for natural audio, plus per-word TTS to measure
individual word durations. Word timestamps are computed by proportional mapping
of word durations onto the sentence timeline — giving word-by-word sync with
natural-sounding audio.
"""

import os
import json
import hashlib
import subprocess
import struct
import tempfile
import wave
import shutil


def _get_ffmpeg():
    """Get path to FFmpeg binary."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg") or "ffmpeg"


# ---------------------------------------------------------------------------
# Language → Voice auto-selection (edge_tts neural voices)
# ---------------------------------------------------------------------------

# Default voice per language — used when meta.language is set in JSON
LANGUAGE_VOICE_MAP = {
    # English variants
    "english":    "en-IN-PrabhatNeural",
    "en":         "en-IN-PrabhatNeural",
    "en-in":      "en-IN-PrabhatNeural",
    "en-us":      "en-US-GuyNeural",
    "en-gb":      "en-GB-RyanNeural",
    "en-au":      "en-AU-WilliamNeural",
    # Hindi
    "hindi":      "hi-IN-MadhurNeural",
    "hi":         "hi-IN-MadhurNeural",
    # Tamil
    "tamil":      "ta-IN-ValluvarNeural",
    "ta":         "ta-IN-ValluvarNeural",
    # Telugu
    "telugu":     "te-IN-MohanNeural",
    "te":         "te-IN-MohanNeural",
    # Kannada
    "kannada":    "kn-IN-GaganNeural",
    "kn":         "kn-IN-GaganNeural",
    # Malayalam
    "malayalam":  "ml-IN-MidhunNeural",
    "ml":         "ml-IN-MidhunNeural",
    # Marathi
    "marathi":    "mr-IN-ManoharNeural",
    "mr":         "mr-IN-ManoharNeural",
    # Bengali
    "bengali":    "bn-IN-BashkarNeural",
    "bn":         "bn-IN-BashkarNeural",
    "bangla":     "bn-IN-BashkarNeural",
    # Gujarati
    "gujarati":   "gu-IN-NiranjanNeural",
    "gu":         "gu-IN-NiranjanNeural",
    # Punjabi
    "punjabi":    "pa-IN-GurpreetNeural",
    "pa":         "pa-IN-GurpreetNeural",
    # Urdu
    "urdu":       "ur-IN-SalmanNeural",
    "ur":         "ur-IN-SalmanNeural",
    # Odia
    "odia":       "or-IN-SubhasiniNeural",
    "or":         "or-IN-SubhasiniNeural",
    "oriya":      "or-IN-SubhasiniNeural",
    # Assamese
    "assamese":   "as-IN-PriyomNeural",
    "as":         "as-IN-PriyomNeural",
    # Arabic
    "arabic":     "ar-SA-HamedNeural",
    "ar":         "ar-SA-HamedNeural",
    # French
    "french":     "fr-FR-HenriNeural",
    "fr":         "fr-FR-HenriNeural",
    # Spanish
    "spanish":    "es-ES-AlvaroNeural",
    "es":         "es-ES-AlvaroNeural",
    # German
    "german":     "de-DE-ConradNeural",
    "de":         "de-DE-ConradNeural",
    # Japanese
    "japanese":   "ja-JP-KeitaNeural",
    "ja":         "ja-JP-KeitaNeural",
    # Korean
    "korean":     "ko-KR-InJoonNeural",
    "ko":         "ko-KR-InJoonNeural",
    # Chinese
    "chinese":    "zh-CN-YunxiNeural",
    "zh":         "zh-CN-YunxiNeural",
    "mandarin":   "zh-CN-YunxiNeural",
    # Portuguese
    "portuguese": "pt-BR-AntonioNeural",
    "pt":         "pt-BR-AntonioNeural",
    # Russian
    "russian":    "ru-RU-DmitryNeural",
    "ru":         "ru-RU-DmitryNeural",
}


def get_voice_for_language(language, fallback_voice="en-IN-PrabhatNeural"):
    """Return the best edge_tts voice for a given language string.

    Accepts: "English", "Hindi", "tamil", "te", "en-IN", etc.
    Falls back to fallback_voice if language not recognized.
    """
    if not language:
        return fallback_voice
    key = language.strip().lower().replace(" ", "")
    return LANGUAGE_VOICE_MAP.get(key, fallback_voice)


# ---------------------------------------------------------------------------
# Global word-duration cache (avoids regenerating common words like "the")
# ---------------------------------------------------------------------------

_WORD_CACHE_DIR = None


def _get_word_cache_dir(base_dir):
    """Get or create a shared word-duration cache directory."""
    global _WORD_CACHE_DIR
    if _WORD_CACHE_DIR and os.path.isdir(_WORD_CACHE_DIR):
        return _WORD_CACHE_DIR
    _WORD_CACHE_DIR = os.path.join(base_dir, ".word_cache")
    os.makedirs(_WORD_CACHE_DIR, exist_ok=True)
    return _WORD_CACHE_DIR


def _get_word_duration(word, cache_dir, tts_engine="gtts", lang="en", tld="co.in"):
    """Get TTS duration of a single word. Uses cache to avoid re-generating."""
    key = hashlib.md5(f"{word}|{tts_engine}|{lang}|{tld}".encode()).hexdigest()[:12]
    dur_file = os.path.join(cache_dir, f"{key}.dur")
    audio_file = os.path.join(cache_dir, f"{key}.mp3")

    # Check cache
    if os.path.exists(dur_file):
        try:
            with open(dur_file, "r") as f:
                return float(f.read().strip())
        except (ValueError, IOError):
            pass

    # Generate TTS for this word
    try:
        if tts_engine == "gtts":
            from gtts import gTTS
            tts = gTTS(text=word, lang=lang, tld=tld, slow=False)
            tts.save(audio_file)
        elif tts_engine == "pyttsx3":
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            engine.save_to_file(word, audio_file)
            engine.runAndWait()
        else:
            from gtts import gTTS
            tts = gTTS(text=word, lang=lang, tld=tld, slow=False)
            tts.save(audio_file)

        duration = _get_audio_duration(audio_file)
    except Exception:
        # Fallback: estimate from word length (~0.08s per character)
        duration = max(0.2, len(word) * 0.08)

    # Cache the duration
    try:
        with open(dur_file, "w") as f:
            f.write(f"{duration:.4f}")
    except IOError:
        pass

    return duration


def _compute_word_timestamps(text, sentence_duration, cache_dir,
                             tts_engine="gtts", lang="en", tld="co.in"):
    """Compute word-level timestamps by proportional mapping.

    1. Measure each word's TTS duration individually
    2. Map proportionally onto the sentence's actual duration
    3. Returns list of {word, start, end} (relative to sentence start=0)
    """
    words = text.split()
    if not words:
        return []

    # Get duration for each word
    word_durations = []
    for w in words:
        dur = _get_word_duration(w, cache_dir, tts_engine, lang, tld)
        word_durations.append(dur)

    total_word_dur = sum(word_durations)
    if total_word_dur <= 0:
        # Even split fallback
        per_word = sentence_duration / len(words)
        return [{"word": w, "start": i * per_word, "end": (i + 1) * per_word}
                for i, w in enumerate(words)]

    # Proportional mapping: each word gets a share of sentence_duration
    # proportional to its individual TTS duration
    timestamps = []
    cursor = 0.0
    for i, w in enumerate(words):
        proportion = word_durations[i] / total_word_dur
        word_span = proportion * sentence_duration
        timestamps.append({
            "word": w,
            "start": round(cursor, 4),
            "end": round(cursor + word_span, 4),
        })
        cursor += word_span

    return timestamps


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_audio_for_question(question_data, audio_dir, tts_engine="gtts",
                                lang="en", tld="co.in"):
    """Generate audio + word timestamps for all steps in a question."""
    segments = []
    qid = question_data.get("id", "unknown")
    q_audio_dir = os.path.join(audio_dir, qid)
    os.makedirs(q_audio_dir, exist_ok=True)

    word_cache = _get_word_cache_dir(audio_dir)

    scene_index = 0
    for scene in question_data.get("scenes", []):
        scene_type = scene.get("type", "")

        # Simple scenes with direct audio
        if scene.get("audio"):
            seg = _generate_segment(
                text=scene["audio"],
                output_dir=q_audio_dir,
                filename=f"scene_{scene_index:03d}",
                tts_engine=tts_engine, lang=lang, tld=tld,
                word_cache_dir=word_cache,
            )
            seg["scene_index"] = scene_index
            seg["scene_type"] = scene_type
            seg["step_index"] = None
            segments.append(seg)

        # Scenes with steps
        for step_index, step in enumerate(scene.get("steps", [])):
            if step.get("audio"):
                seg = _generate_segment(
                    text=step["audio"],
                    output_dir=q_audio_dir,
                    filename=f"scene_{scene_index:03d}_step_{step_index:03d}",
                    tts_engine=tts_engine, lang=lang, tld=tld,
                    word_cache_dir=word_cache,
                )
                seg["scene_index"] = scene_index
                seg["scene_type"] = scene_type
                seg["step_index"] = step_index
                segments.append(seg)

        # Verdict audio
        if scene.get("verdict_audio"):
            seg = _generate_segment(
                text=scene["verdict_audio"],
                output_dir=q_audio_dir,
                filename=f"scene_{scene_index:03d}_verdict",
                tts_engine=tts_engine, lang=lang, tld=tld,
                word_cache_dir=word_cache,
            )
            seg["scene_index"] = scene_index
            seg["scene_type"] = scene_type
            seg["step_index"] = "verdict"
            segments.append(seg)

        scene_index += 1

    return segments


def _generate_segment(text, output_dir, filename, tts_engine="gtts",
                      lang="en", tld="co.in", word_cache_dir=None):
    """Generate a single audio segment with word-level timestamps.

    Returns dict with path, duration, text, and word_timestamps.
    """
    output_path = os.path.join(output_dir, f"{filename}.mp3")
    ts_path = os.path.join(output_dir, f"{filename}.words.json")

    # Check cache
    text_hash = hashlib.md5(text.encode()).hexdigest()
    cache_marker = os.path.join(output_dir, f"{filename}.hash")
    if (os.path.exists(output_path) and os.path.exists(cache_marker)
            and os.path.exists(ts_path)):
        try:
            with open(cache_marker, "r") as f:
                if f.read().strip() == text_hash:
                    duration = _get_audio_duration(output_path)
                    with open(ts_path, "r", encoding="utf-8") as f2:
                        word_ts = json.load(f2)
                    return {"path": output_path, "duration": duration,
                            "text": text, "word_timestamps": word_ts}
        except (IOError, json.JSONDecodeError):
            pass

    # Step 1: Generate TTS audio + capture word timestamps
    word_ts = []
    if tts_engine == "edge_tts":
        # edge_tts returns real word boundary timestamps — perfect sync
        word_ts = _generate_edge_tts(text, output_path, voice=tld)
    elif tts_engine == "gtts":
        _generate_gtts(text, output_path, lang, tld)
    elif tts_engine == "pyttsx3":
        _generate_pyttsx3(text, output_path)
    else:
        _generate_gtts(text, output_path, lang, tld)

    duration = _get_audio_duration(output_path)

    # Step 2: Fall back to proportional mapping if no real timestamps
    if not word_ts and word_cache_dir:
        word_ts = _compute_word_timestamps(
            text, duration, word_cache_dir, tts_engine, lang, tld)

    # Cache everything
    with open(cache_marker, "w") as f:
        f.write(text_hash)
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(word_ts, f)

    return {"path": output_path, "duration": duration,
            "text": text, "word_timestamps": word_ts}


# ---------------------------------------------------------------------------
# TTS engines
# ---------------------------------------------------------------------------

def _generate_gtts(text, output_path, lang="en", tld="co.in"):
    """Generate audio using Google TTS."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.save(output_path)
    except Exception as e:
        raise RuntimeError(f"gTTS failed: {e}")


def _generate_pyttsx3(text, output_path):
    """Generate audio using pyttsx3 (offline)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
    except Exception as e:
        raise RuntimeError(f"pyttsx3 failed: {e}")


def _generate_edge_tts(text, output_path, voice="en-IN-NeerjaNeural"):
    """Generate audio using edge_tts stream — captures real word boundary timestamps.

    Returns list of word timestamp dicts: [{word, start, end}, ...]
    These are real timings from the TTS engine (not estimated), giving perfect sync.
    """
    try:
        import asyncio
        import edge_tts
        word_events = []

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            with open(output_path, "wb") as audio_f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start_s = chunk["offset"] / 10_000_000
                        dur_s   = chunk["duration"] / 10_000_000
                        word_events.append({
                            "word":  chunk["text"],
                            "start": round(start_s, 4),
                            "end":   round(start_s + dur_s, 4),
                        })

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, _run()).result()
            else:
                loop.run_until_complete(_run())
        except RuntimeError:
            asyncio.run(_run())

        return word_events

    except Exception as e:
        raise RuntimeError(f"Edge TTS failed: {e}")


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def _get_audio_duration(audio_path):
    """Get duration of audio file using FFmpeg."""
    try:
        ffmpeg = _get_ffmpeg()
        result = subprocess.run(
            [ffmpeg, "-i", audio_path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stderr.split("\n"):
            if "Duration:" in line:
                time_str = line.split("Duration:")[1].split(",")[0].strip()
                parts = time_str.split(":")
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return 3.0


def _generate_silence_wav(duration_ms, output_path, sample_rate=44100):
    """Generate a silent WAV file."""
    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)


def concatenate_audio(segments, output_path, pause_between=300):
    """Concatenate all audio segments with pauses.

    Adjusts word_timestamps to absolute time in the combined audio.
    """
    if not segments:
        raise RuntimeError("No audio segments to concatenate")

    ffmpeg = _get_ffmpeg()
    timeline = []
    current_time = 0.0

    for seg in segments:
        duration = seg.get("duration", _get_audio_duration(seg["path"]))

        # Adjust word timestamps to absolute time
        abs_word_ts = []
        for wt in seg.get("word_timestamps", []):
            abs_word_ts.append({
                "word": wt["word"],
                "start": round(wt["start"] + current_time, 4),
                "end": round(wt["end"] + current_time, 4),
            })

        timeline.append({
            "start": current_time,
            "end": current_time + duration,
            "duration": duration,
            "scene_index": seg.get("scene_index"),
            "scene_type": seg.get("scene_type"),
            "step_index": seg.get("step_index"),
            "text": seg.get("text", ""),
            "word_timestamps": abs_word_ts,
        })
        current_time += duration + pause_between / 1000.0

    try:
        tmpdir = tempfile.mkdtemp(prefix="audio_concat_")
        silence_path = os.path.join(tmpdir, "silence.wav")
        _generate_silence_wav(pause_between, silence_path)

        silence_mp3 = os.path.join(tmpdir, "silence.mp3")
        subprocess.run(
            [ffmpeg, "-y", "-i", silence_path, "-b:a", "128k", silence_mp3],
            capture_output=True, timeout=30,
        )

        concat_list_path = os.path.join(tmpdir, "concat.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments):
                abs_path = os.path.abspath(seg["path"]).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
                if i < len(segments) - 1:
                    abs_silence = os.path.abspath(silence_mp3).replace("\\", "/")
                    f.write(f"file '{abs_silence}'\n")

        subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0",
             "-i", concat_list_path, "-c:a", "libmp3lame",
             "-b:a", "192k", output_path],
            capture_output=True, text=True, timeout=120, check=True,
        )

        total_duration = _get_audio_duration(output_path)
        shutil.rmtree(tmpdir, ignore_errors=True)

        return timeline, total_duration

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Audio concatenation failed: {e.stderr}")
    except Exception as e:
        raise RuntimeError(f"Audio concatenation failed: {e}")

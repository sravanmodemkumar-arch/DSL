"""Background music generator — 10 royalty-free meditation/ambient styles.

All music is procedurally generated using pure synthesis.
No external files needed. 100% free for YouTube/commercial use.
Designed to be very subtle — never competes with narration audio.
"""

import os
import math
import struct
import wave

# Available BGM styles
BGM_STYLES = {
    "calm_waves":    "Calm Waves — slow sine pad, like gentle ocean",
    "zen_garden":    "Zen Garden — soft pentatonic chimes",
    "morning_dew":   "Morning Dew — light airy pad with shimmer",
    "deep_focus":    "Deep Focus — low drone with subtle movement",
    "soft_piano":    "Soft Piano — gentle arpeggio pattern",
    "crystal_bowl":  "Crystal Bowl — singing bowl resonance",
    "forest_stream": "Forest Stream — layered nature-like ambience",
    "twilight":      "Twilight — warm evening pad, slow chords",
    "lotus":         "Lotus — Indian classical-inspired tanpura",
    "silent_mind":   "Silent Mind — barely-there ambient hum",
    "bansuri":       "Bansuri — Indian meditation flute, slow breathy phrases",
}


def generate_bg_music(duration_seconds, output_path, volume=0.08, style="calm_waves"):
    """Generate a soft background music track.

    Args:
        duration_seconds: float — total duration
        output_path: str — output .wav file path
        volume: float — 0.0 to 1.0, default 0.08 (very subtle)
        style: str — one of BGM_STYLES keys

    Returns:
        str — path to generated .wav file
    """
    sample_rate = 44100
    total_samples = int(duration_seconds * sample_rate)

    generators = {
        "calm_waves":    _gen_calm_waves,
        "zen_garden":    _gen_zen_garden,
        "morning_dew":   _gen_morning_dew,
        "deep_focus":    _gen_deep_focus,
        "soft_piano":    _gen_soft_piano,
        "crystal_bowl":  _gen_crystal_bowl,
        "forest_stream": _gen_forest_stream,
        "twilight":      _gen_twilight,
        "lotus":         _gen_lotus,
        "silent_mind":   _gen_silent_mind,
        "bansuri":       _gen_bansuri,
    }

    gen = generators.get(style, _gen_calm_waves)
    samples = gen(total_samples, sample_rate, volume)

    # Apply global fade in/out
    fade_samples = int(sample_rate * 2.5)
    for i in range(min(fade_samples, total_samples)):
        samples[i] *= i / fade_samples
    for i in range(min(fade_samples, total_samples)):
        samples[total_samples - 1 - i] *= i / fade_samples

    # Write WAV
    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            wf.writeframes(struct.pack("<h", int(clamped * 32767)))

    return output_path


# ---------------------------------------------------------------------------
# 10 BGM generators — all output list[float] of samples
# ---------------------------------------------------------------------------

def _gen_calm_waves(n, sr, vol):
    """Warm pad — C minor chord with chorus detuning, slow breath cycle."""
    samples = []
    # C3 minor chord: Sa(C3) Eb3 G3 — gentle, meditative
    # Each note has a detuned copy for chorus warmth
    chord = [
        (130.81, 131.11),   # C3 pair  (+0.30 Hz beating)
        (155.56, 155.90),   # Eb3 pair (+0.34 Hz)
        (196.00, 196.40),   # G3 pair  (+0.40 Hz)
    ]
    for i in range(n):
        t = i / sr
        breath = 0.72 + 0.28 * math.sin(2 * math.pi * 0.05 * t)  # 20s cycle
        s = 0.0
        for fa, fb in chord:
            s += math.sin(2 * math.pi * fa * t) * 0.20
            s += math.sin(2 * math.pi * fa * 2 * t) * 0.07
            s += math.sin(2 * math.pi * fb * t) * 0.14
        s = math.tanh(s * 1.4) / 1.4  # gentle warmth
        samples.append(s * breath * vol)
    return samples


def _gen_zen_garden(n, sr, vol):
    """Soft pentatonic chimes — random-ish bell tones."""
    samples = [0.0] * n
    # C pentatonic: C4, D4, E4, G4, A4
    notes = [261.63, 293.66, 329.63, 392.00, 440.00]
    chime_interval = int(sr * 2.5)  # one chime every 2.5 seconds

    for c in range(n // chime_interval + 1):
        start = c * chime_interval
        freq = notes[c % len(notes)]
        for j in range(min(int(sr * 2), n - start)):
            t = j / sr
            env = math.exp(-t * 1.8) * min(t * 80, 1.0)
            s = math.sin(2 * math.pi * freq * t) * 0.4
            s += math.sin(2 * math.pi * freq * 2.0 * t) * 0.2  # harmonic
            s += math.sin(2 * math.pi * freq * 3.0 * t) * 0.05
            idx = start + j
            if idx < n:
                samples[idx] += s * env * vol
    return samples


def _gen_morning_dew(n, sr, vol):
    """Light airy pad with high shimmer."""
    samples = []
    base = [196.00, 246.94, 293.66]  # G3, B3, D4
    for i in range(n):
        t = i / sr
        s = 0.0
        for f in base:
            s += math.sin(2 * math.pi * f * t) * 0.2
        # High shimmer
        shimmer = math.sin(2 * math.pi * 2093 * t) * 0.015 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.15 * t))
        s += shimmer
        # Breath
        breath = 0.7 + 0.3 * math.sin(2 * math.pi * 0.1 * t)
        samples.append(s * breath * vol)
    return samples


def _gen_deep_focus(n, sr, vol):
    """Low drone with subtle LFO movement."""
    samples = []
    base = 65.41  # C2
    for i in range(n):
        t = i / sr
        freq = base + math.sin(2 * math.pi * 0.03 * t) * 1.5
        s = math.sin(2 * math.pi * freq * t) * 0.4
        s += math.sin(2 * math.pi * freq * 2 * t) * 0.15
        s += math.sin(2 * math.pi * freq * 3 * t) * 0.05
        lfo = 0.7 + 0.3 * math.sin(2 * math.pi * 0.07 * t)
        samples.append(s * lfo * vol)
    return samples


def _gen_soft_piano(n, sr, vol):
    """Gentle arpeggio — C E G C pattern."""
    samples = [0.0] * n
    notes = [261.63, 329.63, 392.00, 523.25]
    note_dur = int(sr * 1.8)
    spacing = int(sr * 0.9)

    for idx in range(n // spacing + 1):
        start = idx * spacing
        freq = notes[idx % len(notes)]
        for j in range(min(note_dur, n - start)):
            t = j / sr
            env = math.exp(-t * 1.5) * min(t * 60, 1.0)
            s = math.sin(2 * math.pi * freq * t) * 0.4
            s += math.sin(2 * math.pi * freq * 2 * t) * 0.15
            s += math.sin(2 * math.pi * freq * 4 * t) * 0.03
            if start + j < n:
                samples[start + j] += s * env * vol
    return samples


def _gen_crystal_bowl(n, sr, vol):
    """Singing bowl resonance — long sustain, rich harmonics."""
    samples = [0.0] * n
    bowl_freq = 174.61  # F3 — heart chakra bowl
    strike_interval = int(sr * 6)  # strike every 6 seconds

    for c in range(n // strike_interval + 1):
        start = c * strike_interval
        for j in range(min(int(sr * 5.5), n - start)):
            t = j / sr
            env = math.exp(-t * 0.4) * min(t * 30, 1.0)
            s = math.sin(2 * math.pi * bowl_freq * t) * 0.3
            s += math.sin(2 * math.pi * bowl_freq * 2.0 * t) * 0.2
            s += math.sin(2 * math.pi * bowl_freq * 2.99 * t) * 0.1  # slightly inharmonic
            s += math.sin(2 * math.pi * bowl_freq * 4.07 * t) * 0.05
            # Beating effect
            s += math.sin(2 * math.pi * (bowl_freq + 0.5) * t) * 0.1
            if start + j < n:
                samples[start + j] += s * env * vol
    return samples


def _gen_forest_stream(n, sr, vol):
    """Layered ambience — low pad + gentle high texture."""
    samples = []
    for i in range(n):
        t = i / sr
        # Low bed
        low = math.sin(2 * math.pi * 110 * t) * 0.2
        low += math.sin(2 * math.pi * 165 * t) * 0.15
        # "Water" texture — multiple sine waves with phase drift
        water = 0.0
        for k in range(5):
            f = 800 + k * 317
            phase = math.sin(2 * math.pi * (0.1 + k * 0.07) * t)
            water += math.sin(2 * math.pi * f * t + phase * 3) * 0.02
        # Bird-like chirp every ~4 seconds
        chirp_phase = (t % 4.0) / 4.0
        if 0.0 < chirp_phase < 0.02:
            chirp = math.sin(2 * math.pi * 2500 * t) * 0.03 * (1 - chirp_phase / 0.02)
        else:
            chirp = 0.0
        breath = 0.7 + 0.3 * math.sin(2 * math.pi * 0.06 * t)
        samples.append((low + water + chirp) * breath * vol)
    return samples


def _gen_twilight(n, sr, vol):
    """Warm evening pad — slow chord progression with detuned chorus."""
    samples = []
    # Chords with detuned copies for richness (Indian minor feel)
    chords = [
        [220.00, 261.63, 329.63],  # Am  (A3 C4 E4)
        [196.00, 246.94, 293.66],  # G   (G3 B3 D4)
        [174.61, 220.00, 261.63],  # F   (F3 A3 C4)
        [196.00, 220.00, 293.66],  # Gsus (slow resolution)
    ]
    chord_dur = 8.0  # longer, more meditative transitions
    for i in range(n):
        t = i / sr
        ci = int(t / chord_dur) % len(chords)
        chord = chords[ci]
        pos = (t % chord_dur) / chord_dur
        # Smooth crossfade with cosine taper
        if pos < 0.08:
            fade = 0.5 - 0.5 * math.cos(math.pi * pos / 0.08)
        elif pos > 0.92:
            fade = 0.5 - 0.5 * math.cos(math.pi * (1.0 - pos) / 0.08)
        else:
            fade = 1.0
        s = 0.0
        for f in chord:
            s += math.sin(2 * math.pi * f * t) * 0.18
            s += math.sin(2 * math.pi * f * 2 * t) * 0.06
            s += math.sin(2 * math.pi * (f + 0.3) * t) * 0.10  # chorus
        s = math.tanh(s * 1.3) / 1.3
        samples.append(s * fade * vol)
    return samples


def _gen_lotus(n, sr, vol):
    """Continuous Indian tanpura drone — Sa Pa Sa' with chorus detuning and warmth.

    Real tanpura sound character:
    - Multiple slightly detuned copies of each note create warm natural beating
    - Rich harmonics (4 overtones per string)
    - Soft tanh saturation mimics the jivari (characteristic tanpura buzz/warmth)
    - Very slow breath LFO (40s cycle) — feels alive without being distracting
    - Truly continuous, no gaps or plucking cycles
    """
    samples = []

    # Tanpura tuning — C3 as Sa (deep, warm, meditative)
    # Each "string" has two slightly detuned copies — creates gentle beating
    sa1_a = 130.81   # C3  — Sa low, copy A
    sa1_b = 131.31   # C3 +0.5 Hz — creates ~0.5 Hz beating (slow, calming)
    pa_a  = 196.00   # G3  — Pa (perfect fifth)
    pa_b  = 196.50   # G3 +0.5 Hz detuned
    sa2   = 261.63   # C4  — Sa high (octave, airy)

    for i in range(n):
        t = i / sr

        # Very slow global breath — 40 second cycle
        breath = 0.82 + 0.18 * math.sin(2 * math.pi * 0.025 * t)

        # Sa low — two detuned copies, 3 harmonics each
        s  = math.sin(2 * math.pi * sa1_a * t)       * 0.26
        s += math.sin(2 * math.pi * sa1_a * 2 * t)   * 0.11
        s += math.sin(2 * math.pi * sa1_a * 3 * t)   * 0.045
        s += math.sin(2 * math.pi * sa1_b * t)       * 0.19
        s += math.sin(2 * math.pi * sa1_b * 2 * t)   * 0.07

        # Pa — two detuned copies, 2 harmonics each
        s += math.sin(2 * math.pi * pa_a  * t)       * 0.16
        s += math.sin(2 * math.pi * pa_a  * 2 * t)   * 0.06
        s += math.sin(2 * math.pi * pa_b  * t)       * 0.10
        s += math.sin(2 * math.pi * pa_b  * 2 * t)   * 0.04

        # Sa high — light overtone presence
        s += math.sin(2 * math.pi * sa2   * t)       * 0.09
        s += math.sin(2 * math.pi * sa2   * 2 * t)   * 0.03

        # Soft tanh saturation — adds warmth and jivari-like character
        # Compresses peaks slightly, introduces gentle harmonic colouring
        s = math.tanh(s * 1.6) / 1.6

        samples.append(s * breath * vol)

    return samples


def _gen_silent_mind(n, sr, vol):
    """Barely-there ambient hum — the most subtle option."""
    samples = []
    for i in range(n):
        t = i / sr
        s = math.sin(2 * math.pi * 110 * t) * 0.15
        s += math.sin(2 * math.pi * 220 * t) * 0.05
        # Ultra-slow breathing
        breath = 0.5 + 0.5 * math.sin(2 * math.pi * 0.04 * t)
        samples.append(s * breath * vol * 0.6)  # extra quiet
    return samples


def _gen_bansuri(n, sr, vol):
    """Indian meditation bansuri — phase-accurate vibrato, lowpass breath noise, slow phrases.

    Uses:
    - Phase accumulation (no vibrato phase jumps)
    - LCG pseudo-random noise lowpass-filtered to ~1.5 kHz (breath texture)
    - Raag Bhupali pentatonic: Sa Ga Pa Dha Sa' (C E G A C') — calming, meditative
    - Gentle 5 Hz vibrato with 350ms delayed onset
    - More musical phrase structure with breathing rests between phrases
    """
    samples = [0.0] * n

    # Fast LCG pseudo-random number generator (no numpy needed)
    _rng = [314159265]
    def _rand():
        _rng[0] = (_rng[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return (_rng[0] / 0x80000000) - 1.0

    # Pre-generate lowpass-filtered noise buffer — fc ≈ 1.5 kHz @ 44100 Hz
    # Single-pole IIR: y[i] = alpha*x[i] + (1-alpha)*y[i-1]
    # alpha = 0.22  →  fc ≈ 0.22 * 44100 / (2*pi) ≈ 1545 Hz
    lp_alpha = 0.22
    lp_buf = [0.0] * n
    lp_v = 0.0
    for i in range(n):
        lp_v = lp_alpha * _rand() + (1.0 - lp_alpha) * lp_v
        lp_buf[i] = lp_v

    # Raag Bhupali pentatonic: Sa(C4) Ga(E4) Pa(G4) Dha(A4) Sa'(C5)
    sa = 261.63
    scale = [sa, sa * 1.25, sa * 1.5, sa * (5.0/3.0), sa * 2.0]

    # Slow melodic phrases — (scale_index, duration_seconds)
    phrase = [
        (0, 2.5), (1, 1.8), (2, 2.2), (1, 1.5), (0, 3.5),
        (2, 2.0), (3, 2.8), (4, 3.5),
        (3, 2.0), (2, 1.8), (1, 2.5), (0, 4.0),
        (0, 2.0), (1, 2.0), (2, 2.5), (3, 2.0), (4, 3.0),
        (3, 1.5), (2, 2.0), (1, 2.5), (0, 5.0),
    ]

    # Build event timeline with natural breath gaps
    events = []
    t_cur = 1.8  # opening silence
    pi = 0
    while t_cur < n / sr - 6.0:
        ni, dur = phrase[pi % len(phrase)]
        events.append((t_cur, scale[ni], dur))
        t_cur += dur + (0.55 if dur >= 3.0 else 0.28)
        if (pi + 1) % len(phrase) == 0:
            t_cur += 2.5  # long breath between full phrase cycles
        pi += 1

    # Render each note
    for (t_start, freq, dur) in events:
        i0 = int(t_start * sr)
        nn = int(dur * sr)
        atk     = min(int(0.16 * sr), nn // 5)   # 160ms attack
        rel     = min(int(0.45 * sr), nn // 3)   # 450ms release
        vib_del = int(0.35 * sr)                  # vibrato starts 350ms in
        vib_rmp = int(0.55 * sr)                  # 550ms gradual ramp-up

        phase = 0.0
        for j in range(nn):
            idx = i0 + j
            if idx >= n:
                break

            # Amplitude envelope (power curve for soft attack, linear release)
            if j < atk:
                env = math.pow(j / atk, 0.65)
            elif j > nn - rel:
                env = max(0.0, (nn - j) / rel)
            else:
                env = 1.0

            # Vibrato: delayed onset, gradual ramp, 5 Hz
            if j > vib_del:
                vib_gain = min(1.0, (j - vib_del) / vib_rmp) * 0.0075 * freq
            else:
                vib_gain = 0.0
            inst_f = freq + vib_gain * math.sin(2 * math.pi * 5.0 * j / sr)

            # Phase accumulation — correct continuous phase (no jumps)
            phase += 2.0 * math.pi * inst_f / sr

            # Additive flute harmonics (real flute: strong fund + 2nd, weak 3rd+)
            s  = math.sin(phase)       * 0.60
            s += math.sin(2 * phase)   * 0.22
            s += math.sin(3 * phase)   * 0.09
            s += math.sin(4 * phase)   * 0.025

            # Breath noise: stronger on attack/release, subtle on sustain
            noise_gain = max(0.04, 0.22 * (1.0 - 0.65 * env))
            s += lp_buf[idx] * noise_gain

            samples[idx] += s * env * vol

    return samples


# ---------------------------------------------------------------------------
# Audio mixing
# ---------------------------------------------------------------------------

def mix_audio_with_bgm(narration_path, bgm_path, output_path, bgm_volume=0.08):
    """Mix narration audio with background music using FFmpeg.

    BGM is kept very low (default 8%) so narration dominates completely.
    Uses sidechaincompress to auto-duck BGM when narration is active.

    Args:
        narration_path: str — path to narration MP3/WAV
        bgm_path: str — path to BGM WAV
        output_path: str — output MP3 path
        bgm_volume: float — BGM volume (0.03–0.15 recommended, default 0.08)
    """
    # Clamp volume to sane range — never let BGM dominate narration
    bgm_volume = max(0.02, min(bgm_volume, 0.20))

    try:
        import subprocess
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            import shutil as _sh
            ffmpeg = _sh.which("ffmpeg") or "ffmpeg"

        # Sidechain ducking: BGM volume drops further when narration is speaking
        # sidechaincompress: threshold=-30dB, ratio=6:1, attack=200ms, release=1000ms
        # This makes BGM nearly silent during speech, slightly louder in pauses
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.4f}[bgm];"
            f"[bgm][0:a]sidechaincompress=threshold=0.02:ratio=6:attack=200:release=1000[ducked];"
            f"[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[out]"
        )

        subprocess.run(
            [ffmpeg, "-y",
             "-i", narration_path,
             "-i", bgm_path,
             "-filter_complex", filter_complex,
             "-map", "[out]",
             "-c:a", "libmp3lame", "-b:a", "192k",
             output_path],
            capture_output=True, text=True, timeout=120, check=True,
        )
        return output_path

    except Exception:
        # Fallback: simple mix without ducking (still at low volume)
        try:
            filter_simple = (
                f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.4f}[bgm];"
                f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[out]"
            )
            subprocess.run(
                [ffmpeg, "-y",
                 "-i", narration_path,
                 "-i", bgm_path,
                 "-filter_complex", filter_simple,
                 "-map", "[out]",
                 "-c:a", "libmp3lame", "-b:a", "192k",
                 output_path],
                capture_output=True, text=True, timeout=120, check=True,
            )
            return output_path
        except Exception:
            import shutil
            shutil.copy2(narration_path, output_path)
            return output_path

"""Full video generation pipeline — parallel CPU/GPU rendering + auto-cleanup."""

import os
import sys
import shutil
import subprocess
import threading
import concurrent.futures
from datetime import datetime, timezone

# ── CPU throttling — keep total usage ≤ 70% ─────────────────────────────────
# 1. Worker processes run at BELOW_NORMAL priority (Windows) / nice +10 (Unix)
# 2. CPU affinity restricted to 70% of logical cores
# 3. FFmpeg also launched at reduced priority
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_TARGET_UTIL = 0.70  # match hardware.py allocation

def _throttle_current_process():
    """Lower priority + restrict CPU affinity for current process."""
    if not _HAS_PSUTIL:
        return
    try:
        p = psutil.Process()
        # Set below-normal priority
        if sys.platform == "win32":
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
        # Restrict affinity to 70% of cores
        all_cpus = list(range(os.cpu_count() or 1))
        limit = max(1, int(len(all_cpus) * _TARGET_UTIL))
        p.cpu_affinity(all_cpus[:limit])
    except Exception:
        pass  # non-critical — best effort

def _throttle_subprocess(proc):
    """Lower priority + restrict CPU affinity for a subprocess (e.g. FFmpeg)."""
    if not _HAS_PSUTIL:
        return
    try:
        p = psutil.Process(proc.pid)
        if sys.platform == "win32":
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
        all_cpus = list(range(os.cpu_count() or 1))
        limit = max(1, int(len(all_cpus) * _TARGET_UTIL))
        p.cpu_affinity(all_cpus[:limit])
    except Exception:
        pass

# ── Module-level GPU encoding lock ────────────────────────────────────────────
# Serialises FFmpeg GPU encodes across concurrently running videos.
# CPU encodes (libx264) are NOT serialised — they run fully in parallel.
_GPU_ENCODE_LOCK = threading.Lock()

from .audio import generate_audio_for_question, concatenate_audio
from .renderer import FrameRenderer
from .sync import build_timeline, get_active_state
from .bgmusic import generate_bg_music, mix_audio_with_bgm


def _parse_bitrate_mb(bitrate_str):
    """Parse bitrate string like '25M' → 25.0 (megabits)."""
    s = bitrate_str.strip().upper()
    if s.endswith("M"):
        return float(s[:-1])
    elif s.endswith("K"):
        return float(s[:-1]) / 1000
    return float(s) / 1_000_000  # assume bits


def _min_bitrate(bitrate_str):
    """Return 40% of max bitrate as minimum floor string.
    E.g. '25M' → '10M', '10M' → '4M', '15M' → '6M'
    This prevents CRF from over-compressing static PPT content."""
    mb = _parse_bitrate_mb(bitrate_str)
    floor = max(2.0, mb * 0.40)  # at least 2Mbps, otherwise 40% of max
    return f"{floor:.0f}M"


def _double_bitrate(bitrate_str):
    """Return 2× bitrate for VBV buffer size. E.g. '25M' → '50M'."""
    mb = _parse_bitrate_mb(bitrate_str)
    return f"{mb * 2:.0f}M"
from .hardware import detect_hardware, compute_allocation


# ── Module-level worker (must be top-level to be picklable for ProcessPoolExecutor) ──

def _render_chunk(args):
    """Render a contiguous range of frames in a worker process."""
    _throttle_current_process()  # limit CPU priority + affinity in worker
    (frame_start, frame_end, fps, timeline, question_data,
     width, height, theme_colors, watermark_cfg, frames_dir) = args

    renderer = FrameRenderer(width=width, height=height,
                             theme=theme_colors, watermark=watermark_cfg)
    for frame_num in range(frame_start, frame_end):
        t = frame_num / fps
        state = get_active_state(timeline, t, question_data)
        frame = renderer.render_frame(state)
        frame.save(os.path.join(frames_dir, f"frame_{frame_num:06d}.png"), "PNG")
    return frame_end - frame_start


class VideoPipeline:
    """End-to-end pipeline: JSON → Audio → Frames (parallel) → Video (GPU/CPU)."""

    def __init__(self, config):
        self.config = config
        self.resolutions = config.get("RESOLUTIONS", {"1080p": (1920, 1080)})
        self.quality_presets = config.get("QUALITY_PRESETS", {"P5": {"bitrate": "10M", "fps": 30}})

    # ── Public ───────────────────────────────────────────────────────────────

    def process_question(self, question_data, output_dir, resolution="1080p",
                         quality_preset="P7", theme="dark", progress_callback=None,
                         frame_workers=None):
        """Process one question JSON → MP4. Auto-cleans temp files on success."""
        qid = question_data.get("id", "unknown")
        width, height = self.resolutions.get(resolution, (1920, 1080))
        preset = self.quality_presets.get(quality_preset, {"bitrate": "10M", "fps": 30})
        fps = preset.get("fps", 30)
        bitrate = preset.get("bitrate", "10M")
        crf = preset.get("crf", None)   # CRF value for quality-based encoding (P5-P7)
        question_data["_height"] = height

        os.makedirs(output_dir, exist_ok=True)
        # All temp files go inside the per-question output_dir (videos/{qid}/)
        audio_dir  = os.path.join(output_dir, "audio")
        frames_dir = os.path.join(output_dir, "frames")
        os.makedirs(audio_dir,  exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)

        result = {
            "video_id": qid, "video_path": "", "audio_path": "",
            "duration": 0, "frame_count": 0,
            "resolution": resolution, "quality_preset": quality_preset,
        }

        try:
            # ── Stage 1: TTS audio ──────────────────────────────────────────
            _cb(progress_callback, "audio_gen", 10)

            # Auto-select voice from JSON meta.language (falls back to settings)
            tts_engine = self.config.get("TTS_ENGINE", "gtts")
            settings_voice = self.config.get("TTS_TLD", "en-IN-PrabhatNeural")
            json_language = question_data.get("meta", {}).get("language", "")
            if json_language and tts_engine == "edge_tts":
                from engine.audio import get_voice_for_language
                voice = get_voice_for_language(json_language, fallback_voice=settings_voice)
            else:
                voice = settings_voice

            segments = generate_audio_for_question(
                question_data, audio_dir,
                tts_engine=tts_engine,
                lang=self.config.get("TTS_LANG", "en"),
                tld=voice,
            )
            _cb(progress_callback, "audio_gen", 30)

            # ── Stage 2: Concatenate + timeline ─────────────────────────────
            _cb(progress_callback, "timestamp_map", 35)
            raw_audio = os.path.join(output_dir, "audio.mp3")
            audio_timeline, total_duration = concatenate_audio(segments, raw_audio)
            timeline = build_timeline(question_data, audio_timeline)
            result["duration"] = total_duration

            # ── Stage 2b: BGM mix ────────────────────────────────────────────
            bgm_enabled = self.config.get("BGM_ENABLED", True)
            final_audio = raw_audio
            if bgm_enabled:
                import random as _rnd
                bgm_files = [f for f in self.config.get("BGM_FILES", []) if os.path.isfile(f)]
                if bgm_files:
                    bgm_src = _rnd.choice(bgm_files)
                else:
                    bgm_src = os.path.join(output_dir, "bgm.wav")
                    generate_bg_music(total_duration, bgm_src, volume=1.0,
                                      style=self.config.get("BGM_STYLE", "ambient"))
                mixed = os.path.join(output_dir, "mixed.mp3")
                mix_audio_with_bgm(raw_audio, bgm_src, mixed,
                                   bgm_volume=self.config.get("BGM_VOLUME", 0.08))
                final_audio = mixed
            result["audio_path"] = final_audio
            _cb(progress_callback, "timestamp_map", 40)

            # ── Stage 3: Asset resolution ────────────────────────────────────
            self._resolve_assets(question_data, timeline)

            # ── Stage 3b: Pre-render Manim animations ─────────────────────────
            self._prerender_manim_scenes(timeline, fps, height)

            # ── Stage 4: Parallel frame rendering ───────────────────────────
            _cb(progress_callback, "rendering", 45)
            theme_colors = self.config.get("THEMES", {}).get(theme) or _dark_theme()
            watermark_cfg = {
                "enabled":    self.config.get("WATERMARK_ENABLED", False),
                "text":       self.config.get("WATERMARK_TEXT", ""),
                "image_path": self.config.get("WATERMARK_IMAGE", ""),
                "opacity":    self.config.get("WATERMARK_OPACITY", 0.35),
            }
            total_frames = int(total_duration * fps)
            result["frame_count"] = total_frames

            self._render_parallel(
                timeline, total_frames, fps, question_data,
                width, height, theme_colors, watermark_cfg, frames_dir,
                progress_callback, frame_workers,
            )
            _cb(progress_callback, "rendering", 85)

            # ── Stage 5: Encode (GPU → CPU fallback) ────────────────────────
            _cb(progress_callback, "encoding", 88)
            video_path = os.path.join(output_dir, "video.mp4")
            self._encode_video(frames_dir, final_audio, video_path, fps, bitrate, width, height, frame_workers, crf=crf)
            result["video_path"] = video_path
            _cb(progress_callback, "encoding", 95)

            # ── Stage 6: Thumbnail ───────────────────────────────────────────
            thumb_path = os.path.join(output_dir, "thumb.png")
            renderer = FrameRenderer(width=width, height=height,
                                     theme=theme_colors, watermark=watermark_cfg)
            self._generate_thumbnail(timeline, question_data, renderer, thumb_path)
            result["thumbnail_path"] = thumb_path

            # ── Stage 7: Thumbnail intro prepend ────────────────────────────
            intro_secs = question_data.get("thumbnail_intro_seconds", 0)
            if intro_secs > 0 and os.path.exists(thumb_path):
                final_path = os.path.join(output_dir, "video_final.mp4")
                self._prepend_thumbnail_intro(
                    thumb_path, video_path, final_path,
                    intro_secs, fps, bitrate, width, height)
                if os.path.exists(final_path):
                    os.replace(final_path, video_path)

            # ── Cleanup: frames + all temp audio (auto after each question) ──
            shutil.rmtree(frames_dir, ignore_errors=True)
            self._cleanup_temp_audio(output_dir)
            result["audio_path"] = ""   # audio deleted; only .mp4 + thumb remain

            _cb(progress_callback, "completed", 100)
            return result

        except Exception as e:
            # Best-effort cleanup of partial files on failure — wipe the whole dir
            shutil.rmtree(output_dir, ignore_errors=True)
            result["error"] = str(e)
            _cb(progress_callback, "failed", 0)
            raise

    # ── Parallel rendering ────────────────────────────────────────────────────

    def _render_parallel(self, timeline, total_frames, fps, question_data,
                         width, height, theme_colors, watermark_cfg, frames_dir,
                         progress_callback, frame_workers=None):
        """Split frame rendering across CPU cores using separate processes.
        Uses hardware-detected 95% allocation. ProcessPoolExecutor bypasses
        the GIL for true multi-core parallelism."""
        if frame_workers is not None:
            workers = max(1, frame_workers)
        else:
            alloc = compute_allocation()
            workers = alloc["frame_workers"]

        # Divide frames into chunks — larger chunks on high-core systems
        alloc = compute_allocation()
        if alloc["chunk_strategy"] == "large":
            # Fewer, larger chunks = less IPC overhead on high-core systems
            chunk_size = max(1, (total_frames + workers - 1) // workers)
        else:
            # More, smaller chunks = better load balancing on low-core systems
            num_chunks = min(workers * 2, total_frames)
            chunk_size = max(1, (total_frames + num_chunks - 1) // num_chunks)

        chunks = []
        for start in range(0, total_frames, chunk_size):
            end = min(start + chunk_size, total_frames)
            chunks.append((
                start, end, fps, timeline, question_data,
                width, height, theme_colors, watermark_cfg, frames_dir,
            ))

        completed = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_render_chunk, c): c for c in chunks}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    completed += fut.result()
                except Exception as e:
                    raise RuntimeError(f"Frame render worker failed: {e}")
                if progress_callback:
                    pct = 45 + int(40 * completed / max(total_frames, 1))
                    progress_callback("rendering", min(pct, 84))

    # ── Encoding ──────────────────────────────────────────────────────────────

    def _encode_video(self, frames_dir, audio_path, output_path, fps, bitrate, width, height, frame_workers=None, crf=None):
        """Encode frames + audio → MP4 using hardware-detected encoder.
        GPU encodes are serialised via _GPU_ENCODE_LOCK; CPU encodes run in parallel.
        P5-P7: 2-pass ABR encoding to guarantee bitrate for static PPT content.
        P1-P4 / GPU: single-pass ABR."""
        ffmpeg = self._get_ffmpeg_path()
        alloc = compute_allocation()
        encoder = alloc["gpu_encoder"]
        enc_flags = list(alloc["gpu_encoder_flags"])
        is_gpu = alloc["is_gpu_encode"]
        enc_threads = alloc["encode_threads"]

        # Pick x264 preset and audio bitrate based on quality tier
        x264_preset = "fast"  # default for P1-P4
        audio_bitrate = "192k"
        if crf:
            crf_val = int(crf)
            if crf_val <= 18:      # P7 Maximum
                x264_preset = "slow"
                audio_bitrate = "320k"
            elif crf_val <= 20:    # P6 High Quality
                x264_preset = "medium"
                audio_bitrate = "256k"
            else:                  # P5 YouTube
                x264_preset = "medium"
                audio_bitrate = "192k"

        input_pattern = os.path.join(frames_dir, "frame_%06d.png")
        passlog = os.path.join(frames_dir, "ffmpeg2pass")

        def _exec(cmd, use_lock):
            print(f"[FFmpeg] CMD: {' '.join(cmd[:8])}... ({len(cmd)} args)")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            _throttle_subprocess(proc)
            stdout, stderr = proc.communicate(timeout=600)
            if proc.returncode != 0:
                print(f"[FFmpeg] FAILED (exit {proc.returncode}): {stderr[-500:]}")
                raise subprocess.CalledProcessError(proc.returncode, cmd,
                                                    stdout, stderr)

        def _run_2pass(enc, preset, threads, use_lock):
            """2-pass ABR encoding — forces target bitrate for consistent file sizes.
            Educational content (PPT-style static frames) needs forced bitrate
            otherwise CRF compresses too aggressively and files are tiny."""
            # Strip -preset from original flags to avoid duplicates
            extra = []
            skip = False
            for f in enc_flags:
                if skip:
                    skip = False
                    continue
                if f == "-preset":
                    skip = True
                    continue
                extra.append(f)

            # Force bitrate with tight VBV — no -tune stillimage (over-compresses)
            # Use -minrate = 60% of target to keep bitrate high even on static frames
            common = [
                "-preset", preset,
                "-b:v", bitrate,
                "-minrate", bitrate,
                "-maxrate", _double_bitrate(bitrate),
                "-bufsize", _double_bitrate(bitrate),
            ]

            # Pass 1: analysis only (no audio, output to /dev/null)
            cmd1 = [
                ffmpeg, "-y",
                "-framerate", str(fps),
                "-i", input_pattern,
                "-c:v", enc,
            ] + extra + common + [
                "-pass", "1", "-passlogfile", passlog,
                "-an", "-f", "null",
                "-threads", threads,
                "-s", f"{width}x{height}",
                os.devnull,
            ]
            if use_lock:
                with _GPU_ENCODE_LOCK:
                    _exec(cmd1, use_lock)
            else:
                _exec(cmd1, use_lock)

            # Pass 2: final encode with audio
            cmd2 = [
                ffmpeg, "-y",
                "-framerate", str(fps),
                "-i", input_pattern,
                "-i", audio_path,
                "-c:v", enc,
            ] + extra + common + [
                "-pass", "2", "-passlogfile", passlog,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", audio_bitrate,
                "-threads", threads,
                "-shortest", "-movflags", "+faststart",
                "-s", f"{width}x{height}",
                output_path,
            ]
            if use_lock:
                with _GPU_ENCODE_LOCK:
                    _exec(cmd2, use_lock)
            else:
                _exec(cmd2, use_lock)

            # Clean up passlog files
            for f in [passlog + "-0.log", passlog + "-0.log.mbtree"]:
                try:
                    os.remove(f)
                except OSError:
                    pass

        def _run_1pass(enc, flags, use_lock, threads):
            """Single-pass ABR for P1-P4 or GPU encoders."""
            cmd = [
                ffmpeg, "-y",
                "-framerate", str(fps),
                "-i", input_pattern,
                "-i", audio_path,
                "-c:v", enc,
            ] + list(flags) + [
                "-b:v", bitrate,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", audio_bitrate,
                "-threads", threads,
                "-shortest", "-movflags", "+faststart",
                "-s", f"{width}x{height}",
                output_path,
            ]
            if use_lock:
                with _GPU_ENCODE_LOCK:
                    _exec(cmd, use_lock)
            else:
                _exec(cmd, use_lock)

        try:
            if crf and not is_gpu:
                # P5-P7 on CPU: 2-pass ABR for guaranteed bitrate
                _run_2pass(encoder, x264_preset, enc_threads, use_lock=False)
            else:
                _run_1pass(encoder, enc_flags, use_lock=is_gpu, threads=enc_threads)
        except subprocess.CalledProcessError:
            if is_gpu:
                cpu_threads = str(max(1, int((os.cpu_count() or 1) * 0.70)))
                if crf:
                    _run_2pass("libx264", x264_preset, cpu_threads, use_lock=False)
                else:
                    _run_1pass("libx264", ["-preset", "fast"], use_lock=False, threads=cpu_threads)
            else:
                raise RuntimeError("FFmpeg libx264 encoding failed.")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found — install FFmpeg and add to PATH.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg encoding timed out.")

    def _prepend_thumbnail_intro(self, thumb_path, video_path, output_path,
                                 duration, fps, bitrate, width, height):
        ffmpeg = self._get_ffmpeg_path()
        try:
            proc = subprocess.Popen([
                ffmpeg, "-y",
                "-loop", "1", "-t", str(duration), "-i", thumb_path,
                "-i", video_path,
                "-filter_complex",
                f"[0:v]scale={width}:{height},fps={fps},format=yuv420p[v0];"
                f"[1:v]scale={width}:{height},fps={fps},format=yuv420p[v1];"
                f"[v0][v1]concat=n=2:v=1:a=0[vout];"
                f"aevalsrc=0:d={duration}[sil];"
                f"[sil][1:a]concat=n=2:v=0:a=1[aout]",
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast",
                "-b:v", bitrate, "-c:a", "aac", "-b:a", "192k",
                output_path,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            _throttle_subprocess(proc)
            stdout, stderr = proc.communicate(timeout=300)
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, "ffmpeg", stdout, stderr)
        except Exception:
            shutil.copy2(video_path, output_path)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _cleanup_temp_audio(self, output_dir):
        """Delete audio segments + intermediate audio files after successful render."""
        for name in ("audio", "frames"):
            p = os.path.join(output_dir, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
        for name in ("audio.mp3", "bgm.wav", "mixed.mp3"):
            path = os.path.join(output_dir, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ── Thumbnail ─────────────────────────────────────────────────────────────

    def _generate_thumbnail(self, timeline, question_data, renderer, output_path):
        from engine.renderer import generate_thumbnail as _gen_thumb
        thumb_data = question_data.get("thumbnail")
        if thumb_data:
            _gen_thumb(thumb_data, output_path,
                       width=renderer.width, height=renderer.height)
            return
        thumb_time = timeline[0]["start"] + 0.5 if timeline else 0
        for entry in timeline:
            target = entry.get("render", {}).get("target", "")
            if target in ("shortcut_columns", "formula_block", "digit_boxes",
                          "equation", "table", "final_answer") or \
               entry.get("scene_type") == "concept":
                thumb_time = entry["start"] + 0.2
                break
        state = get_active_state(timeline, thumb_time, question_data)
        state["progress"] = 0
        renderer.render_frame(state).save(output_path, "PNG")

    # ── Assets ────────────────────────────────────────────────────────────────

    def _resolve_assets(self, question_data, timeline):
        assets = question_data.get("assets", {})
        assets_dir = self.config.get("ASSETS_DIR", "storage/assets")
        asset_map = {}
        for category in ("images", "svgs", "videos", "audio_clips"):
            for key, path in assets.get(category, {}).items():
                asset_map[key] = os.path.join(assets_dir, path.lstrip("/"))

        subject = question_data.get("subject", "")

        for entry in timeline:
            render = entry.get("render", {})
            target = render.get("target", "")

            # Standard asset reference resolution
            src = render.get("src")
            if src and src in asset_map:
                render["src_path"] = asset_map[src]

            # subject_image — direct URL first, then search providers
            if target == "subject_image" and not render.get("src_path"):
                try:
                    from engine.free_media import resolve_media
                    img_cache = os.path.join(assets_dir, "images")
                    path = resolve_media(
                        query=render.get("query", ""),
                        media_type="image",
                        subject=render.get("subject", subject),
                        topic_hint=render.get("topic", ""),
                        cache_dir=img_cache,
                        url=render.get("url", ""),
                    )
                    if path:
                        render["src_path"] = path
                except Exception:
                    pass

            # video_clip — direct URL first, then search providers
            if target == "video_clip" and not render.get("src_path"):
                try:
                    from engine.free_media import resolve_media
                    vid_cache = os.path.join(assets_dir, "videos")
                    path = resolve_media(
                        query=render.get("query", render.get("caption", "")),
                        media_type="video",
                        subject=render.get("subject", subject),
                        topic_hint=render.get("topic", ""),
                        cache_dir=vid_cache,
                        url=render.get("url", ""),
                    )
                    if path:
                        render["src_path"] = path
                except Exception:
                    pass

            # web_image / web_gif — download from direct URL
            if target in ("web_image", "web_gif") and not render.get("src_path"):
                url = render.get("url", "")
                if url:
                    try:
                        img_cache = os.path.join(assets_dir, "web_images")
                        os.makedirs(img_cache, exist_ok=True)
                        import hashlib, urllib.request
                        ext = os.path.splitext(url.split("?")[0])[-1] or ".png"
                        fname = hashlib.md5(url.encode()).hexdigest() + ext
                        local_path = os.path.join(img_cache, fname)
                        if not os.path.exists(local_path):
                            urllib.request.urlretrieve(url, local_path)
                        if os.path.exists(local_path):
                            render["src_path"] = local_path
                    except Exception:
                        pass

            # web_video — download video from URL
            if target == "web_video" and not render.get("src_path"):
                url = render.get("url", "")
                if url:
                    try:
                        vid_cache = os.path.join(assets_dir, "web_videos")
                        os.makedirs(vid_cache, exist_ok=True)
                        import hashlib, urllib.request
                        ext = os.path.splitext(url.split("?")[0])[-1] or ".mp4"
                        fname = hashlib.md5(url.encode()).hexdigest() + ext
                        local_path = os.path.join(vid_cache, fname)
                        if not os.path.exists(local_path):
                            urllib.request.urlretrieve(url, local_path)
                        if os.path.exists(local_path):
                            render["src_path"] = local_path
                    except Exception:
                        pass

            # google_image — search + download via free_media providers
            if target == "google_image" and not render.get("src_path"):
                try:
                    from engine.free_media import resolve_media
                    img_cache = os.path.join(assets_dir, "google_images")
                    path = resolve_media(
                        query=render.get("query", render.get("caption", "")),
                        media_type="image",
                        subject=render.get("subject", subject),
                        topic_hint=render.get("topic", ""),
                        cache_dir=img_cache,
                        url=render.get("url", ""),
                    )
                    if path:
                        render["src_path"] = path
                except Exception:
                    pass

            # person_card — resolve image URL for profile photo
            if target == "person_card" and not render.get("src_path"):
                url = render.get("image_url", render.get("url", ""))
                if url:
                    try:
                        img_cache = os.path.join(assets_dir, "web_images")
                        os.makedirs(img_cache, exist_ok=True)
                        import hashlib, urllib.request
                        ext = os.path.splitext(url.split("?")[0])[-1] or ".png"
                        fname = hashlib.md5(url.encode()).hexdigest() + ext
                        local_path = os.path.join(img_cache, fname)
                        if not os.path.exists(local_path):
                            urllib.request.urlretrieve(url, local_path)
                        if os.path.exists(local_path):
                            render["src_path"] = local_path
                    except Exception:
                        pass

    # ── Manim pre-rendering ──────────────────────────────────────────────────

    def _prerender_manim_scenes(self, timeline, fps, height):
        """Pre-render any manim_scene steps to cached PNG frame sequences.

        Injects _manim_cache_dir, _manim_total_frames, _step_start, _step_end
        into each timeline entry's render dict so the FrameRenderer can read
        the correct animation frame at any given time.
        """
        has_manim = False
        for entry in timeline:
            if entry.get("render", {}).get("target") == "manim_scene":
                has_manim = True
                break
        if not has_manim:
            return

        try:
            from engine.manim_renderer import prerender_scene, MANIM_AVAILABLE
            if not MANIM_AVAILABLE:
                return
        except ImportError:
            return

        ffmpeg_path = self._get_ffmpeg_path()
        # Scale render size proportionally to video height
        render_w = int(height * 1.5)
        render_h = height

        for entry in timeline:
            render = entry.get("render", {})
            if render.get("target") != "manim_scene":
                continue

            scene_type = render.get("scene_type", "")
            params = render.get("params", {})
            step_start = entry.get("start", 0)
            step_end = entry.get("end", step_start + 3)
            duration_s = max(step_end - step_start, 1.0)

            cache_dir, total_frames = prerender_scene(
                scene_type=scene_type,
                params=params,
                duration_s=duration_s,
                fps=fps,
                width=render_w,
                height=render_h,
                ffmpeg_path=ffmpeg_path,
            )

            # Inject cache info into render dict — passes through to FrameRenderer
            render["_manim_cache_dir"] = cache_dir
            render["_manim_total_frames"] = total_frames
            render["_step_start"] = step_start
            render["_step_end"] = step_end

    # ── FFmpeg path ───────────────────────────────────────────────────────────

    def _get_ffmpeg_path(self):
        custom = self.config.get("FFMPEG_PATH", "")
        if custom and os.path.exists(custom):
            return custom
        found = shutil.which("ffmpeg")
        if found:
            return found
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            return "ffmpeg"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cb(fn, stage, pct):
    if fn:
        fn(stage, pct)


def _dark_theme():
    return {
        "bg": "#0f0f23", "card_bg": "#1a1a2e", "text": "#ffffff",
        "text_secondary": "#a0a0b8", "accent": "#00d4ff",
        "success": "#00ff88", "warning": "#ffaa00", "error": "#ff4444",
        "formula_bg": "#2a2a4a", "highlight": "#00d4ff", "border": "#2a2a4a",
    }

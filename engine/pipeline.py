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
        question_data["_height"] = height

        os.makedirs(output_dir, exist_ok=True)
        # Per-video temp dirs — avoids collisions when multiple videos share same output_dir
        audio_dir  = os.path.join(output_dir, f"audio_{qid}")
        frames_dir = os.path.join(output_dir, f"frames_{qid}")
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
            segments = generate_audio_for_question(
                question_data, audio_dir,
                tts_engine=self.config.get("TTS_ENGINE", "gtts"),
                lang=self.config.get("TTS_LANG", "en"),
                tld=self.config.get("TTS_TLD", "co.in"),
            )
            _cb(progress_callback, "audio_gen", 30)

            # ── Stage 2: Concatenate + timeline ─────────────────────────────
            _cb(progress_callback, "timestamp_map", 35)
            raw_audio = os.path.join(output_dir, f"{qid}_audio.mp3")
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
                    bgm_src = os.path.join(output_dir, f"{qid}_bgm.wav")
                    generate_bg_music(total_duration, bgm_src, volume=1.0,
                                      style=self.config.get("BGM_STYLE", "ambient"))
                mixed = os.path.join(output_dir, f"{qid}_mixed.mp3")
                mix_audio_with_bgm(raw_audio, bgm_src, mixed,
                                   bgm_volume=self.config.get("BGM_VOLUME", 0.30))
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
            video_path = os.path.join(output_dir, f"{qid}.mp4")
            self._encode_video(frames_dir, final_audio, video_path, fps, bitrate, width, height, frame_workers)
            result["video_path"] = video_path
            _cb(progress_callback, "encoding", 95)

            # ── Stage 6: Thumbnail ───────────────────────────────────────────
            thumb_path = os.path.join(output_dir, f"{qid}_thumb.png")
            renderer = FrameRenderer(width=width, height=height,
                                     theme=theme_colors, watermark=watermark_cfg)
            self._generate_thumbnail(timeline, question_data, renderer, thumb_path)
            result["thumbnail_path"] = thumb_path

            # ── Stage 7: Thumbnail intro prepend ────────────────────────────
            intro_secs = question_data.get("thumbnail_intro_seconds", 0)
            if intro_secs > 0 and os.path.exists(thumb_path):
                final_path = os.path.join(output_dir, f"{qid}_final.mp4")
                self._prepend_thumbnail_intro(
                    thumb_path, video_path, final_path,
                    intro_secs, fps, bitrate, width, height)
                if os.path.exists(final_path):
                    os.replace(final_path, video_path)

            # ── Cleanup: frames + all temp audio (auto after each question) ──
            shutil.rmtree(frames_dir, ignore_errors=True)
            self._cleanup_temp_audio(qid, output_dir)
            result["audio_path"] = ""   # audio deleted; only .mp4 + thumb remain

            _cb(progress_callback, "completed", 100)
            return result

        except Exception as e:
            # Best-effort cleanup of all partial files on failure
            shutil.rmtree(frames_dir, ignore_errors=True)
            self._cleanup_temp_audio(qid, output_dir)
            for fname in (f"{qid}.mp4", f"{qid}_thumb.png", f"{qid}_final.mp4"):
                p = os.path.join(output_dir, fname)
                try:
                    os.remove(p)
                except OSError:
                    pass
            # Remove output_dir only if now completely empty
            try:
                if not os.listdir(output_dir):
                    os.rmdir(output_dir)
            except OSError:
                pass
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

    def _encode_video(self, frames_dir, audio_path, output_path, fps, bitrate, width, height, frame_workers=None):
        """Encode frames + audio → MP4 using hardware-detected encoder.
        GPU encodes are serialised via _GPU_ENCODE_LOCK; CPU encodes run in parallel."""
        ffmpeg = self._get_ffmpeg_path()
        alloc = compute_allocation()
        encoder = alloc["gpu_encoder"]
        enc_flags = list(alloc["gpu_encoder_flags"])
        is_gpu = alloc["is_gpu_encode"]
        enc_threads = alloc["encode_threads"]

        def _run(enc, flags, use_lock, threads):
            cmd = [
                ffmpeg, "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frames_dir, "frame_%06d.png"),
                "-i", audio_path,
                "-c:v", enc,
            ] + flags + [
                "-b:v", bitrate,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-threads", threads,
                "-shortest", "-movflags", "+faststart",
                "-s", f"{width}x{height}",
                output_path,
            ]

            def _exec(cmd):
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
                _throttle_subprocess(proc)  # limit FFmpeg CPU priority + affinity
                stdout, stderr = proc.communicate(timeout=600)
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, cmd,
                                                        stdout, stderr)

            if use_lock:
                with _GPU_ENCODE_LOCK:   # one GPU encode at a time
                    _exec(cmd)
            else:
                _exec(cmd)

        try:
            _run(encoder, enc_flags, use_lock=is_gpu, threads=enc_threads)
        except subprocess.CalledProcessError:
            # GPU failed — fall back to CPU (no lock needed)
            if is_gpu:
                cpu_threads = str(max(1, int((os.cpu_count() or 1) * 0.70)))
                _run("libx264", ["-preset", "fast"], use_lock=False, threads=cpu_threads)
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

    def _cleanup_temp_audio(self, qid, output_dir):
        """Delete audio segments + intermediate audio files after successful render."""
        audio_dir = os.path.join(output_dir, f"audio_{qid}")
        if os.path.isdir(audio_dir):
            shutil.rmtree(audio_dir, ignore_errors=True)
        for suffix in (f"{qid}_audio.mp3", f"{qid}_bgm.wav", f"{qid}_mixed.mp3"):
            path = os.path.join(output_dir, suffix)
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

            # subject_image — fetch from Pixabay if not already cached
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
                    )
                    if path:
                        render["src_path"] = path
                except Exception:
                    pass

            # video_clip — fetch from Pixabay if src_path missing
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
                    )
                    if path:
                        render["src_path"] = path
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

"""Full video generation pipeline — orchestrates audio, sync, rendering, encoding."""

import os
import json
import subprocess
import tempfile
import shutil
from datetime import datetime, timezone

from .validator import validate_json
from .audio import generate_audio_for_question, concatenate_audio
from .renderer import FrameRenderer
from .sync import build_timeline, get_active_state
from .bgmusic import generate_bg_music, mix_audio_with_bgm


class VideoPipeline:
    """End-to-end pipeline: JSON → Audio → Frames → Video."""

    def __init__(self, config):
        self.config = config
        self.resolutions = config.get("RESOLUTIONS", {"1080p": (1920, 1080)})
        self.quality_presets = config.get("QUALITY_PRESETS", {"P5": {"bitrate": "10M", "fps": 30}})

    def process_question(self, question_data, output_dir, resolution="1080p",
                         quality_preset="P5", theme="dark", progress_callback=None):
        """Process a single question JSON into a video file.

        Args:
            question_data: dict — single question object
            output_dir: str — directory to save output
            resolution: str — resolution key
            quality_preset: str — quality preset key
            theme: str — dark/light
            progress_callback: callable(stage, percent) — progress reporter

        Returns:
            dict with video_path, audio_path, duration, etc.
        """
        qid = question_data.get("id", "unknown")
        width, height = self.resolutions.get(resolution, (1920, 1080))
        preset = self.quality_presets.get(quality_preset, {"bitrate": "10M", "fps": 30})
        fps = preset.get("fps", 30)
        bitrate = preset.get("bitrate", "10M")

        # Store height for position calculations
        question_data["_height"] = height

        os.makedirs(output_dir, exist_ok=True)
        audio_dir = os.path.join(output_dir, "audio")
        frames_dir = os.path.join(output_dir, "frames")
        os.makedirs(audio_dir, exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)

        result = {
            "video_id": qid,
            "video_path": "",
            "audio_path": "",
            "duration": 0,
            "frame_count": 0,
            "resolution": resolution,
            "quality_preset": quality_preset,
        }

        try:
            # Stage 1: Generate audio
            if progress_callback:
                progress_callback("audio_gen", 10)

            tts_engine = self.config.get("TTS_ENGINE", "gtts")
            tts_lang = self.config.get("TTS_LANG", "en")
            tts_tld = self.config.get("TTS_TLD", "co.in")

            segments = generate_audio_for_question(
                question_data, audio_dir,
                tts_engine=tts_engine, lang=tts_lang, tld=tts_tld
            )

            if progress_callback:
                progress_callback("audio_gen", 30)

            # Stage 2: Concatenate audio + build timeline
            if progress_callback:
                progress_callback("timestamp_map", 35)

            combined_audio_path = os.path.join(output_dir, f"{qid}_audio.mp3")
            audio_timeline, total_duration = concatenate_audio(segments, combined_audio_path)

            timeline = build_timeline(question_data, audio_timeline)

            result["duration"] = total_duration

            # Stage 2b: Generate background music and mix
            bgm_enabled = self.config.get("BGM_ENABLED", True)
            bgm_style = self.config.get("BGM_STYLE", "ambient")
            bgm_volume = self.config.get("BGM_VOLUME", 0.15)

            if bgm_enabled:
                # Pick a random file from BGM_FILES list, fallback to procedural
                import random as _random
                bgm_files = self.config.get("BGM_FILES", [])
                valid_files = [f for f in bgm_files if os.path.isfile(f)]
                if valid_files:
                    bgm_path = _random.choice(valid_files)
                else:
                    bgm_path = os.path.join(output_dir, f"{qid}_bgm.wav")
                    generate_bg_music(total_duration, bgm_path, volume=1.0, style=bgm_style)

                mixed_audio_path = os.path.join(output_dir, f"{qid}_mixed.mp3")
                mix_audio_with_bgm(combined_audio_path, bgm_path, mixed_audio_path, bgm_volume=bgm_volume)

                # Use mixed audio for video
                result["audio_path"] = mixed_audio_path
                combined_audio_path = mixed_audio_path
            else:
                result["audio_path"] = combined_audio_path

            if progress_callback:
                progress_callback("timestamp_map", 40)

            # Stage 3: Resolve asset paths in renders
            self._resolve_assets(question_data, timeline)

            # Stage 4: Render frames
            if progress_callback:
                progress_callback("rendering", 45)

            theme_colors = self.config.get("THEMES", {}).get(theme)
            if not theme_colors:
                # Fallback dark theme
                theme_colors = {
                    "bg": "#0f0f23", "card_bg": "#1a1a2e", "text": "#ffffff",
                    "text_secondary": "#a0a0b8", "accent": "#00d4ff",
                    "success": "#00ff88", "warning": "#ffaa00", "error": "#ff4444",
                    "formula_bg": "#2a2a4a", "highlight": "#00d4ff", "border": "#2a2a4a",
                }
            watermark_cfg = {
                "enabled":    self.config.get("WATERMARK_ENABLED", False),
                "text":       self.config.get("WATERMARK_TEXT", ""),
                "image_path": self.config.get("WATERMARK_IMAGE", ""),
                "opacity":    self.config.get("WATERMARK_OPACITY", 0.35),
            }
            renderer = FrameRenderer(width=width, height=height, theme=theme_colors,
                                     watermark=watermark_cfg)

            total_frames = int(total_duration * fps)
            result["frame_count"] = total_frames

            for frame_num in range(total_frames):
                current_time = frame_num / fps
                state = get_active_state(timeline, current_time, question_data)
                frame = renderer.render_frame(state)

                frame_path = os.path.join(frames_dir, f"frame_{frame_num:06d}.png")
                frame.save(frame_path, "PNG")

                if progress_callback and frame_num % (fps * 2) == 0:
                    render_progress = 45 + int(40 * frame_num / max(total_frames, 1))
                    progress_callback("rendering", min(render_progress, 85))

            if progress_callback:
                progress_callback("rendering", 85)

            # Stage 5: Encode video with FFmpeg
            if progress_callback:
                progress_callback("encoding", 88)

            video_path = os.path.join(output_dir, f"{qid}.mp4")
            self._encode_video(
                frames_dir=frames_dir,
                audio_path=combined_audio_path,
                output_path=video_path,
                fps=fps,
                bitrate=bitrate,
                width=width,
                height=height,
            )

            result["video_path"] = video_path

            if progress_callback:
                progress_callback("encoding", 95)

            # Stage 6: Generate thumbnail
            thumb_path = os.path.join(output_dir, f"{qid}_thumb.png")
            self._generate_thumbnail(timeline, question_data, renderer, thumb_path)
            result["thumbnail_path"] = thumb_path

            # Stage 7: Prepend thumbnail intro if requested
            intro_secs = question_data.get("thumbnail_intro_seconds", 0)
            if intro_secs > 0 and os.path.exists(thumb_path):
                final_path = os.path.join(output_dir, f"{qid}_final.mp4")
                self._prepend_thumbnail_intro(
                    thumb_path, video_path, final_path,
                    intro_secs, fps, bitrate, width, height
                )
                if os.path.exists(final_path):
                    os.replace(final_path, video_path)

            # Cleanup frames
            shutil.rmtree(frames_dir, ignore_errors=True)

            if progress_callback:
                progress_callback("completed", 100)

            return result

        except Exception as e:
            result["error"] = str(e)
            if progress_callback:
                progress_callback("failed", 0)
            raise

    def _resolve_assets(self, question_data, timeline):
        """Resolve asset keys to full file paths in timeline render entries."""
        assets = question_data.get("assets", {})
        assets_dir = self.config.get("ASSETS_DIR", "storage/assets")

        asset_map = {}
        for category in ("images", "svgs", "videos", "audio_clips"):
            for key, path in assets.get(category, {}).items():
                full_path = os.path.join(assets_dir, path.lstrip("/"))
                asset_map[key] = full_path

        for entry in timeline:
            render = entry.get("render", {})
            src = render.get("src")
            if src and src in asset_map:
                render["_resolved_path"] = asset_map[src]

    def _get_ffmpeg_path(self):
        """Find FFmpeg binary — check config, PATH, then imageio_ffmpeg fallback."""
        custom = self.config.get("FFMPEG_PATH", "")
        if custom and os.path.exists(custom):
            return custom
        # Try system PATH
        import shutil
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        # Fallback: imageio_ffmpeg package
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            return "ffmpeg"

    def _encode_video(self, frames_dir, audio_path, output_path, fps, bitrate, width, height):
        """Encode frames + audio into MP4 using FFmpeg."""
        ffmpeg_bin = self._get_ffmpeg_path()
        ffmpeg_cmd = [
            ffmpeg_bin, "-y",
            "-framerate", str(fps),
            "-i", os.path.join(frames_dir, "frame_%06d.png"),
            "-i", audio_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-b:v", bitrate,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            "-s", f"{width}x{height}",
            output_path,
        ]

        try:
            subprocess.run(
                ffmpeg_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Install FFmpeg and add to PATH.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg encoding failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg encoding timed out (10 min limit)")

    def _prepend_thumbnail_intro(self, thumb_path, video_path, output_path,
                                    duration, fps, bitrate, width, height):
        """Prepend thumbnail as a silent still-image clip before the main video."""
        try:
            ffmpeg = self._get_ffmpeg_path()
            subprocess.run([
                ffmpeg, "-y",
                # Input 1: thumbnail still image held for `duration` seconds
                "-loop", "1", "-t", str(duration),
                "-i", thumb_path,
                # Input 2: main video
                "-i", video_path,
                # Concat: 1 video+audio segment from thumb (silent), 1 from video
                "-filter_complex",
                f"[0:v]scale={width}:{height},fps={fps},format=yuv420p[v0];"
                f"[1:v]scale={width}:{height},fps={fps},format=yuv420p[v1];"
                f"[v0][v1]concat=n=2:v=1:a=0[vout];"
                f"aevalsrc=0:d={duration}[sil];"
                f"[sil][1:a]concat=n=2:v=0:a=1[aout]",
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-b:v", bitrate,
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ], capture_output=True, text=True, timeout=300, check=True)
        except Exception as e:
            # If prepend fails, keep original video
            import shutil as _sh
            _sh.copy2(video_path, output_path)

    def _generate_thumbnail(self, timeline, question_data, renderer, output_path):
        """Generate thumbnail.

        If question_data has a 'thumbnail' block, use the standalone designer.
        Otherwise fall back to extracting the most visually rich video frame.
        """
        from engine.renderer import generate_thumbnail as _gen_thumb

        thumb_data = question_data.get("thumbnail")
        if thumb_data:
            _gen_thumb(thumb_data, output_path,
                       width=renderer.width, height=renderer.height)
            return

        # Fallback: extract best frame from timeline
        thumb_time = timeline[0]["start"] + 0.5 if timeline else 0
        for entry in timeline:
            target = entry.get("render", {}).get("target", "")
            scene  = entry.get("scene_type", "")
            if target in ("shortcut_columns", "formula_block", "digit_boxes",
                          "equation", "table", "final_answer") or scene == "concept":
                thumb_time = entry["start"] + 0.2
                break

        state = get_active_state(timeline, thumb_time, question_data)
        state["progress"] = 0
        frame = renderer.render_frame(state)
        frame.save(output_path, "PNG")

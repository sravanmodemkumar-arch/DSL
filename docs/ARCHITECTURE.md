# Architecture

## System Overview

The STEM Video Generator follows a pipeline architecture where JSON input flows through discrete stages to produce a final MP4 video.

```
JSON Input
    |
    v
[Validation] --> Error response if invalid
    |
    v
[Audio Generation] --> TTS segments with word timestamps
    |
    v
[Timeline Sync] --> Master timeline mapping audio to visuals
    |
    v
[Asset Resolution] --> Fetch/cache images, videos, media
    |
    v
[Manim Pre-render] --> Pre-render animated scenes to PNG frames
    |
    v
[Frame Rendering] --> Parallel Pillow frame generation (N workers)
    |
    v
[Video Encoding] --> FFmpeg H.264 encoding (GPU -> CPU fallback)
    |
    v
[BGM Mixing] --> Background music overlay
    |
    v
MP4 Output
```

---

## Pipeline Stages

### Stage 1: Audio Generation (`engine/audio.py`)

- Reads all `audio` fields from scenes and steps
- Generates TTS audio segments using Edge TTS (primary) or gTTS (fallback)
- Extracts word-level timestamps for karaoke-style narration sync
- Outputs: list of audio segments with `(scene_index, step_index, start, end, word_timestamps)`

### Stage 2: Timeline Building (`engine/sync.py`)

- `build_timeline()` maps audio segments to render instructions using `(scene_idx, step_idx)` lookup
- Prevents sync drift by using lookup-based matching instead of sequential iteration
- Non-audio scenes get estimated durations based on surrounding audio
- Outputs: ordered timeline of `{start, end, scene_index, step_index, render, audio_text, word_timestamps}`

### Stage 3: Asset Resolution (`engine/pipeline.py`)

- Resolves `src` references to file paths via asset map
- Auto-fetches `subject_image` and `video_clip` from free providers (Pixabay, Wikimedia, Pexels, Unsplash)
- Caches fetched media in `storage/assets/`

### Stage 3b: Manim Pre-rendering (`engine/manim_renderer.py`)

- Scans timeline for `manim_scene` targets
- Generates Python source for each scene template
- Runs `manim render` CLI to produce MP4
- Extracts PNG frame sequences with FFmpeg
- Caches in `storage/cache/manim/{hash}/`
- Injects cache paths and frame counts into timeline entries

### Stage 4: Frame Rendering (`engine/renderer.py`)

- `FrameRenderer` creates each frame using Pillow
- Runs in parallel across N workers (auto-scales to CPU cores)
- Each frame:
  1. Computes `get_active_state(timeline, current_time)` from `sync.py`
  2. Draws mode-aware header (question/options or title bar)
  3. Draws accumulated body elements (concept_text, equations, visuals, etc.)
  4. Draws narration bar with word-level karaoke highlighting
  5. Draws progress bar and branding

### Stage 5: Video Encoding (`engine/pipeline.py`)

- Assembles PNG frames into MP4 using FFmpeg
- Tries GPU encoding (h264_nvenc) first, falls back to CPU (libx264)
- Applies quality preset settings (bitrate, fps)
- Mixes in background music from `storage/assets/bgm/`

---

## State Accumulation Model

The visual state is computed by `get_active_state()` in `sync.py`. Elements accumulate on screen using a target-type keyed dictionary:

```python
work_elements = {}  # target_type -> element data

# Same target replaces previous value:
work_elements["equation"] = {"type": "equation", "value": "x = 3"}

# Different targets coexist:
work_elements["digit_boxes"] = {"type": "digit_boxes", "data": [1, 0, 0, 9, 8]}
work_elements["running_sum"] = {"type": "running_sum", "value": "18"}
```

Special behaviors:
- `instruction_text` clears ALL body elements (section transition)
- `shortcut_columns` and `concept_text` are mutually exclusive
- `final_answer` sets `show_correct = True` permanently

---

## Mode-Aware Rendering

The `mode` field controls header layout:

| Mode | Header Method | Header Height |
|------|--------------|---------------|
| mcq, true_false | `_draw_header()` | ~260px |
| topic | `_draw_topic_bar()` | ~100px |
| match, sequence | `_draw_minimal_bar()` | ~70px |
| numerical | `_draw_numerical_header()` | ~120px |
| assertion | `_draw_assertion_header()` | ~180px |

Each header method returns `body_top` so the body area dynamically adjusts.

---

## Database Schema

Three SQLAlchemy models in `models.py`:

**Video** -- One record per generated video
- Stores metadata, file paths, status, YouTube info
- Organized by subject/chapter/topic hierarchy

**JobQueue** -- Processing jobs with priority and retry
- States: queued -> processing -> completed/failed/cancelled
- Linked to Video via `video_id`

**Setting** -- Key-value configuration store
- Runtime settings persisted across restarts
- Auto-saved from the Settings page

---

## Web Architecture

- **Backend**: Flask with Blueprint-based routing
- **Frontend**: Server-rendered Jinja2 templates with HTMX for dynamic updates
- **Styling**: Tailwind CSS via CDN (no build step)
- **Real-time**: HTMX polling (5s) for queue status and dashboard stats
- **No JavaScript frameworks** -- pure HTMX + vanilla JS in `static/js/app.js`

---

## File Storage

```
storage/
├── videos/{subject}/{topic}/    # Generated MP4 files
├── audio/                       # TTS audio segments
├── json/                        # Uploaded JSON definitions
├── assets/
│   ├── bgm/                     # Background music MP3s
│   ├── images/                  # User + fetched images
│   ├── svgs/                    # User SVG files
│   ├── videos/                  # User + fetched video clips
│   └── watermark/               # Watermark assets
├── cache/
│   └── manim/{hash}/            # Pre-rendered Manim frames
└── exports/                     # Excel/CSV exports
```

Temp files (per-video frames and audio) are cleaned up after successful encoding. Failed jobs also clean up temp files.

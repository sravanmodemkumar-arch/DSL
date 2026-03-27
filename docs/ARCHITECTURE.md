# Architecture

System design, rendering pipeline, and data flow for the STEM Video Generator.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                               │
│  HTMX + Tailwind CSS (CDN) + Jinja2 Templates              │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP (HTMX partials + full pages)
┌─────────────────────────▼───────────────────────────────────┐
│                     FLASK APP                                │
│                                                              │
│  ┌──────────┐ ┌────────┐ ┌────────┐ ┌───────┐ ┌─────────┐ │
│  │Dashboard │ │Upload  │ │Videos  │ │Queue  │ │Settings │ │
│  │Blueprint │ │Blueprint│ │Blueprint│ │Blueprint│ │Blueprint│ │
│  └──────────┘ └───┬────┘ └────────┘ └───────┘ └─────────┘ │
│                    │       ┌─────────┐  ┌─────────┐         │
│                    │       │YouTube  │  │Export   │         │
│                    │       │Blueprint│  │Blueprint│         │
│                    │       └─────────┘  └─────────┘         │
└────────────────────┼────────────────────────────────────────┘
                     │ Background Thread
┌────────────────────▼────────────────────────────────────────┐
│                  RENDERING ENGINE                            │
│                                                              │
│  ┌───────────┐  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Validator │→ │ Audio   │→ │ Sync     │→ │ Renderer  │  │
│  │           │  │ (TTS)   │  │ (Timeline)│  │ (Pillow)  │  │
│  └───────────┘  └────┬────┘  └──────────┘  └─────┬─────┘  │
│                       │                            │         │
│                  ┌────▼────┐                  ┌────▼────┐   │
│                  │ BGMusic │                  │ FFmpeg  │   │
│                  │ (Synth) │                  │ (Encode)│   │
│                  └─────────┘                  └─────────┘   │
└──────────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    STORAGE                                    │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ SQLite   │  │ Videos/  │  │ Audio/   │  │ JSON/     │  │
│  │ Database │  │ (MP4)    │  │ (MP3)    │  │ (Source)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Video Generation Pipeline

The pipeline runs in a **background thread** and processes one question at a time.

```
JSON Input
    │
    ▼
┌──────────────────┐
│ 1. VALIDATE      │  Parse JSON, check schema, verify asset references
│    (10%)         │  Fatal errors → reject. Warnings → continue.
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. GENERATE      │  For each scene/step with "audio" field:
│    AUDIO         │  → Generate TTS audio segment (gTTS/pyttsx3)
│    (10-30%)      │  → Cache by content hash (skip if unchanged)
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. CONCATENATE   │  Join all audio segments with 300ms pauses
│    + TIMELINE    │  → Build master audio file (.mp3)
│    (30-40%)      │  → Build timeline: [{start, end, render, ...}, ...]
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. GENERATE BGM  │  Procedurally generate background music (.wav)
│    + MIX         │  → Match duration to narration
│    (40%)         │  → Mix with ducking (BGM -18 to -26 dB)
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. RENDER FRAMES │  For each frame at target FPS:
│    (45-85%)      │  → Compute current time = frame_num / fps
│                  │  → Query timeline for active state
│                  │  → Render frame with Pillow (question, equations,
│                  │     digit boxes, highlights, results, etc.)
│                  │  → Save as PNG
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 6. ENCODE VIDEO  │  FFmpeg: frames + mixed audio → MP4
│    (85-95%)      │  → H.264 video, AAC audio
│                  │  → Bitrate from quality preset
│                  │  → Resolution from config
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 7. THUMBNAIL     │  Render first meaningful frame as PNG
│    + CLEANUP     │  → Delete temporary frame PNGs
│    (95-100%)     │  → Update database: status=completed
└──────────────────┘
```

---

## Audio-Video Synchronization

The sync engine is the core of the system. It ensures every visual element appears exactly when narrated.

### Timeline Structure

```
Time 0.0s         3.5s         7.0s         10.5s        14.0s
  │                │              │              │              │
  ▼                ▼              ▼              ▼              ▼
┌────────────┐┌────────────┐┌────────────┐┌────────────┐┌────────────┐
│  Question  ││   Concept  ││  Step 1    ││  Step 2    ││  Answer    │
│  "show"    ││  "show"    ││  "show"    ││  "update"  ││  "result"  │
│  question  ││  formula   ││  equation  ││  equation  ││  final     │
│  _block    ││  _block    ││  1/10      ││  3/30+2/30 ││  6 days    │
└────────────┘└────────────┘└────────────┘└────────────┘└────────────┘
  ▲ audio[0]    ▲ audio[1]    ▲ audio[2]    ▲ audio[3]    ▲ audio[4]
```

### State Machine

At any given timestamp `t`, the renderer computes the visual state by:

1. Finding all timeline entries where `start <= t`
2. Determining which elements are currently visible
3. Checking the most recent render action for each target
4. Compositing all active elements into a single frame

**Key rule:** The question stays visible at the top throughout the video. Options stay visible once shown. Solution steps appear and update in the center area.

---

## Frame Rendering

The `FrameRenderer` class (Pillow-based) renders each visual component.

### Layout Grid

```
┌──────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────┐    │ ← 80px margin
│  │           QUESTION BLOCK                      │    │
│  │  "Which number is divisible by 9?"           │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  ┌──────────────┐    ┌──────────────┐                │
│  │  A) 277218   │    │  B) 123456   │  ← options    │
│  └──────────────┘    └──────────────┘                │
│  ┌──────────────┐    ┌──────────────┐                │
│  │  C) 654321   │    │  D) 111112   │                │
│  └──────────────┘    └──────────────┘                │
│                                                       │
│           ┌──────────────────────┐                   │
│           │   [2] [7] [7] [2]   │  ← digit boxes   │
│           │   [1] [8]           │                    │
│           └──────────────────────┘                   │
│                                                       │
│           ┌──────────────────────┐                   │
│           │  Running Sum: 27     │  ← running sum   │
│           └──────────────────────┘                   │
│                                                       │
│           ┌──────────────────────┐                   │
│           │  ★ Answer: 277218 ★ │  ← final answer  │
│           └──────────────────────┘                   │
│                                                       │
│           Step: Check divisibility                    │ ← step label
│  ═══════════════════════════════                     │ ← progress bar
└──────────────────────────────────────────────────────┘
```

### Visual Component Types

| Component | Rendering Method | Key Properties |
|-----------|-----------------|----------------|
| question_block | Rounded card, bold text | Always at top |
| options_grid | 2x2 grid of cards | Green for correct |
| equation | Centered math font, card bg | Updates in place |
| formula_block | Named formula, warning color | Highlighted when active |
| digit_boxes | Individual boxes with glow | Indices for highlighting |
| running_sum | Centered label, warning color | Updates progressively |
| sum_box | Bordered result box | Green on completion |
| final_answer | Large green text with glow | Emphasis effect |
| concept_text | Wrapped paragraph, subtle | Fades on highlight |
| image | From assets, positioned | Configurable size |
| svg | Converted via CairoSVG | Configurable position |
| table | Headers + rows, styled | Alternating row colors |

### Scaling

All element sizes scale with resolution:
- `scale = height / 1080`
- A 36px font at 1080p becomes 72px at 4K
- Margins, padding, and spacing all scale proportionally

---

## Background Music System

### Architecture

```
                    ┌─────────────────┐
                    │  Python Math    │
                    │  (sin, cos,     │
                    │   exp, etc.)    │
                    └────────┬────────┘
                             │ Raw samples (float array)
                             ▼
                    ┌─────────────────┐
                    │  WAV Writer     │
                    │  (44100 Hz,     │
                    │   16-bit mono)  │
                    └────────┬────────┘
                             │ .wav file
                             ▼
                    ┌─────────────────┐
Narration .mp3 ───▶│  pydub Mixer    │──▶ Mixed .mp3
                    │  (overlay +     │
                    │   ducking)      │
                    └─────────────────┘
```

### Audio Ducking

BGM volume is reduced by 18-26 dB relative to narration:
- `bgm_volume=0.05` → -26 dB (barely audible)
- `bgm_volume=0.15` → -18 dB (subtle, default)
- `bgm_volume=0.30` → -6 dB (clearly audible)

Narration always dominates. BGM fills silence between sentences.

---

## Database Schema

### Videos Table

```
videos
├── id                 INTEGER PRIMARY KEY
├── video_id           VARCHAR(100) UNIQUE  ← from JSON "id"
├── title              VARCHAR(500)
├── subject            VARCHAR(100) INDEXED
├── chapter            VARCHAR(200)
├── topic              VARCHAR(200) INDEXED
├── subtopic           VARCHAR(200)
├── difficulty          VARCHAR(20)
├── exam_tags          TEXT (comma-separated)
├── purpose_tags       TEXT (comma-separated)
├── grade_tags         TEXT (comma-separated)
├── resolution         VARCHAR(10)
├── quality_preset     VARCHAR(5)
├── duration_seconds   FLOAT
├── fps                INTEGER
├── theme              VARCHAR(10)
├── json_path          VARCHAR(500)
├── video_path         VARCHAR(500)
├── audio_path         VARCHAR(500)
├── thumbnail_path     VARCHAR(500)
├── youtube_url        VARCHAR(500)
├── youtube_video_id   VARCHAR(50)
├── youtube_status     VARCHAR(20)
├── status             VARCHAR(20)
├── error_message      TEXT
├── progress           INTEGER (0-100)
├── created_at         DATETIME
├── updated_at         DATETIME
└── completed_at       DATETIME
```

### Job Queue Table

```
job_queue
├── id                 INTEGER PRIMARY KEY
├── video_id           VARCHAR(100) FK → videos
├── priority           INTEGER (1=urgent, 4=low)
├── status             VARCHAR(20)
├── stage              VARCHAR(30)
├── progress           INTEGER (0-100)
├── error_message      TEXT
├── retry_count        INTEGER
├── max_retries        INTEGER
├── created_at         DATETIME
├── started_at         DATETIME
└── completed_at       DATETIME
```

### Settings Table

```
settings
├── id                 INTEGER PRIMARY KEY
├── key                VARCHAR(100) UNIQUE
├── value              TEXT
└── updated_at         DATETIME
```

---

## Storage Layout

Videos are stored hierarchically for easy browsing:

```
storage/
├── videos/
│   ├── Mathematics/
│   │   ├── Arithmetic/
│   │   │   ├── Addition/
│   │   │   │   ├── q-add-001.mp4
│   │   │   │   ├── q-add-001_audio.mp3
│   │   │   │   ├── q-add-001_bgm.wav
│   │   │   │   ├── q-add-001_mixed.mp3
│   │   │   │   └── q-add-001_thumb.png
│   │   │   └── Divisibility/
│   │   │       └── ...
│   │   └── Algebra/
│   ├── Physics/
│   │   └── Mechanics/
│   └── Chemistry/
├── json/
│   ├── batch_20260326_143000.json
│   └── ...
├── audio/
│   └── q-add-001/
│       ├── scene_000.mp3
│       ├── scene_001_step_000.mp3
│       └── ...
├── assets/
│   ├── images/
│   └── svg/
└── exports/
```

---

## Request Flow

### Page Load (Full HTML)

```
Browser → GET /videos/ → Flask → Jinja2 renders library.html
                                   ↓ extends base.html
                                   ↓ includes components/video_grid.html
                                   → Full HTML response
```

### HTMX Filter Change (Partial HTML)

```
Browser → GET /videos/list?subject=Mathematics
        → Flask → Jinja2 renders components/video_grid.html ONLY
        → Partial HTML response
        → HTMX swaps into #video-grid div
```

### HTMX Auto-Refresh (Polling)

```
Dashboard: hx-get="/stats" hx-trigger="every 10s"
Queue:     hx-get="/queue/list" hx-trigger="every 5s"

Browser → GET /stats → Flask → stats_cards.html partial → swap
```

### Video Processing (Background)

```
Browser → POST /upload/process → Flask creates Video + JobQueue records
                                → Starts background thread
                                → Returns HTML immediately

Background Thread:
  → Picks queued jobs
  → For each job:
    → Loads JSON
    → Runs VideoPipeline.process_question()
    → Updates progress in DB (polling visible on queue page)
    → Saves MP4 to storage/videos/
```

---

## Security Measures

| Measure | Implementation |
|---------|---------------|
| JSON size limit | 50 MB max upload |
| Path traversal | `secure_filename()` + path validation |
| SVG sanitization | CairoSVG renders to PNG (strips scripts) |
| SQL injection | SQLAlchemy ORM (parameterized queries) |
| XSS | Jinja2 auto-escaping |
| File type validation | .json and .zip only |
| Process isolation | Each job in its own thread with app context |

---

## Performance Characteristics

| Metric | Typical Value |
|--------|--------------|
| Audio generation | 1-3 seconds per step |
| Frame rendering | 20-50 ms per frame (1080p, Pillow) |
| BGM generation | 2-5 seconds for 5 min track |
| FFmpeg encoding | 10-60 seconds for 5 min video |
| Total per video | 2-5 minutes (1080p, P5, 5 min duration) |
| Parallel jobs | 4 concurrent (configurable) |

### Bottlenecks
1. **Frame rendering** — CPU-bound (Pillow). Scales linearly with duration × FPS.
2. **TTS generation** — Network-bound (gTTS) or CPU-bound (pyttsx3).
3. **FFmpeg encoding** — CPU-bound. Higher quality = slower.

### Optimization Tips
- Use P3/720p for drafts, P5/1080p for final
- Reduce FPS (24 instead of 30) for faster rendering
- Use pyttsx3 for offline/faster TTS (lower quality)
- Increase max_workers for parallel batch processing

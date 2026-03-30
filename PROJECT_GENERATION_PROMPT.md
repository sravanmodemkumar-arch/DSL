# STEM Video Generator — Complete Project Generation Prompt

> **Purpose**: This file contains everything needed to regenerate the entire project from scratch using an AI coding assistant (Claude, GPT-4, Gemini, etc.). Each section is self-contained and can be generated independently.

---

## ═══════════════════════════════════════
## PART 1 — PROJECT OVERVIEW
## ═══════════════════════════════════════

Build a **STEM Video Generator** — a Flask web application that converts structured JSON descriptions into fully animated, narrated educational MP4 videos.

### What It Does

1. User uploads a JSON file describing an educational question or topic
2. System validates the JSON against a strict DSL schema
3. Each question is queued as a job and processed in the background
4. Pipeline generates: TTS audio → synchronized timeline → parallel frame rendering → FFmpeg encoding → final MP4
5. Completed videos appear in a web library; can be uploaded to YouTube via OAuth2

### Core Technical Stack

```
Language:    Python 3.12
Web:         Flask 3.1.0 + Jinja2 + HTMX + Tailwind CSS (CDN)
Database:    SQLite (WAL mode) + SQLAlchemy 2.0.36
Rendering:   Pillow 11.1.0 (frame-by-frame PNG generation)
TTS:         edge_tts (primary) + gTTS (fallback)
Audio:       pydub + wave + FFmpeg
Video:       FFmpeg H.264 (GPU h264_nvenc → CPU libx264 fallback)
YouTube:     google-api-python-client 2.159.0 + google-auth-oauthlib
Export:      openpyxl 3.1.5
```

### File Structure

```
DSL/
├── app.py                    # Flask factory + startup resume logic
├── config.py                 # Config class, resolution map, quality presets, themes
├── models.py                 # SQLAlchemy models: Video, JobQueue, Setting
├── requirements.txt
│
├── engine/
│   ├── __init__.py           # Re-exports
│   ├── validator.py          # JSON DSL schema validation
│   ├── audio.py              # TTS + word-level timestamp mapping
│   ├── sync.py               # Timeline builder + get_active_state()
│   ├── renderer.py           # FrameRenderer — Pillow-based PPT-style frames
│   ├── pipeline.py           # VideoPipeline: orchestrates all stages
│   ├── hardware.py           # CPU/GPU detection + worker allocation
│   ├── bgmusic.py            # Procedural ambient background music (WAV synthesis)
│   ├── manim_renderer.py     # 20 Manim animation templates
│   └── free_media.py         # Auto-fetch stock photos/videos from free APIs
│
├── routes/
│   ├── __init__.py           # Blueprint registration
│   ├── dashboard.py          # Home page with live stats
│   ├── upload.py             # JSON upload, validation, queue submission, job runner
│   ├── videos.py             # Video library with search/filter/pagination
│   ├── queue_routes.py       # Job queue management (cancel, retry, delete, prioritize)
│   ├── settings.py           # Configuration UI (50+ settings)
│   ├── youtube.py            # OAuth2 YouTube upload
│   ├── export.py             # Excel/CSV data export
│   └── assets.py             # Custom image/SVG/video asset upload & browser
│
├── templates/
│   ├── base.html             # Master layout with sidebar nav
│   ├── dashboard.html        # Stats + recent videos + active jobs
│   ├── upload.html           # JSON upload + live validation + batch submit
│   ├── library.html          # Video grid with search/filter/pagination
│   ├── queue.html            # Job queue monitor
│   ├── settings.html         # Full settings panel
│   ├── youtube.html          # YouTube auth + upload history
│   ├── export.html           # Export page
│   ├── video_detail.html     # Single video metadata + player
│   ├── assets.html           # Asset tree browser
│   ├── 404.html, 500.html
│   └── components/           # HTMX partials
│       ├── stats_cards.html
│       ├── queue_list.html
│       ├── queue_item.html
│       └── video_grid.html
│
├── storage/
│   ├── videos/{video_id}/    # UUID-named dirs: video.mp4 + thumb.png + temp files
│   ├── json/                 # Uploaded JSON batches
│   ├── audio/                # TTS word cache (.word_cache/)
│   ├── assets/bgm/           # Background music MP3s
│   ├── assets/images/        # User + fetched images
│   ├── assets/watermark/     # Watermark image
│   └── exports/              # Excel/CSV outputs
│
└── instance/
    └── stemvideo.db          # SQLite database
```

---

## ═══════════════════════════════════════
## PART 2 — CONFIGURATION (config.py)
## ═══════════════════════════════════════

```python
import os
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _bool(key, default="false"):
    return os.environ.get(key, default).lower() in ("true", "1", "yes")

def _int(key, default):
    try: return int(os.environ.get(key, default))
    except ValueError: return int(default)

def _float(key, default):
    try: return float(os.environ.get(key, default))
    except ValueError: return float(default)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "stem-video-dev-key")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'stemvideo.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"timeout": 30, "check_same_thread": False},
    }

    # Storage paths
    STORAGE_DIR  = os.path.join(BASE_DIR, "storage")
    VIDEOS_DIR   = os.path.join(BASE_DIR, "storage", "videos")
    JSON_DIR     = os.path.join(BASE_DIR, "storage", "json")
    ASSETS_DIR   = os.path.join(BASE_DIR, "storage", "assets")
    AUDIO_DIR    = os.path.join(BASE_DIR, "storage", "audio")
    EXPORTS_DIR  = os.path.join(BASE_DIR, "storage", "exports")

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"json", "zip"}

    DEFAULT_RESOLUTION     = os.environ.get("DEFAULT_RESOLUTION",     "1080p")
    DEFAULT_QUALITY_PRESET = os.environ.get("DEFAULT_QUALITY_PRESET", "P7")
    DEFAULT_THEME          = os.environ.get("DEFAULT_THEME",          "dark")
    DEFAULT_FPS            = _int("DEFAULT_FPS", "30")

    RESOLUTIONS = {
        "360p":  (640,  360),
        "720p":  (1280, 720),
        "1080p": (1920, 1080),
        "2K":    (2560, 1440),
        "4K":    (3840, 2160),
    }

    # P1-P7 quality presets: P1=preview, P7=maximum (60fps CRF)
    QUALITY_PRESETS = {
        "P1": {"bitrate": "1M",  "fps": 24, "antialiasing": False, "label": "Preview"},
        "P2": {"bitrate": "2M",  "fps": 24, "antialiasing": True,  "label": "Draft"},
        "P3": {"bitrate": "4M",  "fps": 30, "antialiasing": True,  "label": "Mobile"},
        "P4": {"bitrate": "6M",  "fps": 30, "antialiasing": True,  "label": "Standard"},
        "P5": {"bitrate": "10M", "crf": "22", "fps": 30, "antialiasing": True, "label": "YouTube"},
        "P6": {"bitrate": "15M", "crf": "20", "fps": 60, "antialiasing": True, "label": "High Quality"},
        "P7": {"bitrate": "25M", "crf": "18", "fps": 60, "antialiasing": True, "label": "Maximum"},
    }

    # TTS: edge_tts (best, Indian voices) | gtts | pyttsx3
    TTS_ENGINE = os.environ.get("TTS_ENGINE", "edge_tts")
    TTS_LANG   = os.environ.get("TTS_LANG",   "en")
    TTS_TLD    = os.environ.get("TTS_VOICE",  "en-IN-PrabhatNeural")  # voice for edge_tts

    BGM_ENABLED = _bool("BGM_ENABLED", "true")
    BGM_STYLE   = os.environ.get("BGM_STYLE", "bansuri")
    BGM_VOLUME  = _float("BGM_VOLUME", "0.30")
    BGM_FILES   = []  # populate with local MP3 paths if available

    WATERMARK_ENABLED = _bool("WATERMARK_ENABLED", "false")
    WATERMARK_TEXT    = os.environ.get("WATERMARK_TEXT", "")
    WATERMARK_IMAGE   = os.path.join(BASE_DIR, "storage", "assets", "watermark", "watermark.png")
    WATERMARK_OPACITY = _float("WATERMARK_OPACITY", "0.35")

    MAX_WORKERS = _int("MAX_WORKERS", "4")
    JOB_TIMEOUT = _int("JOB_TIMEOUT", "600")

    YOUTUBE_CLIENT_SECRETS = os.path.join(BASE_DIR, "client_secrets.json")
    YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


THEMES = {
    "dark": {
        "bg": "#0f0f23", "card_bg": "#1a1a2e", "text": "#ffffff",
        "text_secondary": "#a0a0b8", "accent": "#00d4ff",
        "success": "#00ff88", "warning": "#ffaa00", "error": "#ff4444",
        "formula_bg": "#2a2a4a", "highlight": "#00d4ff", "border": "#2a2a4a",
    },
    "light": {
        "bg": "#f5f5f5", "card_bg": "#ffffff", "text": "#1a1a1a",
        "text_secondary": "#666666", "accent": "#0066cc",
        "success": "#00aa55", "warning": "#cc8800", "error": "#cc3333",
        "formula_bg": "#e8e8f0", "highlight": "#0066cc", "border": "#dddddd",
    },
}
```

---

## ═══════════════════════════════════════
## PART 3 — DATABASE MODELS (models.py)
## ═══════════════════════════════════════

Three models: `Video`, `JobQueue`, `Setting`.

### Video

Stores one record per video being generated or already completed.

```
video_id        VARCHAR(100) UNIQUE INDEX    # matches question "id" from JSON
title           VARCHAR(500)
subject         VARCHAR(100) INDEX
chapter         VARCHAR(200)
topic           VARCHAR(200) INDEX
subtopic        VARCHAR(200)
difficulty      VARCHAR(20)                  # easy|medium|hard
exam_tags       TEXT                         # comma-separated
purpose_tags    TEXT
grade_tags      TEXT
resolution      VARCHAR(10)                  # 360p|720p|1080p|2K|4K
quality_preset  VARCHAR(5)                   # P1-P7
duration_seconds FLOAT
fps             INTEGER
theme           VARCHAR(10)                  # dark|light
json_path       VARCHAR(500)                 # source JSON file
output_dir      VARCHAR(500)                 # per-video directory containing all output files
video_path      VARCHAR(500)                 # final MP4
audio_path      VARCHAR(500)                 # final mixed audio
thumbnail_path  VARCHAR(500)
youtube_url     VARCHAR(500)
youtube_video_id VARCHAR(50)
youtube_status  VARCHAR(20)                  # not_uploaded|uploading|published|failed
status          VARCHAR(20)                  # pending|processing|completed|failed
error_message   TEXT
progress        INTEGER (0-100)
created_at      DATETIME
updated_at      DATETIME
completed_at    DATETIME
```

### JobQueue

One record per processing job, linked to Video via `video_id`.

```
video_id        FK -> videos.video_id
priority        INTEGER (1=urgent, 2=high, 3=normal, 4=low)
status          VARCHAR(20)    # queued|processing|completed|failed|cancelled
stage           VARCHAR(30)    # audio_gen|timestamp_map|rendering|encoding
progress        INTEGER (0-100)
error_message   TEXT
retry_count     INTEGER
max_retries     INTEGER (default 1)
created_at, started_at, completed_at  DATETIME
```

### Setting

Key-value store for runtime configuration, persisted to DB.

```python
@staticmethod
def get(key, default="") -> str
@staticmethod
def set(key, value) -> None   # upsert + db.session.commit()
```

### Startup (app.py)

- Enable SQLite WAL mode: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=30000`
- On startup: reset any "processing" jobs to "queued" (crashed mid-run)
- Resume all queued jobs via `_start_processing(app)`

---

## ═══════════════════════════════════════
## PART 4 — JSON DSL SPECIFICATION
## ═══════════════════════════════════════

The JSON input is an **array** of question/topic objects.

### Top-Level Fields

```json
{
  "id": "q-math-percentage-15pct-240",   // REQUIRED. Unique slug. Used as video_id.
  "mode": "mcq",                          // REQUIRED. See modes below.

  "meta": {                               // REQUIRED.
    "subject": "Mathematics",
    "topic": "Percentage",
    "subtopic": "Finding percentage of a number",
    "chapter": "Chapter 8",
    "difficulty": "easy",                 // easy|medium|hard
    "exam": "SSC / UPSC / Banking",
    "grade": "6-7"
  },

  "thumbnail": {                          // Optional. Drives thumb.png text.
    "title": "Percentage",
    "subtitle": "Find 15% of 240",
    "badge": "Quick Trick",
    "bg_color": "#1A237E",
    "accent_color": "#EF6C00"
  },

  "youtube": {                            // Optional. Auto-filled on YouTube upload.
    "title": "What is 15% of 240? | SSC Math | Percentage Trick",
    "description": "...",
    "tags": ["math", "percentage", "SSC"],
    "privacy": "public",
    "category_id": "27"
  },

  "question": { ... },                    // Mode-specific (see below)
  "topic_header": { ... },               // topic/match/sequence modes
  "scenes": [ ... ]                      // REQUIRED. Array of scene objects.
}
```

### Video Modes (8 total)

| Mode | Question Block | Options | Correct | topic_header |
|------|---------------|---------|---------|--------------|
| `mcq` | text | 4 options {key,value} | key | – |
| `true_false` | text | 2 options (True/False) | key | – |
| `fill_blank` | text with `___` | – | – | – |
| `numerical` | text | – | – | – |
| `assertion` | text + assertion + reason | 4 options | key | – |
| `topic` | – | – | – | {title, subtitle} |
| `match` | – | – | – | {title, subtitle} |
| `sequence` | – | – | – | {title, subtitle} |

### Scene Types

```
question     — Shows the question_block header
options      — Reveals the options_grid
concept      — Multi-step explanation (requires "steps" array)
solution     — Multi-step worked solution (requires "steps")
intro        — Multi-step intro for topic mode (requires "steps")
visual_intro — Timed visual without audio (auto-duration)
answer       — Final answer reveal
```

### Scene Structure

**Simple scene** (question, options, answer, visual_intro):
```json
{
  "type": "question",
  "text": "What is 15% of 240?",
  "audio": "What is fifteen percent of two forty?",
  "render": {
    "action": "show",
    "target": "question_block"
  }
}
```

**Stepped scene** (concept, solution, intro):
```json
{
  "type": "concept",
  "steps": [
    {
      "text": "Step label (shown as step heading)",
      "audio": "TTS narration text — what students hear",
      "render": {
        "action": "show",
        "target": "equation",
        "value": "15% = 15/100"
      }
    }
  ]
}
```

### Render Actions

```
show           — Display element
hide           — Remove element
highlight      — Highlight existing element
update         — Update value of existing element
animate        — Trigger CSS/JS animation
show_result    — Show with result styling
draw_arrow     — Draw connecting arrow
zoom           — Zoom element
replace        — Replace element content
sequence       — Trigger step sequence
clear          — Remove element from screen
highlight_option — Highlight specific option key in header
```

### Render Targets (35+)

**Header (always visible):**
- `question_block` — Shows question text in header
- `options_grid` — Reveals A/B/C/D options
- `final_answer` — Locks correct answer highlight

**Body elements (accumulate on screen):**

| Target | Data Fields | Description |
|--------|-------------|-------------|
| `equation` | `value` | Math equation, gray card |
| `formula_block` | `value` | Formula with blue accent bar |
| `digit_boxes` | `data: []`, `highlighted_indices: []` | Blue PPT digit boxes |
| `running_sum` | `value` | Orange bold sum text |
| `sum_box` | `value` | Gray sum result box |
| `result_box` | `value` | Gray result card |
| `fraction` | `numerator`, `denominator`, `result` | Math fraction display |
| `concept_text` | `heading`, `text`, `items: []` | Blue concept card |
| `highlight_box` | `text`, `color` | Full-width colored rule box |
| `key_facts` | `heading`, `facts: [{key,value}]` | Key:Value table |
| `process_steps` | `heading`, `steps: []` | Numbered step list |
| `two_col_text` | `heading`, `left:{title,items}`, `right:{title,items}` | Comparison card |
| `shortcut_columns` | `left:{title,rows:[]}`, `right:{title,rows:[]}` | Bordered two-column |
| `instruction_text` | `text` | Orange banner — CLEARS all prior body elements |
| `step_label` | `text` | Blue step heading label |
| `table` | `headers:[]`, `rows:[[]]` | Blue-header table |
| `timeline` | `heading`, `items:[{year,event}]` | Chronological timeline |
| `chem_equation` | `reactants:[]`, `products:[]`, `conditions` | Chemical equation |
| `flow_chart` | `steps:[{label,note}]` | Process flowchart |
| `t_account` | `title`, `debit:[]`, `credit:[]` | T-account (accounting) |
| `memory_trick` | `text`, `breakdown:[]`, `mnemonic` | Mnemonic/memory card |
| `analogy` | `a`, `b`, `c`, `d` | A:B::C:D analogy display |
| `number_line` | `min`, `max`, `marks:[]`, `highlight:[]` | Number line diagram |
| `blank_reveal` | `blank_text`, `answer` | Fill-blank reveal |
| `match_columns` | `left:[]`, `right:[]`, `pairs:{}` | Match-the-following |
| `sequence_list` | `items:[]`, `revealed: bool` | Ordered sequence |
| `numerical_answer` | `value`, `unit` | Answer for numerical mode |
| `title_card` | `title`, `subtitle` | Full-screen intro title |
| `section_header` | `title` | Section divider |
| `image` | `src`, `caption` | Image from assets dict |
| `svg` | `src` | SVG from assets dict |
| `builtin_visual` | `name` | One of 74 built-in Pillow illustrations |
| `subject_image` | `query`, `alt` | Auto-fetch stock photo |
| `video_clip` | `query`, `alt` | Auto-fetch stock video |
| `matplotlib_plot` | `plot_type`, `data:{x,y,labels}`, `title` | Generated chart |
| `manim_scene` | `scene_name`, `params:{}` | Pre-rendered Manim animation |

### Built-in Visuals (74 names)

```
cell, animal_cell, plant_cell, mitosis, meiosis, dna_double_helix, photosynthesis,
chloroplast, neuron, heart, lungs, digestive_system, eye, ear, skeleton,
atom, electron_shell, periodic_table_cell, molecule_h2o, molecule_co2,
circuit_battery, circuit_resistor, circuit_diagram, magnet_field, wave_diagram,
lens_diagram, prism_refraction, mirror_reflection, pendulum, projectile_path,
acid_base_reaction, test_tube, flask, bunsen_burner, crystal_structure,
map_india, map_world, compass_rose, river_delta, mountain_cross_section,
number_line_simple, fraction_bar, coordinate_axes, triangle_labeled,
circle_labeled, pie_chart_simple, bar_chart_simple, venn_diagram,
budget_circle, gdp_bar, supply_demand, flowchart_simple, org_chart,
parliament_seating, court_structure, election_booth,
music_staff, art_palette, sports_podium, book_open, graduation_cap,
trophy, calculator, clock_face, thermometer, ruler_scale, weighing_balance,
solar_system, moon_phases, water_cycle, carbon_cycle, food_chain,
nitrogen_cycle
```

### Manim Scene Templates (20 names)

```
function_plot, multi_function, derivative, integral,
vector_addition, matrix_transform, pythagorean, circle_theorem,
number_line_walk, trig_circle, equation_transform,
wave, projectile, pendulum, electric_field, lens_ray,
energy_diagram, text_reveal, bar_chart_anim, graph_network
```

### Assets Dict (optional)

```json
"assets": {
  "images": {"my_diagram": "images/my_diagram.png"},
  "svgs":   {"my_icon": "svg/my_icon.svg"},
  "audio_clips": {"intro_sting": "audio/sting.mp3"}
}
```

Reference in render: `"src": "my_diagram"` (uses asset key lookup, not path).

---

## ═══════════════════════════════════════
## PART 5 — ENGINE: validator.py
## ═══════════════════════════════════════

### Purpose
Validates a list of question dicts before rendering. Returns `(is_valid: bool, errors: list[ValidationError])`.

### Rules
- Root must be a JSON array
- No duplicate `id` values
- `mode` must be in: `mcq, topic, true_false, fill_blank, numerical, match, assertion, sequence`
- `meta.subject` and `meta.topic` are required
- `meta.difficulty` must be `easy|medium|hard` (warning if missing/wrong)
- `mcq, true_false, assertion` require `question.text`, `question.options`, `question.correct`
- `topic, match, sequence` need `topic_header` (warning if missing)
- `assertion` requires `question.assertion` + `question.reason`
- All `scenes` must have valid `type`
- `concept, solution, intro` scenes require `steps` array
- Each `render` must have `action` (from VALID_ACTIONS) and `target`
- `render.position` and `render.size` validated as warnings
- `_DOC` objects are silently skipped

### ValidationError class
```python
class ValidationError:
    path: str           # e.g. "[0].question.text"
    message: str
    severity: str       # "error" (fatal) | "warning" (non-fatal)

    def to_dict(self) -> dict
    def __repr__(self) -> str   # "[ERROR] path: message"
```

---

## ═══════════════════════════════════════
## PART 6 — ENGINE: audio.py
## ═══════════════════════════════════════

### Purpose
Generate TTS audio for every `audio` field in the JSON. Return segments with word-level timestamps.

### Key Functions

```python
def generate_audio_for_question(question_data, audio_dir,
                                 tts_engine="edge_tts",
                                 lang="en", tld="en-IN-PrabhatNeural"):
    """
    Walk all scenes and steps, generate one MP3 per audio field.
    Returns: list of segment dicts:
      {
        scene_index: int,
        step_index: int | None | "verdict",
        file: str,            # path to MP3
        start: float,         # cumulative start seconds
        end: float,           # cumulative end seconds
        word_timestamps: [    # per-word timing within segment
          {"word": str, "start": float, "end": float}
        ]
      }
    """

def concatenate_audio(segments, output_path):
    """
    Merge all segment MP3s into one master audio file using pydub.
    Returns: (audio_timeline, total_duration)
      audio_timeline — same segment list but with absolute start/end times
    """

def _generate_edge_tts(text, output_path, voice="en-IN-PrabhatNeural"):
    """
    Generate TTS using edge_tts asyncio library.
    Falls back to asyncio.run() in non-main threads.
    Returns: list of word timestamps (may be empty if not available)
    """

def _compute_word_timestamps(words, segment_start, segment_end, cache_dir, tts_engine, lang, tld):
    """
    Measure individual word TTS durations (cached in .word_cache/).
    Scale proportionally to actual segment duration.
    Returns: list of {"word": str, "start": float, "end": float}
    """
```

### Word Cache
- Directory: `storage/audio/.word_cache/`
- Key: `MD5("{word}|{engine}|{lang}|{tld}")[:12]`
- Files: `{key}.dur` (float seconds), `{key}.mp3` (audio)
- Avoids regenerating common words like "the", "is", "a"

### TTS Engine Priority
1. `edge_tts` — Best quality, free, Indian voices, word-level timestamps built-in
2. `gtts` — Google Translate TTS, good quality, no timestamps
3. `pyttsx3` — Offline fallback, robotic quality

---

## ═══════════════════════════════════════
## PART 7 — ENGINE: sync.py
## ═══════════════════════════════════════

### Purpose
Map audio segments to render instructions. Compute visual state at any time `t`.

### build_timeline(question_data, audio_segments, buffer_ms=300)

**Algorithm:**
1. Build lookup: `{(scene_idx, step_idx): segment}` — prevents sync drift
2. Walk scenes:
   - Simple scene with `audio` + `render` → look up segment by (scene_idx, None) → add entry
   - Steps scene → for each step, look up (scene_idx, step_idx)
   - No-audio scene with `render` → auto-duration: look ahead to next audio segment, cap at 3s
   - Steps without audio → 1.5s default duration
3. Each entry: `{start, end, scene_index, scene_type, step_index, render, text, audio_text, word_timestamps}`

### get_active_state(timeline, current_time, question_data)

**Algorithm:**
1. Walk timeline entries where `entry["start"] <= current_time`
2. Maintain accumulation dict `work_elements = {}` (target → data)
3. Same target key replaces previous; different targets coexist
4. Return state dict containing:
   - `mode`, `question_text`, `options_data`, `correct_option`
   - `question_shown`, `options_shown`, `highlighted_option`, `show_correct`
   - `work_elements` dict
   - `step_text`, `narration` (word timestamps for current segment)
   - `topic_header`, `topic_shown`, `current_time`

**Special dispatch rules:**
- `target == "question_block"` → `question_shown = True`
- `target == "options_grid"` → `options_shown = True`
- `target == "final_answer"` → `show_correct = True` (permanent)
- `target == "instruction_text"` → clears all `work_elements` (section break)
- `action == "highlight"` on any element → sets `element["highlighted"] = True`
- `action == "update"` → updates `value` field of existing element
- `target == "shortcut_columns"` → removes `concept_text` (mutually exclusive)

---

## ═══════════════════════════════════════
## PART 8 — ENGINE: renderer.py
## ═══════════════════════════════════════

### FrameRenderer class

```python
class FrameRenderer:
    def __init__(self, width=1920, height=1080, theme=None, watermark=None):
        # PPT color palette — always used regardless of theme parameter
        self.C = PPT_COLORS  # see below
        self.scale = height / 1080   # everything scaled relative to 1080p
        self.margin_x = int(width * 0.025)
        self.content_x = int(width * 0.04)
        self.usable_w = width - 2 * self.margin_x
        self.content_w = width - 2 * self.content_x
        self.header_h = int(height * 0.20)
        self.stripe_h = int(5 * self.scale)   # orange accent stripe

    def render_frame(self, state) -> PIL.Image:
        """
        state = {
            "mode": str,
            "question_text": str,
            "options_data": [{"key": str, "value": str}],
            "correct_option": str,
            "highlighted_option": str,
            "show_correct": bool,
            "question_shown": bool,
            "options_shown": bool,
            "work_elements": {target: element_dict},
            "step_text": str,
            "narration": {"audio_text": str, "word_timestamps": [...]},
            "current_time": float,
            "topic_header": {"title": str, "subtitle": str} | None,
            "topic_shown": bool,
        }
        Returns: PIL.Image (RGB, width x height)
        """
```

### PPT Color Palette

```python
PPT_COLORS = {
    "bg": "#FFFFFF",                    # White body
    "header_bg": "#1A237E",             # Dark navy header
    "accent_stripe": "#EF6C00",         # Orange stripe under header
    "question_label": "#F9A825",        # Gold "Q:" label
    "header_text": "#FFFFFF",
    "body_text": "#212121",
    "body_secondary": "#757575",
    "note_text": "#1A237E",
    "blue": "#1565C0",
    "green": "#2E7D32",
    "orange": "#EF6C00",
    "red": "#C62828",
    "card_bg": "#F5F5F5",
    "concept_blue_bg": "#E3F2FD",
    "concept_orange_bg": "#FFF3E0",
    "digit_bg": "#FFFFFF",
    "digit_border": "#1565C0",
    "digit_text": "#1565C0",
    "success": "#2E7D32",
    "fail": "#C62828",
    "result_bg": "#F5F5F5",
    "narration_bg": "#1A237E",          # Karaoke bar background
    "narration_spoken": "#FFFFFF",      # Already-spoken words
    "narration_active": "#F9A825",      # Currently spoken word (gold highlight)
    "narration_pending": "#5C6BC0",     # Upcoming words
    "progress": "#EF6C00",
}

OPTION_BAR_COLORS = {  # Left accent bar per option
    "a": "#1565C0", "b": "#2E7D32", "c": "#EF6C00", "d": "#C62828",
}
```

### Layout System

Each mode uses a different header method (all return `body_top` y-coordinate):

```
mcq, true_false         → _draw_header()          header_h ≈ 260px at 1080p
topic                   → _draw_topic_bar()        header_h ≈ 100px
match, sequence         → _draw_minimal_bar()      header_h ≈ 70px
numerical               → _draw_numerical_header() header_h ≈ 120px
assertion               → _draw_assertion_header() header_h ≈ 180px
```

Body area: from `body_top` to `body_bottom = height - 30*scale - karaoke_h`

Narration bar: always drawn at bottom, ~50px tall, shows word-by-word karaoke

### Fonts

Try bundled Poppins from `storage/assets/fonts/`:
- `Poppins-Regular.ttf`, `Poppins-Medium.ttf`, `Poppins-SemiBold.ttf`, `Poppins-Bold.ttf`
- Fallback: system fonts (`/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf`, etc.)
- Final fallback: `ImageFont.load_default()`

### Body Element Rendering (draw methods)

Each `_draw_*` method signature: `(self, draw, frame, element, y) -> new_y`

```
_draw_equation(draw, frame, element, y)         # gray card, centered text
_draw_formula(draw, frame, element, y)          # blue left bar + light bg
_draw_digit_boxes(draw, frame, element, y)      # PPT digit boxes row
_draw_highlight_box(draw, frame, element, y)    # full-width colored rule box
_draw_key_facts(draw, frame, element, y)        # key:value table
_draw_process_steps(draw, frame, element, y)    # numbered steps
_draw_two_col_text(draw, frame, element, y)     # two-column comparison
_draw_shortcut_columns(draw, frame, element, y) # bordered two-col shortcut
_draw_concept_text(draw, frame, element, y)     # heading + text + bullet list
_draw_running_sum(draw, frame, element, y)      # orange bold total
_draw_result_box(draw, frame, element, y)       # gray result card
_draw_final_answer(draw, frame, element, y)     # green success box
_draw_fraction(draw, frame, element, y)         # inline math fraction
_draw_table(draw, frame, element, y)            # blue-header table
_draw_timeline(draw, frame, element, y)         # chronological timeline
_draw_chem_equation(draw, frame, element, y)    # chemical equation
_draw_flow_chart(draw, frame, element, y)       # process flow
_draw_t_account(draw, frame, element, y)        # T-account
_draw_memory_trick(draw, frame, element, y)     # mnemonic card
_draw_analogy(draw, frame, element, y)          # A:B::C:D display
_draw_number_line(draw, frame, element, y)      # number line
_draw_title_card(draw, frame, element, y)       # full-screen title
_draw_concept_text(draw, frame, element, y)     # concept with heading/items
_draw_blank_reveal(draw, frame, element, y)     # fill-blank answer
_draw_match_columns(draw, frame, element, y)    # match columns
_draw_sequence_list(draw, frame, element, y)    # sequence order
_draw_numerical_answer(draw, frame, element, y) # numerical answer box
_draw_image(frame, element, y, max_y)           # image from file
_draw_svg(frame, element, y, max_y)             # SVG from file (CairoSVG)
```

### Karaoke Narration Bar

Drawn at bottom of every frame:
1. Dark navy background bar
2. Split audio_text into words
3. Words before current time → white
4. Word active at current time → gold highlight
5. Words after current time → muted blue

```python
def _find_active_word(word_timestamps, current_time) -> str:
    for wt in word_timestamps:
        if wt["start"] <= current_time <= wt["end"]:
            return wt["word"]
    return ""
```

---

## ═══════════════════════════════════════
## PART 9 — ENGINE: pipeline.py
## ═══════════════════════════════════════

### VideoPipeline class

```python
class VideoPipeline:
    def __init__(self, config: dict):
        # config keys used: RESOLUTIONS, QUALITY_PRESETS, TTS_ENGINE, TTS_LANG,
        # TTS_TLD, BGM_ENABLED, BGM_FILES, BGM_STYLE, BGM_VOLUME,
        # THEMES, WATERMARK_ENABLED, WATERMARK_TEXT, WATERMARK_IMAGE, WATERMARK_OPACITY

    def process_question(self, question_data, output_dir, resolution="1080p",
                          quality_preset="P7", theme="dark",
                          progress_callback=None, frame_workers=None) -> dict:
        """
        Full pipeline. Returns:
        {
          "video_id": str,
          "video_path": str,
          "audio_path": str,
          "thumbnail_path": str,
          "duration": float,
          "frame_count": int,
          "resolution": str,
          "quality_preset": str,
        }
        Raises on failure (caller handles InterruptedError separately for cancel).
        """
```

### Pipeline Stages

```
Stage 1: TTS audio generation
  → engine/audio.generate_audio_for_question()
  → progress: 10% → 30%

Stage 2: Concatenate audio + build timeline
  → engine/audio.concatenate_audio()
  → engine/sync.build_timeline()
  → progress: 35%

Stage 2b: BGM mixing (optional)
  → engine/bgmusic.generate_bg_music() if no BGM files available
  → engine/bgmusic.mix_audio_with_bgm()
  → progress: 40%

Stage 3: Asset resolution
  → engine/free_media for subject_image / video_clip targets
  → progress: 43%

Stage 3b: Manim pre-rendering
  → engine/manim_renderer.prerender_manim_scenes()
  → progress: 44%

Stage 4: Parallel frame rendering
  → ProcessPoolExecutor with frame_workers workers
  → Each chunk: range(start, end) of frame numbers
  → worker calls: renderer.render_frame(get_active_state(timeline, t))
  → progress: 45% → 84%

Stage 5: FFmpeg video encoding
  → Try GPU: h264_nvenc (NVIDIA) / h264_amf (AMD) / h264_qsv (Intel)
  → Fallback CPU: libx264
  → CRF for P5-P7, ABR for P1-P4
  → progress: 85% → 95%

Stage 6: Thumbnail generation
  → Render one frame at t=2.0s
  → Save as thumb.png

Stage 7: Cleanup
  → Delete frames/ and audio/ subdirs on success
```

### Progress Callback Signature

```python
def progress_callback(stage: str, percent: int) -> None:
    # Called throughout pipeline
    # stage: "audio_gen" | "timestamp_map" | "rendering" | "encoding" | "failed"
    # percent: 0-100
    # Raise InterruptedError("Job cancelled by user") to stop pipeline mid-run
```

### CPU Throttling

```python
def _throttle_current_process():
    """Limit worker process: nice +10 (Unix) + affinity to 70% of cores."""
    import psutil
    p = psutil.Process()
    p.nice(10)
    all_cpus = list(range(os.cpu_count()))
    limit = max(1, int(len(all_cpus) * 0.70))
    p.cpu_affinity(all_cpus[:limit])
```

### GPU Encode Lock

```python
_GPU_ENCODE_LOCK = threading.Lock()
# GPU encodes are serialized (shared resource)
# CPU encodes run fully in parallel (no lock)
```

---

## ═══════════════════════════════════════
## PART 10 — ENGINE: hardware.py
## ═══════════════════════════════════════

### Purpose
Detect hardware and compute optimal worker allocation.

```python
def detect_hardware() -> dict:
    return {
        "cpu_name": str,
        "physical_cores": int,
        "logical_cores": int,
        "cpu_mhz": float,
        "ram_gb": float,
        "ram_available_gb": float,
        "gpu_vendor": str,          # "NVIDIA" | "AMD" | "Intel" | "None"
        "gpu_name": str,
        "gpu_vram_mb": int,
        "gpu_encoder": str,         # "h264_nvenc" | "h264_amf" | "h264_qsv" | "libx264"
        "gpu_decode": bool,
    }

def compute_allocation(hw: dict, target_util=0.70, active_videos=1) -> dict:
    return {
        "frame_workers": int,    # cores assigned per video
        "encode_threads": int,
        "gpu_encode": bool,
        "chunk_strategy": str,   # "large" | "small"
    }

def print_hardware_summary(hw, alloc):
    """Print formatted hardware profile on startup."""
```

---

## ═══════════════════════════════════════
## PART 11 — ENGINE: bgmusic.py
## ═══════════════════════════════════════

### Purpose
Generate procedural ambient background music as WAV, then mix with voice audio.

```python
BGM_STYLES = [
    "calm_waves", "zen_garden", "morning_dew", "deep_focus", "soft_piano",
    "crystal_bowl", "forest_stream", "twilight", "lotus", "silent_mind", "bansuri"
]

def generate_bg_music(duration_sec: float, output_path: str,
                       volume=1.0, style="ambient") -> None:
    """
    Pure synthesis (no external files). Uses wave module.
    Generates: sustained sine/triangle tones + light percussion + chord progressions.
    Loopable: repeats to fill total_duration.
    """

def mix_audio_with_bgm(voice_path: str, bgm_path: str,
                        output_path: str, bgm_volume=0.30) -> None:
    """
    Mix voice audio (1.0) + background music (bgm_volume) using pydub.
    Output: MP3 stereo.
    """
```

---

## ═══════════════════════════════════════
## PART 12 — FLASK APP FACTORY (app.py)
## ═══════════════════════════════════════

```python
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["RESOLUTIONS"] = Config.RESOLUTIONS
    app.config["QUALITY_PRESETS"] = Config.QUALITY_PRESETS

    # Create storage dirs
    for d in [Config.STORAGE_DIR, Config.VIDEOS_DIR, Config.JSON_DIR,
              Config.ASSETS_DIR, Config.AUDIO_DIR, Config.EXPORTS_DIR,
              os.path.join(Config.ASSETS_DIR, "images"), ...]:
        os.makedirs(d, exist_ok=True)

    # Init DB with WAL mode
    db.init_app(app)
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))
            conn.commit()
        db.create_all()

    # Logging (rotate at 2MB, only WARNING+)
    log_handler = RotatingFileHandler("server.log", maxBytes=2*1024*1024, backupCount=0)
    log_handler.setLevel(logging.WARNING)
    app.logger.addHandler(log_handler)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    register_blueprints(app)

    # Static file serving
    @app.route("/storage/<path:filename>")
    def serve_storage(filename):
        return send_from_directory(Config.STORAGE_DIR, filename)

    return app
```

---

## ═══════════════════════════════════════
## PART 13 — ROUTE: upload.py
## ═══════════════════════════════════════

### Endpoints

```
GET  /upload/                  → upload.html
POST /upload/validate          → HTMX: validate JSON, return HTML result
POST /upload/process           → validate + create DB records + queue jobs + start worker
GET  /upload/download/reference-schema  → REFERENCE_SCHEMA.json
GET  /upload/download/prompt            → PROMPT_JSON_GENERATOR.md
```

### /upload/process logic

1. Parse JSON from form field `json_content` OR uploaded file (supports .zip with multiple .json)
2. Validate via `validate_json(data)`
3. For each question:
   - Create `Video` record (title from meta fields, video_id = question["id"])
   - Create `JobQueue` record (status="queued")
   - Save JSON to `storage/json/{uuid}.json`
4. Call `_start_processing(app)`
5. Return HTMX response with job count

### Queue Worker (_start_processing, _check_and_start_queued)

```python
_active_jobs = {}      # {job_id: threading.Thread}
_active_lock = threading.Lock()
_cancelled_jobs = set()  # job_ids requested to cancel

def _start_processing(app):
    """Trigger: check for queued jobs and launch workers if capacity available."""
    with app.app_context():
        _check_and_start_queued(app)

def _check_and_start_queued(app):
    """
    Auto-scales workers based on hardware:
    - max_concurrent = hardware allocation
    - slots_free = max_concurrent - len(active_jobs)
    - Take next `slots_free` queued jobs, start threads
    - Distribute cores: total_workers / total_active_videos
    """

def _process_single_job(app, job_id, config_dict, frame_workers):
    """
    Run in daemon thread. Critical implementation notes:
    1. Extract video_id as plain string BEFORE try block (avoids SQLAlchemy stale object crash)
    2. Re-query Video and Job objects inside progress_cb instead of using closed-over references
    3. Wrap all db.session.commit() in try/except with rollback fallback
    4. On InterruptedError: mark job cancelled, delete video record + files
    5. On other exceptions: mark job failed, keep video record with error_message
    """
    video_id = job.video_id  # extract early!

    def progress_cb(stage, percent):
        if _is_cancelled(job_id):
            raise InterruptedError("Job cancelled by user")
        try:
            j = db.session.get(JobQueue, job_id)
            v = Video.query.filter_by(video_id=video_id).first()
            if j: j.stage = stage; j.progress = percent
            if v: v.progress = percent
            db.session.commit()
        except Exception:
            try: db.session.rollback()
            except Exception: pass
```

### Cancel / Mark Cancelled

```python
def _mark_cancelled(job_id: int): _cancelled_jobs.add(job_id)
def _is_cancelled(job_id: int) -> bool: return job_id in _cancelled_jobs
def _clear_cancelled(job_id: int): _cancelled_jobs.discard(job_id)
```

---

## ═══════════════════════════════════════
## PART 14 — ROUTE: queue_routes.py
## ═══════════════════════════════════════

### Endpoints

```
GET  /queue/                         → queue.html (stats + full list)
GET  /queue/list                     → HTMX partial: job list
POST /queue/<job_id>/cancel          → cancel + delete video + restart queue
POST /queue/<job_id>/retry           → reset to queued + restart queue
POST /queue/<job_id>/delete          → delete job + video + files
POST /queue/<job_id>/priority        → update priority (1-4)
POST /queue/clear-completed          → delete all completed jobs
POST /queue/clear-cancelled          → delete all cancelled/failed jobs + files
```

### File Cleanup (_cleanup_video_files)

```python
def _cleanup_video_files(video):
    """Delete output_dir entirely if set (new path).
    Fallback: delete individual files (legacy path).
    Walk up and remove empty parent directories."""
```

---

## ═══════════════════════════════════════
## PART 15 — ROUTE: settings.py
## ═══════════════════════════════════════

### Endpoints

```
GET  /settings/                    → settings.html with all current values
POST /settings/save                → save all form fields at once
POST /settings/save-field          → auto-save single field (HTMX)
POST /settings/reset               → reset all to defaults
GET  /settings/tts-preview         → serve voice sample MP3
POST /settings/tts-generate-samples → pre-generate all voice samples
POST /settings/watermark/upload    → upload watermark image
POST /settings/watermark/delete    → remove watermark
GET  /settings/watermark/status    → HTMX: show current watermark filename
POST /settings/youtube/save-oauth-keys → build client_secrets.json
POST /settings/youtube/upload-secrets → upload client_secrets.json file
GET  /settings/youtube/secrets-status → HTMX: connection status
POST /settings/youtube/remove-secrets → delete oauth files
```

### Settings Keys (50+)

```python
DEFAULTS = {
    "default_resolution": "1080p",
    "default_quality_preset": "P7",
    "default_duration_minutes": "8",
    "default_theme": "dark",
    "default_fps": "30",
    "tts_engine": "edge_tts",
    "tts_lang": "en",
    "tts_tld": "en-IN-PrabhatNeural",
    "max_workers": "4",
    "job_timeout": "600",
    "bgm_enabled": "true",
    "bgm_style": "bansuri",
    "bgm_volume": "0.30",
    "watermark_enabled": "false",
    "watermark_text": "",
    "watermark_opacity": "0.35",
    "auto_youtube_upload": "false",
    "youtube_default_privacy": "public",
    "youtube_default_category": "27",
    "youtube_language": "en",
    "copyright_owner": "",
    "copyright_year": "",
    "content_license": "all-rights-reserved",
    # ... + youtube OAuth fields, storage path, ffmpeg path
}
```

---

## ═══════════════════════════════════════
## PART 16 — ROUTE: videos.py
## ═══════════════════════════════════════

### Endpoints

```
GET  /videos/                → library.html with filters
GET  /videos/list            → HTMX partial: filtered video grid
GET  /videos/<video_id>      → video_detail.html
GET  /videos/<video_id>/stream → serve video file
POST /videos/<video_id>/delete → delete video + files + job
POST /videos/<video_id>/update-meta → update title/tags/etc
```

### Filters

```
?subject=  &topic=  &difficulty=  &status=  &q=  &sort=  &page=
```

---

## ═══════════════════════════════════════
## PART 17 — ROUTE: youtube.py
## ═══════════════════════════════════════

### Endpoints

```
GET  /youtube/                         → youtube.html
GET  /youtube/auth                     → redirect to Google OAuth
GET  /youtube/oauth-callback           → handle code + store token
POST /youtube/<video_id>/upload        → upload to YouTube
GET  /youtube/<video_id>/status        → check upload status (HTMX)
POST /youtube/<video_id>/set-metadata  → update title/desc/tags
```

### OAuth Flow

1. `client_secrets.json` stored at project root (Web app credentials from Google Cloud Console)
2. Scopes: `https://www.googleapis.com/auth/youtube.upload`
3. Token cached in `youtube_token.json`
4. Upload uses `googleapiclient.discovery.build("youtube", "v3", credentials=creds)`
5. Resumable upload for large files

---

## ═══════════════════════════════════════
## PART 18 — ROUTE: dashboard.py
## ═══════════════════════════════════════

```
GET  /              → dashboard.html
GET  /stats         → HTMX partial: stats cards (auto-refresh every 5s)
```

Stats shown:
- Total videos, completed, processing, failed, queued
- Subjects breakdown
- Recent 6 videos
- Active job progress bars

---

## ═══════════════════════════════════════
## PART 19 — TEMPLATES
## ═══════════════════════════════════════

### base.html structure

```html
<!DOCTYPE html>
<html>
<head>
  <!-- Tailwind CSS CDN -->
  <!-- HTMX CDN -->
  <title>{% block title %}{% endblock %} | STEM Video Generator</title>
</head>
<body class="bg-gray-950 text-white min-h-screen flex">
  <!-- Sidebar navigation -->
  <aside class="w-64 bg-gray-900 border-r border-gray-800">
    <nav>
      <a href="/">Dashboard</a>
      <a href="/upload">Upload</a>
      <a href="/videos">Library</a>
      <a href="/queue">Queue</a>
      <a href="/youtube">YouTube</a>
      <a href="/export">Export</a>
      <a href="/assets">Assets</a>
      <a href="/settings">Settings</a>
    </nav>
  </aside>

  <!-- Main content -->
  <main class="flex-1 p-8">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

### HTMX Patterns Used

```html
<!-- Auto-refresh stats every 5 seconds -->
<div hx-get="/stats" hx-trigger="every 5s" hx-swap="outerHTML">

<!-- Live JSON validation as user types -->
<textarea name="json_content"
          hx-post="/upload/validate"
          hx-trigger="input delay:500ms"
          hx-target="#validation-result">

<!-- Cancel job (removes card on success) -->
<button hx-post="/queue/42/cancel" hx-swap="delete" hx-target="closest .job-card">

<!-- Auto-save single setting field -->
<input name="bgm_volume"
       hx-post="/settings/save-field"
       hx-trigger="change"
       hx-vals='{"key": "bgm_volume"}'>

<!-- Progress polling for active job -->
<div hx-get="/queue/42/progress"
     hx-trigger="every 2s [document.querySelector('.job-active')]"
     hx-swap="outerHTML">
```

---

## ═══════════════════════════════════════
## PART 20 — REQUIREMENTS.txt
## ═══════════════════════════════════════

```
Flask==3.1.0
python-dotenv==1.0.1
Flask-SQLAlchemy==3.1.1
SQLAlchemy==2.0.36
Pillow==11.1.0
gTTS==2.5.4
edge-tts
pydub==0.25.1
moviepy==2.1.2
CairoSVG==2.7.1
openpyxl==3.1.5
google-api-python-client==2.159.0
google-auth-oauthlib==1.2.1
jsonschema==4.23.0
Werkzeug==3.1.3
psutil
imageio-ffmpeg
geopandas
geodatasets
```

---

## ═══════════════════════════════════════
## PART 21 — CRITICAL IMPLEMENTATION NOTES
## ═══════════════════════════════════════

### 1. SQLAlchemy Thread Safety (MOST IMPORTANT)

The background thread (`_process_single_job`) runs inside `with app.app_context()`. SQLAlchemy ORM objects become stale after `db.session.commit()`.

**Problem**: Capturing `video` object in `progress_cb` closure → if user deletes Video from UI mid-render → any `db.session.commit()` triggers `ObjectDeletedError` → session corrupted → all subsequent commits fail with `PendingRollbackError`.

**Solution**:
```python
# Extract plain string BEFORE the try block
video_id = job.video_id   # plain str, not ORM object attribute

def progress_cb(stage, percent):
    # Re-query by ID every time — never use closed-over ORM objects
    j = db.session.get(JobQueue, job_id)
    v = Video.query.filter_by(video_id=video_id).first()
    ...
    try:
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass

# In except blocks — use plain string, not video.video_id
except Exception as e:
    print(f"[Video] FAIL  {video_id}: {e}")   # ← video_id string, not video.video_id
    db.session.expire_all()
    video_obj = Video.query.filter_by(video_id=video_id).first()
    ...
```

### 2. ProcessPoolExecutor in Threads

Frame rendering uses `ProcessPoolExecutor` inside a daemon thread. Worker functions (`_render_chunk`) must be module-level (not nested) to be picklable.

### 3. edge_tts in Non-Main Threads

`edge_tts` uses asyncio. In Python 3.12, `asyncio.get_event_loop()` raises `RuntimeError` in threads without a running loop. Always use:
```python
asyncio.run(_run())   # not asyncio.get_event_loop().run_until_complete()
```

### 4. SQLite WAL Mode

Required for concurrent multi-video writes. Must be set with `PRAGMA journal_mode=WAL` at connection time, not just in SQLAlchemy config.

### 5. output_dir Pattern

Every video gets a unique output directory: `storage/videos/{video_id}/`
- Contains: `video.mp4`, `thumb.png`, `audio.mp3`, `mixed.mp3`, `frames/`, `audio/`
- On success: `frames/` and `audio/` subdirs are deleted (keeping only final outputs)
- On cancel/delete: entire `output_dir` is `shutil.rmtree`'d

### 6. Settings Dynamic Apply

`_get_config()` in `upload.py` must read from DB every call (not cache):
```python
def _get_config():
    """Build config dict from DB settings — called fresh each time."""
    from models import Setting
    return {
        "TTS_ENGINE": Setting.get("tts_engine", app.config["TTS_ENGINE"]),
        "BGM_ENABLED": Setting.get("bgm_enabled", "true").lower() == "true",
        ...
    }
```

### 7. Video ID Slugging

The `id` field from JSON becomes `video_id` in the database and the `output_dir` folder name. It must be a valid filesystem path component. Validate with:
```python
import re
assert re.match(r'^[a-z0-9][a-z0-9\-_]{2,98}$', video_id)
```

### 8. Startup Job Resume

On Flask startup (only in main process, not reloader):
1. Find all jobs with `status="processing"` → reset to `status="queued"` (they crashed mid-run)
2. Find all jobs with `status="queued"` → call `_start_processing(app)` to resume

```python
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    # only in actual server process, not werkzeug reloader
    _resume_on_startup(app)
```

---

## ═══════════════════════════════════════
## PART 22 — SETUP INSTRUCTIONS
## ═══════════════════════════════════════

```bash
# 1. Clone / create project directory
mkdir DSL && cd DSL
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install FFmpeg (required for video encoding)
sudo apt install ffmpeg      # Ubuntu/Debian
# OR: brew install ffmpeg    # macOS

# 4. Download Poppins fonts (optional but recommended)
mkdir -p storage/assets/fonts
# Download from Google Fonts: Poppins Regular, Medium, SemiBold, Bold
# Place in storage/assets/fonts/

# 5. Run
python app.py
# Open http://localhost:5000

# 6. Optional: set environment variables
export TTS_ENGINE=edge_tts
export BGM_ENABLED=true
export DEFAULT_RESOLUTION=1080p
export DEFAULT_QUALITY_PRESET=P5
```

---

## ═══════════════════════════════════════
## PART 23 — GENERATION ORDER FOR AI
## ═══════════════════════════════════════

When regenerating this project with an AI assistant, generate files in this order:

```
1.  requirements.txt
2.  config.py
3.  models.py
4.  engine/__init__.py
5.  engine/validator.py
6.  engine/audio.py
7.  engine/sync.py
8.  engine/renderer.py          ← largest file, ~2500 lines
9.  engine/bgmusic.py
10. engine/hardware.py
11. engine/free_media.py
12. engine/manim_renderer.py
13. engine/pipeline.py          ← orchestrates all engine modules
14. routes/__init__.py
15. routes/upload.py            ← most complex route (queue logic)
16. routes/queue_routes.py
17. routes/settings.py
18. routes/videos.py
19. routes/dashboard.py
20. routes/youtube.py
21. routes/export.py
22. routes/assets.py
23. app.py
24. templates/base.html
25. templates/dashboard.html
26. templates/upload.html
27. templates/queue.html
28. templates/library.html
29. templates/settings.html
30. templates/youtube.html
31. templates/export.html
32. templates/video_detail.html
33. templates/assets.html
34. templates/components/stats_cards.html
35. templates/components/queue_list.html
36. templates/components/queue_item.html
37. templates/components/video_grid.html
38. templates/404.html
39. templates/500.html
```

### Key Prompts Per File

**For engine/renderer.py**: "Generate a Pillow-based video frame renderer that creates 1920x1080 educational video frames matching a PPT style: dark navy header (#1A237E) with question and options, orange accent stripe (#EF6C00), white body. Scale everything by `height/1080`. Implement mode-aware headers and 30+ body element draw methods each returning new_y."

**For engine/pipeline.py**: "Generate a VideoPipeline class that orchestrates: TTS audio → timeline sync → asset resolution → parallel frame rendering (ProcessPoolExecutor) → FFmpeg encoding (GPU h264_nvenc → CPU libx264 fallback) → thumbnail. Include CPU throttling (nice +10 + 70% affinity) and a GPU encode lock for concurrent video safety."

**For routes/upload.py**: "Generate a Flask blueprint with queue processing. Use daemon threads to run jobs. CRITICAL: extract video_id as plain string before try block; re-query ORM objects by ID in progress_cb; wrap all db.session.commit() in try/except + rollback fallback; use plain string video_id in except blocks, never access video.video_id after possible deletion."

**For engine/sync.py**: "Build a timeline using (scene_idx, step_idx) dict lookup — never sequential iteration. Implement accumulation-based get_active_state() where same target replaces, different targets coexist. Special: instruction_text clears all body elements; final_answer sets show_correct permanently."

---

*End of PROJECT_GENERATION_PROMPT.md*

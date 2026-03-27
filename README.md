# STEM Video Generator

A **deterministic JSON-driven video generation engine** for educational content. Feed it a JSON file describing a math, physics, chemistry, or reasoning problem — it produces a fully rendered video with narration, step-by-step visuals, and background music.

Built for teachers, coaching institutes, and content creators who need to produce thousands of educational videos at scale.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install FFmpeg (required for video encoding)
# Windows: winget install ffmpeg
# Mac: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# 3. Run the application
python app.py

# 4. Open in browser
# http://localhost:5000
```

---

## What It Does

1. **You write JSON** describing a question, its solution steps, and how to render each step
2. **The engine generates audio** (text-to-speech narration for each step)
3. **It renders frames** (Pillow-based, dark theme, large readable text)
4. **It syncs audio + video** (each visual appears exactly when narrated)
5. **It adds background music** (10 meditation-style options, royalty-free)
6. **It encodes to MP4** (FFmpeg, H.264, configurable resolution/quality)

No AI at runtime. The engine executes your JSON instructions exactly.

---

## Features

| Feature | Description |
|---------|-------------|
| **JSON DSL** | Write rendering instructions as JSON — scenes, steps, render actions |
| **Multi-Subject** | Mathematics, Physics, Chemistry, Reasoning, and any extensible subject |
| **Video Settings** | 360p to 4K resolution, 7 quality presets (P1-P7), dark/light themes |
| **Background Music** | 10 meditation-style BGM options, procedurally generated, YouTube-safe |
| **TTS Narration** | Google TTS (Indian English) or pyttsx3 (offline), configurable accent |
| **Batch Processing** | Upload ZIP with hundreds of JSON files, process in parallel |
| **Video Library** | Browse by subject/topic/subtopic, filter, search, paginate |
| **Queue System** | Priority-based job queue with progress tracking and retry |
| **Preview** | Render 5 key frames before committing to full video generation |
| **Excel Export** | Download spreadsheets: master list, subject-wise, topic-wise, YouTube links |
| **YouTube Management** | Manual URL entry or API upload (optional), bulk operations |
| **Dashboard** | Stats, recent videos, subject distribution, active jobs overview |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / Flask 3.1 / Jinja2 |
| Frontend | HTMX 2.0 / Tailwind CSS (CDN) |
| Database | SQLite (via SQLAlchemy) |
| Rendering | Pillow (frames) + FFmpeg (encoding) |
| Audio | gTTS or pyttsx3 (narration) + pydub (mixing) |
| BGM | Pure Python synthesis (no external files) |
| Export | openpyxl (Excel) |

No Node.js. No React. No build tools. Just Python.

---

## Project Structure

```
DSL/
├── app.py                      # Flask application entry point
├── config.py                   # All configuration and constants
├── models.py                   # SQLAlchemy models (Video, JobQueue, Setting)
├── requirements.txt            # Python dependencies
│
├── engine/                     # Video generation engine
│   ├── validator.py            # JSON schema validation
│   ├── audio.py                # TTS generation + concatenation
│   ├── bgmusic.py              # 10 procedural BGM generators
│   ├── renderer.py             # Pillow frame renderer (all visual components)
│   ├── sync.py                 # Audio-video timeline builder + state machine
│   └── pipeline.py             # End-to-end orchestration
│
├── routes/                     # Flask blueprints
│   ├── dashboard.py            # / — home dashboard
│   ├── upload.py               # /upload — JSON editor + processing
│   ├── videos.py               # /videos — library, detail, preview, download
│   ├── queue_routes.py         # /queue — job monitoring
│   ├── youtube.py              # /youtube — upload management
│   ├── export.py               # /export — Excel/CSV generation
│   └── settings.py             # /settings — configuration panel
│
├── templates/                  # Jinja2 templates
│   ├── base.html               # Layout: sidebar + HTMX + Tailwind
│   ├── dashboard.html          # Stats and overview
│   ├── upload.html             # JSON editor with settings
│   ├── library.html            # Video grid with filters
│   ├── video_detail.html       # Player, metadata, actions
│   ├── preview.html            # Key frame preview
│   ├── queue.html              # Job queue monitoring
│   ├── youtube.html            # YouTube link management
│   ├── export.html             # Export configuration
│   ├── settings.html           # All settings
│   ├── 404.html / 500.html     # Error pages
│   └── components/             # HTMX partials
│
├── static/                     # CSS + JS
├── storage/                    # Generated files
│   ├── videos/                 # Output MP4s (by subject/topic)
│   ├── json/                   # Uploaded JSON files
│   ├── audio/                  # Generated audio
│   ├── assets/                 # Images + SVGs
│   └── exports/                # Excel files
│
└── docs/                       # Documentation
    ├── SETUP.md
    ├── JSON_DSL_GUIDE.md
    ├── API_REFERENCE.md
    └── ARCHITECTURE.md
```

---

## Sample JSON

```json
[
  {
    "id": "q-addition-001",
    "meta": {
      "subject": "Mathematics",
      "topic": "Arithmetic",
      "subtopic": "Addition",
      "difficulty": "easy"
    },
    "scenes": [
      {
        "type": "question",
        "text": "What is 25 + 37?",
        "audio": "What is twenty five plus thirty seven?",
        "render": { "action": "show", "target": "question_block" }
      },
      {
        "type": "solution",
        "steps": [
          {
            "text": "5 + 7 = 12",
            "audio": "First, add the units. Five plus seven equals twelve.",
            "render": { "action": "show", "target": "equation", "value": "5 + 7 = 12" }
          },
          {
            "text": "2 + 3 + 1 = 6",
            "audio": "Now add the tens with carry. Two plus three plus one equals six.",
            "render": { "action": "update", "target": "equation", "value": "2 + 3 + 1 = 6" }
          },
          {
            "text": "Answer: 62",
            "audio": "So twenty five plus thirty seven equals sixty two.",
            "render": { "action": "show_result", "target": "final_answer", "value": "62" }
          }
        ]
      }
    ]
  }
]
```

See [docs/JSON_DSL_GUIDE.md](docs/JSON_DSL_GUIDE.md) for the full specification.

---

## Documentation

| Document | Description |
|----------|-------------|
| [SETUP.md](docs/SETUP.md) | Installation, prerequisites, first run |
| [JSON_DSL_GUIDE.md](docs/JSON_DSL_GUIDE.md) | How to write JSON files — every field, action, and component |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | All 32 HTTP endpoints with parameters |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, rendering pipeline, sync engine |

---

## Background Music

10 royalty-free, YouTube-safe BGM styles (procedurally generated, no external files):

| Style | Mood |
|-------|------|
| Calm Waves | Slow sine pad, like gentle ocean |
| Zen Garden | Soft pentatonic chimes |
| Morning Dew | Light airy pad with shimmer |
| Deep Focus | Low drone with subtle movement |
| Soft Piano | Gentle arpeggio pattern |
| Crystal Bowl | Singing bowl resonance |
| Forest Stream | Layered nature ambience |
| Twilight | Warm evening chord progression |
| Lotus | Indian tanpura-inspired drone |
| Silent Mind | Barely-there ambient hum |

BGM is enabled by default. Select style per-video or globally in Settings.

---

## Target Audience

- **Exam prep** — SSC, UPSC, Banking, Railways, JEE, NEET, CAT, GATE
- **School boards** — CBSE, ICSE, State boards (Class 6-12)
- **Coaching institutes** — Bulk video generation for course content
- **YouTube educators** — Batch produce and upload educational videos
- **Self-study** — Step-by-step problem solving videos

---

## License

Internal project. All generated BGM is royalty-free for commercial use.

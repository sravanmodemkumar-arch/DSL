# STEM Video Generator

**AI-powered educational video generation engine driven by a JSON DSL.**

Upload a structured JSON file describing a question, topic, or concept. The engine generates a fully narrated, animated educational video with TTS audio, visual elements, background music, and YouTube-ready metadata.

---

## Features

- **8 Video Modes** -- MCQ, Topic Explanation, True/False, Fill-in-the-Blank, Numerical, Match-the-Following, Assertion-Reason, Sequence/Ordering
- **6-Layer Visual System** -- Pillow illustrations, free stock photos, free stock videos, matplotlib graphs, RDKit molecules, Manim animations
- **74 Built-in Visuals** -- Biology, Physics, Chemistry, Math, Geography, Polity, Economics, Computer Science, Reasoning
- **20 Manim Animated Scenes** -- Function plots, wave propagation, projectile motion, derivatives, unit circle, and more
- **Word-Level Audio Sync** -- Edge TTS with karaoke-style narration highlighting
- **Background Music** -- 8 royalty-free educational BGM tracks, default ON
- **YouTube Integration** -- OAuth2 upload with auto-generated SEO metadata
- **Web Dashboard** -- Upload, preview, library, queue, settings, export, assets
- **Batch Processing** -- Upload multiple questions, process concurrently
- **7 Quality Presets** -- P1 (Preview) to P7 (Maximum 4K 60fps 25Mbps)

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Optional (for advanced visuals):**
```bash
pip install matplotlib      # Scientific graphs
pip install rdkit           # 2D molecular structures
pip install manim           # Animated math/physics scenes
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings (defaults work out of the box)
```

### 3. Run

```bash
python app.py
```

Open http://127.0.0.1:5000

### 4. Generate a Video

1. Go to **Upload** page
2. Paste or upload a JSON file (see `sample_all_elements.json` for examples)
3. Click **Process** -- the job enters the queue
4. Watch progress on the **Queue** page
5. Download or preview the video from the **Library**

---

## Project Structure

```
DSL/
├── app.py                    # Flask entry point
├── config.py                 # All configuration (resolution, quality, TTS, BGM, etc.)
├── models.py                 # Database models (Video, JobQueue, Setting)
├── requirements.txt          # Python dependencies
│
├── engine/                   # Core video generation
│   ├── audio.py              # TTS with word-level timestamps (edge_tts/gTTS)
│   ├── bgmusic.py            # Background music (8 royalty-free tracks)
│   ├── free_media.py         # Auto-fetch images/videos (Pixabay/Wikimedia/Pexels/Unsplash)
│   ├── manim_renderer.py     # 20 animated Manim scene templates
│   ├── pipeline.py           # End-to-end: JSON -> audio -> frames -> video
│   ├── renderer.py           # Pillow frame renderer (74 visuals, 35+ elements)
│   ├── sync.py               # Audio-video sync & timeline builder
│   └── validator.py          # JSON schema validation
│
├── routes/                   # Flask blueprints
│   ├── dashboard.py          # Home page with stats
│   ├── upload.py             # JSON upload & processing
│   ├── videos.py             # Video library & filtering
│   ├── queue_routes.py       # Job queue management
│   ├── youtube.py            # YouTube OAuth & upload
│   ├── export.py             # Excel/CSV export
│   ├── settings.py           # Settings management
│   └── assets.py             # Asset upload & management
│
├── templates/                # Jinja2 HTML (HTMX + Tailwind CDN)
├── static/                   # CSS, JS, voice samples
├── storage/                  # Generated videos, audio, JSON, exports, assets
│
├── PROMPT_JSON_GENERATOR.md  # AI prompt for generating valid JSON (v5.0)
├── REFERENCE_SCHEMA.json     # Annotated schema with inline docs
└── sample_all_elements.json  # Example JSON with all element types
```

---

## JSON DSL Overview

The engine is driven by a JSON DSL (Domain-Specific Language). Each JSON file defines one or more educational videos.

```json
[
  {
    "id": "q-math-percentage-15-of-240",
    "mode": "mcq",
    "thumbnail": { "title": "Percentage", "subtitle": "Find 15% of 240", ... },
    "meta": { "subject": "Mathematics", "topic": "Percentage", ... },
    "youtube": { "title": "...", "description": "...", "tags": [...] },
    "question": { "text": "...", "options": [...], "correct": "b" },
    "scenes": [
      { "type": "question", "audio": "...", "render": { "action": "show", "target": "question_block" } },
      { "type": "options",  "audio": "...", "render": { "action": "show", "target": "options_grid" } },
      { "type": "concept",  "steps": [
        { "text": "...", "audio": "...", "render": { "action": "show", "target": "highlight_box", "text": "..." } },
        { "text": "...", "audio": "...", "render": { "action": "show", "target": "equation", "value": "..." } }
      ]}
    ]
  }
]
```

See [PROMPT_JSON_GENERATOR.md](PROMPT_JSON_GENERATOR.md) for the complete DSL specification and [REFERENCE_SCHEMA.json](REFERENCE_SCHEMA.json) for an annotated schema with inline documentation.

---

## Video Modes

| Mode | Description | Header Layout | End Element |
|------|-------------|---------------|-------------|
| `mcq` | Multiple choice (default) | Question + 4 options | `final_answer` |
| `topic` | Topic explanation | Slim title bar | None needed |
| `true_false` | True or False | Question + T/F pills | `final_answer` |
| `fill_blank` | Fill in the blank | Question with `___` | `blank_reveal` |
| `numerical` | Calculate answer | Question + badge | `numerical_answer` |
| `match` | Match the following | Minimal bar | `match_columns` |
| `assertion` | Assertion & Reason | A + R header | `final_answer` |
| `sequence` | Arrange in order | Minimal bar | `sequence_list` |

---

## Visual System (6 Layers)

| Layer | Source | Requires |
|-------|--------|----------|
| `builtin_visual` | 74 Pillow-drawn diagrams | Nothing (offline) |
| `subject_image` | Pixabay/Wikimedia/Pexels/Unsplash | Internet + API keys (optional) |
| `video_clip` | Pixabay/Pexels video | Internet + API keys (optional) |
| `matplotlib_plot` | Line/bar/scatter/pie/histogram | `pip install matplotlib` |
| `rdkit_mol` | 2D molecular structure from SMILES | `pip install rdkit` |
| `manim_scene` | 20 animated templates | `pip install manim` |

All optional layers fall back gracefully if their library is not installed.

---

## Render Targets (35+)

**Layout:** `question_block`, `options_grid`, `option_a/b/c/d`, `final_answer`

**Text/Concept:** `concept_text`, `highlight_box`, `instruction_text`, `formula_block`

**Math:** `equation`, `digit_boxes`, `running_sum`, `fraction`, `sum_box`, `shortcut_columns`, `number_line`

**Science:** `chem_equation`, `flow_chart`, `key_facts`, `process_steps`, `two_col_text`, `t_account`

**General:** `table`, `timeline`, `memory_trick`, `analogy`, `image`, `svg`

**Mode-specific:** `title_card`, `section_header`, `blank_reveal`, `match_columns`, `sequence_list`, `numerical_answer`

**Advanced:** `builtin_visual`, `subject_image`, `video_clip`, `matplotlib_plot`, `rdkit_mol`, `manim_scene`

---

## Quality Presets

| Preset | Bitrate | FPS | Use Case |
|--------|---------|-----|----------|
| P1 | 1 Mbps | 24 | Quick preview |
| P2 | 2 Mbps | 24 | Draft review |
| P3 | 4 Mbps | 30 | Mobile viewing |
| P4 | 6 Mbps | 30 | Standard quality |
| P5 | 10 Mbps | 30 | YouTube upload |
| P6 | 15 Mbps | 60 | High quality |
| P7 | 25 Mbps | 60 | Maximum quality (default) |

---

## Configuration

All settings can be configured via:
1. `.env` file (environment variables)
2. Web dashboard **Settings** page (persisted in SQLite)
3. `config.py` defaults

Key settings: resolution (360p-4K), quality preset (P1-P7), TTS engine/voice, BGM style/volume, watermark, YouTube OAuth.

---

## API Keys (Optional)

For auto-fetching stock images and videos, add API keys to `.env`:

```env
PIXABAY_API_KEY=your_key_here     # pixabay.com/api/docs/
PEXELS_API_KEY=your_key_here      # pexels.com/api/
UNSPLASH_API_KEY=your_key_here    # unsplash.com/developers
```

Wikimedia Commons works without any API key. Pixabay works at reduced rate without a key.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, Flask |
| Frontend | Jinja2 + HTMX + Tailwind CSS (CDN) |
| Database | SQLite (WAL mode) |
| Frame Rendering | Pillow (PIL) |
| Video Encoding | FFmpeg (GPU -> CPU fallback) |
| TTS | Edge TTS (primary), gTTS (fallback) |
| Audio Mixing | pydub |
| Graphs | matplotlib |
| Molecules | RDKit |
| Animations | Manim Community Edition |
| YouTube | Google API Client + OAuth2 |
| Export | openpyxl (Excel) |

---

## License

This project is proprietary. All rights reserved.

# STEM Video Generator — Ultra-Pro Degree-Level Generation Prompt

> **Purpose**: Complete specification to regenerate the entire project from scratch at university/competitive-exam level.
> Covers architecture, all engine modules, DSL schema, render targets, subject-specific science, and code contracts.
> Written for AI coding assistants. Generate files in the order listed in Part 24.

---

## ═══════════════════════════════════════
## PART 1 — VISION & SCOPE
## ═══════════════════════════════════════

Build a **STEM Video Generator** — a Flask web application that converts structured JSON into
fully animated, narrated, degree-level educational MP4 videos.

### What It Produces
- Narrated videos for MCQ, concept explanation, derivation, lab procedure, diagram annotation
- Subject-aware visuals: LaTeX equations, molecular structures, circuit diagrams, maps, cell diagrams
- 8 subject themes with distinct color palettes (Math, Physics, Chemistry, Biology, Geography, History, Economics, Polity)
- Manim-powered mathematical animations (3Blue1Brown quality)
- Progressive step-by-step derivations with equation morphing
- Real scientific data via free APIs (PubChem, PDB, World Bank, NCBI, NASA)
- Word-level synchronized narration (karaoke highlighting)
- Background music from local asset library
- Output: H.264 MP4 (360p → 4K), exported to library + optional YouTube upload

### User Flow
1. Upload JSON file describing questions/topics
2. System validates against DSL schema
3. Each question → background job → pipeline:
   - TTS audio generation (edge_tts with word timestamps)
   - Timeline sync (audio segments ↔ render events)
   - Parallel frame rendering (ProcessPoolExecutor)
   - FFmpeg encoding (GPU h264_nvenc → CPU libx264 fallback)
4. Completed videos shown in web library
5. Optional YouTube OAuth2 upload

---

## ═══════════════════════════════════════
## PART 2 — TECHNOLOGY STACK
## ═══════════════════════════════════════

### Core
```
Python         3.12
Flask          3.1.0
SQLAlchemy     2.0.36
SQLite         WAL mode (concurrent reads + writes)
Pillow         11.x       Frame rendering (PPT-style PNG frames)
FFmpeg         system     H.264 encoding, audio mux, concat
edge_tts                  Word-level TTS (Microsoft Neural voices)
pydub                     Audio processing
```

### Scientific Visualization
```
matplotlib     3.x        LaTeX mathtext rendering, charts, plots
numpy          2.x        Array math, signal processing
scipy          1.x        Curve fitting, transforms, numerical methods
sympy          1.x        Symbolic math → LaTeX string generation
manim-community           Mathematical animation engine (3Blue1Brown)
plotly         5.x        Interactive charts → static PNG via kaleido
kaleido                   Plotly static export
networkx       3.x        Graph/network diagrams (food webs, phylogenetics)
schemdraw                 Electric circuit diagrams
```

### Subject Science Packages
```
rdkit                     Molecule structure 2D rendering
pubchempy                 PubChem REST API wrapper
biopython                 DNA/protein sequences, phylogenetics
geopandas                 Choropleth maps, India/world maps
cartopy                   Geospatial projections
shapely                   Geometry for maps
```

### Web & Export
```
openpyxl                  Excel export
google-api-python-client  YouTube OAuth2 upload
google-auth-oauthlib
HTMX                      Partial page updates (CDN)
Tailwind CSS              Styling (CDN)
```

### requirements.txt (complete)
```
flask==3.1.0
flask-sqlalchemy==3.1.1
flask-wtf==1.2.2
python-dotenv==1.0.1
pillow==11.1.0
edge-tts==6.1.12
pydub==0.25.1
openpyxl==3.1.5
google-api-python-client==2.159.0
google-auth-oauthlib==1.2.1
requests==2.32.3
numpy>=1.26.0
scipy>=1.12.0
matplotlib>=3.8.0
sympy>=1.12
plotly>=5.18.0
kaleido==0.2.1
networkx>=3.2
schemdraw>=0.18
manim>=0.18.0
rdkit>=2023.9.1
pubchempy>=1.0.4
biopython>=1.83
geopandas>=0.14.0
cartopy>=0.22.0
shapely>=2.0.0
```

---

## ═══════════════════════════════════════
## PART 3 — FILE STRUCTURE (COMPLETE)
## ═══════════════════════════════════════

```
DSL/
├── app.py                          # Flask factory + WAL mode + startup resume
├── config.py                       # Config class with subject themes, all settings
├── models.py                       # Video, JobQueue, Setting models
├── requirements.txt
│
├── engine/
│   ├── __init__.py                 # Re-exports
│   ├── validator.py                # JSON DSL schema validation
│   ├── audio.py                    # edge_tts + word-level timestamps
│   ├── sync.py                     # build_timeline() + get_active_state()
│   ├── renderer.py                 # FrameRenderer (main compositor, subject themes)
│   ├── compositor.py               # NEW: Multi-layer Pillow compositing
│   ├── latex_renderer.py           # NEW: LaTeX → PNG via matplotlib.mathtext + sympy
│   ├── animator.py                 # NEW: 8 animation types with easing
│   ├── pipeline.py                 # VideoPipeline orchestrator (7 stages)
│   ├── hardware.py                 # CPU/GPU detection + worker allocation
│   ├── bgmusic.py                  # Procedural ambient background music
│   ├── manim_renderer.py           # 30+ Manim animation templates (incl. 3D)
│   ├── free_media.py               # Stock photo/video auto-fetch
│   ├── data_fetcher.py             # NEW: PubChem, PDB, World Bank, NCBI, NASA APIs
│   └── subjects/
│       ├── __init__.py
│       ├── math_renderer.py        # Manim math, 3D graphs, function plots, geometry
│       ├── physics_renderer.py     # Circuit diagrams, Bohr model, ray diagrams, waves
│       ├── chemistry_renderer.py   # RDKit molecules, periodic table, energy diagrams
│       ├── biology_renderer.py     # Cell diagrams, Punnett squares, food chains, DNA
│       └── geography_renderer.py   # GeoPandas choropleth, India/world maps
│
├── routes/
│   ├── __init__.py
│   ├── dashboard.py
│   ├── upload.py                   # Upload + validate + queue + run pipeline
│   ├── videos.py                   # Library with search/filter/pagination
│   ├── queue_routes.py             # Cancel, retry, delete, prioritize
│   ├── settings.py                 # 50+ settings UI
│   ├── youtube.py                  # OAuth2 YouTube upload
│   ├── export.py                   # Excel/CSV export
│   └── assets.py                   # Asset browser + upload
│
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── library.html
│   ├── queue.html
│   ├── settings.html
│   ├── youtube.html
│   ├── video_detail.html
│   ├── assets.html
│   └── components/
│       ├── stats_cards.html
│       ├── job_row.html
│       ├── video_card.html
│       └── progress_bar.html
│
├── static/
│   ├── css/main.css
│   └── js/
│       ├── upload.js               # Live JSON validation UI
│       └── queue.js                # SSE progress updates
│
├── storage/
│   ├── videos/
│   ├── json/
│   ├── audio/
│   ├── exports/
│   └── assets/
│       ├── bgm/
│       ├── fonts/                  # Noto Sans + Noto Sans Math + Noto Serif
│       ├── watermark/
│       ├── cache/                  # API response cache
│       └── images/
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_validator.py
    │   ├── test_sync.py
    │   └── test_renderer.py
    ├── integration/
    │   └── test_pipeline.py
    └── api/
        └── test_routes.py
```

---

## ═══════════════════════════════════════
## PART 4 — config.py
## ═══════════════════════════════════════

### Subject Color Palettes (CRITICAL — used by renderer.py)
```python
SUBJECT_THEMES = {
    "math": {
        "header_bg":   "#0D1B2A",   # deep navy
        "accent":      "#F4631E",   # orange-red
        "accent2":     "#FFB347",   # amber
        "text":        "#FFFFFF",
        "body_bg":     "#F0F4FF",
        "card_bg":     "#FFFFFF",
        "highlight":   "#FFE066",
        "correct":     "#2ECC71",
        "wrong":       "#E74C3C",
        "border":      "#B0BEC5",
    },
    "physics": {
        "header_bg":   "#0A0A23",   # electric dark blue
        "accent":      "#00CFFF",
        "accent2":     "#7F00FF",
        "text":        "#FFFFFF",
        "body_bg":     "#EFF6FF",
        "card_bg":     "#FFFFFF",
        "highlight":   "#00CFFF",
        "correct":     "#00E676",
        "wrong":       "#FF5252",
        "border":      "#90CAF9",
    },
    "chemistry": {
        "header_bg":   "#1A0533",   # deep purple
        "accent":      "#BB86FC",
        "accent2":     "#CF6679",
        "text":        "#FFFFFF",
        "body_bg":     "#F5F0FF",
        "card_bg":     "#FFFFFF",
        "highlight":   "#BB86FC",
        "correct":     "#69F0AE",
        "wrong":       "#FF6E40",
        "border":      "#CE93D8",
    },
    "biology": {
        "header_bg":   "#0D3320",   # forest green
        "accent":      "#56C596",
        "accent2":     "#A8E063",
        "text":        "#FFFFFF",
        "body_bg":     "#F0FFF4",
        "card_bg":     "#FFFFFF",
        "highlight":   "#B2FFB2",
        "correct":     "#00C853",
        "wrong":       "#FF6D00",
        "border":      "#A5D6A7",
    },
    "geography": {
        "header_bg":   "#003D4D",   # deep teal
        "accent":      "#26C6DA",
        "accent2":     "#80DEEA",
        "text":        "#FFFFFF",
        "body_bg":     "#E0F7FA",
        "card_bg":     "#FFFFFF",
        "highlight":   "#B2EBF2",
        "correct":     "#00E5FF",
        "wrong":       "#FF7043",
        "border":      "#80CBC4",
    },
    "history": {
        "header_bg":   "#3E1C00",   # dark brown
        "accent":      "#FF8A65",
        "accent2":     "#FFD54F",
        "text":        "#FFFFFF",
        "body_bg":     "#FFF8F0",
        "card_bg":     "#FFFFFF",
        "highlight":   "#FFE0B2",
        "correct":     "#66BB6A",
        "wrong":       "#EF5350",
        "border":      "#FFCC80",
    },
    "economics": {
        "header_bg":   "#002B36",   # dark teal
        "accent":      "#2AA198",
        "accent2":     "#268BD2",
        "text":        "#FFFFFF",
        "body_bg":     "#F0FFFA",
        "card_bg":     "#FFFFFF",
        "highlight":   "#B2DFDB",
        "correct":     "#26A69A",
        "wrong":       "#EF5350",
        "border":      "#80CBC4",
    },
    "polity": {
        "header_bg":   "#4A0020",   # maroon
        "accent":      "#FF4081",
        "accent2":     "#FF8A65",
        "text":        "#FFFFFF",
        "body_bg":     "#FFF0F5",
        "card_bg":     "#FFFFFF",
        "highlight":   "#FFD6E7",
        "correct":     "#69F0AE",
        "wrong":       "#FF5252",
        "border":      "#F48FB1",
    },
    "default": {
        "header_bg":   "#1A237E",   # indigo (fallback)
        "accent":      "#EF6C00",
        "accent2":     "#42A5F5",
        "text":        "#FFFFFF",
        "body_bg":     "#F5F5F5",
        "card_bg":     "#FFFFFF",
        "highlight":   "#FFF9C4",
        "correct":     "#2ECC71",
        "wrong":       "#E74C3C",
        "border":      "#B0BEC5",
    },
}
```

### Resolution Map
```python
RESOLUTIONS = {
    "360p":  (640,  360),
    "720p":  (1280, 720),
    "1080p": (1920, 1080),
    "2K":    (2560, 1440),
    "4K":    (3840, 2160),
}
```

### Quality Presets
```python
QUALITY_PRESETS = {
    "P1": {"bitrate": "1M",  "fps": 24, "antialiasing": False, "label": "Preview"},
    "P2": {"bitrate": "2M",  "fps": 24, "antialiasing": True,  "label": "Draft"},
    "P3": {"bitrate": "4M",  "fps": 30, "antialiasing": True,  "label": "Mobile"},
    "P4": {"bitrate": "6M",  "fps": 30, "antialiasing": True,  "label": "Standard"},
    "P5": {"bitrate": "10M", "crf": "22", "fps": 30, "antialiasing": True, "label": "YouTube"},
    "P6": {"bitrate": "15M", "crf": "20", "fps": 60, "antialiasing": True, "label": "High Quality"},
    "P7": {"bitrate": "25M", "crf": "18", "fps": 60, "antialiasing": True, "label": "Maximum"},
}
```

### TTS Voices (edge_tts)
```
en-IN-PrabhatNeural   — Indian male (clear, default)
en-IN-NeerjaNeural    — Indian female (clear)
en-IN-AaravNeural     — Indian male (young)
en-IN-AnanyaNeural    — Indian female (warm)
hi-IN-SwaraNeural     — Hindi female
hi-IN-MadhurNeural    — Hindi male
```

---

## ═══════════════════════════════════════
## PART 5 — models.py
## ═══════════════════════════════════════

Three SQLAlchemy models: **Video**, **JobQueue**, **Setting**.

### Video model fields
```
id, video_id (UUID str, unique, indexed), title
subject, chapter, topic, subtopic, difficulty
exam_tags, purpose_tags, grade_tags  (comma-separated Text)
resolution, quality_preset, duration_seconds, fps, theme
json_path, output_dir, video_path, audio_path, thumbnail_path
youtube_url, youtube_video_id
youtube_status (not_uploaded | uploading | published | failed)
status (pending | processing | completed | failed)
error_message (Text), progress (0-100 Integer)
created_at, updated_at, completed_at
```

### JobQueue model fields
```
id, video_id (FK → videos.video_id)
priority (1=urgent, 2=high, 3=normal, 4=low)
status (queued | processing | completed | failed | cancelled)
stage (audio_gen | timestamp_map | rendering | encoding)
progress (0-100), error_message (Text)
retry_count, max_retries (default 1)
created_at, started_at, completed_at
```

### Setting model
- key/value store
- static `get(key, default="")` and `set(key, value)` class methods

---

## ═══════════════════════════════════════
## PART 6 — JSON DSL SCHEMA (COMPLETE)
## ═══════════════════════════════════════

### Root Structure
The root must be a JSON array. Objects with a `_DOC` key are silently skipped.

```json
[
  { "_DOC": "Documentation objects are silently skipped" },
  {
    "id":   "unique-slug",
    "mode": "mcq",
    "meta": {
      "subject":    "math",
      "chapter":    "Algebra",
      "topic":      "Quadratic Equations",
      "difficulty": "hard",
      "exam_tags":  ["JEE", "CBSE-12"],
      "grade_tags": ["11", "12"]
    },
    "question": { ... },
    "scenes":   [ ... ]
  }
]
```

### 8 Valid Modes
```
mcq          Multiple choice question (4 options a/b/c/d)
topic        Concept explanation (no question block)
true_false   True/False question
fill_blank   Fill in the blank
numerical    Numerical answer (e.g. "42.5")
match        Match the following (pairs)
assertion    Assertion-Reason type
sequence     Arrange items in correct order
```

### Scene Types
```
question       Introductory scene: renders question text
options        Shows MCQ options grid
concept        Step-by-step explanation (MUST have non-empty "steps" array)
visual_intro   Animated intro for the topic
answer         Reveals correct answer
```

### Render Object (per scene or step)
```json
{
  "action":   "show",
  "target":   "equation",
  "value":    "x^2 + 5x + 6 = 0",
  "position": "center",
  "size":     "large",
  "color":    "accent"
}
```

### Valid Actions (VALID_ACTIONS set — exactly 12)
```
show             Display element
hide             Remove element
highlight        Pulse-highlight an existing element
update           Replace value of existing element
animate          Trigger animation sequence
show_result      Show correct answer overlay
draw_arrow       Draw annotation arrow to element
zoom             Zoom into element
replace          Replace element with new one
sequence         Show steps as numbered sequence
clear            Remove all work elements
highlight_option Highlight an MCQ option (a/b/c/d)
```

### 65+ Valid Render Targets

#### Text & Equations
```
question_block       MCQ question text
options_grid         MCQ 4-option grid
concept_text         Heading + paragraph explanation
equation             Single math equation (LaTeX-rendered)
formula_block        Multi-line formula (LaTeX)
derivation_chain     Step-by-step equation derivation (steps array)
proof_block          QED-style mathematical proof
latex_equation       Raw LaTeX string rendered via mathtext
key_facts            Heading + key:value bullet list
process_steps        Numbered step list
two_col_text         Two-column comparison
result_box           Final answer box
final_answer         Answer reveal overlay
running_sum          Accumulating total display
highlight_box        Colored callout box
title_card           Large title + subtitle card
```

#### Math & Numbers
```
digit_boxes          Individual digit breakdown boxes
factor_tree          Prime factor tree diagram
venn_diagram         Two/three-circle Venn diagram
number_line          Number line with marked points
coordinate_axes      2D/3D coordinate system
bar_chart            Animated bar chart (matplotlib)
pie_chart            Animated pie chart (matplotlib)
balance_scale        Balance scale (equations)
```

#### Physics
```
circuit_diagram      Electric circuit (schemdraw: resistors, capacitors, etc.)
bohr_model           Bohr atomic model with electron shells
free_body_diagram    Arrow-based force diagram
wave_diagram         Sin/cos wave with labeled parts (crest, trough, λ, A)
ray_diagram          Optics ray diagram (mirrors/lenses with construction rays)
velocity_diagram     Velocity/acceleration vectors
energy_level         Quantum energy level diagram with transitions
```

#### Chemistry
```
molecule_2d          2D molecular structure (RDKit from SMILES)
periodic_element     Single element tile (symbol, atomic number, mass)
periodic_table       Full mini periodic table with highlighted groups
reaction_equation    Balanced chemical equation with state symbols
energy_diagram       Potential energy / reaction coordinate curve
orbital_diagram      Electron orbital filling (Aufbau, box notation)
acid_base_scale      pH scale with indicator bands
```

#### Biology
```
cell_diagram         Animal/plant/bacterial cell with labeled organelles
punnett_square       Genetics Punnett square (2×2 monohybrid or 4×4 dihybrid)
food_chain           Food chain / food web with directional arrows
dna_structure        DNA double helix with base pair labels (A-T, G-C)
phylogenetic_tree    Cladogram from newick format (biopython)
human_anatomy        Labeled human body part diagram
microscope_view      Simulated circular microscope viewport
```

#### Geography & History
```
india_map            India map with highlighted/choropleth states (geopandas)
world_map            World map with highlighted countries
climate_map          Köppen climate zone map
timeline_bar         Historical timeline with events (alternating above/below)
```

#### Reasoning & Logic
```
comparison_table     Multi-column tabular comparison
hierarchy_tree       Tree hierarchy diagram
process_cycle        Circular cycle diagram (carbon cycle, water cycle)
cause_effect         Cause → Effect arrows diagram
```

#### Spatial / Visual
```
direction_map        Compass-rose direction diagram
seating_layout       Circular/rectangular seating arrangement
clock_diagram        Clock face with hands
family_tree          Genealogy tree diagram
labeled_image        User-provided image with text overlays
zoom_box             Magnified sub-region box
overlay_formula      Formula overlaid on top of image
```

---

## ═══════════════════════════════════════
## PART 7 — engine/validator.py
## ═══════════════════════════════════════

```python
"""JSON DSL schema validator."""

VALID_MODES     = {"mcq","topic","true_false","fill_blank","numerical","match","assertion","sequence"}
VALID_SCENES    = {"question","options","concept","visual_intro","answer"}
VALID_ACTIONS   = {"show","hide","highlight","update","animate","show_result","draw_arrow",
                   "zoom","replace","sequence","clear","highlight_option"}
VALID_TARGETS   = { ... all 65+ targets ... }
VALID_POSITIONS = {"top","bottom","left","right","center","top_left","top_right",
                   "bottom_left","bottom_right","work_area","full_screen"}
VALID_SIZES     = {"small","medium","large","xl","full"}
VALID_DIFFICULTIES = {"easy","medium","hard","very_hard"}

class ValidationError:
    def __init__(self, path: str, message: str, severity: str = "error"): ...
    def __repr__(self) -> str: ...
    def to_dict(self) -> dict: ...

def validate_json(data) -> tuple[bool, list[ValidationError]]:
    """
    Validate a list of question dicts.
    Returns (is_valid, errors_list).

    Rules:
    - Root must be a list → fatal if not
    - Objects with "_DOC" key → silently skipped
    - Each item: id (str, unique), mode, meta.subject, meta.topic required
    - concept scenes must have non-empty "steps" list
    - Each render: action in VALID_ACTIONS, target in VALID_TARGETS
    - position/size/color invalid → warning (not fatal)
    - difficulty invalid → warning (not fatal)
    - topic_header missing in topic mode → warning
    - Duplicate IDs → error
    """
```

---

## ═══════════════════════════════════════
## PART 8 — engine/audio.py
## ═══════════════════════════════════════

### Word-Level TTS Pipeline
```python
async def _generate_edge_tts(text: str, voice: str, output_path: str) -> list[dict]:
    """
    Returns list of word timestamps:
    [{"word": "Hello", "start": 0.0, "end": 0.35}, ...]

    Uses edge_tts WordBoundary events for real timestamps.
    CRITICAL: In Python 3.12 threads use asyncio.run() NOT get_event_loop().
    Falls back to _generate_gtts() with proportional timestamps on failure.
    """

def _compute_word_timestamps(text: str, duration: float) -> list[dict]:
    """Proportional mapping — longer words get proportionally more time."""

def generate_audio_for_scene(scene_dict, scene_idx, step_idx, output_dir, voice) -> dict:
    """
    Returns audio segment dict:
    {
        "scene_index":     int,
        "step_index":      int | None,
        "start":           float,
        "end":             float,
        "word_timestamps": list[dict],
        "audio_path":      str,
    }
    """
```

### CRITICAL: asyncio in threads
```python
# CORRECT — works in Python 3.12 thread:
result = asyncio.run(coro)

# WRONG — raises RuntimeError in thread:
loop = asyncio.get_event_loop()
loop.run_until_complete(coro)
```

---

## ═══════════════════════════════════════
## PART 9 — engine/sync.py
## ═══════════════════════════════════════

```python
def build_timeline(question: dict, audio_segments: list[dict]) -> list[dict]:
    """
    Maps audio segments onto scenes/steps by (scene_index, step_index) DICT LOOKUP.
    NOT sequential order — segments may arrive out of order.

    Required keys in each timeline entry:
    start, end, scene_index, scene_type, step_index, render, text, audio_text, word_timestamps

    Scenes without audio (e.g. "options"):
        duration = min(len(options) * 0.6, 3.0)   # 0.5s minimum

    Steps without audio:
        duration = 1.5 seconds

    If no matching segment for an audio step → skip entry (don't crash).
    """

def get_active_state(timeline: list[dict], current_time: float, question: dict) -> dict:
    """
    Accumulation model: replay all events at t <= current_time.
    Returns full render state dict (see state schema below).

    work_elements accumulation:
    - "show"    → work_elements[target] = element
    - "hide"    → del work_elements[target]
    - "highlight" → work_elements[target]["highlighted"] = True
    - "update"  → work_elements[target]["value"] = new_value
    - "clear"   → work_elements.clear()
    - "show_result" → highlighted_option = correct_option, show_correct = True
    """
```

### State Dict Schema
```python
{
    "mode":               str,
    "question_text":      str,
    "options_data":       list[{"key": str, "value": str}],
    "correct_option":     str,
    "highlighted_option": str,
    "show_correct":       bool,
    "question_shown":     bool,
    "options_shown":      bool,
    "work_elements":      dict,   # target_name → element_dict
    "step_text":          str,
    "narration":          dict | None,
    "current_time":       float,
    "topic_header":       dict | None,
    "topic_shown":        bool,
    "subject":            str,    # from meta.subject, used to select theme
}
```

---

## ═══════════════════════════════════════
## PART 10 — engine/latex_renderer.py (NEW)
## ═══════════════════════════════════════

```python
"""
LaTeX equation → PIL Image renderer.
Uses matplotlib.mathtext — no TeX installation needed.
Supports sympy → LaTeX string conversion.
"""
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

def render_latex(latex_str: str, fontsize: int = 32, color: str = "#000000",
                 bg_color: str = None, dpi: int = 150) -> Image.Image:
    """
    Render LaTeX math string to RGBA PIL Image (transparent background).

    latex_str must be wrapped in $...$:
        "$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$"

    Scaling rule:
        Base fontsize for 1080p = 42pt
        For other resolutions: fontsize = round(42 * (frame_width / 1920))
        DPI stays constant at 150.

    Returns PIL Image (RGBA).
    Raises LatexRenderError on failure.
    """

def latex_from_sympy(expr) -> str:
    """Convert sympy expression to $...$ wrapped LaTeX string."""
    from sympy import latex
    return f"${latex(expr)}$"

class LatexRenderError(Exception):
    pass
```

---

## ═══════════════════════════════════════
## PART 11 — engine/compositor.py (NEW)
## ═══════════════════════════════════════

```python
"""
Multi-layer Pillow frame compositor.

Layer order (bottom to top):
  0. Background (solid color or gradient from subject theme)
  1. Header bar (subject-themed strip)
  2. Body panels (white/light card areas)
  3. Subject-specific rendered element (molecule, map, circuit, etc.)
  4. LaTeX equations (transparent PNG sprites)
  5. Annotation arrows (callouts pointing to elements)
  6. Text overlays (narration bar, step label)
  7. UI chrome (progress dot, watermark)
"""
from PIL import Image, ImageDraw
from dataclasses import dataclass
from typing import List

@dataclass
class Layer:
    image: Image.Image
    x: int = 0
    y: int = 0
    opacity: float = 1.0

class FrameCompositor:
    def __init__(self, width: int, height: int): ...

    def add_layer(self, img: Image.Image, x: int = 0, y: int = 0,
                  opacity: float = 1.0) -> None: ...

    def add_latex(self, latex_str: str, x: int, y: int,
                  fontsize: int, color: str = "#000000") -> None:
        """Render LaTeX via latex_renderer and composite at (x, y)."""

    def add_annotation_arrow(self, from_xy: tuple, to_xy: tuple,
                              label: str = "", color: str = "#FF0000") -> None:
        """Curved callout arrow with optional text label."""

    def flatten(self) -> Image.Image:
        """Alpha-composite all layers → final RGB Image."""
```

---

## ═══════════════════════════════════════
## PART 12 — engine/animator.py (NEW)
## ═══════════════════════════════════════

```python
"""
Animation engine — generates interpolated frame sequences.
Used by pipeline.py when render action is "animate".
"""
import math
from PIL import Image

# Easing functions (t: float 0→1, returns float 0→1)
def ease_in_out(t): return t * t * (3 - 2 * t)
def ease_out_elastic(t): ...
def ease_in_cubic(t): return t * t * t

class AnimationType:
    FADE_IN   = "fade_in"      # alpha blend from_frame → to_frame
    SLIDE_IN  = "slide_in"     # translate to_frame from direction (left/right/top/bottom)
    SCALE_IN  = "scale_in"     # zoom to_frame from center (0 → 1 scale)
    TYPEWRITER = "typewriter"  # reveal text character by character
    COUNT_UP  = "count_up"     # animate number from 0 → target
    DRAW_EQ   = "draw_equation" # progressive LaTeX equation reveal
    PULSE     = "highlight_pulse" # size/color pulse for highlight action
    WIPE      = "wipe"         # horizontal wipe reveal

class FrameAnimator:
    def __init__(self, renderer, fps: int = 30): ...

    def animate(self, from_frame: Image.Image, to_frame: Image.Image,
                duration: float, animation_type: str,
                direction: str = "left") -> list[Image.Image]:
        """
        Generate floor(duration * fps) transition frames.
        Returns list of PIL Images.
        """

    def typewriter_frames(self, renderer, state: dict,
                          element_key: str, duration: float) -> list[Image.Image]:
        """Reveal text one character at a time over duration seconds."""

    def count_up_frames(self, renderer, state: dict,
                        element_key: str, target: float,
                        duration: float) -> list[Image.Image]:
        """Animate number counting 0 → target with ease_in_out."""
```

---

## ═══════════════════════════════════════
## PART 13 — engine/renderer.py (REBUILT)
## ═══════════════════════════════════════

### FrameRenderer Contract
```python
class FrameRenderer:
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width  = width
        self.height = height
        self.scale  = width / 1920   # ALL measurements multiply by this

    def render_frame(self, state: dict) -> Image.Image:
        """
        Dispatch by state["mode"]. Returns complete RGB PIL Image.
        subject = state.get("subject", "default") → selects from SUBJECT_THEMES.
        """

    def _get_theme(self, subject: str) -> dict:
        """Return SUBJECT_THEMES.get(subject, SUBJECT_THEMES["default"])"""

    def _blank_frame(self) -> Image.Image: ...
    def _draw_header(self, draw, theme, title, subtitle="") -> int:
        """Draw subject header bar. Returns body_top y-coordinate."""
```

### Layout Zones (at 1920×1080, all values × scale for other resolutions)
```
Header bar:     y = 0   → 120px
Left panel:     x = 0   → 960px,  y = 120 → 980px  (question + options in MCQ)
Right panel:    x = 960 → 1920px, y = 120 → 980px  (work area / subject visual)
Narration bar:  y = 980 → 1080px (full width, word-highlighted audio text)

Topic mode:
  Header:   y = 0   → 120px
  Topic card: y = 120 → 320px (full width title/subtitle)
  Work area:  y = 320 → 980px (full width)
  Narration:  y = 980 → 1080px
```

### Element Renderer Dispatch (work_elements dict → method)
```python
_ELEMENT_RENDERERS = {
    "equation":          _draw_equation,
    "latex_equation":    _draw_latex_equation,      # uses latex_renderer module
    "derivation_chain":  _draw_derivation_chain,    # LaTeX step-by-step
    "key_facts":         _draw_key_facts,
    "concept_text":      _draw_concept_text,
    "process_steps":     _draw_process_steps,
    "two_col_text":      _draw_two_col_text,
    "digit_boxes":       _draw_digit_boxes,
    "highlight_box":     _draw_highlight_box,
    "formula_block":     _draw_formula_block,
    "final_answer":      _draw_final_answer,
    "running_sum":       _draw_running_sum,
    "result_box":        _draw_result_box,
    "title_card":        _draw_title_card,
    "comparison_table":  _draw_comparison_table,
    "bar_chart":         _draw_bar_chart,           # matplotlib → PIL
    "pie_chart":         _draw_pie_chart,
    "venn_diagram":      _draw_venn_diagram,
    "number_line":       _draw_number_line,
    "factor_tree":       _draw_factor_tree,
    "balance_scale":     _draw_balance_scale,
    # Physics
    "circuit_diagram":   _draw_circuit_diagram,     # schemdraw → PIL
    "bohr_model":        _draw_bohr_model,
    "free_body_diagram": _draw_free_body_diagram,
    "wave_diagram":      _draw_wave_diagram,
    "ray_diagram":       _draw_ray_diagram,
    "energy_level":      _draw_energy_level,
    # Chemistry
    "molecule_2d":       _draw_molecule_2d,         # RDKit → PIL
    "periodic_element":  _draw_periodic_element,
    "periodic_table":    _draw_periodic_table,
    "reaction_equation": _draw_reaction_equation,
    "energy_diagram":    _draw_energy_diagram,
    "orbital_diagram":   _draw_orbital_diagram,
    # Biology
    "cell_diagram":      _draw_cell_diagram,
    "punnett_square":    _draw_punnett_square,
    "food_chain":        _draw_food_chain,
    "dna_structure":     _draw_dna_structure,
    "phylogenetic_tree": _draw_phylogenetic_tree,
    # Geography
    "india_map":         _draw_india_map,           # geopandas → PIL
    "world_map":         _draw_world_map,
    "timeline_bar":      _draw_timeline_bar,
    # Logic / Misc
    "hierarchy_tree":    _draw_hierarchy_tree,
    "process_cycle":     _draw_process_cycle,
    "cause_effect":      _draw_cause_effect,
    "direction_map":     _draw_direction_map,
    "seating_layout":    _draw_seating_layout,
    "clock_diagram":     _draw_clock_diagram,
    "family_tree":       _draw_family_tree,
}
```

### Font Strategy
```python
FONT_PATHS = [
    "storage/assets/fonts/NotoSansMath-Regular.ttf",
    "storage/assets/fonts/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
# Try each in order; fall back to ImageFont.load_default()
# All font sizes = round(base_size * self.scale)
```

---

## ═══════════════════════════════════════
## PART 14 — engine/pipeline.py (REBUILT)
## ═══════════════════════════════════════

### 7-Stage Pipeline
```python
class VideoPipeline:
    """
    Stage 1: audio_gen      — TTS for each scene/step, collect segments
    Stage 2: timestamp_map  — build_timeline() from segments
    Stage 3: thumbnail      — render single frame at t=2.0s → JPEG
    Stage 4: rendering      — parallel frame render (ProcessPoolExecutor)
    Stage 5: encoding       — FFmpeg concat + audio mix + BGM
    Stage 6: cleanup        — delete temp frame PNGs
    Stage 7: complete       — update DB status, return output path
    """

    def run(self, video_id: str, json_path: str, question_dict: dict,
            settings: dict, progress_cb) -> str:
        """Returns final MP4 path."""
```

### CRITICAL: SQLAlchemy Object Safety (routes/upload.py)
```python
# Extract plain strings BEFORE any try block:
video_id  = job.video_id     # plain str
json_path = video.json_path  # plain str
output_dir = video.output_dir

def progress_cb(stage, percent):
    try:
        j = db.session.get(JobQueue, job_id)
        v = Video.query.filter_by(video_id=video_id).first()  # use str not ORM obj
        if j: j.stage = stage; j.progress = percent
        if v: v.progress = percent
        db.session.commit()
    except Exception:
        try: db.session.rollback()
        except Exception: pass

# In ALL except blocks use video_id (str), never video.video_id
```

### Parallel Rendering
```python
def _render_parallel(self, timeline, question, settings, frames_dir, progress_cb):
    """
    ProcessPoolExecutor (true multi-core, bypasses GIL).
    Worker count = min(cpu_count * 0.7, MAX_WORKERS).
    Batch size 500 frames to avoid OOM.
    """

def render_frame_worker(args: tuple) -> str:
    """
    TOP-LEVEL function (not method) — required for ProcessPoolExecutor pickling.
    Calls apply_worker_throttle() at start (nice +10, 70% core affinity).
    args = (frame_idx, time_t, question_dict, settings_dict, frames_dir)
    Returns PNG file path.
    """
```

### FFmpeg Encoding
```python
_GPU_LOCK = threading.Lock()  # module-level, serialize GPU encodes

def _encode_video(self, frames_dir, audio_path, bgm_path, output_path, settings):
    """
    1. Try GPU: h264_nvenc (acquire _GPU_LOCK)
    2. On CalledProcessError fallback: libx264 -crf 18
    3. Audio mix: TTS at vol=1.0, BGM at vol=BGM_VOLUME (0.3 default)
    4. Concat method: concat demuxer (file list), NOT complex filtergraph
    """
```

---

## ═══════════════════════════════════════
## PART 15 — engine/subjects/physics_renderer.py
## ═══════════════════════════════════════

```python
class PhysicsRenderer:

    def render_circuit(self, components: list[dict],
                       topology: str, width: int, height: int, theme: dict) -> Image.Image:
        """
        schemdraw circuit diagram.
        topology: "series" | "parallel"
        components: [{"type": "resistor", "label": "R₁=10Ω"}, {"type": "battery"}, ...]
        Supported types: resistor, capacitor, inductor, battery, bulb, switch, ground, wire
        schemdraw → matplotlib figure → PIL Image
        """

    def render_bohr_model(self, symbol: str, atomic_number: int,
                          electrons_per_shell: list[int],
                          width: int, height: int, theme: dict) -> Image.Image:
        """
        Concentric circles = electron shells.
        Electrons = filled dots on circles.
        Nucleus labeled with symbol + atomic number.
        Example: Na (11): electrons_per_shell = [2, 8, 1]
        """

    def render_free_body_diagram(self, forces: list[dict],
                                  width: int, height: int, theme: dict) -> Image.Image:
        """
        forces: [{"direction": "up", "label": "N = 50N"}, {"direction": "down", "label": "mg"}]
        Object box at center; arrows radiating out.
        Directions: "up","down","left","right","diagonal_ur","diagonal_ul","diagonal_dr","diagonal_dl"
        """

    def render_wave(self, wave_type: str, params: dict,
                    width: int, height: int, theme: dict) -> Image.Image:
        """
        wave_type: "transverse" | "longitudinal" | "standing"
        params: {"wavelength": 2, "amplitude": 1, "label_parts": True}
        Labels: crest, trough, λ (wavelength), A (amplitude), node, antinode
        """

    def render_ray_diagram(self, optic_type: str, params: dict,
                            width: int, height: int, theme: dict) -> Image.Image:
        """
        optic_type: "convex_lens" | "concave_lens" | "concave_mirror" | "convex_mirror"
        params: {"object_distance": 30, "focal_length": 20, "show_image": True}
        Draws: principal axis, lens/mirror, object arrow, image arrow, 3 construction rays.
        """

    def render_energy_level(self, transitions: list[dict], atom: str,
                             width: int, height: int) -> Image.Image:
        """
        Horizontal energy levels (n=1,2,3,4...)
        Vertical arrows for transitions (emission=downward, absorption=upward)
        Label each transition energy: ΔE = hf
        """
```

---

## ═══════════════════════════════════════
## PART 16 — engine/subjects/chemistry_renderer.py
## ═══════════════════════════════════════

```python
class ChemistryRenderer:

    def render_molecule_2d(self, smiles: str, name: str,
                            width: int, height: int, theme: dict) -> Image.Image:
        """
        RDKit: Chem.MolFromSmiles(smiles) → Draw.MolToImage()
        Falls back to text label if RDKit unavailable.

        SMILES examples:
          Water:     "O"
          Ethanol:   "CCO"
          Aspirin:   "CC(=O)Oc1ccccc1C(=O)O"
          Glucose:   "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O"
          Benzene:   "c1ccccc1"
          NaCl:      "[Na+].[Cl-]"
        """

    def render_periodic_element(self, symbol: str, atomic_number: int,
                                  atomic_mass: float, name: str,
                                  width: int, height: int, theme: dict) -> Image.Image:
        """Single tile: large symbol, atomic number top-left, mass bottom, name bottom-right."""

    def render_periodic_table(self, highlight_elements: list[str],
                               highlight_group: str | None,
                               width: int, height: int, theme: dict) -> Image.Image:
        """
        All 118 elements in standard layout.
        Group highlighting: "alkali_metals","alkaline_earth","transition","halogens","noble_gases"
        highlight_elements: list of symbols → accent color fill
        """

    def render_energy_diagram(self, reaction_type: str,
                               activation_energy: float, delta_h: float,
                               width: int, height: int, theme: dict) -> Image.Image:
        """
        reaction_type: "exothermic" | "endothermic"
        Plots potential energy curve with:
          - Reactants level (horizontal line)
          - Activation energy peak
          - Products level
          - ΔH arrow and Ea arrow labeled
        """

    def render_orbital_filling(self, element: str, configuration: str,
                                width: int, height: int) -> Image.Image:
        """
        Box notation orbital diagram.
        configuration: "1s² 2s² 2p⁶ 3s² 3p⁴" (Sulfur)
        Boxes for each orbital; up/down arrows for electrons.
        """
```

---

## ═══════════════════════════════════════
## PART 17 — engine/subjects/biology_renderer.py
## ═══════════════════════════════════════

```python
class BiologyRenderer:

    def render_cell(self, cell_type: str, label_parts: list[str],
                     width: int, height: int, theme: dict) -> Image.Image:
        """
        cell_type: "animal" | "plant" | "bacteria" | "neuron"
        All drawn with Pillow (ellipses, bezier curves, text callouts).
        Animal organelles: nucleus, mitochondria, ribosome, ER, Golgi, lysosomes, cell membrane
        Plant adds: cell wall, chloroplast, large vacuole
        label_parts: subset of organelles to annotate with callout arrows
        """

    def render_punnett_square(self, parent1: str, parent2: str,
                               trait_name: str, width: int, height: int,
                               theme: dict) -> Image.Image:
        """
        2×2 for monohybrid (e.g. Aa × Aa)
        4×4 for dihybrid (e.g. AaBb × AaBb)
        Color coding: homozygous dominant = green, heterozygous = yellow, homozygous recessive = red
        Show phenotype ratio below grid.
        """

    def render_food_chain(self, organisms: list[str],
                           width: int, height: int, theme: dict) -> Image.Image:
        """
        Linear chain: box per organism, arrows showing energy flow.
        organisms: ["Producer","Primary Consumer","Secondary Consumer","Tertiary Consumer","Decomposer"]
        Label trophic level below each box.
        """

    def render_dna_structure(self, sequence: str,
                              width: int, height: int, theme: dict) -> Image.Image:
        """
        sequence: "ATGC" → shows 4 base-pair rungs of double helix
        A-T bonds in blue, G-C bonds in green
        Sugar-phosphate backbone as curved parallel lines
        Base labels on each rung
        """

    def render_phylogenetic_tree(self, taxa: list[str], newick: str,
                                  width: int, height: int) -> Image.Image:
        """
        Use biopython Phylo.read() → draw rectangular cladogram.
        Falls back to simple branching Pillow diagram if biopython unavailable.
        """
```

---

## ═══════════════════════════════════════
## PART 18 — engine/subjects/geography_renderer.py
## ═══════════════════════════════════════

```python
class GeographyRenderer:

    def render_india_map(self, highlight_states: list[str],
                          choropleth_data: dict | None,
                          width: int, height: int, theme: dict) -> Image.Image:
        """
        Uses geopandas with India shapefile (auto-downloaded from Natural Earth).
        highlight_states: solid accent color fill.
        choropleth_data: {"Maharashtra": 95.5} → gradient fill by value.
        Falls back to blank labeled rectangle if shapefile unavailable.
        """

    def render_world_map(self, highlight_countries: list[str],
                          width: int, height: int, theme: dict) -> Image.Image:
        """Natural Earth 110m dataset. Highlighted countries in accent color."""

    def render_climate_zones(self, width: int, height: int) -> Image.Image:
        """Köppen climate classification world map, color coded."""

    def render_timeline(self, events: list[dict],
                         width: int, height: int, theme: dict) -> Image.Image:
        """
        events: [{"year": 1947, "event": "Independence"}, ...]
        Horizontal axis = time; events alternating above/below the line.
        Dots at event years; vertical stems; text labels.
        """
```

---

## ═══════════════════════════════════════
## PART 19 — engine/subjects/math_renderer.py
## ═══════════════════════════════════════

```python
class MathRenderer:

    def render_function_plot(self, expr_str: str, x_range: tuple,
                              width: int, height: int, theme: dict) -> Image.Image:
        """
        matplotlib plot of y=f(x).
        expr_str: Python-syntax string e.g. "x**2 - 3*x + 2"
        Theme colors: body_bg for background, accent for curve, border for axes.
        Shows x-intercepts, vertex, axis labels.
        """

    def render_3d_surface(self, expr_str: str, x_range: tuple, y_range: tuple,
                           width: int, height: int) -> Image.Image:
        """matplotlib Axes3D surface plot."""

    def render_geometry(self, shape: str, params: dict,
                         width: int, height: int, theme: dict) -> Image.Image:
        """
        shape: "triangle" | "circle" | "polygon" | "angle_arc"
        Pillow draw with labeled dimensions, angle marks, tick marks for equal sides.
        """

    def render_venn_diagram(self, sets: list[dict],
                             width: int, height: int, theme: dict) -> Image.Image:
        """
        sets: [{"label": "A", "items": [1,2,3]}, {"label": "B", "items": [2,3,4]}]
        Show intersection, union regions labeled.
        """

    def render_number_theory(self, element_type: str, data: dict,
                               width: int, height: int, theme: dict) -> Image.Image:
        """
        element_type: "factor_tree" | "prime_sieve" | "modular_clock"
        """
```

---

## ═══════════════════════════════════════
## PART 20 — engine/manim_renderer.py (EXPANDED)
## ═══════════════════════════════════════

```python
"""
Manim Community animation templates.
Each template renders a short MP4 clip (2–8 seconds).
Used for special "manim_scene" render target.
All scenes receive params dict from JSON DSL.
"""
from manim import *

# Math scenes:
class QuadraticRootsScene(Scene): ...        # completing-the-square derivation
class FunctionGraphScene(Scene): ...          # y=f(x) with animated tracing point
class MatrixMultiplyScene(Scene): ...         # animated matrix multiply
class LimitVisualizationScene(Scene): ...     # epsilon-delta definition
class IntegrationScene(Scene): ...            # area under curve
class VectorScene(Scene): ...                 # vector addition, dot product
class SetTheoryScene(Scene): ...              # Venn diagrams animated
class ProbabilityTreeScene(Scene): ...        # branching probability tree

# 3D Physics scenes:
class VectorFieldScene(ThreeDScene): ...      # 3D electric/magnetic field
class WaveInterferenceScene(Scene): ...       # constructive/destructive interference
class ProjectileMotionScene(Scene): ...       # parabolic trajectory

# Chemistry / Biology:
class MolecularBondingScene(ThreeDScene): ... # 3D molecular orbitals
class DNAReplicationScene(Scene): ...         # animated DNA unzipping

# Data / ML:
class NeuralNetworkScene(Scene): ...          # animated forward pass
class FourierTransformScene(Scene): ...       # sine wave decomposition + epicycles

def render_manim_scene(scene_class_name: str, params: dict,
                        output_path: str, width: int = 1920,
                        height: int = 1080, fps: int = 30) -> str:
    """
    Render Manim scene to MP4 via subprocess (avoids global state pollution).
    Returns output_path on success. Raises ManimRenderError on failure.
    """
```

---

## ═══════════════════════════════════════
## PART 21 — engine/data_fetcher.py (NEW)
## ═══════════════════════════════════════

```python
"""
Free scientific data APIs — no API keys required (DEMO_KEY for NASA).
All results cached in storage/assets/cache/ with 24h TTL.
"""
import requests, json, os, hashlib, time

CACHE_DIR = "storage/assets/cache"

class DataFetcher:

    def get_compound(self, name: str) -> dict:
        """
        PubChem REST: https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON
        Returns: {molecular_formula, molecular_weight, iupac_name, smiles, inchi, cid}
        """

    def get_molecule_image(self, cid: int, width: int = 300) -> bytes:
        """PubChem PNG: /compound/cid/{cid}/PNG — returns PNG bytes."""

    def get_protein_info(self, pdb_id: str) -> dict:
        """RCSB PDB: https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"""

    def get_gene_info(self, gene_symbol: str, organism: str = "human") -> dict:
        """NCBI Entrez eutils (no key, max 3 req/s)."""

    def get_country_stat(self, country_code: str, indicator: str) -> list[dict]:
        """
        World Bank API: https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json
        indicator: "SP.POP.TOTL" | "NY.GDP.MKTP.CD" | "SE.ADT.LITR.ZS"
        Returns: [{"year": int, "value": float}, ...]
        """

    def get_nasa_apod(self) -> dict:
        """NASA APOD: https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY"""

    def _cache_key(self, *args) -> str:
        return hashlib.md5(str(args).encode()).hexdigest()

    def _cache_get(self, key: str) -> dict | None: ...
    def _cache_set(self, key: str, data, ttl_hours: int = 24): ...
```

---

## ═══════════════════════════════════════
## PART 22 — SAMPLE JSON DSL EXAMPLES
## ═══════════════════════════════════════

### Example 1: Math — Quadratic Equation with LaTeX Derivation
```json
[{
  "id": "math-quadratic-001",
  "mode": "mcq",
  "meta": {
    "subject": "math", "chapter": "Algebra",
    "topic": "Quadratic Equations", "difficulty": "hard",
    "exam_tags": ["JEE", "CBSE-12"]
  },
  "question": {
    "text": "If x² - 5x + 6 = 0, which of the following is a root?",
    "options": [
      {"key": "a", "value": "1"}, {"key": "b", "value": "2"},
      {"key": "c", "value": "4"}, {"key": "d", "value": "5"}
    ],
    "correct": "b"
  },
  "scenes": [
    {
      "type": "question",
      "audio": "If x squared minus 5x plus 6 equals zero, which is a root?",
      "render": {"action": "show", "target": "question_block"}
    },
    {"type": "options", "render": {"action": "show", "target": "options_grid"}},
    {
      "type": "concept",
      "steps": [
        {
          "text": "Write the equation",
          "audio": "We have x squared minus 5x plus 6 equals zero.",
          "render": {"action": "show", "target": "latex_equation", "value": "$x^2 - 5x + 6 = 0$"}
        },
        {
          "text": "Factor",
          "audio": "Factoring: x minus 2 times x minus 3.",
          "render": {
            "action": "show", "target": "derivation_chain",
            "steps": ["$x^2 - 5x + 6 = 0$", "$(x-2)(x-3) = 0$", "$x = 2 \\quad\\text{or}\\quad x = 3$"]
          }
        },
        {
          "text": "Answer",
          "audio": "Therefore x equals 2. Option B is correct.",
          "render": {"action": "highlight_option", "target": "b"}
        }
      ]
    }
  ]
}]
```

### Example 2: Biology — Cell Structure
```json
[{
  "id": "bio-cell-001",
  "mode": "topic",
  "meta": {"subject": "biology", "topic": "Animal Cell Structure", "difficulty": "medium"},
  "topic_header": {"title": "Animal Cell", "subtitle": "Structure and Organelles"},
  "scenes": [
    {
      "type": "visual_intro",
      "audio": "Let us explore the animal cell structure.",
      "render": {"action": "show", "target": "title_card",
                 "title": "Animal Cell", "subtitle": "The Basic Unit of Life"}
    },
    {
      "type": "concept",
      "steps": [
        {
          "text": "Cell diagram",
          "audio": "Here is an animal cell with labeled organelles.",
          "render": {
            "action": "show", "target": "cell_diagram",
            "cell_type": "animal",
            "label_parts": ["nucleus", "mitochondria", "golgi_body", "endoplasmic_reticulum"]
          }
        },
        {
          "text": "Nucleus",
          "audio": "The nucleus controls all cellular activities and stores DNA.",
          "render": {
            "action": "show", "target": "key_facts", "heading": "Nucleus",
            "facts": [
              {"key": "Function", "value": "Controls cell activities"},
              {"key": "Contains", "value": "DNA (genetic material)"},
              {"key": "Bounded by", "value": "Double nuclear membrane"}
            ]
          }
        }
      ]
    }
  ]
}]
```

### Example 3: Physics — Circuit + Bohr Model
```json
[{
  "id": "phy-circuit-001",
  "mode": "mcq",
  "meta": {"subject": "physics", "topic": "Electric Circuits", "difficulty": "medium"},
  "question": {
    "text": "In a series circuit with R₁=10Ω and R₂=20Ω, what is total resistance?",
    "options": [
      {"key": "a", "value": "10 Ω"}, {"key": "b", "value": "30 Ω"},
      {"key": "c", "value": "6.67 Ω"}, {"key": "d", "value": "200 Ω"}
    ],
    "correct": "b"
  },
  "scenes": [
    {
      "type": "question",
      "audio": "In a series circuit with R1 equals 10 ohms and R2 equals 20 ohms, find total resistance.",
      "render": {"action": "show", "target": "question_block"}
    },
    {"type": "options", "render": {"action": "show", "target": "options_grid"}},
    {
      "type": "concept",
      "steps": [
        {
          "text": "Circuit diagram",
          "audio": "Here is the series circuit.",
          "render": {
            "action": "show", "target": "circuit_diagram",
            "components": [
              {"type": "battery", "label": "V"},
              {"type": "resistor", "label": "R₁=10Ω"},
              {"type": "resistor", "label": "R₂=20Ω"}
            ],
            "topology": "series"
          }
        },
        {
          "text": "Formula",
          "audio": "For series: R total equals R1 plus R2 equals 30 ohms.",
          "render": {
            "action": "show", "target": "latex_equation",
            "value": "$R_{total} = R_1 + R_2 = 10 + 20 = 30\\ \\Omega$"
          }
        }
      ]
    }
  ]
}]
```

### Example 4: Chemistry — Molecule + Energy Diagram
```json
[{
  "id": "chem-aspirin-001",
  "mode": "topic",
  "meta": {"subject": "chemistry", "topic": "Organic Chemistry", "difficulty": "hard",
           "exam_tags": ["NEET", "JEE"]},
  "topic_header": {"title": "Aspirin", "subtitle": "Structure and Synthesis"},
  "scenes": [
    {
      "type": "concept",
      "steps": [
        {
          "text": "Molecule",
          "audio": "Aspirin, or acetylsalicylic acid, has this 2D structure.",
          "render": {
            "action": "show", "target": "molecule_2d",
            "smiles": "CC(=O)Oc1ccccc1C(=O)O",
            "name": "Aspirin (Acetylsalicylic Acid)"
          }
        },
        {
          "text": "Reaction energy",
          "audio": "Synthesis is exothermic with moderate activation energy.",
          "render": {
            "action": "show", "target": "energy_diagram",
            "reaction_type": "exothermic",
            "activation_energy": 80,
            "delta_h": -120
          }
        }
      ]
    }
  ]
}]
```

---

## ═══════════════════════════════════════
## PART 23 — routes/upload.py CRITICAL FIXES
## ═══════════════════════════════════════

### Why This Matters
When user deletes a Video row from the UI while the pipeline thread is running,
the ORM `video` object in the `progress_cb` closure becomes stale.
Any attribute access raises `ObjectDeletedError`.
This corrupts the SQLAlchemy session → `PendingRollbackError` on all subsequent commits.
The thread dies without marking the job failed → blank/missing output files.

### The Fix
```python
def run_pipeline_job(job_id: int):
    with app.app_context():
        job = db.session.get(JobQueue, job_id)
        if not job: return

        # ── Extract PLAIN STRINGS before ANY try block ─────────────────────
        video_id   = job.video_id        # str, safe in all exception paths
        video      = Video.query.filter_by(video_id=video_id).first()
        if not video:
            job.status = "failed"; db.session.commit(); return

        json_path  = video.json_path     # str copy
        output_dir = video.output_dir    # str copy
        # ───────────────────────────────────────────────────────────────────

        def _is_cancelled(jid):
            try:
                j = db.session.get(JobQueue, jid)
                db.session.expire(j)
                return j and j.status == "cancelled"
            except Exception:
                try: db.session.rollback()
                except Exception: pass
                return False

        def progress_cb(stage, percent):
            if _is_cancelled(job_id):
                raise InterruptedError("Cancelled")
            try:
                j = db.session.get(JobQueue, job_id)
                v = Video.query.filter_by(video_id=video_id).first()  # str lookup
                if j: j.stage = stage; j.progress = percent
                if v: v.progress = percent
                db.session.commit()
            except Exception:
                try: db.session.rollback()
                except Exception: pass

        try:
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            db.session.commit()

            pipeline = VideoPipeline()
            output_path = pipeline.run(video_id, json_path, question, settings, progress_cb)

            j = db.session.get(JobQueue, job_id)
            v = Video.query.filter_by(video_id=video_id).first()
            if j: j.status = "completed"; j.progress = 100
            if v: v.status = "completed"; v.video_path = output_path; v.progress = 100
            db.session.commit()

        except InterruptedError:
            j = db.session.get(JobQueue, job_id)
            v = Video.query.filter_by(video_id=video_id).first()
            if j: j.status = "cancelled"
            if v: v.status = "cancelled"
            try: db.session.commit()
            except Exception: db.session.rollback()

        except Exception as e:
            print(f"[Pipeline] FAIL {video_id}: {e}")  # str not ORM
            j = db.session.get(JobQueue, job_id)
            v = Video.query.filter_by(video_id=video_id).first()
            if j: j.status = "failed"; j.error_message = str(e)
            if v: v.status = "failed"; v.error_message = str(e)
            try: db.session.commit()
            except Exception: db.session.rollback()
```

### WAL Mode (app.py)
```python
from sqlalchemy import event

@event.listens_for(db.engine, "connect")
def set_wal_mode(dbapi_conn, conn_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=10000")
    cursor.close()
```

---

## ═══════════════════════════════════════
## PART 24 — GENERATION ORDER (for AI)
## ═══════════════════════════════════════

Generate files in this exact order (each depends on prior):

```
01  requirements.txt
02  config.py                      ← SUBJECT_THEMES, RESOLUTIONS, QUALITY_PRESETS, TTS voices
03  models.py                      ← Video, JobQueue, Setting
04  engine/__init__.py
05  engine/validator.py            ← VALID_MODES, VALID_ACTIONS, VALID_TARGETS (65+), ValidationError
06  engine/latex_renderer.py       ← NEW: matplotlib.mathtext LaTeX → PIL Image
07  engine/compositor.py           ← NEW: multi-layer compositor, annotation arrows
08  engine/animator.py             ← NEW: FadeIn/SlideIn/TypeWriter/CountUp/Wipe with easing
09  engine/audio.py                ← edge_tts + proportional timestamps + asyncio.run() fix
10  engine/sync.py                 ← build_timeline (index-based lookup) + get_active_state
11  engine/subjects/__init__.py
12  engine/subjects/math_renderer.py        ← function plots, geometry, 3D surfaces
13  engine/subjects/physics_renderer.py     ← schemdraw circuits, Bohr, ray diagram, waves
14  engine/subjects/chemistry_renderer.py   ← RDKit molecules, periodic table, energy diagram
15  engine/subjects/biology_renderer.py     ← cell diagrams, Punnett, food chain, DNA
16  engine/subjects/geography_renderer.py   ← geopandas India/world maps, timeline
17  engine/renderer.py             ← REBUILT: compositor + latex + subjects dispatch (65+ targets)
18  engine/manim_renderer.py       ← 30+ Manim templates including 3D scenes
19  engine/data_fetcher.py         ← NEW: PubChem, RCSB PDB, World Bank, NCBI, NASA
20  engine/hardware.py             ← CPU/GPU detection, worker count, cpu_affinity throttle
21  engine/bgmusic.py              ← procedural WAV BGM synthesis
22  engine/free_media.py           ← Unsplash/Pexels free stock fetch
23  engine/pipeline.py             ← REBUILT: animation-aware, 7-stage, ProcessPoolExecutor
24  routes/__init__.py
25  routes/upload.py               ← CRITICAL SQLAlchemy plain-string pattern (Part 23)
26  routes/videos.py
27  routes/queue_routes.py
28  routes/settings.py
29  routes/youtube.py
30  routes/export.py
31  routes/assets.py
32  app.py                         ← factory + WAL mode + directory bootstrap + startup resume
33  templates/base.html
34  templates/dashboard.html
35  templates/upload.html
36  templates/library.html
37  templates/queue.html
38  templates/settings.html
39  templates/video_detail.html
40  templates/youtube.html
41  templates/assets.html
42  templates/components/stats_cards.html
43  templates/components/job_row.html
44  templates/components/video_card.html
45  static/css/main.css
46  static/js/upload.js
47  static/js/queue.js
48  tests/conftest.py
49  tests/unit/test_validator.py
50  tests/unit/test_sync.py
51  tests/unit/test_renderer.py
52  tests/integration/test_pipeline.py
```

---

## ═══════════════════════════════════════
## PART 25 — DEGREE-LEVEL VISUAL CONCEPTS
## ═══════════════════════════════════════

### Mathematics (JEE / University Level)
- LaTeX-rendered equations (matplotlib.mathtext — no TeX installation)
- Progressive derivation: each step appears one at a time with typewriter effect
- Geometric proofs: labeled diagrams (angle marks, tick marks for equal sides)
- 3D surface plots (matplotlib Axes3D)
- Animated function graphs, area under curve (Manim)
- Number theory: factor trees, modular arithmetic clock diagrams
- Vectors: magnitude+direction arrows, dot/cross product visualization
- Matrices: animated multiplication with colored element highlighting
- Integration: shaded area with Riemann sum animation

### Physics (NEET / JEE / B.Sc Level)
- Circuit diagrams (schemdraw): actual component symbols (not text descriptions)
- Bohr atomic model: concentric electron shells with electron count
- Free body diagrams: labeled force vectors from center object
- Wave diagrams: crest/trough/wavelength/amplitude labels
- Ray diagrams: optics construction rays for mirrors/lenses
- Energy level diagrams: quantum transitions, spectral line colors
- 3D electric/magnetic field lines (Manim ThreeDScene)

### Chemistry (NEET / B.Sc Level)
- 2D molecular structure images from SMILES (RDKit)
- Periodic table element tiles (symbol, atomic number, mass, config)
- Potential energy diagrams: exothermic/endothermic curves with Ea and ΔH
- Orbital filling box notation (Aufbau, Hund's rule)
- Balanced equations with physical state symbols: (s), (l), (g), (aq)
- pH scale with indicator color bands
- Lewis dot structures

### Biology (NEET / B.Sc Level)
- Labeled cell diagrams (Pillow-drawn, callout arrows, organelle shapes)
- Punnett squares (2×2 and 4×4) with phenotype ratios
- DNA double helix with A-T/G-C base pair labels
- Food chains with directional energy-flow arrows
- Phylogenetic trees (biopython + Pillow cladogram)
- Microscopy viewport (circular mask, specimen detail)

### Geography (UPSC / B.A. Level)
- India state map with choropleth shading (geopandas)
- World map with highlighted countries
- Historical timelines (horizontal axis, alternating labels)
- Climate/river/mountain labeled overlays on maps

### Economics (UPSC / B.A. Level)
- Supply-demand curve intersections (matplotlib)
- GDP/population time series (animated plotly → kaleido PNG)
- Production possibility curve (PPF)
- IS-LM model diagram

### History / Polity (UPSC Level)
- Constitutional hierarchy trees (Parliament → Ministries → Departments)
- Timeline: chronological events with year markers
- Comparison tables (multi-column tabular)
- Map overlays showing empire extents

---

## ═══════════════════════════════════════
## PART 26 — ANIMATION SYSTEM
## ═══════════════════════════════════════

### Frame Generation Strategy
```
For each timeline entry (duration D seconds at fps F):
  total_frames = int(D * F)
  render single frame → duplicate total_frames times (static)

Transition between entries (default 0.3s):
  transition_frames = int(0.3 * fps)
  FrameAnimator.animate(from_frame, to_frame, 0.3, FADE_IN)

For "animate" action elements:
  Use FrameAnimator with specified animation_type
```

### TypeWriter Effect
```python
# For concept_text, equation:
# At frame i of N total: show first floor(i/N * len(text)) characters
# Rest replaced with spaces or empty string
```

### CountUp Effect
```python
# For result_box, running_sum:
# At frame i: display round(ease_in_out(i/N) * target, 2)
```

### Derivation Chain (sequential reveal)
```
Phase 1 (0 → 1/n): TypeWriter reveal of step 1
Phase 2 (1/n → 2/n): FadeIn step 2 below step 1, all steps visible
...
Phase n (n-1)/n → 1): FadeIn final step, highlight with pulse
```

---

## ═══════════════════════════════════════
## PART 27 — HARDWARE & PERFORMANCE
## ═══════════════════════════════════════

### Worker Throttling (engine/hardware.py)
```python
import psutil, os

def get_worker_count(target_utilization: float = 0.70) -> int:
    total = psutil.cpu_count(logical=False) or 4
    return max(1, int(total * target_utilization))

def apply_worker_throttle():
    """Call at start of each ProcessPoolExecutor worker process."""
    os.nice(10)   # BELOW_NORMAL priority on Unix
    n = get_worker_count(0.70)
    all_cores = list(range(psutil.cpu_count()))
    try:
        psutil.Process().cpu_affinity(all_cores[:n])
    except (AttributeError, NotImplementedError):
        pass   # not supported on all platforms
```

### GPU Encode Lock (engine/pipeline.py)
```python
_GPU_LOCK = threading.Lock()   # module-level singleton

def _encode_with_gpu(self, cmd):
    with _GPU_LOCK:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return result.returncode == 0
```

### Memory-Safe Batch Rendering
```python
BATCH_SIZE = 500
for batch_start in range(0, total_frames, BATCH_SIZE):
    batch = range(batch_start, min(batch_start + BATCH_SIZE, total_frames))
    futures = [executor.submit(render_frame_worker, (i, ...)) for i in batch]
    for f in as_completed(futures):
        f.result()   # raises on error
```

---

## ═══════════════════════════════════════
## PART 28 — TEST SUITE SPECIFICATION
## ═══════════════════════════════════════

### tests/conftest.py
```python
MINIMAL_MCQ_JSON = {
    "id": "test-mcq-001",
    "mode": "mcq",
    "meta": {"subject": "math", "topic": "Arithmetic", "difficulty": "easy"},
    "question": {
        "text": "What is 2 + 2?",
        "options": [
            {"key": "a", "value": "3"}, {"key": "b", "value": "4"},
            {"key": "c", "value": "5"}, {"key": "d", "value": "6"}
        ],
        "correct": "b"
    },
    "scenes": [
        {"type": "question", "audio": "What is two plus two?",
         "render": {"action": "show", "target": "question_block"}},
        {"type": "options", "render": {"action": "show", "target": "options_grid"}},
        {"type": "concept", "steps": [
            {"text": "Answer", "audio": "The answer is four.",
             "render": {"action": "show", "target": "result_box", "value": "4"}}
        ]}
    ]
}

# Fixtures: app (temp SQLite), client, db_session (rollback teardown),
#           sample_mcq (deepcopy), sample_topic (deepcopy),
#           mock_tts (patches engine.audio._generate_edge_tts → no network),
#           renderer (FrameRenderer(640, 360))
```

### Key Test Invariants
```
validator:
  - VALID_ACTIONS has exactly 12 entries
  - duplicate IDs → error
  - invalid difficulty → warning (not fatal)
  - missing topic_header in topic mode → warning (not fatal)

sync:
  - build_timeline uses dict lookup by (scene_idx, step_idx), NOT sequential
  - options scene gets auto-duration 0.5–3.0s
  - step without audio → 1.5s duration
  - work_elements accumulate (different targets coexist)
  - second "show" on same target replaces first

renderer:
  - all 65+ targets render without exception at 640×360
  - MCQ frame: >= 10% non-white pixels
  - topic frame: >= 10% non-white pixels
  - frame.size == (renderer.width, renderer.height) always
```

---

## ═══════════════════════════════════════
## PART 29 — DEPLOYMENT & ENVIRONMENT
## ═══════════════════════════════════════

### .env Variables
```
SECRET_KEY=change-me-in-production
DEFAULT_RESOLUTION=1080p
DEFAULT_QUALITY_PRESET=P7
DEFAULT_THEME=dark
DEFAULT_FPS=30
TTS_ENGINE=edge_tts
TTS_VOICE=en-IN-PrabhatNeural
BGM_ENABLED=true
BGM_STYLE=lotus
BGM_VOLUME=0.30
MAX_WORKERS=4
JOB_TIMEOUT=600
WATERMARK_ENABLED=false
```

### Directory Bootstrap (app.py create_app)
```python
DIRS = [
    Config.STORAGE_DIR, Config.VIDEOS_DIR, Config.JSON_DIR,
    Config.ASSETS_DIR, Config.AUDIO_DIR, Config.EXPORTS_DIR,
    os.path.join(Config.ASSETS_DIR, "bgm"),
    os.path.join(Config.ASSETS_DIR, "fonts"),
    os.path.join(Config.ASSETS_DIR, "cache"),
    os.path.join(Config.ASSETS_DIR, "images"),
    os.path.join(Config.ASSETS_DIR, "watermark"),
]
for d in DIRS:
    os.makedirs(d, exist_ok=True)
```

### Startup Resume (app.py)
```python
def _resume_interrupted_jobs(app):
    """On restart: reset any 'processing' jobs to 'queued'."""
    with app.app_context():
        stuck = JobQueue.query.filter_by(status="processing").all()
        for j in stuck:
            j.status = "queued"
            v = Video.query.filter_by(video_id=j.video_id).first()
            if v: v.status = "pending"; v.progress = 0
        if stuck:
            db.session.commit()
            print(f"[Startup] Resumed {len(stuck)} interrupted jobs")
```

---

*End of PROJECT_GENERATION_PROMPT.md — 29 parts, complete degree-level specification.*
*To regenerate: provide this file to an AI and say "Generate all files in the order listed in Part 24."*

# Setup Guide

## Prerequisites

- Python 3.10 or higher
- FFmpeg installed and in system PATH
- pip (Python package manager)

### FFmpeg Installation

**Windows:**
```bash
# Via winget
winget install FFmpeg

# Or download from https://ffmpeg.org/download.html
# Add to PATH
```

**Linux:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/sravanmodemkumar-arch/DSL.git
cd DSL
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Optional Libraries

For advanced visual features:

```bash
# Scientific graphs (line, bar, scatter, pie, histogram)
pip install matplotlib

# 2D molecular structures from SMILES strings
pip install rdkit

# Animated math/physics/chemistry scenes (20 templates)
pip install manim
```

Each optional library falls back gracefully if not installed.

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your preferred settings. The defaults work out of the box.

### 6. Run

```bash
python app.py
```

Open http://127.0.0.1:5000 in your browser.

---

## Configuration

### Environment Variables (.env)

```env
# Flask
SECRET_KEY=change-this-to-a-random-secret-key

# Video Defaults
DEFAULT_RESOLUTION=1080p          # 360p | 720p | 1080p | 2K | 4K
DEFAULT_QUALITY_PRESET=P7         # P1 (Preview) to P7 (Maximum)
DEFAULT_THEME=dark                # dark | light
DEFAULT_FPS=30                    # 24 | 30 | 60

# TTS (Text-to-Speech)
TTS_ENGINE=edge_tts               # edge_tts | gtts | pyttsx3
TTS_VOICE=en-IN-PrabhatNeural     # See voice list below

# Background Music
BGM_ENABLED=true
BGM_STYLE=lotus                   # calm_waves | zen_garden | lotus | bansuri | ...
BGM_VOLUME=0.30                   # 0.0 to 1.0

# Free Media API Keys (optional - enhances image/video fetching)
PIXABAY_API_KEY=                  # Free at pixabay.com/api/docs/
PEXELS_API_KEY=                   # Free at pexels.com/api/
UNSPLASH_API_KEY=                 # Free at unsplash.com/developers

# Worker Settings
MAX_WORKERS=4                     # Concurrent video processes
JOB_TIMEOUT=600                   # Timeout in seconds per job
```

### Available TTS Voices (Edge TTS)

| Voice | Language | Gender | Style |
|-------|----------|--------|-------|
| `en-IN-PrabhatNeural` | English (India) | Male | Clear, professional |
| `en-IN-NeerjaNeural` | English (India) | Female | Clear, warm |
| `en-IN-AaravNeural` | English (India) | Male | Young |
| `en-IN-AnanyaNeural` | English (India) | Female | Warm |
| `hi-IN-SwaraNeural` | Hindi | Female | Natural |
| `hi-IN-MadhurNeural` | Hindi | Male | Natural |
| `ta-IN-PallaviNeural` | Tamil | Female | Natural |
| `te-IN-ShrutiNeural` | Telugu | Female | Natural |

Preview voices on the Settings page after running `Generate Voice Samples`.

---

## Directory Structure After First Run

```
DSL/
├── instance/
│   └── stemvideo.db          # SQLite database (auto-created)
├── storage/
│   ├── videos/               # Generated MP4 files
│   ├── audio/                # TTS audio segments (temp)
│   ├── json/                 # Uploaded JSON files
│   ├── assets/
│   │   ├── bgm/              # Background music (included)
│   │   ├── images/           # User + fetched images
│   │   ├── svgs/             # User SVG files
│   │   └── videos/           # User + fetched video clips
│   ├── cache/
│   │   └── manim/            # Manim animation cache
│   └── exports/              # Excel/CSV exports
└── static/
    └── voice_samples/        # TTS voice previews (generated)
```

All directories are auto-created on first run.

---

## YouTube Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **YouTube Data API v3**
3. Create OAuth 2.0 credentials (Desktop application)
4. Download `client_secrets.json` and place in project root
5. On the YouTube page in the dashboard, click **Connect YouTube**
6. Complete the OAuth flow

---

## Troubleshooting

### FFmpeg not found
Ensure FFmpeg is installed and in your system PATH:
```bash
ffmpeg -version
```

### Edge TTS connection errors
Edge TTS requires an internet connection. If offline, switch to `pyttsx3` in Settings (lower quality but works offline).

### Manim render failures
Ensure LaTeX is installed for Manim equation rendering:
```bash
# Windows
winget install MiKTeX.MiKTeX

# Linux
sudo apt install texlive-full

# macOS
brew install --cask mactex
```

### Database locked errors
The app uses SQLite WAL mode for concurrent access. If you see lock errors, increase the timeout in `config.py`:
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    "connect_args": {"timeout": 60},
}
```

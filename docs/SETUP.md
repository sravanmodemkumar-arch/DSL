# Setup Guide

## Prerequisites

### Required
| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Backend runtime |
| FFmpeg | 6.0+ | Video encoding (MP4/H.264) |
| pip | Latest | Package manager |

### Optional
| Software | Purpose |
|----------|---------|
| Google Cloud TTS account | Higher quality TTS (default gTTS works without it) |
| YouTube API credentials | Automated YouTube upload (manual URL entry works without it) |

---

## Step 1: Clone / Download

```bash
cd your-workspace
# If using git:
git clone <repo-url> DSL
cd DSL
```

---

## Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### What gets installed:
| Package | Purpose |
|---------|---------|
| Flask 3.1 | Web framework |
| Flask-SQLAlchemy | Database ORM |
| Pillow | Image/frame rendering |
| gTTS | Google Text-to-Speech |
| pydub | Audio processing |
| openpyxl | Excel file generation |
| jsonschema | JSON validation |
| CairoSVG | SVG rendering (optional) |
| moviepy | Video processing utilities |

---

## Step 3: Install FFmpeg

FFmpeg is required for encoding video frames into MP4.

### Windows
```bash
# Using winget (Windows 11)
winget install ffmpeg

# Or using chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
# Extract and add bin/ folder to your PATH
```

### Verify FFmpeg
```bash
ffmpeg -version
# Should show version info
```

### macOS
```bash
brew install ffmpeg
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install ffmpeg
```

---

## Step 4: Run the Application

```bash
python app.py
```

Output:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Open **http://localhost:5000** in your browser.

---

## Step 5: First Video

1. Go to **Upload JSON** (sidebar)
2. Click **Load Sample** to insert a sample question
3. Choose resolution (default: 1080p) and quality (default: P5)
4. Click **Validate JSON** to check
5. Click **Process & Generate Videos**
6. Go to **Queue** to watch progress
7. Once complete, find it in **Video Library**

---

## Directory Structure After First Run

```
DSL/
├── instance/
│   └── stemvideo.db          # SQLite database (auto-created)
├── storage/
│   ├── videos/                # Generated MP4 files
│   │   └── Mathematics/
│   │       └── Arithmetic/
│   │           └── Addition/
│   │               ├── q-addition-001.mp4
│   │               ├── q-addition-001_audio.mp3
│   │               ├── q-addition-001_bgm.wav
│   │               ├── q-addition-001_mixed.mp3
│   │               └── q-addition-001_thumb.png
│   ├── json/                  # Uploaded JSON files
│   ├── audio/                 # Per-question audio segments
│   └── assets/                # Images and SVGs
│       ├── images/
│       └── svg/
```

---

## Configuration

All settings are in `config.py`. You can also change them at runtime through the **Settings** page.

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_RESOLUTION` | 1080p | Video resolution |
| `DEFAULT_QUALITY_PRESET` | P5 | Quality preset |
| `DEFAULT_DURATION_MINUTES` | 8 | Max video duration |
| `DEFAULT_THEME` | dark | Visual theme |
| `TTS_ENGINE` | gtts | TTS engine (gtts / pyttsx3) |
| `TTS_TLD` | co.in | Accent (co.in = Indian English) |
| `BGM_ENABLED` | True | Background music on/off |
| `BGM_STYLE` | calm_waves | Default BGM style |
| `BGM_VOLUME` | 0.15 | BGM volume (0.05-0.30) |
| `MAX_WORKERS` | 4 | Parallel processing threads |

---

## Resolution Options

| Resolution | Dimensions | Best For |
|-----------|------------|----------|
| 360p | 640 x 360 | Quick preview, testing |
| 720p | 1280 x 720 | Mobile viewing |
| 1080p | 1920 x 1080 | YouTube (recommended) |
| 2K | 2560 x 1440 | High quality displays |
| 4K | 3840 x 2160 | Maximum quality |

---

## Quality Presets

| Preset | Bitrate | FPS | Best For |
|--------|---------|-----|----------|
| P1 | 1 Mbps | 24 | Quick preview |
| P2 | 2 Mbps | 24 | Draft review |
| P3 | 4 Mbps | 30 | Mobile |
| P4 | 6 Mbps | 30 | Standard |
| **P5** | **10 Mbps** | **30** | **YouTube (default)** |
| P6 | 15 Mbps | 60 | High quality |
| P7 | 25 Mbps | 60 | Maximum / archival |

---

## YouTube Setup (Optional)

YouTube API is optional. You can manually paste YouTube URLs after uploading through YouTube Studio.

To enable API-based upload:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project
3. Enable **YouTube Data API v3**
4. Create **OAuth 2.0 credentials** (Desktop application)
5. Download `client_secrets.json` and place in project root
6. First upload will open a browser for authorization

---

## Troubleshooting

### "FFmpeg not found"
FFmpeg is not in your PATH. Install it and verify with `ffmpeg -version`.

### "gTTS failed"
Requires internet connection. Switch to `pyttsx3` in Settings for offline TTS.

### "No audio output"
Install `pydub` dependency: `pip install pydub`. On some systems you also need `ffprobe` (included with FFmpeg).

### Videos take too long
- Lower resolution (720p instead of 1080p)
- Lower quality preset (P3 instead of P5)
- Reduce max workers if CPU is overloaded

### Database errors
Delete `instance/stemvideo.db` and restart. The database is auto-recreated.

### Port 5000 in use
```bash
python app.py  # Edit app.py to change port
# Or:
flask run --port 8080
```

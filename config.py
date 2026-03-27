import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file from project root

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _bool(key, default="false"):
    return os.environ.get(key, default).lower() in ("true", "1", "yes")


def _int(key, default):
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return int(default)


def _float(key, default):
    try:
        return float(os.environ.get(key, default))
    except ValueError:
        return float(default)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "stem-video-gen-secret-key-change-in-prod")
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

    # Upload
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024   # 50 MB
    ALLOWED_EXTENSIONS = {"json", "zip"}

    # Video defaults
    DEFAULT_RESOLUTION    = os.environ.get("DEFAULT_RESOLUTION",    "1080p")
    DEFAULT_QUALITY_PRESET = os.environ.get("DEFAULT_QUALITY_PRESET", "P5")
    DEFAULT_THEME         = os.environ.get("DEFAULT_THEME",         "dark")
    DEFAULT_FPS           = _int("DEFAULT_FPS", "30")

    # Resolution map
    RESOLUTIONS = {
        "360p":  (640,  360),
        "720p":  (1280, 720),
        "1080p": (1920, 1080),
        "2K":    (2560, 1440),
        "4K":    (3840, 2160),
    }

    # Quality presets
    QUALITY_PRESETS = {
        "P1": {"bitrate": "1M",  "fps": 24, "antialiasing": False, "label": "Preview"},
        "P2": {"bitrate": "2M",  "fps": 24, "antialiasing": True,  "label": "Draft"},
        "P3": {"bitrate": "4M",  "fps": 30, "antialiasing": True,  "label": "Mobile"},
        "P4": {"bitrate": "6M",  "fps": 30, "antialiasing": True,  "label": "Standard"},
        "P5": {"bitrate": "10M", "fps": 30, "antialiasing": True,  "label": "YouTube"},
        "P6": {"bitrate": "15M", "fps": 60, "antialiasing": True,  "label": "High Quality"},
        "P7": {"bitrate": "25M", "fps": 60, "antialiasing": True,  "label": "Maximum"},
    }

    # TTS
    # Engines:  edge_tts (best, free) | gtts | pyttsx3
    # Voices (edge_tts):
    #   en-IN-NeerjaNeural  — Indian female (clear)       en-IN-PrabhatNeural — Indian male (clear)
    #   en-IN-AaravNeural   — Indian male (young)         en-IN-AnanyaNeural  — Indian female (warm)
    #   hi-IN-SwaraNeural   — Hindi female                hi-IN-MadhurNeural  — Hindi male
    #   ta-IN-PallaviNeural — Tamil female                te-IN-ShrutiNeural  — Telugu female
    TTS_ENGINE = os.environ.get("TTS_ENGINE", "edge_tts")
    TTS_LANG   = os.environ.get("TTS_LANG",   "en")
    TTS_TLD    = os.environ.get("TTS_VOICE",  "en-IN-PrabhatNeural")  # voice name for edge_tts

    # Background Music
    # Styles: calm_waves | zen_garden | morning_dew | deep_focus | soft_piano
    #         crystal_bowl | forest_stream | twilight | lotus | silent_mind | bansuri
    BGM_ENABLED = _bool("BGM_ENABLED", "true")
    BGM_STYLE   = os.environ.get("BGM_STYLE",  "lotus")
    BGM_VOLUME  = _float("BGM_VOLUME", "0.30")
    BGM_FILES   = [
        os.path.join(BASE_DIR, "storage", "assets", "bgm", f)
        for f in [
            "viacheslavstarostin-educational-education-school-music-340837.mp3",
            "delosound-educational-education-school-music-2-432211.mp3",
            "hitslab-study-educational-learning-music-345519.mp3",
            "krasnoshchok-educational-educational-learning-study-music-409483.mp3",
            "mondamusic-educational-education-school-music-499164.mp3",
            "sigmamusicart-background-educational-environment-music-369011.mp3",
            "soundore-the-music-free-educational-506592.mp3",
            "viacheslavstarostin-background-backsound-educational-music-366035.mp3",
        ]
    ]

    # Watermark
    WATERMARK_ENABLED = _bool("WATERMARK_ENABLED", "false")
    WATERMARK_TEXT    = os.environ.get("WATERMARK_TEXT",    "")
    WATERMARK_IMAGE   = os.path.join(BASE_DIR, "storage", "assets", "watermark", "watermark.png")
    WATERMARK_OPACITY = _float("WATERMARK_OPACITY", "0.35")

    # Workers
    MAX_WORKERS = _int("MAX_WORKERS", "4")
    JOB_TIMEOUT = _int("JOB_TIMEOUT", "600")

    # YouTube OAuth
    YOUTUBE_CLIENT_SECRETS = os.path.join(BASE_DIR, "client_secrets.json")
    YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


# Theme colors (not in .env — complex colour maps)
THEMES = {
    "dark": {
        "bg": "#0f0f23",
        "card_bg": "#1a1a2e",
        "text": "#ffffff",
        "text_secondary": "#a0a0b8",
        "accent": "#00d4ff",
        "success": "#00ff88",
        "warning": "#ffaa00",
        "error": "#ff4444",
        "formula_bg": "#2a2a4a",
        "highlight": "#00d4ff",
        "border": "#2a2a4a",
    },
    "light": {
        "bg": "#f5f5f5",
        "card_bg": "#ffffff",
        "text": "#1a1a1a",
        "text_secondary": "#666666",
        "accent": "#0066cc",
        "success": "#00aa55",
        "warning": "#cc8800",
        "error": "#cc3333",
        "formula_bg": "#e8e8f0",
        "highlight": "#0066cc",
        "border": "#dddddd",
    },
}

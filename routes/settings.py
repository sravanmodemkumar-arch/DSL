import os
import tempfile
from flask import Blueprint, render_template, request, current_app, send_file, jsonify
from werkzeug.utils import secure_filename
from models import db, Setting

settings_bp = Blueprint("settings", __name__)

# Default settings
DEFAULTS = {
    "default_resolution": "1080p",
    "default_quality_preset": "P5",
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
    "bgm_volume": "0.15",
    "auto_youtube_upload": "false",
    "youtube_default_privacy": "public",
    "youtube_default_category": "27",
    "storage_path": "",
    "ffmpeg_path": "ffmpeg",
    "watermark_enabled": "false",
    "watermark_text": "",
    "watermark_opacity": "0.35",
}


@settings_bp.route("/")
def index():
    settings = {}
    for key, default in DEFAULTS.items():
        settings[key] = Setting.get(key, default)

    resolutions = list(current_app.config["RESOLUTIONS"].keys())
    presets = current_app.config["QUALITY_PRESETS"]

    return render_template(
        "settings.html",
        settings=settings,
        resolutions=resolutions,
        presets=presets,
    )


@settings_bp.route("/save", methods=["POST"])
def save():
    """Save all settings from form."""
    for key in DEFAULTS:
        value = request.form.get(key, DEFAULTS[key])
        Setting.set(key, value)

    return '''
    <div class="text-green-400 p-3 rounded bg-green-400/10 border border-green-400/20">
        Settings saved successfully!
    </div>
    '''


@settings_bp.route("/tts-preview")
def tts_preview():
    """Serve pre-generated sample MP3; fall back to live generation if missing."""
    import re
    voice = request.args.get("voice", "en-IN-NeerjaNeural")
    if not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+Neural", voice):
        return jsonify({"error": "Invalid voice name"}), 400

    static_dir = os.path.join(current_app.root_path, "static", "voice_samples")
    cached = os.path.join(static_dir, f"{voice}.mp3")

    if os.path.exists(cached):
        return send_file(cached, mimetype="audio/mpeg", as_attachment=False,
                         download_name="preview.mp3")

    # Not pre-generated — generate live and cache it for next time
    os.makedirs(static_dir, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    try:
        from engine.audio import _generate_edge_tts
        sample_text = "Hello! I am your learning assistant. Let's explore this topic together."
        _generate_edge_tts(sample_text, tmp.name, voice=voice)
        # Cache it
        import shutil
        shutil.move(tmp.name, cached)
        return send_file(cached, mimetype="audio/mpeg", as_attachment=False,
                         download_name="preview.mp3")
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/tts-generate-samples", methods=["POST"])
def tts_generate_samples():
    """Trigger pre-generation of all voice samples (called from Settings UI)."""
    force = request.form.get("force", "false") == "true"
    try:
        import sys
        sys.path.insert(0, current_app.root_path)
        from generate_voice_samples import run as gen_run
        result = gen_run(force=force)
        total = len(result["ok"]) + len(result["skipped"])
        failed = len(result["fail"])
        msg = f"Generated {len(result['ok'])}, skipped {len(result['skipped'])}"
        if failed:
            msg += f", {failed} failed: {', '.join(v for v, _ in result['fail'])}"
        color = "green" if not failed else "yellow"
        return f'''<div class="text-{color}-400 p-3 rounded bg-{color}-400/10 border border-{color}-400/20">{msg}</div>'''
    except Exception as e:
        return f'''<div class="text-red-400 p-3 rounded bg-red-400/10 border border-red-400/20">Error: {e}</div>'''


@settings_bp.route("/reset", methods=["POST"])
def reset():
    """Reset all settings to defaults."""
    for key, value in DEFAULTS.items():
        Setting.set(key, value)

    return '''
    <div class="text-yellow-400 p-3 rounded bg-yellow-400/10 border border-yellow-400/20">
        Settings reset to defaults. Reload the page to see changes.
    </div>
    '''


@settings_bp.route("/watermark/upload", methods=["POST"])
def watermark_upload():
    """Upload watermark image — stored as storage/assets/watermark/watermark.png."""
    f = request.files.get("watermark_file")
    if not f or not f.filename:
        return '<div class="text-red-400 p-2 text-sm">No file selected.</div>'

    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        return '<div class="text-red-400 p-2 text-sm">Only PNG / JPG / WEBP allowed.</div>'

    wm_dir = os.path.join(current_app.config["ASSETS_DIR"], "watermark")
    os.makedirs(wm_dir, exist_ok=True)
    dest = os.path.join(wm_dir, "watermark" + ext)
    # Remove old watermark files
    for old in os.listdir(wm_dir):
        os.remove(os.path.join(wm_dir, old))
    f.save(dest)

    # Save path to settings so pipeline picks it up
    Setting.set("watermark_image_path", dest)

    return f'<div class="text-green-400 p-2 text-sm">Watermark saved: {os.path.basename(dest)}</div>'


@settings_bp.route("/watermark/delete", methods=["POST"])
def watermark_delete():
    """Remove watermark image."""
    wm_dir = os.path.join(current_app.config["ASSETS_DIR"], "watermark")
    removed = False
    if os.path.isdir(wm_dir):
        for f in os.listdir(wm_dir):
            os.remove(os.path.join(wm_dir, f))
            removed = True
    Setting.set("watermark_image_path", "")
    msg = "Watermark removed." if removed else "No watermark found."
    return f'<div class="text-yellow-400 p-2 text-sm">{msg}</div>'


@settings_bp.route("/watermark/status")
def watermark_status():
    """Return current watermark filename (for UI display)."""
    wm_dir = os.path.join(current_app.config["ASSETS_DIR"], "watermark")
    files  = os.listdir(wm_dir) if os.path.isdir(wm_dir) else []
    name   = files[0] if files else ""
    if name:
        return f'<span class="text-green-400 text-xs">{name} (active)</span>'
    return '<span class="text-gray-500 text-xs">No image uploaded</span>'

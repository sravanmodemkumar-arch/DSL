import os
import logging
from logging.handlers import RotatingFileHandler

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP for local OAuth (dev only)

from flask import Flask
from config import Config, BASE_DIR
from models import db
from routes import register_blueprints

LOG_FILE = os.path.join(BASE_DIR, "server.log")



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Copy class attributes that are dicts (not picked up by from_object)
    app.config["RESOLUTIONS"] = Config.RESOLUTIONS
    app.config["QUALITY_PRESETS"] = Config.QUALITY_PRESETS

    # Ensure directories exist
    for d in [
        Config.STORAGE_DIR, Config.VIDEOS_DIR, Config.JSON_DIR,
        Config.ASSETS_DIR, Config.AUDIO_DIR, Config.EXPORTS_DIR,
        os.path.join(Config.ASSETS_DIR, "images"),
        os.path.join(Config.ASSETS_DIR, "svg"),
        os.path.join(Config.ASSETS_DIR, "videos"),
        os.path.join(Config.ASSETS_DIR, "watermark"),
        os.path.join(BASE_DIR, "instance"),
    ]:
        os.makedirs(d, exist_ok=True)

    # Init database
    db.init_app(app)
    with app.app_context():
        # Enable WAL mode for concurrent multi-video write support
        from sqlalchemy import text
        with db.engine.connect() as _conn:
            _conn.execute(text("PRAGMA journal_mode=WAL"))
            _conn.execute(text("PRAGMA synchronous=NORMAL"))
            _conn.execute(text("PRAGMA busy_timeout=30000"))
            _conn.commit()
        db.create_all()

    # ── Logging — rotate at 2 MB, keep 0 backups (auto-cleanup) ─────────
    log_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=0, encoding="utf-8"
    )
    log_handler.setLevel(logging.WARNING)  # Only warnings+errors to file
    log_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    app.logger.addHandler(log_handler)

    # Suppress verbose werkzeug request logging (each HTTP request)
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.ERROR)  # Only log errors, not every GET/POST

    # Register blueprints
    register_blueprints(app)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("500.html"), 500

    # Serve uploaded videos
    @app.route("/storage/<path:filename>")
    def serve_storage(filename):
        from flask import send_from_directory
        return send_from_directory(Config.STORAGE_DIR, filename)

    return app


app = create_app()

# Auto-resume queued jobs on startup (only in actual server process, not reloader)
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    # Show hardware profile on startup
    from engine.hardware import detect_hardware, compute_allocation, print_hardware_summary
    hw = detect_hardware()
    alloc = compute_allocation(hw)
    print_hardware_summary(hw, alloc)

    with app.app_context():
        from models import JobQueue, Video
        # Reset stuck "processing" jobs back to "queued"
        stuck = JobQueue.query.filter_by(status="processing").all()
        for j in stuck:
            j.status = "queued"
            v = Video.query.filter_by(video_id=j.video_id).first()
            if v:
                v.status = "pending"
        if stuck:
            db.session.commit()
            print(f"[Startup] Reset {len(stuck)} stuck job(s) back to queued")
        # Resume processing if any queued jobs exist
        pending = JobQueue.query.filter_by(status="queued").count()
        if pending > 0:
            from routes.upload import _start_processing
            _start_processing(app)
            print(f"[Startup] Resuming {pending} queued job(s)")

if __name__ == "__main__":
    app.run(debug=True, port=5000)

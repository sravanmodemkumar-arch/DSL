import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP for local OAuth (dev only)

from flask import Flask
from config import Config, BASE_DIR
from models import db
from routes import register_blueprints



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

if __name__ == "__main__":
    app.run(debug=True, port=5000)

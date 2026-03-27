from .dashboard import dashboard_bp
from .upload import upload_bp
from .videos import videos_bp
from .queue_routes import queue_bp
from .youtube import youtube_bp
from .export import export_bp
from .settings import settings_bp
from .assets import assets_bp


def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp, url_prefix="/upload")
    app.register_blueprint(videos_bp, url_prefix="/videos")
    app.register_blueprint(queue_bp, url_prefix="/queue")
    app.register_blueprint(youtube_bp, url_prefix="/youtube")
    app.register_blueprint(export_bp, url_prefix="/export")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(assets_bp, url_prefix="/assets")

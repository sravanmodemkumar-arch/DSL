from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)

    # Hierarchy
    subject = db.Column(db.String(100), nullable=False, index=True)
    chapter = db.Column(db.String(200), default="")
    topic = db.Column(db.String(200), nullable=False, index=True)
    subtopic = db.Column(db.String(200), default="")
    difficulty = db.Column(db.String(20), default="medium")

    # Tags
    exam_tags = db.Column(db.Text, default="")       # comma-separated
    purpose_tags = db.Column(db.Text, default="")     # comma-separated
    grade_tags = db.Column(db.Text, default="")       # comma-separated

    # Video settings
    resolution = db.Column(db.String(10), default="1080p")
    quality_preset = db.Column(db.String(5), default="P7")
    duration_seconds = db.Column(db.Float, default=0)
    fps = db.Column(db.Integer, default=30)
    theme = db.Column(db.String(10), default="dark")

    # File paths
    json_path = db.Column(db.String(500), default="")
    output_dir = db.Column(db.String(500), default="")   # unique UUID-named dir for all render outputs
    video_path = db.Column(db.String(500), default="")
    audio_path = db.Column(db.String(500), default="")
    thumbnail_path = db.Column(db.String(500), default="")

    # YouTube
    youtube_url = db.Column(db.String(500), default="")
    youtube_video_id = db.Column(db.String(50), default="")
    youtube_status = db.Column(db.String(20), default="not_uploaded")  # not_uploaded, uploading, published, failed

    # Status
    status = db.Column(db.String(20), default="pending")  # pending, processing, completed, failed
    error_message = db.Column(db.Text, default="")
    progress = db.Column(db.Integer, default=0)  # 0-100

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "video_id": self.video_id,
            "title": self.title,
            "subject": self.subject,
            "chapter": self.chapter,
            "topic": self.topic,
            "subtopic": self.subtopic,
            "difficulty": self.difficulty,
            "exam_tags": self.exam_tags.split(",") if self.exam_tags else [],
            "purpose_tags": self.purpose_tags.split(",") if self.purpose_tags else [],
            "grade_tags": self.grade_tags.split(",") if self.grade_tags else [],
            "resolution": self.resolution,
            "quality_preset": self.quality_preset,
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "theme": self.theme,
            "video_path": self.video_path,
            "youtube_url": self.youtube_url,
            "youtube_status": self.youtube_status,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
        }


class JobQueue(db.Model):
    __tablename__ = "job_queue"

    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(100), db.ForeignKey("videos.video_id"), nullable=False)
    priority = db.Column(db.Integer, default=2)  # 1=urgent, 2=high, 3=normal, 4=low
    status = db.Column(db.String(20), default="queued")  # queued, processing, completed, failed, cancelled
    stage = db.Column(db.String(30), default="")  # audio_gen, timestamp_map, rendering, encoding
    progress = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, default="")
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    video = db.relationship("Video", backref=db.backref("jobs", lazy=True))


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @staticmethod
    def get(key, default=""):
        s = Setting.query.filter_by(key=key).first()
        return s.value if s else default

    @staticmethod
    def set(key, value):
        s = Setting.query.filter_by(key=key).first()
        if s:
            s.value = str(value)
        else:
            s = Setting(key=key, value=str(value))
            db.session.add(s)
        db.session.commit()

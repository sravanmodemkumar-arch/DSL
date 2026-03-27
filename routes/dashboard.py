from flask import Blueprint, render_template
from models import db, Video, JobQueue
from sqlalchemy import func

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    total_videos = Video.query.count()
    completed = Video.query.filter_by(status="completed").count()
    processing = Video.query.filter_by(status="processing").count()
    failed = Video.query.filter_by(status="failed").count()
    pending = Video.query.filter_by(status="pending").count()

    # Videos by subject
    subject_counts = (
        db.session.query(Video.subject, func.count(Video.id))
        .group_by(Video.subject)
        .all()
    )
    subjects = {s: c for s, c in subject_counts}

    # Recent videos
    recent = Video.query.order_by(Video.created_at.desc()).limit(10).all()

    # Active jobs
    active_jobs = JobQueue.query.filter(
        JobQueue.status.in_(["queued", "processing"])
    ).order_by(JobQueue.priority, JobQueue.created_at).limit(5).all()

    # YouTube stats
    uploaded = Video.query.filter_by(youtube_status="published").count()

    return render_template(
        "dashboard.html",
        total_videos=total_videos,
        completed=completed,
        processing=processing,
        failed=failed,
        pending=pending,
        subjects=subjects,
        recent=recent,
        active_jobs=active_jobs,
        uploaded=uploaded,
    )


@dashboard_bp.route("/stats")
def stats_partial():
    """HTMX partial for live stats refresh."""
    total_videos = Video.query.count()
    completed = Video.query.filter_by(status="completed").count()
    processing = Video.query.filter_by(status="processing").count()
    failed = Video.query.filter_by(status="failed").count()
    pending = Video.query.filter_by(status="pending").count()

    return render_template(
        "components/stats_cards.html",
        total_videos=total_videos,
        completed=completed,
        processing=processing,
        failed=failed,
        pending=pending,
    )

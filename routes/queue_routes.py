import os
import shutil
from flask import Blueprint, render_template, request
from models import db, JobQueue, Video
from datetime import datetime, timezone

queue_bp = Blueprint("queue", __name__)


@queue_bp.route("/")
def index():
    status_filter = request.args.get("status", "")
    query = JobQueue.query

    if status_filter:
        query = query.filter(JobQueue.status == status_filter)

    jobs = query.order_by(JobQueue.priority, JobQueue.created_at.desc()).all()

    # Stats
    queued = JobQueue.query.filter_by(status="queued").count()
    processing = JobQueue.query.filter_by(status="processing").count()
    completed = JobQueue.query.filter_by(status="completed").count()
    failed = JobQueue.query.filter_by(status="failed").count()

    return render_template(
        "queue.html",
        jobs=jobs,
        queued=queued,
        processing=processing,
        completed=completed,
        failed=failed,
        status_filter=status_filter,
    )


@queue_bp.route("/list")
def list_partial():
    """HTMX partial — returns job list."""
    status_filter = request.args.get("status", "")
    query = JobQueue.query

    if status_filter:
        query = query.filter(JobQueue.status == status_filter)

    jobs = query.order_by(JobQueue.priority, JobQueue.created_at.desc()).all()
    return render_template("components/queue_list.html", jobs=jobs)


@queue_bp.route("/<int:job_id>/cancel", methods=["POST"])
def cancel(job_id):
    job = JobQueue.query.get_or_404(job_id)
    if job.status in ("queued", "processing"):
        job.status = "cancelled"
        video = Video.query.filter_by(video_id=job.video_id).first()
        if video:
            video.status = "failed"
            video.progress = 0
            video.error_message = "Cancelled by user"
            # Clean up any partially generated files
            _cleanup_video_files(video)
        db.session.commit()
    return render_template("components/queue_item.html", job=job)


def _cleanup_video_files(video):
    """Delete all files generated for a video (used on cancel or delete)."""
    # Individual known file paths
    for path in [video.video_path, video.audio_path, video.thumbnail_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # Output directory (audio segments, bgm, mixed, frames)
    if video.video_path:
        output_dir = os.path.dirname(video.video_path)
        if output_dir and os.path.isdir(output_dir):
            qid = video.video_id
            # Temp audio files
            for suffix in (f"{qid}_audio.mp3", f"{qid}_bgm.wav", f"{qid}_mixed.mp3"):
                p = os.path.join(output_dir, suffix)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            # Audio segments dir
            audio_dir = os.path.join(output_dir, "audio")
            if os.path.isdir(audio_dir):
                shutil.rmtree(audio_dir, ignore_errors=True)
            # Frames dir (if render was interrupted)
            frames_dir = os.path.join(output_dir, "frames")
            if os.path.isdir(frames_dir):
                shutil.rmtree(frames_dir, ignore_errors=True)

    # Clear paths in DB
    video.video_path = ""
    video.audio_path = ""
    video.thumbnail_path = ""


@queue_bp.route("/<int:job_id>/retry", methods=["POST"])
def retry(job_id):
    job = JobQueue.query.get_or_404(job_id)
    job.status = "queued"
    job.progress = 0
    job.stage = ""
    job.error_message = ""
    job.retry_count = 0

    video = Video.query.filter_by(video_id=job.video_id).first()
    if video:
        video.status = "pending"
        video.progress = 0
        video.error_message = ""

    db.session.commit()

    from routes.upload import _start_processing
    from flask import current_app
    _start_processing(current_app._get_current_object())

    return render_template("components/queue_item.html", job=job)


@queue_bp.route("/<int:job_id>/priority", methods=["POST"])
def set_priority(job_id):
    job = JobQueue.query.get_or_404(job_id)
    priority = request.form.get("priority", 3, type=int)
    job.priority = max(1, min(4, priority))
    db.session.commit()
    return render_template("components/queue_item.html", job=job)


@queue_bp.route("/clear-completed", methods=["POST"])
def clear_completed():
    JobQueue.query.filter_by(status="completed").delete()
    db.session.commit()
    return ""

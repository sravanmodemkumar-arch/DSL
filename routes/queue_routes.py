import os
import shutil
from flask import Blueprint, render_template, request, current_app
from sqlalchemy import text
from models import db, JobQueue, Video
from datetime import datetime, timezone

_ACTIVE_FIRST = text(
    "CASE status WHEN 'processing' THEN 0 WHEN 'queued' THEN 1 "
    "WHEN 'failed' THEN 2 WHEN 'completed' THEN 3 ELSE 4 END"
)

queue_bp = Blueprint("queue", __name__)


@queue_bp.route("/")
def index():
    status_filter = request.args.get("status", "")
    query = JobQueue.query

    if status_filter:
        query = query.filter(JobQueue.status == status_filter)

    jobs = query.order_by(_ACTIVE_FIRST, JobQueue.priority, JobQueue.created_at.desc()).all()

    # Stats
    queued = JobQueue.query.filter_by(status="queued").count()
    processing = JobQueue.query.filter_by(status="processing").count()
    completed = JobQueue.query.filter_by(status="completed").count()
    failed = JobQueue.query.filter_by(status="failed").count()
    cancelled = JobQueue.query.filter_by(status="cancelled").count()
    total = queued + processing + completed + failed + cancelled

    return render_template(
        "queue.html",
        jobs=jobs,
        queued=queued,
        processing=processing,
        completed=completed,
        failed=failed,
        cancelled=cancelled,
        total=total,
        status_filter=status_filter,
    )


@queue_bp.route("/list")
def list_partial():
    """HTMX partial — returns job list."""
    status_filter = request.args.get("status", "")
    query = JobQueue.query

    if status_filter:
        query = query.filter(JobQueue.status == status_filter)

    jobs = query.order_by(_ACTIVE_FIRST, JobQueue.priority, JobQueue.created_at.desc()).all()
    return render_template("components/queue_list.html", jobs=jobs)


@queue_bp.route("/<int:job_id>/cancel", methods=["POST"])
def cancel(job_id):
    job = JobQueue.query.get_or_404(job_id)
    if job.status in ("queued", "processing"):
        # Signal the running job to stop (checked in progress_cb)
        if job.status == "processing":
            from routes.upload import _mark_cancelled
            _mark_cancelled(job_id)

        video = Video.query.filter_by(video_id=job.video_id).first()
        json_path = ""
        if video:
            json_path = video.json_path or ""
            _cleanup_video_files(video)
            db.session.delete(video)
        db.session.delete(job)
        db.session.commit()
        if json_path:
            _cleanup_orphaned_json(json_path)

        # Restart queue so remaining queued jobs keep processing
        from routes.upload import _start_processing
        from flask import current_app
        _start_processing(current_app._get_current_object())

        return ""  # HTMX removes the card
    return render_template("components/queue_item.html", job=job)


def _cleanup_orphaned_json(json_path):
    """Delete the batch JSON file if no video records reference it anymore."""
    if not json_path or not os.path.exists(json_path):
        return
    if Video.query.filter_by(json_path=json_path).count() == 0:
        try:
            os.remove(json_path)
        except OSError:
            pass


def _remove_empty_dirs(path, stop_at):
    """Walk up from path removing empty directories until stop_at is reached."""
    path = os.path.abspath(path)
    stop_at = os.path.abspath(stop_at)
    while path and path != stop_at and path.startswith(stop_at):
        try:
            if os.path.isdir(path) and not os.listdir(path):
                os.rmdir(path)
            else:
                break
        except OSError:
            break
        path = os.path.dirname(path)


def _cleanup_video_files(video):
    """Delete all files generated for a video (used on cancel or delete)."""
    videos_root = current_app.config.get("VIDEOS_DIR", "")

    # ── New path: UUID-named output_dir — wipe the whole directory at once ──
    if getattr(video, "output_dir", None) and video.output_dir:
        out = video.output_dir
        if os.path.isdir(out):
            shutil.rmtree(out, ignore_errors=True)
        # Walk up and remove now-empty parent dirs (subtopic → topic → subject)
        _remove_empty_dirs(os.path.dirname(out), stop_at=videos_root)
        video.video_path = ""
        video.audio_path = ""
        video.thumbnail_path = ""
        video.output_dir = ""
        return

    # ── Legacy fallback: old records without output_dir ──
    for path in [video.video_path, video.audio_path, video.thumbnail_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    candidate_dirs = set()
    if video.video_path:
        candidate_dirs.add(os.path.dirname(video.video_path))
    if videos_root and video.subject:
        candidate_dirs.add(os.path.join(
            videos_root, video.subject, video.topic or "", video.subtopic or "general",
        ))

    qid = video.video_id
    for output_dir in candidate_dirs:
        if not output_dir or not os.path.isdir(output_dir):
            continue
        for suffix in (f"{qid}_audio.mp3", f"{qid}_bgm.wav", f"{qid}_mixed.mp3"):
            p = os.path.join(output_dir, suffix)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        for d in (f"audio_{qid}", f"frames_{qid}", "audio", "frames"):
            p = os.path.join(output_dir, d)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
        for fname in list(os.listdir(output_dir)):
            if fname.startswith(qid):
                try:
                    os.remove(os.path.join(output_dir, fname))
                except Exception:
                    pass
        _remove_empty_dirs(output_dir, stop_at=videos_root)

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
        # Restore the question-ID-based output directory
        from flask import current_app as _app
        video.output_dir = os.path.join(
            _app.config["VIDEOS_DIR"],
            video.video_id,
        )
        # Apply current settings so changed resolution/quality take effect
        from models import Setting
        video.resolution = Setting.get("default_resolution", _app.config["DEFAULT_RESOLUTION"])
        video.quality_preset = Setting.get("default_quality_preset", _app.config["DEFAULT_QUALITY_PRESET"])
        video.theme = Setting.get("default_theme", _app.config["DEFAULT_THEME"])

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


@queue_bp.route("/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    """Delete a job and its video record + all generated files."""
    job = JobQueue.query.get_or_404(job_id)
    # Signal if currently processing
    if job.status == "processing":
        from routes.upload import _mark_cancelled
        _mark_cancelled(job_id)
    video = Video.query.filter_by(video_id=job.video_id).first()
    json_path = video.json_path if video else ""
    if video:
        _cleanup_video_files(video)
        db.session.delete(video)
    db.session.delete(job)
    db.session.commit()
    _cleanup_orphaned_json(json_path)   # delete batch JSON if nothing else references it

    # Restart queue so remaining jobs keep processing
    from routes.upload import _start_processing
    from flask import current_app
    _start_processing(current_app._get_current_object())

    return ""   # empty → HTMX removes the card


@queue_bp.route("/clear-completed", methods=["POST"])
def clear_completed():
    JobQueue.query.filter_by(status="completed").delete()
    db.session.commit()
    return ""


@queue_bp.route("/clear-cancelled", methods=["POST"])
def clear_cancelled():
    """Delete all cancelled/failed jobs and their video records + files."""
    jobs = JobQueue.query.filter(
        JobQueue.status.in_(["cancelled", "failed"])
    ).all()
    json_paths = set()
    for job in jobs:
        video = Video.query.filter_by(video_id=job.video_id).first()
        if video:
            if video.json_path:
                json_paths.add(video.json_path)
            _cleanup_video_files(video)
            db.session.delete(video)
        db.session.delete(job)
    db.session.commit()
    for jp in json_paths:
        _cleanup_orphaned_json(jp)
    return ""

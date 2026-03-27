import os
import json
import zipfile
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, render_template, request, current_app, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from models import db, Video, JobQueue
from engine.validator import validate_json
from engine.pipeline import VideoPipeline
from datetime import datetime, timezone

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/")
def index():
    return render_template("upload.html")


@upload_bp.route("/download/reference-schema")
def download_reference_schema():
    path = os.path.join(current_app.root_path, "REFERENCE_SCHEMA.json")
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name="REFERENCE_SCHEMA.json",
                     mimetype="application/json")


@upload_bp.route("/download/prompt")
def download_prompt():
    path = os.path.join(current_app.root_path, "PROMPT_JSON_GENERATOR.md")
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name="PROMPT_JSON_GENERATOR.md",
                     mimetype="text/markdown")


@upload_bp.route("/validate", methods=["POST"])
def validate():
    """HTMX endpoint — validate JSON content and return results."""
    json_text = request.form.get("json_content", "")
    if not json_text.strip():
        return '<div class="text-red-400 p-3">No JSON content provided</div>'

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        return f'<div class="text-red-400 p-3">Invalid JSON syntax: {e}</div>'

    is_valid, errors = validate_json(data)

    if is_valid and not errors:
        count = len(data) if isinstance(data, list) else 1
        return f'<div class="text-green-400 p-3">Valid JSON — {count} question(s) found. Ready to process.</div>'

    html = '<div class="space-y-2 p-3">'
    for err in errors:
        color = "red" if err.severity == "error" else "yellow"
        html += f'<div class="text-{color}-400 text-sm">[{err.severity.upper()}] {err.path}: {err.message}</div>'
    html += "</div>"
    return html


@upload_bp.route("/process", methods=["POST"])
def process():
    """Process uploaded JSON — create video records and queue jobs."""
    json_text = request.form.get("json_content", "")
    json_file = request.files.get("json_file")

    # Settings from form
    resolution = request.form.get("resolution", current_app.config["DEFAULT_RESOLUTION"])
    quality = request.form.get("quality_preset", current_app.config["DEFAULT_QUALITY_PRESET"])
    theme = request.form.get("theme", current_app.config["DEFAULT_THEME"])

    # Get JSON content — support .json and .zip files
    data = []

    if json_file and json_file.filename:
        fname = secure_filename(json_file.filename)
        if fname.endswith(".zip"):
            # Extract all .json files from ZIP
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    zip_path = os.path.join(tmpdir, fname)
                    json_file.save(zip_path)
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        for name in zf.namelist():
                            if name.endswith(".json") and not name.startswith("__"):
                                content = zf.read(name).decode("utf-8")
                                try:
                                    parsed = json.loads(content)
                                    if isinstance(parsed, list):
                                        data.extend(parsed)
                                    else:
                                        data.append(parsed)
                                except json.JSONDecodeError:
                                    pass  # skip invalid files
            except zipfile.BadZipFile:
                return '<div class="text-red-400 p-3">Invalid ZIP file</div>'
        else:
            json_text = json_file.read().decode("utf-8")

    if not data:
        # Fall back to editor content
        if not json_text.strip():
            return '<div class="text-red-400 p-3">No JSON content provided</div>'
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            return f'<div class="text-red-400 p-3">Invalid JSON: {e}</div>'

    if not isinstance(data, list):
        data = [data]

    is_valid, errors = validate_json(data)
    fatal = [e for e in errors if e.severity == "error"]
    if fatal:
        html = '<div class="text-red-400 p-3">Validation failed:<br>'
        for e in fatal[:10]:
            html += f'{e.path}: {e.message}<br>'
        html += '</div>'
        return html

    # Save JSON file
    json_dir = current_app.config["JSON_DIR"]
    os.makedirs(json_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(json_dir, f"batch_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Create video records and queue jobs
    created = 0
    requeued = 0
    skipped = 0
    for q in data:
        qid = q.get("id", f"q_{ts}_{created}")
        meta = q.get("meta", {})

        # Title: prefer question text, fall back to thumbnail title, then ID
        title = (
            q.get("question", {}).get("text")
            or q.get("thumbnail", {}).get("title", "")
            or qid
        )

        # exam_tags: meta.exam is a string like "SSC / UPSC / Banking"
        raw_exam = meta.get("exam", meta.get("exam_tags", "")) or ""
        if isinstance(raw_exam, list):
            exam_tags_str = ",".join(raw_exam)
        else:
            exam_tags_str = ",".join(p.strip() for p in raw_exam.replace("/", ",").split(",") if p.strip())

        # grade_tags: meta.grade is a plain string
        raw_grade = meta.get("grade", meta.get("grade_tags", "")) or ""
        if isinstance(raw_grade, list):
            grade_tags_str = ",".join(raw_grade)
        else:
            grade_tags_str = raw_grade.strip()

        # purpose_tags: optional list or string
        raw_purpose = meta.get("purpose", meta.get("purpose_tags", "")) or ""
        if isinstance(raw_purpose, list):
            purpose_tags_str = ",".join(raw_purpose)
        else:
            purpose_tags_str = raw_purpose.strip()

        # Check for existing video
        existing = Video.query.filter_by(video_id=qid).first()
        if existing:
            if existing.status == "completed":
                # Already rendered — skip
                skipped += 1
                continue
            else:
                # pending/failed/cancelled — re-queue with updated JSON path
                existing.json_path = json_path
                existing.status = "pending"
                existing.progress = 0
                existing.error_message = ""
                # Cancel any existing queued/processing job first
                JobQueue.query.filter_by(video_id=qid).filter(
                    JobQueue.status.in_(["queued", "processing", "cancelled", "failed"])
                ).delete()
                job = JobQueue(video_id=qid, priority=3, status="queued")
                db.session.add(job)
                requeued += 1
                continue

        video = Video(
            video_id=qid,
            title=title,
            subject=meta.get("subject", "Unknown"),
            chapter=meta.get("chapter", ""),
            topic=meta.get("topic", ""),
            subtopic=meta.get("subtopic", ""),
            difficulty=meta.get("difficulty", "medium"),
            exam_tags=exam_tags_str,
            purpose_tags=purpose_tags_str,
            grade_tags=grade_tags_str,
            resolution=resolution,
            quality_preset=quality,
            theme=theme,
            json_path=json_path,
            status="pending",
        )
        db.session.add(video)

        job = JobQueue(video_id=qid, priority=3, status="queued")
        db.session.add(job)
        created += 1

    db.session.commit()

    # Start processing in background
    if created + requeued > 0:
        _start_processing(current_app._get_current_object())

    parts = []
    if created:
        parts.append(f"{created} new")
    if requeued:
        parts.append(f"{requeued} re-queued")
    if skipped:
        parts.append(f"{skipped} skipped (already completed)")

    return f'''
    <div class="text-green-400 p-3">
        Queued {", ".join(parts)} video(s).
        <a href="/queue" class="underline text-cyan-400">View Queue</a>
    </div>
    '''


# ── Queue processor — dynamic concurrent multi-video ──────────────────────────

_queue_running = False
_queue_lock = threading.Lock()


def _start_processing(app):
    """Start background queue processor — no-op if already running."""
    global _queue_running
    with _queue_lock:
        if _queue_running:
            return
        _queue_running = True
    thread = threading.Thread(target=_process_queue, args=(app,), daemon=True)
    thread.start()


def _process_queue(app):
    """Wrapper that clears the running flag when done."""
    global _queue_running
    try:
        _run_queue(app)
    finally:
        with _queue_lock:
            _queue_running = False


def _run_queue(app):
    """Process all queued jobs with dynamic CPU/GPU concurrency.

    Hardware auto-detection:
      total_cores < 4  → 1 video  using all cores
      4–7 cores        → 2 videos × (cores//2) each
      8–15 cores       → cores//4 videos × 4 cores each
      16–31 cores      → cores//4 videos × 4 cores each
      32+ cores        → cores//8 videos × 8 cores each (capped at 16/video)

    GPU encoding is serialised via a module-level lock in pipeline.py so
    concurrent videos don't fight over the GPU.
    """
    total_cores = os.cpu_count() or 1

    if total_cores < 4:
        concurrent_videos = 1
        cores_per_video   = total_cores
    elif total_cores < 8:
        cores_per_video   = max(2, total_cores // 2)
        concurrent_videos = max(1, total_cores // cores_per_video)
    else:
        cores_per_video   = max(4, min(16, total_cores // 8))
        concurrent_videos = max(1, total_cores // cores_per_video)

    # Build config dict once (read from app config in main thread)
    with app.app_context():
        from config import THEMES
        from models import Setting as _Setting
        _wm_path = _Setting.get("watermark_image_path", app.config.get("WATERMARK_IMAGE", ""))
        config_dict = {
            "RESOLUTIONS":       app.config["RESOLUTIONS"],
            "QUALITY_PRESETS":   app.config["QUALITY_PRESETS"],
            "TTS_ENGINE":        app.config["TTS_ENGINE"],
            "TTS_LANG":          app.config["TTS_LANG"],
            "TTS_TLD":           app.config["TTS_TLD"],
            "ASSETS_DIR":        app.config["ASSETS_DIR"],
            "THEMES":            THEMES,
            "BGM_ENABLED":       app.config.get("BGM_ENABLED", True),
            "BGM_STYLE":         app.config.get("BGM_STYLE", "ambient"),
            "BGM_VOLUME":        app.config.get("BGM_VOLUME", 0.15),
            "BGM_FILES":         app.config.get("BGM_FILES", []),
            "WATERMARK_ENABLED": _Setting.get("watermark_enabled", "false") == "true",
            "WATERMARK_TEXT":    _Setting.get("watermark_text", ""),
            "WATERMARK_IMAGE":   _wm_path,
            "WATERMARK_OPACITY": float(_Setting.get("watermark_opacity", "0.35")),
            "VIDEOS_DIR":        app.config["VIDEOS_DIR"],
        }

    # Process jobs in batches of concurrent_videos until queue is empty
    while True:
        with app.app_context():
            # Atomically claim next batch
            jobs = (JobQueue.query
                    .filter_by(status="queued")
                    .order_by(JobQueue.priority, JobQueue.created_at)
                    .limit(concurrent_videos)
                    .all())
            if not jobs:
                break
            job_ids = []
            for job in jobs:
                job.status = "processing"
                job.started_at = datetime.now(timezone.utc)
                job_ids.append(job.id)
            db.session.commit()

        # Run this batch in parallel — each job in its own thread + app context
        with ThreadPoolExecutor(max_workers=len(job_ids)) as executor:
            futures = {
                executor.submit(_process_single_job, app, jid, config_dict, cores_per_video): jid
                for jid in job_ids
            }
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception:
                    pass  # errors are recorded inside _process_single_job


def _process_single_job(app, job_id, config_dict, frame_workers):
    """Process one video job in its own thread with its own SQLAlchemy session."""
    with app.app_context():
        job = db.session.get(JobQueue, job_id)
        if not job:
            return

        video = Video.query.filter_by(video_id=job.video_id).first()
        if not video:
            job.status = "failed"
            job.error_message = "Video record not found"
            db.session.commit()
            return

        video.status = "processing"
        db.session.commit()

        try:
            with open(video.json_path, "r", encoding="utf-8") as f:
                all_questions = json.load(f)

            question_data = next(
                (q for q in all_questions if q.get("id") == video.video_id), None
            )
            if not question_data:
                raise ValueError(f"Question {video.video_id} not found in JSON")

            output_dir = os.path.join(
                config_dict["VIDEOS_DIR"],
                video.subject,
                video.topic,
                video.subtopic or "general",
            )
            os.makedirs(output_dir, exist_ok=True)

            def progress_cb(stage, percent):
                job.stage = stage
                job.progress = percent
                video.progress = percent
                db.session.commit()

            pipeline = VideoPipeline(config_dict)
            result = pipeline.process_question(
                question_data=question_data,
                output_dir=output_dir,
                resolution=video.resolution,
                quality_preset=video.quality_preset,
                theme=video.theme,
                progress_callback=progress_cb,
                frame_workers=frame_workers,
            )

            video.video_path       = result.get("video_path", "")
            video.audio_path       = result.get("audio_path", "")
            video.thumbnail_path   = result.get("thumbnail_path", "")
            video.duration_seconds = result.get("duration", 0)
            video.status           = "completed"
            video.progress         = 100
            video.completed_at     = datetime.now(timezone.utc)
            job.status             = "completed"
            job.progress           = 100
            job.completed_at       = datetime.now(timezone.utc)
            db.session.commit()

        except Exception as e:
            video.status      = "failed"
            video.error_message = str(e)
            job.status        = "failed"
            job.error_message = str(e)
            job.completed_at  = datetime.now(timezone.utc)
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status  = "queued"
                video.status = "pending"
            db.session.commit()

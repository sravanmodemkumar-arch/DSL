import os
import json
import zipfile
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, render_template, request, current_app, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from models import db, Video, JobQueue
from engine.validator import validate_json
from engine.pipeline import VideoPipeline
from engine.hardware import detect_hardware, compute_allocation
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

    # Settings from form → DB Settings → config.py (in priority order)
    from models import Setting as _Setting
    resolution = request.form.get("resolution") or _Setting.get("default_resolution", current_app.config["DEFAULT_RESOLUTION"])
    quality = request.form.get("quality_preset") or _Setting.get("default_quality_preset", current_app.config["DEFAULT_QUALITY_PRESET"])
    theme = request.form.get("theme") or _Setting.get("default_theme", current_app.config["DEFAULT_THEME"])

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

    # Strip reference/documentation objects (have a top-level _DOC key)
    data = [q for q in data if not (isinstance(q, dict) and "_DOC" in q)]
    if not data:
        return '<div class="text-yellow-400 p-3">No processable questions found — file appears to be a reference schema only.</div>'

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

        # Each question gets its own directory named by question ID
        _output_dir = os.path.join(
            current_app.config["VIDEOS_DIR"],
            qid,
        )

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
            output_dir=_output_dir,
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


# ── Queue processor — trigger-based parallel with 70% utilization ─────────────
#
# Trigger points (all call _check_and_start_queued):
#   1. New upload          2. Job completed       3. Job failed
#   4. Job cancelled       5. Job deleted          6. Job retry
#   7. Server startup
#
# Each queued job gets its own thread. Cores are distributed dynamically:
#   total_active = currently processing + newly queued
#   cores_per_video = 70% of logical cores / total_active

_active_jobs = {}              # job_id -> thread, tracks running jobs
_active_lock = threading.Lock()
_cancelled_jobs = set()
_cancelled_lock = threading.Lock()


def _mark_cancelled(job_id):
    """Called by cancel/delete route to signal a running job to stop."""
    with _cancelled_lock:
        _cancelled_jobs.add(job_id)


def _is_cancelled(job_id):
    with _cancelled_lock:
        return job_id in _cancelled_jobs


def _clear_cancelled(job_id):
    with _cancelled_lock:
        _cancelled_jobs.discard(job_id)


def _get_config(app):
    """Build config dict — always reads live settings from DB so changes apply immediately."""
    with app.app_context():
        from config import THEMES
        from models import Setting as _Setting
        _wm_path = _Setting.get("watermark_image_path", app.config.get("WATERMARK_IMAGE", ""))
        return {
            "RESOLUTIONS":       app.config["RESOLUTIONS"],
            "QUALITY_PRESETS":   app.config["QUALITY_PRESETS"],
            "TTS_ENGINE":        _Setting.get("tts_engine",  app.config["TTS_ENGINE"]),
            "TTS_LANG":          _Setting.get("tts_lang",    app.config["TTS_LANG"]),
            "TTS_TLD":           _Setting.get("tts_tld",     app.config["TTS_TLD"]),
            "ASSETS_DIR":        app.config["ASSETS_DIR"],
            "THEMES":            THEMES,
            "BGM_ENABLED":       _Setting.get("bgm_enabled", str(app.config.get("BGM_ENABLED", True))).lower() in ("true", "1", "yes"),
            "BGM_STYLE":         _Setting.get("bgm_style",   app.config.get("BGM_STYLE", "ambient")),
            "BGM_VOLUME":        float(_Setting.get("bgm_volume", str(app.config.get("BGM_VOLUME", 0.08)))),
            "BGM_FILES":         app.config.get("BGM_FILES", []),
            "WATERMARK_ENABLED": _Setting.get("watermark_enabled", "false").lower() in ("true", "1", "yes"),
            "WATERMARK_TEXT":    _Setting.get("watermark_text", ""),
            "WATERMARK_IMAGE":   _wm_path,
            "WATERMARK_OPACITY": float(_Setting.get("watermark_opacity", "0.35")),
            "VIDEOS_DIR":        app.config["VIDEOS_DIR"],
        }


def _start_processing(app):
    """Single entry point — called from all 7 triggers."""
    _check_and_start_queued(app)


# Minimum cores per video to be effective (ProcessPoolExecutor overhead)
_MIN_CORES_PER_VIDEO = 3


def _check_and_start_queued(app):
    """Check for queued jobs and start as many as possible in parallel.

    Logic:
      total_workers = 70% of logical cores (e.g. 11 on 16-core)
      max_concurrent = total_workers // MIN_CORES_PER_VIDEO (e.g. 15//3 = 5)
      slots_free = max_concurrent - currently_active
      Start up to slots_free new jobs, each getting total_workers // total_active cores.

    Example on 16-core (15 workers):
      1 video  → 15 cores     5 videos → 3 cores each
      2 videos → 7 cores each   10 queued → 5 run now, 5 wait
    """
    config_dict = _get_config(app)
    alloc = compute_allocation()
    total_workers = alloc["frame_workers"]
    max_concurrent = max(1, total_workers // _MIN_CORES_PER_VIDEO)

    with app.app_context():
        # Clean up finished threads
        with _active_lock:
            done = [jid for jid, t in _active_jobs.items() if not t.is_alive()]
            for jid in done:
                del _active_jobs[jid]
            active_count = len(_active_jobs)

        slots_free = max(0, max_concurrent - active_count)
        if slots_free == 0:
            return

        # Claim only as many as we have slots for
        jobs = (JobQueue.query
                .filter_by(status="queued")
                .order_by(JobQueue.priority, JobQueue.created_at)
                .limit(slots_free)
                .all())
        if not jobs:
            return

        new_ids = []
        for job in jobs:
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            new_ids.append(job.id)
        db.session.commit()

    # Distribute cores across active + new
    total_active = active_count + len(new_ids)
    cores = max(_MIN_CORES_PER_VIDEO, total_workers // max(1, total_active))

    print(f"[Queue] {len(new_ids)} new + {active_count} active "
          f"= {total_active} videos x {cores} cores "
          f"(total {total_workers} @ 70%, max {max_concurrent} concurrent)")

    for jid in new_ids:
        t = threading.Thread(
            target=_process_single_job,
            args=(app, jid, config_dict, cores),
            daemon=True,
        )
        with _active_lock:
            _active_jobs[jid] = t
        t.start()


def _job_finished(app, job_id):
    """Called when a job completes/fails/cancels — clean up and trigger next."""
    with _active_lock:
        _active_jobs.pop(job_id, None)
    # Trigger: pick up any newly queued jobs
    _check_and_start_queued(app)


def _process_single_job(app, job_id, config_dict, frame_workers):
    """Process one video job in its own thread."""
    with app.app_context():
        job = db.session.get(JobQueue, job_id)
        if not job or _is_cancelled(job_id):
            _clear_cancelled(job_id)
            _job_finished(app, job_id)
            return

        video = Video.query.filter_by(video_id=job.video_id).first()
        if not video:
            job.status = "failed"
            job.error_message = "Video record not found"
            db.session.commit()
            _job_finished(app, job_id)
            return

        # Save plain string ID early — avoids SQLAlchemy lazy-reload crashes in except blocks
        video_id = job.video_id
        json_path = video.json_path
        output_dir = video.output_dir or os.path.join(
            config_dict["VIDEOS_DIR"],
            video.subject,
            video.topic or "general",
            video.subtopic or "general",
        )
        resolution = video.resolution
        quality_preset = video.quality_preset
        theme = video.theme

        video.status = "processing"
        db.session.commit()
        print(f"[Video] START {video_id} ({frame_workers} cores)")

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                all_questions = json.load(f)

            question_data = next(
                (q for q in all_questions if q.get("id") == video_id), None
            )
            if not question_data:
                raise ValueError(f"Question {video_id} not found in JSON")

            os.makedirs(output_dir, exist_ok=True)

            def progress_cb(stage, percent):
                if _is_cancelled(job_id):
                    raise InterruptedError("Job cancelled by user")
                try:
                    j = db.session.get(JobQueue, job_id)
                    v = Video.query.filter_by(video_id=video_id).first()
                    if j:
                        j.stage = stage
                        j.progress = percent
                    if v:
                        v.progress = percent
                    db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass

            pipeline = VideoPipeline(config_dict)
            result = pipeline.process_question(
                question_data=question_data,
                output_dir=output_dir,
                resolution=resolution,
                quality_preset=quality_preset,
                theme=theme,
                progress_callback=progress_cb,
                frame_workers=frame_workers,
            )

            if _is_cancelled(job_id):
                raise InterruptedError("Job cancelled by user")

            print(f"[Video] DONE  {video_id} ({result.get('duration', 0):.1f}s)")
            db.session.expire_all()
            job = db.session.get(JobQueue, job_id)
            video = Video.query.filter_by(video_id=video_id).first()
            if video:
                video.video_path       = result.get("video_path", "")
                video.audio_path       = result.get("audio_path", "")
                video.thumbnail_path   = result.get("thumbnail_path", "")
                video.duration_seconds = result.get("duration", 0)
                video.status           = "completed"
                video.progress         = 100
                video.completed_at     = datetime.now(timezone.utc)
            if job:
                job.status             = "completed"
                job.progress           = 100
                job.completed_at       = datetime.now(timezone.utc)
            db.session.commit()

            _cleanup_after_success()

        except InterruptedError:
            print(f"[Video] CANCELLED {video_id}")
            _clear_cancelled(job_id)
            db.session.expire_all()
            job = db.session.get(JobQueue, job_id)
            video_check = Video.query.filter_by(video_id=video_id).first()
            if job:
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
            if video_check:
                video_check.status = "failed"
                video_check.error_message = "Cancelled by user"
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        except Exception as e:
            _clear_cancelled(job_id)
            print(f"[Video] FAIL  {video_id}: {e}")
            db.session.expire_all()
            job = db.session.get(JobQueue, job_id)
            video_obj = Video.query.filter_by(video_id=video_id).first()
            if video_obj:
                video_obj.status = "failed"
                video_obj.error_message = str(e)
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = "queued"
                    if video_obj:
                        video_obj.status = "pending"
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        # Trigger: job done, check for more queued work
        _job_finished(app, job_id)


def _cleanup_after_success():
    """Clean logs and temp files after successful video render to free memory/disk."""
    project_root = os.path.dirname(os.path.dirname(__file__))

    # 1. Truncate server.log (clear all request/debug logs)
    for log_name in ("server.log", "server.log.1"):
        log_path = os.path.join(project_root, log_name)
        try:
            if os.path.exists(log_path):
                with open(log_path, "w") as f:
                    f.truncate(0)
        except Exception:
            pass

    # 2. Clear Python __pycache__ dirs to free memory
    for dirpath, dirnames, _filenames in os.walk(project_root):
        for d in dirnames:
            if d == "__pycache__":
                cache_path = os.path.join(dirpath, d)
                try:
                    import shutil
                    shutil.rmtree(cache_path, ignore_errors=True)
                except Exception:
                    pass

    # 3. Clear any leftover temp frame/audio dirs
    storage_dir = os.path.join(project_root, "storage")
    for entry in os.listdir(storage_dir) if os.path.isdir(storage_dir) else []:
        full = os.path.join(storage_dir, entry)
        if os.path.isdir(full) and (entry.startswith("frames_") or entry.startswith("audio_")):
            try:
                import shutil
                shutil.rmtree(full, ignore_errors=True)
            except Exception:
                pass

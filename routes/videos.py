import os
from flask import Blueprint, render_template, request, current_app, send_file, abort
from models import db, Video

videos_bp = Blueprint("videos", __name__)


@videos_bp.route("/")
def library():
    page = request.args.get("page", 1, type=int)
    per_page = 12
    subject = request.args.get("subject", "")
    topic = request.args.get("topic", "")
    subtopic = request.args.get("subtopic", "")
    difficulty = request.args.get("difficulty", "")
    status = request.args.get("status", "")
    search = request.args.get("search", "")
    sort = request.args.get("sort", "newest")

    query = Video.query

    if subject:
        query = query.filter(Video.subject == subject)
    if topic:
        query = query.filter(Video.topic == topic)
    if subtopic:
        query = query.filter(Video.subtopic == subtopic)
    if difficulty:
        query = query.filter(Video.difficulty == difficulty)
    if status:
        query = query.filter(Video.status == status)
    if search:
        query = query.filter(
            (Video.title.ilike(f"%{search}%")) |
            (Video.video_id.ilike(f"%{search}%")) |
            (Video.subject.ilike(f"%{search}%")) |
            (Video.topic.ilike(f"%{search}%"))
        )

    if sort == "newest":
        query = query.order_by(Video.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Video.created_at.asc())
    elif sort == "subject":
        query = query.order_by(Video.subject, Video.topic, Video.subtopic)
    elif sort == "duration":
        query = query.order_by(Video.duration_seconds.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get filter options
    subjects = [r[0] for r in db.session.query(Video.subject).distinct().all() if r[0]]
    topics = [r[0] for r in db.session.query(Video.topic).distinct().all() if r[0]]

    return render_template(
        "library.html",
        videos=pagination.items,
        pagination=pagination,
        subjects=subjects,
        topics=topics,
        filters={
            "subject": subject,
            "topic": topic,
            "subtopic": subtopic,
            "difficulty": difficulty,
            "status": status,
            "search": search,
            "sort": sort,
        },
    )


@videos_bp.route("/list")
def list_partial():
    """HTMX partial — returns just the video grid for filtering."""
    page = request.args.get("page", 1, type=int)
    per_page = 12
    subject = request.args.get("subject", "")
    topic = request.args.get("topic", "")
    difficulty = request.args.get("difficulty", "")
    status = request.args.get("status", "")
    search = request.args.get("search", "")
    sort = request.args.get("sort", "newest")

    query = Video.query
    if subject:
        query = query.filter(Video.subject == subject)
    if topic:
        query = query.filter(Video.topic == topic)
    if difficulty:
        query = query.filter(Video.difficulty == difficulty)
    if status:
        query = query.filter(Video.status == status)
    if search:
        query = query.filter(
            (Video.title.ilike(f"%{search}%")) |
            (Video.video_id.ilike(f"%{search}%"))
        )

    if sort == "newest":
        query = query.order_by(Video.created_at.desc())
    elif sort == "subject":
        query = query.order_by(Video.subject, Video.topic)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "components/video_grid.html",
        videos=pagination.items,
        pagination=pagination,
    )


@videos_bp.route("/<video_id>")
def detail(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    return render_template("video_detail.html", video=video)


@videos_bp.route("/<video_id>/download")
def download(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    if not video.video_path or not os.path.exists(video.video_path):
        abort(404, "Video file not found")
    return send_file(video.video_path, as_attachment=True, download_name=f"{video_id}.mp4")


@videos_bp.route("/<video_id>/preview")
def preview(video_id):
    """Generate a quick preview — render 5 key frames from the JSON."""
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    return render_template("preview.html", video=video)


@videos_bp.route("/<video_id>/preview-frames")
def preview_frames(video_id):
    """HTMX endpoint — generate and return preview frame images."""
    import json
    import base64
    import io
    from engine.renderer import FrameRenderer
    from engine.sync import get_active_state, build_timeline
    from config import THEMES

    video = Video.query.filter_by(video_id=video_id).first_or_404()
    if not video.json_path or not os.path.exists(video.json_path):
        return '<div class="text-red-400 p-3">JSON file not found</div>'

    with open(video.json_path, "r", encoding="utf-8") as f:
        all_q = json.load(f)

    question = None
    for q in all_q:
        if q.get("id") == video.video_id:
            question = q
            break
    if not question:
        return '<div class="text-red-400 p-3">Question not found in JSON</div>'

    # Build a fake timeline with estimated durations
    scenes = question.get("scenes", [])
    fake_timeline = []
    t = 0.0
    for si, scene in enumerate(scenes):
        if scene.get("audio") or scene.get("render"):
            fake_timeline.append({
                "start": t, "end": t + 3.0,
                "scene_index": si, "scene_type": scene.get("type", ""),
                "step_index": None, "render": scene.get("render", {}),
                "text": scene.get("text", ""), "audio_text": scene.get("audio", ""),
            })
            t += 3.5
        for sti, step in enumerate(scene.get("steps", [])):
            fake_timeline.append({
                "start": t, "end": t + 3.0,
                "scene_index": si, "scene_type": scene.get("type", ""),
                "step_index": sti, "render": step.get("render", {}),
                "text": step.get("text", ""), "audio_text": step.get("audio", ""),
            })
            t += 3.5

    if not fake_timeline:
        return '<div class="text-gray-500 p-3">No renderable content</div>'

    # Pick 5 evenly spaced frames
    theme_colors = THEMES.get(video.theme or "dark", THEMES["dark"])
    renderer = FrameRenderer(width=960, height=540, theme=theme_colors)
    question["_height"] = 540

    total = fake_timeline[-1]["end"]
    frame_times = [total * i / 5 + 0.5 for i in range(5)]

    html = '<div class="grid grid-cols-1 md:grid-cols-5 gap-3">'
    for idx, ft in enumerate(frame_times):
        state = get_active_state(fake_timeline, ft, question)
        frame = renderer.render_frame(state)

        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        # Find what step this is
        label = ""
        for entry in fake_timeline:
            if entry["start"] <= ft <= entry["end"]:
                label = entry.get("text", entry.get("scene_type", ""))
                break

        html += f'''
        <div class="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
            <img src="data:image/png;base64,{b64}" class="w-full aspect-video" alt="Frame {idx+1}">
            <p class="text-xs text-gray-400 p-2 truncate">{label}</p>
        </div>
        '''
    html += '</div>'
    return html


@videos_bp.route("/<video_id>/stream")
def stream(video_id):
    """Stream video file for in-browser playback with Range request support."""
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    if not video.video_path or not os.path.exists(video.video_path):
        abort(404, "Video file not found")
    return send_file(video.video_path, mimetype="video/mp4", conditional=True)


@videos_bp.route("/<video_id>/thumbnail")
def thumbnail(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    if video.thumbnail_path and os.path.exists(video.thumbnail_path):
        return send_file(video.thumbnail_path, mimetype="image/png")
    abort(404)


@videos_bp.route("/<video_id>/delete", methods=["DELETE"])
def delete(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()

    from models import JobQueue
    from routes.queue_routes import _cleanup_video_files
    JobQueue.query.filter_by(video_id=video_id).delete()
    _cleanup_video_files(video)

    db.session.delete(video)
    db.session.commit()

    return ""


@videos_bp.route("/<video_id>/clean-temp", methods=["POST"])
def clean_temp(video_id):
    """Delete intermediate files (audio segments, raw audio, BGM) — keep video + thumbnail."""
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    if video.status != "completed" or not video.video_path:
        return '<div class="text-yellow-400 p-2 text-sm">Video not completed — nothing cleaned</div>'

    output_dir = os.path.dirname(video.video_path)
    freed = _clean_temp_files(video_id, output_dir)
    return f'<div class="text-green-400 p-2 text-sm">Cleaned — {freed} temp files removed</div>'


@videos_bp.route("/clean-all-temp", methods=["POST"])
def clean_all_temp():
    """Delete intermediate files for ALL completed videos."""
    completed = Video.query.filter_by(status="completed").all()
    total_freed = 0
    for video in completed:
        if video.video_path and os.path.exists(video.video_path):
            output_dir = os.path.dirname(video.video_path)
            total_freed += _clean_temp_files(video.video_id, output_dir)
    return f'<div class="text-green-400 p-3 text-sm">Done — {total_freed} temp files removed across {len(completed)} videos</div>'


def _clean_temp_files(qid, output_dir):
    """Remove audio segments, raw audio, BGM wav, mixed audio from output_dir. Returns count removed."""
    import shutil
    removed = 0

    # Audio segments directory
    audio_dir = os.path.join(output_dir, "audio")
    if os.path.isdir(audio_dir):
        shutil.rmtree(audio_dir, ignore_errors=True)
        removed += 1

    # Intermediate audio files
    for suffix in (f"{qid}_audio.mp3", f"{qid}_bgm.wav", f"{qid}_mixed.mp3"):
        path = os.path.join(output_dir, suffix)
        if os.path.exists(path):
            os.remove(path)
            removed += 1

    return removed


@videos_bp.route("/completed-ids")
def completed_ids():
    """Return list of completed video IDs for bulk download."""
    from flask import jsonify
    videos = Video.query.filter_by(status="completed").all()
    ids = [v.video_id for v in videos if v.video_path and os.path.exists(v.video_path)]
    return jsonify(ids)


@videos_bp.route("/<video_id>/retry", methods=["POST"])
def retry(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    video.status = "pending"
    video.progress = 0
    video.error_message = ""
    video.output_dir = os.path.join(
        current_app.config["VIDEOS_DIR"],
        video_id,
    )

    # Apply current settings so changed resolution/quality take effect
    from models import JobQueue, Setting
    video.resolution = Setting.get("default_resolution", current_app.config["DEFAULT_RESOLUTION"])
    video.quality_preset = Setting.get("default_quality_preset", current_app.config["DEFAULT_QUALITY_PRESET"])
    video.theme = Setting.get("default_theme", current_app.config["DEFAULT_THEME"])

    job = JobQueue(video_id=video_id, priority=2, status="queued")
    db.session.add(job)
    db.session.commit()

    # Trigger processing
    from routes.upload import _start_processing
    _start_processing(current_app._get_current_object())

    return '<div class="text-green-400 p-2">Re-queued for processing</div>'

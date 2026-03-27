import os
import json
from flask import Blueprint, render_template, request, current_app, redirect, url_for, session
from models import db, Video

youtube_bp = Blueprint("youtube", __name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "youtube_token.json")


def _token_path():
    return os.path.join(current_app.root_path, "youtube_token.json")


def _secrets_path():
    return current_app.config.get("YOUTUBE_CLIENT_SECRETS",
                                  os.path.join(current_app.root_path, "client_secrets.json"))


def _has_secrets():
    return os.path.exists(_secrets_path())


def _has_token():
    return os.path.exists(_token_path())


def _get_credentials():
    """Load saved credentials, refresh if expired. Returns creds or None."""
    if not _has_token():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(_token_path(), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(_token_path(), "w") as f:
                f.write(creds.to_json())
        return creds if creds and creds.valid else None
    except Exception:
        return None


@youtube_bp.route("/")
def index():
    videos = Video.query.filter_by(status="completed").order_by(Video.created_at.desc()).all()
    uploaded = Video.query.filter_by(youtube_status="published").count()
    not_uploaded = Video.query.filter(
        Video.status == "completed",
        Video.youtube_status == "not_uploaded"
    ).count()

    auth_status = {
        "has_secrets": _has_secrets(),
        "has_token": _has_token(),
        "connected": _get_credentials() is not None,
    }

    return render_template(
        "youtube.html",
        videos=videos,
        uploaded=uploaded,
        not_uploaded=not_uploaded,
        auth=auth_status,
    )


# ── OAuth flow ────────────────────────────────────────────────────────────────

@youtube_bp.route("/auth")
def auth():
    """Start OAuth flow — redirect user to Google consent page."""
    if not _has_secrets():
        return redirect(url_for("youtube.index") + "?error=no_secrets")

    import os as _os
    _os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    try:
        import json as _json
        from requests_oauthlib import OAuth2Session
        from models import Setting

        saved_uri = Setting.get("youtube_redirect_uri", "").strip()
        redirect_uri = saved_uri if saved_uri else "http://127.0.0.1:5000/youtube/oauth-callback"

        secrets = _json.load(open(_secrets_path()))
        cfg = secrets.get("web") or secrets.get("installed")
        client_id = cfg["client_id"]

        oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=SCOPES)
        auth_url, state = oauth.authorization_url(
            cfg.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            access_type="offline",
            prompt="consent",
        )
        session["oauth_state"] = state
        session["oauth_redirect_uri"] = redirect_uri
        return redirect(auth_url)
    except Exception as e:
        return redirect(url_for("youtube.index") + f"?error={e}")


@youtube_bp.route("/oauth-callback")
def oauth_callback():
    """Handle Google OAuth callback — exchange code for token and save."""
    import os as _os
    _os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    error = request.args.get("error")
    if error:
        return redirect(url_for("youtube.index") + f"?error={error}")

    try:
        import json as _json
        from requests_oauthlib import OAuth2Session
        from google.oauth2.credentials import Credentials

        redirect_uri = session.get("oauth_redirect_uri", "http://127.0.0.1:5000/youtube/oauth-callback")
        secrets = _json.load(open(_secrets_path()))
        cfg = secrets.get("web") or secrets.get("installed")
        client_id     = cfg["client_id"]
        client_secret = cfg["client_secret"]
        token_uri     = cfg.get("token_uri", "https://oauth2.googleapis.com/token")

        oauth = OAuth2Session(client_id, redirect_uri=redirect_uri,
                              scope=SCOPES, state=session.get("oauth_state"))
        token = oauth.fetch_token(
            token_uri,
            authorization_response=request.url.replace("http://", "http://"),
            client_secret=client_secret,
            include_client_id=True,
        )

        creds = Credentials(
            token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        with open(_token_path(), "w") as f:
            f.write(creds.to_json())
        return redirect(url_for("youtube.index") + "?connected=1")
    except Exception as e:
        return redirect(url_for("youtube.index") + f"?error={e}")


@youtube_bp.route("/disconnect", methods=["POST"])
def disconnect():
    """Remove saved token — disconnect YouTube account."""
    token = _token_path()
    if os.path.exists(token):
        os.remove(token)
    return redirect(url_for("youtube.index"))


# ── Upload ────────────────────────────────────────────────────────────────────

@youtube_bp.route("/upload/<video_id>", methods=["POST"])
def upload_video(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()

    if not video.video_path or not os.path.exists(video.video_path):
        return '<div class="text-red-400 p-2">Video file not found</div>'

    creds = _get_credentials()
    if not creds:
        return '<div class="text-yellow-400 p-2 text-sm">YouTube not connected. Click "Connect YouTube Account" first.</div>'

    try:
        video.youtube_status = "uploading"
        db.session.commit()

        title, description, tags = _build_metadata(video)
        yt_cfg = _get_yt_upload_config(video)

        yt_id = _upload_to_youtube(
            video.video_path, title, description, tags, creds,
            privacy=yt_cfg["privacy"],
            category=yt_cfg["category"],
            language=yt_cfg["language"],
            license=yt_cfg["license"],
            made_for_kids=yt_cfg["made_for_kids"],
        )

        if yt_id:
            video.youtube_video_id = yt_id
            video.youtube_url = f"https://www.youtube.com/watch?v={yt_id}"
            video.youtube_status = "published"
            # Add to playlist if specified
            playlist_id = yt_cfg.get("playlist_id", "")
            if playlist_id:
                _add_to_playlist(yt_id, playlist_id, creds)
        else:
            video.youtube_status = "failed"

        db.session.commit()
        return render_template("components/youtube_status.html", video=video)

    except Exception as e:
        video.youtube_status = "failed"
        db.session.commit()
        return f'<div class="text-red-400 p-2 text-sm">Upload failed: {e}</div>'


@youtube_bp.route("/bulk-upload", methods=["POST"])
def bulk_upload():
    creds = _get_credentials()
    if not creds:
        return '<div class="text-yellow-400 p-3 text-sm">YouTube not connected. Connect account first.</div>'

    videos = Video.query.filter(
        Video.status == "completed",
        Video.youtube_status == "not_uploaded"
    ).all()

    results = {"success": 0, "failed": 0}
    for video in videos:
        try:
            video.youtube_status = "uploading"
            db.session.commit()
            title, description, tags = _build_metadata(video)
            yt_cfg = _get_yt_upload_config(video)
            yt_id = _upload_to_youtube(
                video.video_path, title, description, tags, creds,
                privacy=yt_cfg["privacy"],
                category=yt_cfg["category"],
                language=yt_cfg["language"],
                license=yt_cfg["license"],
                made_for_kids=yt_cfg["made_for_kids"],
            )
            if yt_id:
                video.youtube_video_id = yt_id
                video.youtube_url = f"https://www.youtube.com/watch?v={yt_id}"
                video.youtube_status = "published"
                playlist_id = yt_cfg.get("playlist_id", "")
                if playlist_id:
                    _add_to_playlist(yt_id, playlist_id, creds)
                results["success"] += 1
            else:
                video.youtube_status = "failed"
                results["failed"] += 1
        except Exception:
            video.youtube_status = "failed"
            results["failed"] += 1
        db.session.commit()

    return f'<div class="text-green-400 p-3 text-sm">Done: {results["success"]} uploaded, {results["failed"]} failed</div>'


@youtube_bp.route("/update-url/<video_id>", methods=["POST"])
def update_url(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    url = request.form.get("youtube_url", "").strip()
    if url:
        video.youtube_url = url
        video.youtube_status = "published"
        if "v=" in url:
            video.youtube_video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video.youtube_video_id = url.split("youtu.be/")[1].split("?")[0]
    else:
        video.youtube_url = ""
        video.youtube_video_id = ""
        video.youtube_status = "not_uploaded"
    db.session.commit()
    return render_template("components/youtube_status.html", video=video)


# ── Internal ──────────────────────────────────────────────────────────────────

def _build_metadata(video):
    """Build YouTube title, description and tags for a video.

    Priority order:
      1. youtube block inside the video's JSON file (explicit override)
      2. Auto-generated from meta/thumbnail/question fields in the JSON
      3. Fallback from Video model fields (subject, topic, exam_tags, etc.)
    """
    import json as _json

    # ── Load question JSON ────────────────────────────────────────────────────
    yt_block = {}
    q_data = {}
    if video.json_path and os.path.exists(video.json_path):
        try:
            with open(video.json_path, "r", encoding="utf-8") as f:
                all_q = _json.load(f)
            for q in all_q:
                if q.get("id") == video.video_id:
                    q_data = q
                    yt_block = q.get("youtube", {})
                    break
        except Exception:
            pass

    meta      = q_data.get("meta", {})
    thumbnail = q_data.get("thumbnail", {})
    question  = q_data.get("question", {})

    # ── Helper: exam list ─────────────────────────────────────────────────────
    raw_exam = meta.get("exam", video.exam_tags or "")
    if isinstance(raw_exam, list):
        exam_list = raw_exam
    else:
        exam_list = [p.strip() for p in raw_exam.replace("/", ",").split(",") if p.strip()]

    grade_str   = meta.get("grade", video.grade_tags or "")
    subject     = meta.get("subject", video.subject or "")
    topic       = meta.get("topic", video.topic or "")
    subtopic    = meta.get("subtopic", video.subtopic or "")
    difficulty  = meta.get("difficulty", video.difficulty or "medium")

    # ── TITLE ─────────────────────────────────────────────────────────────────
    if yt_block.get("title"):
        title = yt_block["title"][:100]
    else:
        # Auto-generate: "Topic — Subtopic | Difficulty | Exam | Subject"
        parts = [p for p in [topic, subtopic] if p]
        topic_str = " — ".join(parts) if parts else subject
        exam_str  = " | " + exam_list[0] if exam_list else ""
        diff_str  = f" | {difficulty.capitalize()}" if difficulty else ""
        title = f"{topic_str}{diff_str}{exam_str}"[:95]
        if subject and subject.lower() not in title.lower():
            title = f"{title} | {subject}"
        title = title[:100]

    # ── DESCRIPTION ───────────────────────────────────────────────────────────
    if yt_block.get("description"):
        # Use JSON description, append hashtags at the end
        raw_desc = yt_block["description"]
        ht_list  = yt_block.get("hashtags", [])
        if ht_list:
            raw_desc = raw_desc.rstrip() + "\n\n" + " ".join(ht_list)
        description = raw_desc[:5000]
    else:
        # Auto-generate rich description
        duration_str = ""
        if video.duration_seconds:
            m, s = int(video.duration_seconds) // 60, int(video.duration_seconds) % 60
            duration_str = f"{m}:{s:02d} min"

        q_text  = question.get("text", video.title or "")
        th_sub  = thumbnail.get("subtitle", "")
        exam_ln = ", ".join(exam_list) if exam_list else ""

        desc_lines = [
            f"📚 {q_text}",
            "",
        ]
        if th_sub:
            desc_lines += [th_sub, ""]

        desc_lines += [
            f"In this video we cover {topic or subject} from {subject}.",
            "Clear step-by-step explanation designed for exam preparation.",
            "",
            "─────────────────────────────",
            "📌 VIDEO DETAILS",
            "─────────────────────────────",
            f"Subject   : {subject}",
        ]
        if topic:
            desc_lines.append(f"Topic     : {topic}")
        if subtopic:
            desc_lines.append(f"Subtopic  : {subtopic}")
        desc_lines.append(f"Difficulty: {difficulty.capitalize() if difficulty else 'N/A'}")
        if duration_str:
            desc_lines.append(f"Duration  : {duration_str}")
        if exam_ln:
            desc_lines += ["", "─────────────────────────────",
                           "🎯 FOR EXAMS", "─────────────────────────────", exam_ln]
        if grade_str:
            desc_lines += ["", f"🎓 Grade / Level: {grade_str}"]
        desc_lines += [
            "",
            "─────────────────────────────",
            "🔔 SUBSCRIBE for daily exam shortcuts, concept videos & solved questions.",
            "👍 LIKE if this helped you!",
            "💬 COMMENT your doubts below.",
            "─────────────────────────────",
            "",
        ]
        # Auto hashtags
        auto_tags = [f"#{subject.replace(' ', '')}", f"#{topic.replace(' ', '')}"]
        for ex in exam_list[:3]:
            auto_tags.append(f"#{''.join(ex.split())}")
        auto_tags += ["#Education", "#ExamPreparation", "#StudyWithMe", "#MathsShortcut"]
        desc_lines.append(" ".join(dict.fromkeys(auto_tags)))

        description = "\n".join(desc_lines)[:5000]

    # ── TAGS ──────────────────────────────────────────────────────────────────
    if yt_block.get("tags"):
        # JSON tags merged with core subject/topic for discoverability
        base = [subject, topic, subtopic]
        tags = list(dict.fromkeys(yt_block["tags"] + [t for t in base if t]))[:30]
    else:
        raw_tags = (
            [subject, topic, subtopic, difficulty,
             "education", "exam preparation", "study tips", "shortcut"]
            + exam_list
            + ([grade_str] if grade_str else [])
        )
        tags = list(dict.fromkeys(t for t in raw_tags if t))[:30]

    return title, description, tags


def _get_yt_upload_config(video):
    """Read upload config from JSON youtube block, fall back to settings defaults."""
    import json as _json
    from models import Setting

    yt_block = {}
    if video.json_path and os.path.exists(video.json_path):
        try:
            with open(video.json_path, "r", encoding="utf-8") as f:
                all_q = _json.load(f)
            for q in all_q:
                if q.get("id") == video.video_id:
                    yt_block = q.get("youtube", {})
                    break
        except Exception:
            pass

    return {
        "privacy":       yt_block.get("privacy")       or Setting.get("youtube_default_privacy", "public"),
        "category":      yt_block.get("category")      or Setting.get("youtube_default_category", "27"),
        "language":      yt_block.get("language")      or Setting.get("youtube_language", "en"),
        "license":       yt_block.get("license")       or Setting.get("youtube_license", "youtube"),
        "made_for_kids": yt_block.get("made_for_kids", None),
        "playlist_id":   yt_block.get("playlist_id")   or Setting.get("youtube_playlist_id", ""),
    }


def _upload_to_youtube(video_path, title, description, tags, creds,
                       privacy="public", category="27", language="en",
                       license="youtube", made_for_kids=False):
    """Upload video using pre-authorized credentials. Returns YouTube video ID or None."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        youtube = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": str(category),
                "defaultLanguage": language or "en",
            },
            "status": {
                "privacyStatus": privacy or "public",
                "license": license or "youtube",
                "selfDeclaredMadeForKids": bool(made_for_kids),
            },
        }
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True,
                                chunksize=10 * 1024 * 1024)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = req.next_chunk()
        return response.get("id")
    except Exception:
        return None


def _add_to_playlist(video_id, playlist_id, creds):
    """Add an uploaded video to a YouTube playlist. Silently ignores errors."""
    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", credentials=creds)
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
    except Exception:
        pass

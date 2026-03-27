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

        title = f"{video.subject} - {video.topic}: {video.title[:80]}"
        description = (
            f"Subject: {video.subject}\n"
            f"Topic: {video.topic}\n"
            f"Subtopic: {video.subtopic}\n"
            f"Difficulty: {video.difficulty}\n\n"
            f"Generated by STEM Video Generation System"
        )
        tags = [t for t in [video.subject, video.topic, video.subtopic, video.difficulty,
                             "education", "STEM"] if t]

        yt_id = _upload_to_youtube(video.video_path, title, description, tags, creds)

        if yt_id:
            video.youtube_video_id = yt_id
            video.youtube_url = f"https://www.youtube.com/watch?v={yt_id}"
            video.youtube_status = "published"
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
            title = f"{video.subject} - {video.topic}: {video.title[:80]}"
            description = f"Subject: {video.subject}\nTopic: {video.topic}\n"
            tags = [t for t in [video.subject, video.topic, "education", "STEM"] if t]
            yt_id = _upload_to_youtube(video.video_path, title, description, tags, creds)
            if yt_id:
                video.youtube_video_id = yt_id
                video.youtube_url = f"https://www.youtube.com/watch?v={yt_id}"
                video.youtube_status = "published"
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

def _upload_to_youtube(video_path, title, description, tags, creds):
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
                "categoryId": "27",
            },
            "status": {"privacyStatus": "public"},
        }
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = req.execute()
        return response.get("id")
    except Exception:
        return None

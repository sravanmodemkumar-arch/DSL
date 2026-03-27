"""Asset management — upload images, SVGs, videos for use in JSON renders."""

import os
from flask import Blueprint, render_template, request, current_app, jsonify, send_from_directory
from werkzeug.utils import secure_filename

assets_bp = Blueprint("assets", __name__)

ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ALLOWED_SVG   = {".svg"}
ALLOWED_VIDEO = {".mp4", ".webm", ".mov", ".avi"}
ALL_ALLOWED   = ALLOWED_IMAGE | ALLOWED_SVG | ALLOWED_VIDEO


def _asset_dir(kind, subject=""):
    base = os.path.join(current_app.config["ASSETS_DIR"], kind)
    if subject:
        base = os.path.join(base, secure_filename(subject))
    os.makedirs(base, exist_ok=True)
    return base


def _categorize(ext):
    if ext in ALLOWED_IMAGE:  return "images"
    if ext in ALLOWED_SVG:    return "svgs"
    if ext in ALLOWED_VIDEO:  return "videos"
    return None


@assets_bp.route("/")
def index():
    """Asset manager main page."""
    assets_dir = current_app.config["ASSETS_DIR"]
    tree = {}
    for kind in ("images", "svgs", "videos"):
        kind_dir = os.path.join(assets_dir, kind)
        os.makedirs(kind_dir, exist_ok=True)
        tree[kind] = []
        for root, dirs, files in os.walk(kind_dir):
            for f in sorted(files):
                fpath = os.path.join(root, f)
                rel   = os.path.relpath(fpath, assets_dir).replace("\\", "/")
                tree[kind].append({
                    "name":    f,
                    "rel":     rel,
                    "key":     os.path.splitext(f)[0],
                    "size":    os.path.getsize(fpath),
                    "subdir":  os.path.relpath(root, kind_dir) if root != kind_dir else "",
                })
    return render_template("assets.html", tree=tree)


@assets_bp.route("/upload", methods=["POST"])
def upload():
    """Upload one or more asset files."""
    subject = request.form.get("subject", "").strip()
    files   = request.files.getlist("files")
    results = []

    for f in files:
        if not f or not f.filename:
            continue
        fname = secure_filename(f.filename)
        ext   = os.path.splitext(fname)[1].lower()
        kind  = _categorize(ext)
        if not kind:
            results.append({"file": fname, "ok": False, "msg": "Unsupported file type"})
            continue
        dest_dir = _asset_dir(kind, subject)
        dest     = os.path.join(dest_dir, fname)
        f.save(dest)
        rel = os.path.relpath(dest, current_app.config["ASSETS_DIR"]).replace("\\", "/")
        results.append({"file": fname, "ok": True, "kind": kind, "rel": rel,
                        "key": os.path.splitext(fname)[0]})

    ok_count = sum(1 for r in results if r["ok"])
    html = f'<div class="text-green-400 p-3">{ok_count} file(s) uploaded.</div>'
    html += '<div class="text-xs text-gray-400 mt-1 space-y-1">'
    for r in results:
        if r["ok"]:
            html += f'<div>&#10003; {r["file"]} &rarr; <code>{r["rel"]}</code> (key: <b>{r["key"]}</b>)</div>'
        else:
            html += f'<div class="text-red-400">&#10007; {r["file"]}: {r["msg"]}</div>'
    html += '</div>'
    return html


@assets_bp.route("/delete", methods=["POST"])
def delete():
    """Delete an asset by relative path."""
    rel  = request.form.get("rel", "")
    if not rel or ".." in rel:
        return '<div class="text-red-400 p-2 text-sm">Invalid path.</div>'
    full = os.path.join(current_app.config["ASSETS_DIR"], rel)
    if os.path.isfile(full):
        os.remove(full)
        return f'<div class="text-yellow-400 p-2 text-sm">Deleted: {rel}</div>'
    return '<div class="text-red-400 p-2 text-sm">File not found.</div>'


@assets_bp.route("/list")
def list_assets():
    """JSON API — list all assets (for JSON editor autocomplete)."""
    assets_dir = current_app.config["ASSETS_DIR"]
    out = {"images": {}, "svgs": {}, "videos": {}}
    for kind in out:
        kind_dir = os.path.join(assets_dir, kind)
        if not os.path.isdir(kind_dir):
            continue
        for root, dirs, files in os.walk(kind_dir):
            for f in files:
                key = os.path.splitext(f)[0]
                rel = os.path.relpath(
                    os.path.join(root, f), kind_dir).replace("\\", "/")
                out[kind][key] = rel
    return jsonify(out)

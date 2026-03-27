import os
import io
from datetime import datetime
from flask import Blueprint, render_template, request, current_app, send_file
from models import db, Video

export_bp = Blueprint("export", __name__)


@export_bp.route("/")
def index():
    subjects = [r[0] for r in db.session.query(Video.subject).distinct().all() if r[0]]
    topics = [r[0] for r in db.session.query(Video.topic).distinct().all() if r[0]]
    total = Video.query.filter_by(status="completed").count()
    return render_template("export.html", subjects=subjects, topics=topics, total=total)


@export_bp.route("/download", methods=["POST"])
def download():
    """Generate and download Excel file."""
    export_type = request.form.get("export_type", "master")
    subject_filter = request.form.get("subject", "")
    status_filter = request.form.get("status", "completed")
    fmt = request.form.get("format", "xlsx")

    query = Video.query
    if status_filter:
        query = query.filter(Video.status == status_filter)
    if subject_filter:
        query = query.filter(Video.subject == subject_filter)

    videos = query.order_by(Video.subject, Video.topic, Video.subtopic).all()

    if fmt == "csv":
        return _generate_csv(videos, export_type)
    else:
        return _generate_excel(videos, export_type)


def _generate_excel(videos, export_type):
    """Generate Excel workbook with multiple sheets."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="0066CC", end_color="0066CC", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    def col_letter(col_num):
        """Convert 1-based column number to Excel letter (1=A, 27=AA)."""
        result = ""
        while col_num > 0:
            col_num -= 1
            result = chr(65 + col_num % 26) + result
            col_num //= 26
        return result

    def write_headers(ws, headers):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border
            ws.column_dimensions[col_letter(col)].width = max(len(h) + 5, 15)

    def write_row(ws, row_num, data):
        for col, val in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.border = thin_border

    headers = [
        "Video ID", "Title", "Subject", "Chapter", "Topic", "Subtopic",
        "Difficulty", "Duration (s)", "Resolution", "Quality",
        "Status", "YouTube URL", "YouTube Status",
        "Exam Tags", "Purpose Tags", "Created At"
    ]

    if export_type == "master":
        ws = wb.active
        ws.title = "Master List"
        write_headers(ws, headers)
        for i, v in enumerate(videos, 2):
            write_row(ws, i, [
                v.video_id, v.title, v.subject, v.chapter, v.topic, v.subtopic,
                v.difficulty, round(v.duration_seconds, 1), v.resolution, v.quality_preset,
                v.status, v.youtube_url, v.youtube_status,
                v.exam_tags, v.purpose_tags,
                v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
            ])

    elif export_type == "subject":
        wb.remove(wb.active)
        subjects = {}
        for v in videos:
            subjects.setdefault(v.subject, []).append(v)

        for subj, vids in subjects.items():
            ws = wb.create_sheet(title=subj[:31])
            write_headers(ws, headers)
            for i, v in enumerate(vids, 2):
                write_row(ws, i, [
                    v.video_id, v.title, v.subject, v.chapter, v.topic, v.subtopic,
                    v.difficulty, round(v.duration_seconds, 1), v.resolution, v.quality_preset,
                    v.status, v.youtube_url, v.youtube_status,
                    v.exam_tags, v.purpose_tags,
                    v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
                ])

    elif export_type == "topic":
        wb.remove(wb.active)
        topics = {}
        for v in videos:
            key = f"{v.subject} - {v.topic}"
            topics.setdefault(key, []).append(v)

        for topic_key, vids in topics.items():
            ws = wb.create_sheet(title=topic_key[:31])
            write_headers(ws, headers)
            for i, v in enumerate(vids, 2):
                write_row(ws, i, [
                    v.video_id, v.title, v.subject, v.chapter, v.topic, v.subtopic,
                    v.difficulty, round(v.duration_seconds, 1), v.resolution, v.quality_preset,
                    v.status, v.youtube_url, v.youtube_status,
                    v.exam_tags, v.purpose_tags,
                    v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
                ])

    elif export_type == "youtube":
        ws = wb.active
        ws.title = "YouTube Links"
        yt_headers = ["Video ID", "Subject", "Topic", "Subtopic", "Title", "YouTube URL", "Status"]
        write_headers(ws, yt_headers)
        row = 2
        for v in videos:
            if v.youtube_url:
                write_row(ws, row, [
                    v.video_id, v.subject, v.topic, v.subtopic,
                    v.title, v.youtube_url, v.youtube_status,
                ])
                row += 1

    # Save to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stem_videos_{export_type}_{ts}.xlsx"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _generate_csv(videos, export_type):
    """Generate CSV export."""
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "Video ID", "Title", "Subject", "Chapter", "Topic", "Subtopic",
        "Difficulty", "Duration (s)", "Resolution", "Quality",
        "Status", "YouTube URL", "YouTube Status",
        "Exam Tags", "Purpose Tags", "Created At"
    ]
    writer.writerow(headers)

    for v in videos:
        writer.writerow([
            v.video_id, v.title, v.subject, v.chapter, v.topic, v.subtopic,
            v.difficulty, round(v.duration_seconds, 1), v.resolution, v.quality_preset,
            v.status, v.youtube_url, v.youtube_status,
            v.exam_tags, v.purpose_tags,
            v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
        ])

    buffer = io.BytesIO(output.getvalue().encode("utf-8"))
    buffer.seek(0)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"stem_videos_{export_type}_{ts}.csv",
        mimetype="text/csv",
    )

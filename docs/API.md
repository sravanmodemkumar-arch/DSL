# API Reference

All endpoints are served by Flask. The dashboard is HTML-based (Jinja2 + HTMX), but several endpoints also return JSON or serve files.

---

## Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard home page with stats |
| GET | `/stats` | HTMX partial -- live stats cards |

---

## Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/upload/` | Upload page |
| POST | `/upload/validate` | Validate JSON (HTMX) -- returns validation result HTML |
| POST | `/upload/process` | Process JSON -- creates Video records, queues jobs |
| GET | `/upload/download/reference-schema` | Download `REFERENCE_SCHEMA.json` |
| GET | `/upload/download/prompt` | Download `PROMPT_JSON_GENERATOR.md` |

### POST `/upload/process`

**Input:** Multipart form with `file` (JSON or ZIP) or `json_text` (raw JSON string)

**Behavior:**
1. Validates JSON against schema
2. Creates `Video` record for each question
3. Creates `JobQueue` entry for each video
4. Redirects to `/queue`

---

## Video Library

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/videos/` | Library page with filters |
| GET | `/videos/list` | HTMX partial -- filtered video grid |
| GET | `/videos/<video_id>` | Video detail page |
| POST | `/videos/<video_id>/delete` | Delete video + files |
| GET | `/videos/<video_id>/download` | Download MP4 file |

### Query Parameters for `/videos/list`

| Param | Type | Description |
|-------|------|-------------|
| `subject` | string | Filter by subject |
| `topic` | string | Filter by topic |
| `difficulty` | string | Filter by difficulty (easy/medium/hard) |
| `status` | string | Filter by status (completed/failed/processing) |
| `search` | string | Search in title, topic, subtopic |
| `sort` | string | Sort field (created_at, title, subject) |
| `page` | int | Page number |

---

## Job Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/queue/` | Queue page |
| GET | `/queue/list` | HTMX partial -- job list with status |
| POST | `/queue/<job_id>/cancel` | Cancel a queued/processing job |
| POST | `/queue/<job_id>/retry` | Retry a failed job |
| POST | `/queue/<job_id>/delete` | Delete job record |
| GET | `/queue/stats` | HTMX partial -- queue statistics |

---

## YouTube

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/youtube/` | YouTube management page |
| GET | `/youtube/oauth-start` | Begin OAuth2 flow (redirects to Google) |
| GET | `/youtube/oauth-callback` | OAuth2 callback handler |
| POST | `/youtube/logout` | Disconnect YouTube account |
| POST | `/youtube/<video_id>/upload` | Upload video to YouTube |
| GET | `/youtube/<video_id>/status` | Check upload status |

### YouTube Upload

Requires OAuth2 authentication first. Uses metadata from the JSON `youtube` block if present, otherwise auto-generates from `meta` + `thumbnail` + `question`.

---

## Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/export/` | Export page |
| POST | `/export/download` | Generate and download Excel/CSV |

### POST `/export/download`

**Form params:**
- `format`: `xlsx` or `csv`
- `subject`: filter by subject (optional)
- `status`: filter by status (optional)

**Excel output includes:**
- Master sheet (all videos)
- Per-subject sheets
- Per-topic sheets
- Formatted headers and column widths

---

## Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/settings/` | Settings page |
| POST | `/settings/update` | Update settings (HTMX) |
| POST | `/settings/generate-voice-samples` | Generate TTS voice preview MP3s |

### Settings Keys

| Key | Default | Description |
|-----|---------|-------------|
| `default_resolution` | `1080p` | Video resolution |
| `default_quality_preset` | `P7` | Quality preset (P1-P7) |
| `default_theme` | `dark` | Video theme |
| `default_fps` | `30` | Frames per second |
| `tts_engine` | `edge_tts` | TTS engine |
| `tts_voice` | `en-IN-PrabhatNeural` | TTS voice |
| `bgm_enabled` | `true` | Background music on/off |
| `bgm_style` | `bansuri` | BGM style |
| `bgm_volume` | `0.30` | BGM volume (0.0-1.0) |
| `max_workers` | `4` | Concurrent processing |

---

## Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/assets/` | Asset manager page |
| POST | `/assets/upload` | Upload image/SVG/video asset |
| POST | `/assets/<asset_id>/delete` | Delete asset |
| GET | `/assets/<asset_type>/<filename>` | Serve asset file |

### POST `/assets/upload`

**Form params:**
- `file`: The asset file (image/SVG/video)
- `category`: `images`, `svgs`, or `videos`
- `subject`: Subject folder (e.g., `biology`, `physics`)

---

## Storage Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/storage/<path:filename>` | Serve generated video/thumbnail files |

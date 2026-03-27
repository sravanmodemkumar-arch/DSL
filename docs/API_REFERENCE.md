# API Reference

All HTTP endpoints for the STEM Video Generator. The UI uses HTMX to call these endpoints, but they can also be called directly.

---

## Dashboard

### `GET /`
**Dashboard home page.** Shows stats, recent videos, subject distribution, active jobs.

### `GET /stats`
**HTMX partial.** Returns stats cards HTML (total, completed, processing, pending, failed).
Auto-refreshed every 10 seconds on dashboard.

---

## Upload

### `GET /upload/`
**Upload page.** JSON editor, file upload, video settings panel.

### `POST /upload/validate`
**Validate JSON content.** Returns HTML with validation results.

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `json_content` | string | form | Raw JSON text |

**Response:** HTML div with green (valid) or red (errors) messages.

### `POST /upload/process`
**Process JSON — create videos and queue jobs.** Accepts JSON text or file upload (JSON or ZIP).

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `json_content` | string | form | Raw JSON text (from editor) |
| `json_file` | file | form | JSON or ZIP file upload |
| `resolution` | string | form | 360p / 720p / 1080p / 2K / 4K |
| `quality_preset` | string | form | P1 through P7 |
| `theme` | string | form | dark / light |
| `max_duration` | integer | form | Max video duration in minutes |
| `bgm_style` | string | form | BGM style or "none" |

**Response:** HTML with success count and queue link, or error message.

**ZIP upload:** Extracts all `.json` files from the ZIP and processes them as a batch.

---

## Video Library

### `GET /videos/`
**Video library page.** Grid view with filters and search.

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `page` | integer | query | Page number (default: 1) |
| `subject` | string | query | Filter by subject |
| `topic` | string | query | Filter by topic |
| `subtopic` | string | query | Filter by subtopic |
| `difficulty` | string | query | easy / medium / hard |
| `status` | string | query | pending / processing / completed / failed |
| `search` | string | query | Search title, ID, subject, topic |
| `sort` | string | query | newest / oldest / subject / duration |

### `GET /videos/list`
**HTMX partial.** Returns video grid HTML. Same parameters as above.
Called by filter/search changes via HTMX.

### `GET /videos/<video_id>`
**Video detail page.** Player, metadata, download/delete/retry actions.

### `GET /videos/<video_id>/preview`
**Preview page.** Renders 5 key frames from JSON without full video generation.

### `GET /videos/<video_id>/preview-frames`
**HTMX partial.** Generates and returns 5 preview frame images as base64 inline PNGs.

### `GET /videos/<video_id>/stream`
**Video streaming.** Returns the MP4 file for in-browser playback.

### `GET /videos/<video_id>/download`
**Download MP4.** Returns the video as an attachment download.

### `GET /videos/<video_id>/thumbnail`
**Thumbnail image.** Returns the PNG thumbnail.

### `DELETE /videos/<video_id>/delete`
**Delete video.** Removes database record and all associated files (video, audio, thumbnail).

### `POST /videos/<video_id>/retry`
**Retry failed generation.** Re-queues the video for processing.

---

## Queue

### `GET /queue/`
**Queue management page.** Shows all jobs with stats.

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `status` | string | query | Filter: queued / processing / completed / failed |

### `GET /queue/list`
**HTMX partial.** Returns job list HTML. Auto-refreshed every 5 seconds.

### `POST /queue/<job_id>/cancel`
**Cancel a job.** Sets job status to cancelled.

### `POST /queue/<job_id>/retry`
**Retry a failed job.** Resets status to queued and triggers processing.

### `POST /queue/<job_id>/priority`
**Set job priority.**

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `priority` | integer | form | 1=urgent, 2=high, 3=normal, 4=low |

### `POST /queue/clear-completed`
**Delete all completed jobs** from the queue. Does not affect video records.

---

## YouTube

### `GET /youtube/`
**YouTube management page.** Lists all completed videos with upload status.

### `POST /youtube/upload/<video_id>`
**Upload video to YouTube.** Requires YouTube API credentials (optional).
Falls back to manual URL entry if no credentials configured.

### `POST /youtube/bulk-upload`
**Upload all ready videos.** Processes all completed, non-uploaded videos.

### `POST /youtube/update-url/<video_id>`
**Manually set YouTube URL.**

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `youtube_url` | string | form | Full YouTube URL |

---

## Export

### `GET /export/`
**Export configuration page.** Select export type, filters, format.

### `POST /export/download`
**Generate and download export file.**

| Parameter | Type | Source | Description |
|-----------|------|--------|-------------|
| `export_type` | string | form | master / subject / topic / youtube |
| `subject` | string | form | Filter by subject (empty = all) |
| `status` | string | form | Filter by status (default: completed) |
| `format` | string | form | xlsx / csv |

**Export types:**
| Type | Description |
|------|-------------|
| `master` | All videos in one sheet |
| `subject` | Separate sheet per subject |
| `topic` | Separate sheet per subject+topic |
| `youtube` | Only videos with YouTube URLs |

**Excel columns:** Video ID, Title, Subject, Chapter, Topic, Subtopic, Difficulty, Duration, Resolution, Quality, Status, YouTube URL, YouTube Status, Exam Tags, Purpose Tags, Created At

---

## Settings

### `GET /settings/`
**Settings page.** All configurable options.

### `POST /settings/save`
**Save settings.** Accepts all setting fields as form data.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `default_resolution` | string | 1080p | Default video resolution |
| `default_quality_preset` | string | P5 | Default quality |
| `default_duration_minutes` | string | 8 | Default max duration |
| `default_theme` | string | dark | Default visual theme |
| `default_fps` | string | 30 | Default frame rate |
| `tts_engine` | string | gtts | TTS engine |
| `tts_lang` | string | en | TTS language |
| `tts_tld` | string | co.in | TTS accent |
| `bgm_enabled` | string | true | Enable background music |
| `bgm_style` | string | calm_waves | Default BGM style |
| `bgm_volume` | string | 0.15 | BGM volume (0.05-0.30) |
| `max_workers` | string | 4 | Parallel workers |
| `job_timeout` | string | 600 | Timeout per job (seconds) |
| `ffmpeg_path` | string | ffmpeg | Path to FFmpeg binary |
| `auto_youtube_upload` | string | false | Auto-upload after generation |
| `youtube_default_privacy` | string | public | Default YouTube privacy |
| `youtube_default_category` | string | 27 | YouTube category (27=Education) |

### `POST /settings/reset`
**Reset all settings to defaults.**

---

## Static / Storage

### `GET /static/<path:filename>`
**Static files** (CSS, JS). Served by Flask.

### `GET /storage/<path:filename>`
**Storage files** (videos, audio, etc.). Served from the storage directory.

---

## Error Responses

| Code | Page | Description |
|------|------|-------------|
| 404 | 404.html | Resource not found |
| 500 | 500.html | Internal server error |

HTMX partials return HTML fragments (not full pages) with error styling.

---

## DSL — Option Highlighting in the Header

The header options row (always visible once options are shown) supports two highlight states:

| State | Color | How to trigger |
|-------|-------|----------------|
| **Being explained** | 🟠 Saffron (orange) | `{ "action": "show", "target": "option_b" }` |
| **Correct answer** | 🟢 Green | `{ "action": "show", "target": "final_answer" }` |

### Highlight an option in saffron (while explaining it)
```json
{ "action": "show", "target": "option_b" }
```
- Valid targets: `option_a`, `option_b`, `option_c`, `option_d`
- Use at the **start** of working steps for that option
- Only one option is saffron at a time — new highlight replaces previous
- Alternative: `{ "action": "highlight_option", "target": "options_grid", "key": "b" }`

### Reveal the correct answer in green (final step)
```json
{ "action": "show", "target": "final_answer" }
```
- Always the **last step** in every video
- Automatically highlights `question.correct` option in green
- Removes saffron — green replaces it
- Correct option stays green for the rest of the video

### Complete pattern example
```json
{ "steps": [
  {
    "text": "Rule of 9 — Key Rule",
    "audio": "The rule of nine says: add all digits...",
    "render": { "action": "show", "target": "concept_text", "heading": "Rule of 9", "items": ["..."] }
  },
  {
    "text": "Testing Option B",
    "audio": "Now testing Option B — watch the header, Option B is highlighted.",
    "render": { "action": "show", "target": "option_b" }
  },
  {
    "text": "Digit sum of 10098",
    "audio": "Add the digits: 1+0+0+9+8 = 18. Eighteen divided by nine equals two.",
    "render": { "action": "show", "target": "shortcut_columns", "left": { "title": "Rule of 9", "digit_data": [1,0,0,9,8], "operator": "+", "numerator": "18", "denominator": "9", "result": "2", "verdict": "Divisible by 9!", "pass": true } }
  },
  {
    "text": "Answer",
    "audio": "Option B passes both tests. It is the correct answer.",
    "render": { "action": "show", "target": "final_answer" }
  }
]}
```

> **Visual flow:** No highlight → `option_b` saffron → working steps (still saffron) → `final_answer` turns green

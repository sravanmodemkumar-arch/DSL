# Changelog

## 2026-03-27 -- v5.0

### Added
- **8 Video Modes**: mcq, topic, true_false, fill_blank, numerical, match, assertion, sequence
- **Mode-aware renderer**: 4 header methods (`_draw_topic_bar`, `_draw_minimal_bar`, `_draw_numerical_header`, `_draw_assertion_header`)
- **7 new element renderers**: title_card, section_header, blank_reveal, match_columns, sequence_list, numerical_answer, manim_scene
- **Manim integration**: 20 animated scene templates (Math 11, Physics 5, Chemistry 1, General 3)
- **engine/manim_renderer.py**: Pre-rendering pipeline with frame caching
- **engine/free_media.py**: Multi-provider image/video fetcher (Wikimedia, Pixabay, Pexels, Unsplash)
- **74 builtin_visual illustrations**: Biology 18, Physics 20, Chemistry 12, Math 10, Geography 4, Polity 2, Economics 2, CS 6, Reasoning 3, Universal 6
- **matplotlib_plot target**: Scientific graphs (line, bar, scatter, pie, histogram)
- **rdkit_mol target**: 2D molecular structures from SMILES strings
- PROMPT_JSON_GENERATOR.md v5.0 with complete DSL specification
- REFERENCE_SCHEMA.json with inline documentation for all 35+ elements
- Project documentation (README, Architecture, API, Setup, DSL Guide, Visual Reference)

### Changed
- Default quality preset: P5 -> **P7** (25Mbps, 60fps)
- sync.py `get_active_state()` now mode-aware with conditional headers
- renderer.py `render_frame()` returns dynamic `body_top` per mode
- pipeline.py adds Stage 3b for Manim pre-rendering

## 2026-03-26 -- v4.0

### Added
- Concurrent multi-video processing (auto-scales to CPU cores)
- .env configuration with dotenv
- Storage cleanup (temp files on success and failure)
- Queue UX: auto-redirect on upload, active-first sort
- BGM volume default 0.30
- Corner label on thumbnails
- Auto-save settings (no Save button)
- Copyright & licensing section in settings

## 2026-03-25 -- v3.0

### Added
- Job queue with priority, retry, cancel
- Video library with filtering and search
- YouTube OAuth2 upload integration
- Excel/CSV export with formatted sheets
- Asset manager (images, SVGs, videos)
- Settings page with TTS voice preview
- Background music (8 royalty-free tracks)
- Error pages (404, 500)

## 2026-03-24 -- v2.0

### Added
- Flask web dashboard
- SQLite database with Video, JobQueue, Setting models
- HTMX live updates (5s polling)
- Upload page with JSON validation
- Video preview and download

## 2026-03-23 -- v1.0

### Added
- Core video pipeline (JSON -> TTS -> frames -> MP4)
- Pillow frame renderer with dark theme
- Edge TTS with word-level timestamps
- FFmpeg encoding (GPU -> CPU fallback)
- Basic render targets (question_block, options_grid, equation, concept_text)

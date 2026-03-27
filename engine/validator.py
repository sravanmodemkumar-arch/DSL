"""JSON DSL schema validator — strict validation before rendering."""

import json
import os

VALID_SCENE_TYPES = {"question", "options", "visual_intro", "concept", "solution", "answer", "intro"}
VALID_MODES = {"mcq", "topic", "true_false", "fill_blank", "numerical", "match", "assertion", "sequence"}
VALID_ACTIONS = {
    "show", "hide", "highlight", "update", "animate", "show_result",
    "draw_arrow", "zoom", "replace", "sequence",
    "clear",              # remove element from screen
    "highlight_option",   # highlight specific option in header
}
VALID_POSITIONS = {"center", "top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"}
VALID_SIZES = {"small", "medium", "large", "full"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


class ValidationError:
    def __init__(self, path, message, severity="error"):
        self.path = path
        self.message = message
        self.severity = severity  # error | warning

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.path}: {self.message}"

    def to_dict(self):
        return {"path": self.path, "message": self.message, "severity": self.severity}


def validate_json(data, assets_dir=None):
    """Validate a list of question objects. Returns (is_valid, errors)."""
    errors = []

    if not isinstance(data, list):
        errors.append(ValidationError("root", "Root must be a JSON array"))
        return False, errors

    seen_ids = set()
    for i, question in enumerate(data):
        prefix = f"[{i}]"
        # Skip reference/documentation objects
        if isinstance(question, dict) and "_DOC" in question:
            continue
        _validate_question(question, prefix, errors, seen_ids, assets_dir)

    has_fatal = any(e.severity == "error" for e in errors)
    return not has_fatal, errors


def _validate_question(q, prefix, errors, seen_ids, assets_dir):
    if not isinstance(q, dict):
        errors.append(ValidationError(prefix, "Question must be an object"))
        return

    # mode
    mode = q.get("mode", "mcq")
    if mode not in VALID_MODES:
        errors.append(ValidationError(f"{prefix}.mode", f"Invalid mode: {mode}. Must be: {VALID_MODES}"))
        mode = "mcq"  # fallback for remaining checks

    # id
    qid = q.get("id")
    if not qid or not isinstance(qid, str):
        errors.append(ValidationError(f"{prefix}.id", "Missing or invalid 'id'"))
    elif qid in seen_ids:
        errors.append(ValidationError(f"{prefix}.id", f"Duplicate id: {qid}"))
    else:
        seen_ids.add(qid)

    # meta
    meta = q.get("meta")
    if not meta or not isinstance(meta, dict):
        errors.append(ValidationError(f"{prefix}.meta", "Missing or invalid 'meta'"))
    else:
        if not meta.get("subject"):
            errors.append(ValidationError(f"{prefix}.meta.subject", "Missing 'subject'"))
        if not meta.get("topic"):
            errors.append(ValidationError(f"{prefix}.meta.topic", "Missing 'topic'"))
        diff = meta.get("difficulty", "")
        if diff and diff not in VALID_DIFFICULTIES:
            errors.append(ValidationError(f"{prefix}.meta.difficulty", f"Invalid difficulty: {diff}. Must be: {VALID_DIFFICULTIES}", "warning"))

    # mode-specific field checks
    question = q.get("question", {})
    has_question = bool(question.get("text"))
    has_options = bool(question.get("options"))
    has_correct = bool(question.get("correct"))
    has_topic_header = bool(q.get("topic_header"))

    # Modes that need a question block
    if mode in ("mcq", "true_false", "fill_blank", "numerical", "assertion"):
        if not has_question:
            errors.append(ValidationError(f"{prefix}.question.text", f"Mode '{mode}' requires 'question.text'"))
    # Modes that need options
    if mode in ("mcq", "true_false", "assertion"):
        if not has_options:
            errors.append(ValidationError(f"{prefix}.question.options", f"Mode '{mode}' requires 'question.options'"))
        if not has_correct:
            errors.append(ValidationError(f"{prefix}.question.correct", f"Mode '{mode}' requires 'question.correct'"))
    # true_false: exactly 2 options
    if mode == "true_false" and has_options:
        opts = question.get("options", [])
        if len(opts) != 2:
            errors.append(ValidationError(f"{prefix}.question.options", f"Mode 'true_false' requires exactly 2 options, got {len(opts)}", "warning"))
    # Modes that need topic_header
    if mode in ("topic", "match", "sequence"):
        if not has_topic_header:
            errors.append(ValidationError(f"{prefix}.topic_header", f"Mode '{mode}' requires 'topic_header'", "warning"))
    # assertion: needs assertion + reason fields
    if mode == "assertion":
        if not question.get("assertion"):
            errors.append(ValidationError(f"{prefix}.question.assertion", "Mode 'assertion' requires 'question.assertion'"))
        if not question.get("reason"):
            errors.append(ValidationError(f"{prefix}.question.reason", "Mode 'assertion' requires 'question.reason'"))

    # assets
    assets = q.get("assets", {})
    asset_keys = set()
    if isinstance(assets, dict):
        for category in ("images", "svgs", "audio_clips"):
            cat_data = assets.get(category, {})
            if isinstance(cat_data, dict):
                for key, path in cat_data.items():
                    asset_keys.add(key)
                    if assets_dir and not os.path.exists(os.path.join(assets_dir, path.lstrip("/"))):
                        errors.append(ValidationError(f"{prefix}.assets.{category}.{key}", f"Asset file not found: {path}", "warning"))

    # scenes
    scenes = q.get("scenes")
    if not scenes or not isinstance(scenes, list):
        errors.append(ValidationError(f"{prefix}.scenes", "Missing or invalid 'scenes' array"))
        return

    for j, scene in enumerate(scenes):
        _validate_scene(scene, f"{prefix}.scenes[{j}]", errors, asset_keys)


def _validate_scene(scene, prefix, errors, asset_keys):
    if not isinstance(scene, dict):
        errors.append(ValidationError(prefix, "Scene must be an object"))
        return

    scene_type = scene.get("type")
    if not scene_type:
        errors.append(ValidationError(f"{prefix}.type", "Missing scene 'type'"))
    elif scene_type not in VALID_SCENE_TYPES:
        errors.append(ValidationError(f"{prefix}.type", f"Invalid scene type: {scene_type}. Must be: {VALID_SCENE_TYPES}"))

    # Scenes with steps
    if scene_type in ("concept", "solution", "intro"):
        steps = scene.get("steps")
        if not steps or not isinstance(steps, list):
            errors.append(ValidationError(f"{prefix}.steps", f"Scene type '{scene_type}' requires 'steps' array"))
        else:
            for k, step in enumerate(steps):
                _validate_step(step, f"{prefix}.steps[{k}]", errors, asset_keys)
    else:
        # Simple scenes may have a direct render
        render = scene.get("render")
        if render:
            _validate_render(render, f"{prefix}.render", errors, asset_keys)


def _validate_step(step, prefix, errors, asset_keys):
    if not isinstance(step, dict):
        errors.append(ValidationError(prefix, "Step must be an object"))
        return

    if not step.get("text"):
        errors.append(ValidationError(f"{prefix}.text", "Missing 'text'", "warning"))
    if not step.get("audio"):
        errors.append(ValidationError(f"{prefix}.audio", "Missing 'audio'", "warning"))

    render = step.get("render")
    if render:
        _validate_render(render, f"{prefix}.render", errors, asset_keys)


def _validate_render(render, prefix, errors, asset_keys):
    if not isinstance(render, dict):
        errors.append(ValidationError(prefix, "Render must be an object"))
        return

    action = render.get("action")
    if not action:
        errors.append(ValidationError(f"{prefix}.action", "Missing 'action'"))
    elif action not in VALID_ACTIONS:
        errors.append(ValidationError(f"{prefix}.action", f"Invalid action: {action}. Must be: {VALID_ACTIONS}"))

    if not render.get("target"):
        errors.append(ValidationError(f"{prefix}.target", "Missing 'target'"))

    # Check asset reference
    src = render.get("src")
    if src and src not in asset_keys:
        errors.append(ValidationError(f"{prefix}.src", f"Asset key '{src}' not found in assets", "warning"))

    pos = render.get("position")
    if pos and pos not in VALID_POSITIONS:
        errors.append(ValidationError(f"{prefix}.position", f"Invalid position: {pos}", "warning"))

    size = render.get("size")
    if size and size not in VALID_SIZES:
        errors.append(ValidationError(f"{prefix}.size", f"Invalid size: {size}", "warning"))

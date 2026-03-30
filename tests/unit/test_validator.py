"""Unit tests for engine.validator — JSON DSL schema validation."""
import copy
import pytest
import sys
sys.path.insert(0, "/home/sravan/DSL")

from engine.validator import validate_json, ValidationError
from tests.conftest import MINIMAL_MCQ_JSON, MINIMAL_TOPIC_JSON


# ── Helper ────────────────────────────────────────────────────────────────────

def _wrap(q):
    """Wrap a single question dict in a list (validate_json expects a list)."""
    return [q]


def _errors_of(data, severity="error"):
    _, errors = validate_json(data)
    return [e for e in errors if e.severity == severity]


# ── Valid inputs ──────────────────────────────────────────────────────────────

class TestValidInputs:
    def test_valid_mcq(self, sample_mcq):
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert is_valid
        fatal = [e for e in errors if e.severity == "error"]
        assert fatal == []

    def test_valid_topic(self, sample_topic):
        is_valid, errors = validate_json(_wrap(sample_topic))
        assert is_valid
        fatal = [e for e in errors if e.severity == "error"]
        assert fatal == []

    def test_multiple_questions(self, sample_mcq, sample_topic):
        sample_topic["id"] = "topic-unique-002"
        is_valid, errors = validate_json([sample_mcq, sample_topic])
        assert is_valid

    def test_doc_object_skipped(self, sample_mcq):
        """Objects with _DOC key should be silently skipped."""
        doc = {"_DOC": "This is documentation"}
        is_valid, errors = validate_json([doc, sample_mcq])
        assert is_valid

    def test_root_must_be_list(self):
        is_valid, errors = validate_json({"id": "x", "mode": "mcq"})
        assert not is_valid
        assert any("Root must be a JSON array" in e.message for e in errors)


# ── ID validation ─────────────────────────────────────────────────────────────

class TestIDValidation:
    def test_missing_id(self, sample_mcq):
        del sample_mcq["id"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid
        assert any("id" in e.path for e in errors if e.severity == "error")

    def test_duplicate_id(self, sample_mcq):
        q2 = copy.deepcopy(sample_mcq)
        # Same id in both
        is_valid, errors = validate_json([sample_mcq, q2])
        assert not is_valid
        assert any("Duplicate id" in e.message for e in errors)

    def test_non_string_id(self, sample_mcq):
        sample_mcq["id"] = 123
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid


# ── Mode validation ───────────────────────────────────────────────────────────

class TestModeValidation:
    def test_invalid_mode(self, sample_mcq):
        sample_mcq["mode"] = "invalid_mode"
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid
        assert any("Invalid mode" in e.message for e in errors)

    def test_all_valid_modes(self, sample_mcq):
        valid_modes = ["mcq", "topic", "true_false", "fill_blank", "numerical",
                       "match", "assertion", "sequence"]
        for mode in valid_modes:
            q = copy.deepcopy(sample_mcq)
            q["mode"] = mode
            q["id"] = f"test-{mode}"
            # topic/match/sequence need topic_header, not question — just check no "Invalid mode"
            _, errors = validate_json(_wrap(q))
            mode_errors = [e for e in errors if "Invalid mode" in e.message]
            assert mode_errors == [], f"Mode '{mode}' should be valid"


# ── Meta validation ───────────────────────────────────────────────────────────

class TestMetaValidation:
    def test_missing_meta(self, sample_mcq):
        del sample_mcq["meta"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_missing_meta_subject(self, sample_mcq):
        del sample_mcq["meta"]["subject"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_missing_meta_topic(self, sample_mcq):
        del sample_mcq["meta"]["topic"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_invalid_difficulty_is_warning(self, sample_mcq):
        sample_mcq["meta"]["difficulty"] = "impossible"
        is_valid, errors = validate_json(_wrap(sample_mcq))
        # Difficulty is just a warning, not fatal
        assert is_valid
        warn = [e for e in errors if e.severity == "warning" and "difficulty" in e.path]
        assert warn


# ── MCQ-specific validation ───────────────────────────────────────────────────

class TestMCQValidation:
    def test_missing_question_text(self, sample_mcq):
        del sample_mcq["question"]["text"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_missing_options(self, sample_mcq):
        del sample_mcq["question"]["options"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_missing_correct(self, sample_mcq):
        del sample_mcq["question"]["correct"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid


# ── Topic-specific validation ─────────────────────────────────────────────────

class TestTopicValidation:
    def test_topic_without_topic_header_is_warning(self, sample_topic):
        del sample_topic["topic_header"]
        is_valid, errors = validate_json(_wrap(sample_topic))
        # topic_header is only a warning
        assert is_valid
        warn = [e for e in errors if e.severity == "warning" and "topic_header" in e.path]
        assert warn


# ── Scenes validation ─────────────────────────────────────────────────────────

class TestScenesValidation:
    def test_missing_scenes(self, sample_mcq):
        del sample_mcq["scenes"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_empty_scenes(self, sample_mcq):
        sample_mcq["scenes"] = []
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid

    def test_invalid_scene_type(self, sample_mcq):
        sample_mcq["scenes"][0]["type"] = "unknown_scene_type"
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid
        assert any("Invalid scene type" in e.message for e in errors)

    def test_concept_scene_requires_steps(self, sample_mcq):
        # Remove steps from concept scene
        for scene in sample_mcq["scenes"]:
            if scene["type"] == "concept":
                del scene["steps"]
                break
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid
        assert any("requires 'steps'" in e.message for e in errors)

    def test_valid_scene_types(self, sample_mcq):
        valid_simple_types = ["question", "options", "visual_intro", "answer"]
        for scene_type in valid_simple_types:
            q = copy.deepcopy(sample_mcq)
            q["scenes"][0]["type"] = scene_type
            _, errors = validate_json(_wrap(q))
            type_errors = [e for e in errors if "Invalid scene type" in e.message]
            assert type_errors == [], f"Scene type '{scene_type}' should be valid"


# ── Render action validation ──────────────────────────────────────────────────

class TestRenderValidation:
    def test_invalid_action(self, sample_mcq):
        sample_mcq["scenes"][0]["render"]["action"] = "explode"
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid
        assert any("Invalid action" in e.message for e in errors)

    def test_missing_target(self, sample_mcq):
        del sample_mcq["scenes"][0]["render"]["target"]
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert not is_valid
        assert any("Missing 'target'" in e.message for e in errors)

    def test_invalid_position_is_warning(self, sample_mcq):
        sample_mcq["scenes"][0]["render"]["position"] = "diagonal"
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert is_valid  # warning not fatal
        warn = [e for e in errors if e.severity == "warning" and "position" in e.path]
        assert warn

    def test_invalid_size_is_warning(self, sample_mcq):
        sample_mcq["scenes"][0]["render"]["size"] = "enormous"
        is_valid, errors = validate_json(_wrap(sample_mcq))
        assert is_valid  # warning not fatal
        warn = [e for e in errors if e.severity == "warning" and "size" in e.path]
        assert warn

    def test_valid_actions(self):
        valid_actions = ["show", "hide", "highlight", "update", "animate",
                         "show_result", "draw_arrow", "zoom", "replace",
                         "sequence", "clear", "highlight_option"]
        from engine.validator import VALID_ACTIONS
        assert set(valid_actions) == VALID_ACTIONS


# ── ValidationError helper ────────────────────────────────────────────────────

class TestValidationError:
    def test_repr(self):
        e = ValidationError("root.id", "Missing id", "error")
        assert "[ERROR]" in repr(e)
        assert "root.id" in repr(e)

    def test_to_dict(self):
        e = ValidationError("root.id", "Missing id", "warning")
        d = e.to_dict()
        assert d["path"] == "root.id"
        assert d["message"] == "Missing id"
        assert d["severity"] == "warning"

    def test_default_severity_is_error(self):
        e = ValidationError("x", "y")
        assert e.severity == "error"

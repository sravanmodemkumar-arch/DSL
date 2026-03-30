"""Unit tests for engine.renderer — frame rendering with Pillow."""
import sys
import pytest
sys.path.insert(0, "/home/sravan/DSL")

from PIL import Image
from engine.renderer import FrameRenderer
from engine.sync import build_timeline, get_active_state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _blank_ratio(img):
    """Return fraction of pixels that are white (#FFFFFF) background."""
    pixels = list(img.getdata())
    white = sum(1 for p in pixels if p == (255, 255, 255))
    return white / len(pixels)


def _is_mostly_non_white(img, threshold=0.3):
    """True if at least `threshold` fraction of pixels differ from white."""
    return _blank_ratio(img) < (1.0 - threshold)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def renderer():
    return FrameRenderer(width=640, height=360)


# ── Initialization ────────────────────────────────────────────────────────────

class TestRendererInit:
    def test_creates_at_target_resolution(self):
        r = FrameRenderer(width=640, height=360)
        assert r.width == 640
        assert r.height == 360

    def test_scale_factor(self):
        r = FrameRenderer(width=640, height=360)
        assert r.scale == pytest.approx(640 / 1920, rel=1e-3)

    def test_blank_frame_dimensions(self, renderer):
        frame = renderer._blank_frame()
        assert frame.size == (renderer.width, renderer.height)
        assert frame.mode == "RGB"


# ── MCQ mode rendering ────────────────────────────────────────────────────────

class TestMCQRendering:
    def _make_mcq_state(self, question_shown=True, options_shown=True):
        return {
            "mode": "mcq",
            "question_text": "Which number is divisible by 9?",
            "options_data": [
                {"key": "a", "value": "12"},
                {"key": "b", "value": "18"},
                {"key": "c", "value": "25"},
                {"key": "d", "value": "31"},
            ],
            "correct_option": "b",
            "highlighted_option": "",
            "show_correct": False,
            "question_shown": question_shown,
            "options_shown": options_shown,
            "work_elements": {},
            "step_text": "",
            "narration": None,
            "current_time": 0.0,
            "topic_header": None,
            "topic_shown": False,
        }

    def test_renders_without_exception(self, renderer):
        state = self._make_mcq_state()
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)
        assert frame.size == (renderer.width, renderer.height)

    def test_frame_has_content(self, renderer):
        state = self._make_mcq_state()
        frame = renderer.render_frame(state)
        # Should have significant non-white content (header, options)
        assert _is_mostly_non_white(frame, threshold=0.1)

    def test_no_question_shown(self, renderer):
        state = self._make_mcq_state(question_shown=False, options_shown=False)
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_highlighted_option(self, renderer):
        state = self._make_mcq_state()
        state["highlighted_option"] = "b"
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_correct_shown(self, renderer):
        state = self._make_mcq_state()
        state["show_correct"] = True
        state["highlighted_option"] = "b"
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_equation_element(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["equation"] = {
            "type": "equation",
            "value": "9 × 2 = 18",
            "highlighted": False,
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_highlight_box(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["highlight_box"] = {
            "type": "highlight_box",
            "text": "Divisibility Rule of 9",
            "color": "blue",
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_key_facts(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["key_facts"] = {
            "type": "key_facts",
            "heading": "Key Rules",
            "facts": [
                {"key": "Rule of 9", "value": "Sum of digits divisible by 9"},
                {"key": "Rule of 3", "value": "Sum of digits divisible by 3"},
            ],
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_concept_text(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["concept_text"] = {
            "type": "concept_text",
            "heading": "Divisibility Rules",
            "text": "A number is divisible by 9 if the sum of its digits is 9.",
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_digit_boxes(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["digit_boxes"] = {
            "type": "digit_boxes",
            "data": [1, 8],
            "highlighted_indices": [0],
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_formula_block(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["formula_block"] = {
            "type": "formula_block",
            "value": "Sum = 1 + 8 = 9",
            "highlighted": False,
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_final_answer(self, renderer):
        state = self._make_mcq_state()
        state["work_elements"]["final_answer"] = {
            "type": "final_answer",
            "value": "18",
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_with_narration(self, renderer):
        state = self._make_mcq_state()
        state["narration"] = {
            "audio_text": "The answer is B, eighteen.",
            "word_timestamps": [
                {"word": "The", "start": 0.0, "end": 0.3},
                {"word": "answer", "start": 0.3, "end": 0.6},
                {"word": "is", "start": 0.6, "end": 0.9},
                {"word": "B", "start": 0.9, "end": 1.2},
            ],
        }
        state["current_time"] = 0.5
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)


# ── Topic mode rendering ──────────────────────────────────────────────────────

class TestTopicRendering:
    def _make_topic_state(self):
        return {
            "mode": "topic",
            "question_text": "",
            "options_data": [],
            "correct_option": "",
            "highlighted_option": "",
            "show_correct": False,
            "question_shown": False,
            "options_shown": False,
            "work_elements": {},
            "step_text": "Introduction",
            "narration": None,
            "current_time": 0.0,
            "topic_header": {
                "title": "Photosynthesis",
                "subtitle": "How plants make food",
            },
            "topic_shown": True,
        }

    def test_topic_mode_renders(self, renderer):
        state = self._make_topic_state()
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)
        assert frame.size == (renderer.width, renderer.height)

    def test_topic_with_title_card(self, renderer):
        state = self._make_topic_state()
        state["work_elements"]["title_card"] = {
            "type": "title_card",
            "title": "Photosynthesis",
            "subtitle": "How plants make food",
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_topic_with_key_facts(self, renderer):
        state = self._make_topic_state()
        state["work_elements"]["key_facts"] = {
            "type": "key_facts",
            "heading": "Key Facts",
            "facts": [
                {"key": "Location", "value": "Chloroplasts"},
                {"key": "Reactants", "value": "CO2 + H2O"},
            ],
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)


# ── Element-specific rendering ────────────────────────────────────────────────

class TestElementRendering:
    """Test that each known element type renders without crashing."""

    def _base_state(self):
        return {
            "mode": "mcq",
            "question_text": "Test Q",
            "options_data": [{"key": "a", "value": "Yes"}, {"key": "b", "value": "No"}],
            "correct_option": "a",
            "highlighted_option": "",
            "show_correct": False,
            "question_shown": True,
            "options_shown": True,
            "work_elements": {},
            "step_text": "",
            "narration": None,
            "current_time": 0.0,
            "topic_header": None,
            "topic_shown": False,
        }

    def _render_with(self, renderer, element_type, element_data):
        state = self._base_state()
        state["work_elements"][element_type] = {"type": element_type, **element_data}
        return renderer.render_frame(state)

    def test_process_steps(self, renderer):
        frame = self._render_with(renderer, "process_steps", {
            "heading": "Method",
            "steps": ["Step 1: Add", "Step 2: Multiply", "Step 3: Verify"],
        })
        assert isinstance(frame, Image.Image)

    def test_two_col_text(self, renderer):
        frame = self._render_with(renderer, "two_col_text", {
            "heading": "Comparison",
            "left": {"title": "Left", "items": ["A", "B"]},
            "right": {"title": "Right", "items": ["X", "Y"]},
        })
        assert isinstance(frame, Image.Image)

    def test_running_sum(self, renderer):
        frame = self._render_with(renderer, "running_sum", {"value": "45"})
        assert isinstance(frame, Image.Image)

    def test_result_box(self, renderer):
        frame = self._render_with(renderer, "result_box", {"value": "18"})
        assert isinstance(frame, Image.Image)

    def test_equation_highlighted(self, renderer):
        state = self._base_state()
        state["work_elements"]["equation"] = {
            "type": "equation", "value": "2 + 2 = 4", "highlighted": True
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)

    def test_multiple_elements_coexist(self, renderer):
        state = self._base_state()
        state["work_elements"]["equation"] = {
            "type": "equation", "value": "x = 5", "highlighted": False
        }
        state["work_elements"]["formula_block"] = {
            "type": "formula_block", "value": "ax + b = c", "highlighted": False
        }
        state["work_elements"]["running_sum"] = {
            "type": "running_sum", "value": "5"
        }
        frame = renderer.render_frame(state)
        assert isinstance(frame, Image.Image)


# ── Resolution consistency ────────────────────────────────────────────────────

class TestResolutions:
    @pytest.mark.parametrize("width,height", [
        (640, 360),    # 360p
        (1280, 720),   # 720p (slow, skip if CI)
    ])
    def test_renders_at_resolution(self, width, height):
        r = FrameRenderer(width=width, height=height)
        state = {
            "mode": "mcq",
            "question_text": "Test question",
            "options_data": [{"key": "a", "value": "Yes"}],
            "correct_option": "a",
            "highlighted_option": "",
            "show_correct": False,
            "question_shown": True,
            "options_shown": True,
            "work_elements": {},
            "step_text": "",
            "narration": None,
            "current_time": 0.0,
            "topic_header": None,
            "topic_shown": False,
        }
        frame = r.render_frame(state)
        assert frame.size == (width, height)


# ── Blank frame detection ─────────────────────────────────────────────────────

class TestNoBlankFrames:
    """Ensure rendered frames are never blank (covers the blank video bug)."""

    def test_mcq_frame_not_blank(self, renderer):
        state = {
            "mode": "mcq",
            "question_text": "What is 9 + 9?",
            "options_data": [
                {"key": "a", "value": "16"},
                {"key": "b", "value": "17"},
                {"key": "c", "value": "18"},
                {"key": "d", "value": "19"},
            ],
            "correct_option": "c",
            "highlighted_option": "",
            "show_correct": False,
            "question_shown": True,
            "options_shown": True,
            "work_elements": {
                "equation": {"type": "equation", "value": "9 + 9 = 18", "highlighted": False}
            },
            "step_text": "Addition",
            "narration": None,
            "current_time": 2.5,
            "topic_header": None,
            "topic_shown": False,
        }
        frame = renderer.render_frame(state)
        # At least 30% of pixels should differ from pure white
        assert _is_mostly_non_white(frame, threshold=0.3), \
            f"Frame appears blank — {_blank_ratio(frame)*100:.1f}% white pixels"

    def test_topic_frame_not_blank(self, renderer):
        state = {
            "mode": "topic",
            "question_text": "",
            "options_data": [],
            "correct_option": "",
            "highlighted_option": "",
            "show_correct": False,
            "question_shown": False,
            "options_shown": False,
            "work_elements": {
                "concept_text": {
                    "type": "concept_text",
                    "heading": "What is Photosynthesis?",
                    "text": "Plants convert sunlight to food.",
                }
            },
            "step_text": "Definition",
            "narration": None,
            "current_time": 1.0,
            "topic_header": {"title": "Photosynthesis", "subtitle": "Biology"},
            "topic_shown": True,
        }
        frame = renderer.render_frame(state)
        assert _is_mostly_non_white(frame, threshold=0.1), \
            f"Topic frame appears blank — {_blank_ratio(frame)*100:.1f}% white pixels"

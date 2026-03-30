"""Unit tests for engine.sync — timeline building and state accumulation."""
import pytest
import sys
sys.path.insert(0, "/home/sravan/DSL")

from engine.sync import build_timeline, get_active_state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_seg(scene_idx, step_idx, start, end, text="spoken text"):
    """Build a fake audio segment dict as returned by engine.audio."""
    words = text.split()
    t = start
    wts = []
    for w in words:
        wts.append({"word": w, "start": round(t, 3), "end": round(t + 0.3, 3)})
        t += 0.3
    return {
        "scene_index": scene_idx,
        "step_index": step_idx,
        "start": start,
        "end": end,
        "word_timestamps": wts,
    }


# ── build_timeline ────────────────────────────────────────────────────────────

class TestBuildTimeline:
    def test_empty_scenes(self):
        tl = build_timeline({"scenes": []}, [])
        assert tl == []

    def test_single_scene_with_audio(self):
        q = {
            "scenes": [
                {
                    "type": "question",
                    "text": "What is 2+2?",
                    "audio": "What is two plus two?",
                    "render": {"action": "show", "target": "question_block"},
                }
            ]
        }
        segs = [_make_seg(0, None, 0.0, 3.0)]
        tl = build_timeline(q, segs)
        assert len(tl) == 1
        assert tl[0]["start"] == 0.0
        assert tl[0]["end"] == 3.0
        assert tl[0]["scene_type"] == "question"

    def test_steps_within_scene(self):
        q = {
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "Step 1",
                            "audio": "First step audio",
                            "render": {"action": "show", "target": "concept_text"},
                        },
                        {
                            "text": "Step 2",
                            "audio": "Second step audio",
                            "render": {"action": "show", "target": "highlight_box"},
                        },
                    ],
                }
            ]
        }
        segs = [
            _make_seg(0, 0, 0.0, 2.0),
            _make_seg(0, 1, 2.3, 4.5),
        ]
        tl = build_timeline(q, segs)
        assert len(tl) == 2
        assert tl[0]["step_index"] == 0
        assert tl[1]["step_index"] == 1
        assert tl[1]["start"] == 2.3

    def test_scene_without_audio_gets_duration(self):
        """Options scenes (no audio) get a 0.5-3s auto-duration."""
        q = {
            "scenes": [
                {
                    "type": "question",
                    "audio": "The question",
                    "render": {"action": "show", "target": "question_block"},
                },
                {
                    "type": "options",
                    "render": {"action": "show", "target": "options_grid"},
                    # No audio field
                },
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "Explanation",
                            "audio": "Here is the answer.",
                            "render": {"action": "show", "target": "concept_text"},
                        }
                    ],
                },
            ]
        }
        segs = [
            _make_seg(0, None, 0.0, 2.0),
            _make_seg(2, 0, 3.0, 5.5),
        ]
        tl = build_timeline(q, segs)
        # Should have 3 entries: question + options (auto) + concept step
        assert len(tl) == 3
        options_entry = tl[1]
        assert options_entry["scene_type"] == "options"
        assert options_entry["end"] > options_entry["start"]
        assert (options_entry["end"] - options_entry["start"]) <= 3.0

    def test_step_without_audio_gets_default_duration(self):
        q = {
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "Silent step",
                            "render": {"action": "show", "target": "concept_text"},
                            # No "audio"
                        }
                    ],
                }
            ]
        }
        tl = build_timeline(q, [])
        assert len(tl) == 1
        assert tl[0]["end"] - tl[0]["start"] == pytest.approx(1.5)

    def test_segment_lookup_by_index(self):
        """Segment matching must be index-based, not order-based."""
        q = {
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {"text": "A", "audio": "A audio", "render": {"action": "show", "target": "c"}},
                        {"text": "B", "audio": "B audio", "render": {"action": "show", "target": "c"}},
                    ],
                }
            ]
        }
        # Supply segments in reverse order
        segs = [
            _make_seg(0, 1, 5.0, 7.0),
            _make_seg(0, 0, 0.0, 3.0),
        ]
        tl = build_timeline(q, segs)
        assert len(tl) == 2
        # Step 0 should have start=0.0, step 1 should have start=5.0
        assert tl[0]["start"] == 0.0
        assert tl[1]["start"] == 5.0

    def test_missing_segment_skips_entry(self):
        """If no segment matches, step is skipped rather than crashing."""
        q = {
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {"text": "Step", "audio": "Step audio", "render": {"action": "show", "target": "c"}},
                    ],
                }
            ]
        }
        # Provide segment for wrong index
        segs = [_make_seg(99, 0, 0.0, 2.0)]
        tl = build_timeline(q, segs)
        assert tl == []

    def test_timeline_entries_have_required_keys(self):
        q = {
            "scenes": [
                {
                    "type": "question",
                    "text": "Q text",
                    "audio": "Q audio",
                    "render": {"action": "show", "target": "question_block"},
                }
            ]
        }
        segs = [_make_seg(0, None, 0.0, 2.0)]
        tl = build_timeline(q, segs)
        required = {"start", "end", "scene_index", "scene_type", "step_index", "render",
                    "text", "audio_text", "word_timestamps"}
        for entry in tl:
            assert required.issubset(entry.keys()), f"Missing keys: {required - entry.keys()}"


# ── get_active_state ──────────────────────────────────────────────────────────

class TestGetActiveState:
    def _make_mcq_question(self):
        return {
            "mode": "mcq",
            "question": {
                "text": "What is 2+2?",
                "options": [
                    {"key": "a", "value": "3"},
                    {"key": "b", "value": "4"},
                ],
                "correct": "b",
            },
            "scenes": [
                {
                    "type": "question",
                    "audio": "What is two plus two?",
                    "render": {"action": "show", "target": "question_block"},
                },
                {
                    "type": "options",
                    "render": {"action": "show", "target": "options_grid"},
                },
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "Answer",
                            "audio": "The answer is B.",
                            "render": {"action": "show", "target": "final_answer"},
                        }
                    ],
                },
            ],
        }

    def _make_timeline(self, question):
        segs = [
            _make_seg(0, None, 0.0, 2.0, "What is two plus two?"),
            _make_seg(2, 0, 3.0, 5.0, "The answer is B."),
        ]
        return build_timeline(question, segs)

    def test_before_start_returns_empty_state(self):
        q = self._make_mcq_question()
        tl = self._make_timeline(q)
        state = get_active_state(tl, -1.0, q)
        assert not state["question_shown"]
        assert not state["options_shown"]

    def test_during_question_shows_question(self):
        q = self._make_mcq_question()
        tl = self._make_timeline(q)
        state = get_active_state(tl, 1.0, q)
        assert state["question_shown"]

    def test_after_options_shows_both(self):
        q = self._make_mcq_question()
        tl = self._make_timeline(q)
        # After the options scene fires
        state = get_active_state(tl, 2.5, q)
        assert state["question_shown"]
        assert state["options_shown"]

    def test_question_text_extracted_correctly(self):
        q = self._make_mcq_question()
        tl = self._make_timeline(q)
        state = get_active_state(tl, 1.0, q)
        assert state["question_text"] == "What is 2+2?"

    def test_options_data_extracted(self):
        q = self._make_mcq_question()
        tl = self._make_timeline(q)
        state = get_active_state(tl, 1.0, q)
        assert len(state["options_data"]) == 2
        assert state["options_data"][0]["key"] == "a"

    def test_correct_option_known(self):
        q = self._make_mcq_question()
        tl = self._make_timeline(q)
        state = get_active_state(tl, 1.0, q)
        assert state["correct_option"] == "b"

    def test_work_elements_accumulate(self):
        """Multiple concept_text elements with different targets should coexist."""
        q = {
            "mode": "mcq",
            "question": {"text": "Q", "options": [], "correct": "a"},
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "Eq",
                            "audio": "eq audio",
                            "render": {"action": "show", "target": "equation",
                                       "value": "2+2=4"},
                        },
                        {
                            "text": "Formula",
                            "audio": "formula audio",
                            "render": {"action": "show", "target": "formula_block",
                                       "value": "x=4"},
                        },
                    ],
                }
            ],
        }
        segs = [
            _make_seg(0, 0, 0.0, 2.0),
            _make_seg(0, 1, 2.5, 4.5),
        ]
        tl = build_timeline(q, segs)
        state = get_active_state(tl, 3.0, q)
        # Both elements should be visible
        assert "equation" in state["work_elements"]
        assert "formula_block" in state["work_elements"]

    def test_highlight_marks_element(self):
        q = {
            "mode": "mcq",
            "question": {"text": "Q", "options": [], "correct": "a"},
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "Show eq",
                            "audio": "show",
                            "render": {"action": "show", "target": "equation", "value": "x=5"},
                        },
                        {
                            "text": "Highlight eq",
                            "audio": "highlight",
                            "render": {"action": "highlight", "target": "equation"},
                        },
                    ],
                }
            ],
        }
        segs = [_make_seg(0, 0, 0.0, 1.0), _make_seg(0, 1, 1.5, 3.0)]
        tl = build_timeline(q, segs)
        state = get_active_state(tl, 2.0, q)
        assert state["work_elements"]["equation"]["highlighted"] is True

    def test_element_replace_same_target(self):
        """Second show on same target replaces first."""
        q = {
            "mode": "mcq",
            "question": {"text": "Q", "options": [], "correct": "a"},
            "scenes": [
                {
                    "type": "concept",
                    "steps": [
                        {
                            "text": "First",
                            "audio": "first",
                            "render": {"action": "show", "target": "equation", "value": "x=1"},
                        },
                        {
                            "text": "Second",
                            "audio": "second",
                            "render": {"action": "show", "target": "equation", "value": "x=2"},
                        },
                    ],
                }
            ],
        }
        segs = [_make_seg(0, 0, 0.0, 1.0), _make_seg(0, 1, 1.5, 3.0)]
        tl = build_timeline(q, segs)
        state = get_active_state(tl, 2.0, q)
        assert state["work_elements"]["equation"]["value"] == "x=2"

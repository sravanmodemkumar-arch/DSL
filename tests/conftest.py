"""Shared fixtures for all tests."""
import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# ── Minimal valid question JSON for use in all tests ─────────────────────────

MINIMAL_MCQ_JSON = {
    "id": "test-q-001",
    "mode": "mcq",
    "question": {
        "text": "What is 2 + 2?",
        "audio": "What is two plus two?",
        "options": [
            {"key": "a", "value": "3"},
            {"key": "b", "value": "4"},
            {"key": "c", "value": "5"},
            {"key": "d", "value": "6"},
        ],
        "correct": "b",
    },
    "scenes": [
        {
            "type": "question",
            "text": "What is 2 + 2?",
            "audio": "What is two plus two?",
            "render": {"action": "show", "target": "question_block"},
        },
        {
            "type": "options",
            "audio": "Option A three. Option B four. Option C five. Option D six.",
            "render": {"action": "show", "target": "options_grid"},
        },
        {
            "type": "concept",
            "steps": [
                {
                    "text": "Simple Addition",
                    "audio": "Two plus two equals four.",
                    "render": {
                        "action": "show",
                        "target": "highlight_box",
                        "text": "2 + 2 = 4",
                        "color": "blue",
                    },
                },
                {
                    "text": "Verification",
                    "audio": "Count on fingers: one, two, three, four.",
                    "render": {
                        "action": "show",
                        "target": "concept_text",
                        "heading": "Count Method",
                        "items": ["Start at 2", "Add 2 more", "Result = 4"],
                    },
                },
            ],
        },
        {
            "type": "concept",
            "steps": [
                {
                    "text": "Answer",
                    "audio": "The answer is B, four.",
                    "render": {"action": "show", "target": "final_answer"},
                },
            ],
        },
    ],
    "thumbnail": {
        "title": "Basic Addition",
        "subtitle": "2 + 2 = ?",
        "badge": "Math",
        "topic": "Arithmetic",
        "highlights": ["Count method", "Addition rule"],
    },
    "meta": {
        "subject": "Mathematics",
        "topic": "Arithmetic",
        "subtopic": "Addition",
        "difficulty": "easy",
        "exam": "School",
        "grade": "Grade 1",
    },
}

MINIMAL_TOPIC_JSON = {
    "id": "test-topic-001",
    "mode": "topic",
    "topic_header": {
        "title": "Photosynthesis",
        "subtitle": "How plants make food",
    },
    "scenes": [
        {
            "type": "intro",
            "audio": "Today we learn about photosynthesis.",
            "render": {"action": "show", "target": "title_card",
                       "title": "Photosynthesis", "subtitle": "Food from sunlight"},
        },
        {
            "type": "concept",
            "steps": [
                {
                    "text": "Definition",
                    "audio": "Photosynthesis is how plants make food using sunlight.",
                    "render": {
                        "action": "show",
                        "target": "concept_text",
                        "heading": "What is Photosynthesis?",
                        "text": "Plants use sunlight, water, and CO2 to make glucose.",
                    },
                },
                {
                    "text": "Key Facts",
                    "audio": "Location is chloroplasts. Reactants are carbon dioxide and water.",
                    "render": {
                        "action": "show",
                        "target": "key_facts",
                        "heading": "Key Facts",
                        "facts": [
                            {"key": "Location", "value": "Chloroplasts"},
                            {"key": "Reactants", "value": "CO2 + H2O"},
                            {"key": "Products", "value": "Glucose + O2"},
                        ],
                    },
                },
            ],
        },
    ],
    "meta": {
        "subject": "Biology",
        "topic": "Plant Biology",
        "subtopic": "Photosynthesis",
        "difficulty": "medium",
        "exam": "CBSE",
        "grade": "Grade 10",
    },
}


@pytest.fixture(scope="session")
def app():
    """Create a Flask test app with in-memory SQLite."""
    import sys
    sys.path.insert(0, "/home/sravan/DSL")
    os.environ["TESTING"] = "1"

    # Use a temp dir for storage during tests
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TEST_STORAGE_DIR"] = tmpdir

        from app import create_app
        flask_app = create_app()
        flask_app.config.update({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "VIDEOS_DIR": os.path.join(tmpdir, "videos"),
            "JSON_DIR": os.path.join(tmpdir, "json"),
            "AUDIO_DIR": os.path.join(tmpdir, "audio"),
            "WTF_CSRF_ENABLED": False,
        })

        with flask_app.app_context():
            from models import db
            db.create_all()
            yield flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Database session with rollback after each test."""
    from models import db
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def sample_mcq():
    """Return a copy of the minimal MCQ JSON."""
    import copy
    return copy.deepcopy(MINIMAL_MCQ_JSON)


@pytest.fixture
def sample_topic():
    """Return a copy of the minimal topic JSON."""
    import copy
    return copy.deepcopy(MINIMAL_TOPIC_JSON)


@pytest.fixture
def mock_tts():
    """Mock edge_tts to avoid network calls during tests."""
    import io

    def fake_generate_audio(text, output_path, voice="en-IN-NeerjaNeural"):
        # Write a tiny valid MP3 header (silence)
        # 44-byte ID3 header + minimal MPEG frame
        silence = bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MPEG frame header
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ] * 100)
        with open(output_path, "wb") as f:
            f.write(silence)
        # Return fake word timestamps
        words = text.split()
        timestamps = []
        t = 0.0
        for word in words[:20]:  # limit for speed
            timestamps.append({"word": word, "start": round(t, 3), "end": round(t + 0.3, 3)})
            t += 0.3
        return timestamps

    with patch("engine.audio._generate_edge_tts", side_effect=fake_generate_audio) as mock:
        yield mock


@pytest.fixture
def renderer():
    """Create a FrameRenderer at reduced resolution for fast tests."""
    import sys
    sys.path.insert(0, "/home/sravan/DSL")
    from engine.renderer import FrameRenderer
    return FrameRenderer(width=640, height=360)

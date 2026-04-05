import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app, notes_index

TEST_TOKEN = "tok_test123"
TEST_ADMIN = "admin_test_secret"


@pytest.fixture
def tmp_notes(tmp_path, monkeypatch):
    """Temporär notes-mapp för varje test."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / ".trash").mkdir()
    monkeypatch.setattr("backend.main.NOTES_PATH", notes_dir)
    monkeypatch.setattr("backend.main.TRASH_PATH", notes_dir / ".trash")
    # Redirect token file to a temp path so tests never touch the real tokens.json
    tmp_tokens = tmp_path / "tokens.json"
    tmp_tokens.write_text('{"tokens": []}')
    monkeypatch.setattr("backend.main.TOKENS_FILE", tmp_tokens)
    notes_index.clear()
    return notes_dir


@pytest.fixture
def client(tmp_notes, monkeypatch):
    """FastAPI-testklient med autentisering."""
    monkeypatch.setenv("ADMIN_SECRET", TEST_ADMIN)
    monkeypatch.setattr("backend.main.TOKENS", [
        {"name": "test", "token": TEST_TOKEN, "created_at": "2025-04-03T10:00:00"}
    ])
    return TestClient(app)


@pytest.fixture
def auth(client):
    """Headers med giltig token."""
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def admin_auth():
    return {"Authorization": f"Bearer {TEST_ADMIN}"}

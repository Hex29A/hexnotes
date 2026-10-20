"""Tests for ephemeral notes (expires_at / ttl_hours)."""
from datetime import datetime, timedelta, UTC


def test_create_with_ttl_sets_expires_at(client, auth):
    r = client.post("/api/notes", json={"content": "glom snart", "ttl_hours": 24}, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["expires_at"] is not None
    exp = datetime.fromisoformat(data["expires_at"])
    remaining = exp - datetime.now(UTC)
    assert timedelta(hours=23) < remaining <= timedelta(hours=24)


def test_create_without_ttl_no_expires(client, auth):
    r = client.post("/api/notes", json={"content": "vanlig not"}, headers=auth)
    assert r.json()["expires_at"] is None


def test_expires_at_written_to_frontmatter(client, auth, tmp_notes):
    r = client.post("/api/notes", json={"content": "fm-test", "ttl_hours": 48}, headers=auth)
    note_id = r.json()["id"]
    raw = (tmp_notes / f"{note_id}.md").read_text()
    assert "expires_at:" in raw


def test_expires_at_survives_update(client, auth):
    r = client.post("/api/notes", json={"content": "v1", "ttl_hours": 48}, headers=auth)
    note_id = r.json()["id"]
    exp_before = r.json()["expires_at"]
    r2 = client.patch(f"/api/notes/{note_id}", json={"content": "v2\n#tag"}, headers=auth)
    assert r2.status_code == 200
    assert r2.json()["expires_at"] == exp_before


def test_sweep_moves_expired_to_trash(client, auth, tmp_notes):
    from backend.main import build_index, _sweep_expired, invalidate
    r = client.post("/api/notes", json={"content": "redan utgangen"}, headers=auth)
    note_id = r.json()["id"]
    # Write an already expired expires_at straight into the file
    path = tmp_notes / f"{note_id}.md"
    nl = chr(10)
    raw = path.read_text().replace('---' + nl, '---' + nl + 'expires_at: 2000-01-01T00:00:00+00:00' + nl, 1)
    path.write_text(raw)
    build_index()
    n = _sweep_expired()
    assert n >= 1
    assert (tmp_notes / ".trash" / f"{note_id}").exists() or any(tmp_notes.glob(".trash/*"))


# === Regression: the sweep used to compare timestamps as strings ===

def test_ttl_note_survives_until_its_ttl(client, auth, tmp_notes):
    """A note whose TTL runs out later the same UTC day must not be swept.

    The bug: expires_at was written unquoted, YAML gave back a datetime whose
    str() is space-separated, and the string comparison with isoformat() let
    " " (0x20) win over "T" (0x54). Every ephemeral note died at midnight UTC.
    """
    from backend.main import _sweep_expired
    now = datetime.now(UTC)
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    if end_of_day <= now:
        end_of_day += timedelta(days=1)
    hours = max(1, int((end_of_day - now).total_seconds() // 3600))

    r = client.post("/api/notes", json={"content": "lever an", "ttl_hours": hours}, headers=auth)
    note_id = r.json()["id"]
    assert _sweep_expired() == 0
    assert (tmp_notes / f"{note_id}.md").exists(), "the note was swept before its TTL"


def test_expires_at_is_iso_8601(client, auth):
    """new Date() in the frontend needs "T", not a space — otherwise Safari
    gives Invalid Date and the countdown shows NaN."""
    r = client.post("/api/notes", json={"content": "iso", "ttl_hours": 6}, headers=auth)
    exp = r.json()["expires_at"]
    assert " " not in exp, f"expires_at is not ISO 8601: {exp!r}"
    datetime.fromisoformat(exp)


def test_expires_at_stays_iso_through_a_write(client, auth):
    """The format must survive the YAML round trip, not just the first response."""
    r = client.post("/api/notes", json={"content": "v1", "ttl_hours": 6}, headers=auth)
    note_id = r.json()["id"]
    r2 = client.patch(f"/api/notes/{note_id}", json={"content": "v2"}, headers=auth)
    assert " " not in r2.json()["expires_at"]
    r3 = client.post(f"/api/notes/{note_id}/pin", headers=auth)
    assert " " not in r3.json()["expires_at"]


def test_sweep_keeps_note_with_unreadable_expiry(client, auth, tmp_notes):
    """An unreadable expires_at means "don't know" — the note must survive."""
    from backend.main import build_index, _sweep_expired
    r = client.post("/api/notes", json={"content": "skrap"}, headers=auth)
    note_id = r.json()["id"]
    path = tmp_notes / f"{note_id}.md"
    nl = chr(10)
    path.write_text(path.read_text().replace('---' + nl, '---' + nl + 'expires_at: inte-en-tid' + nl, 1))
    build_index()
    assert _sweep_expired() == 0
    assert path.exists()

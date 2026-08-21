"""Tester för ephemeral notes (expires_at / ttl_hours)."""
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
    # Skriv in ett redan utgånget expires_at direkt i filen
    path = tmp_notes / f"{note_id}.md"
    nl = chr(10)
    raw = path.read_text().replace('---' + nl, '---' + nl + 'expires_at: 2000-01-01T00:00:00+00:00' + nl, 1)
    path.write_text(raw)
    build_index()
    n = _sweep_expired()
    assert n >= 1
    assert (tmp_notes / ".trash" / f"{note_id}").exists() or any(tmp_notes.glob(".trash/*"))

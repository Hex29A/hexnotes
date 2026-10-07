"""New tests for v1.20: ephemeral in the API + ordering."""
import re


def test_list_includes_expires_at(client, auth):
    r = client.post("/api/notes", json={"content": "syns i listan", "ttl_hours": 24}, headers=auth)
    assert r.status_code == 200
    lst = client.get("/api/notes", headers=auth).json()
    mine = [n for n in lst if n["id"] == r.json()["id"]]
    assert mine and mine[0]["expires_at"] is not None
    # expires_at must be in the future (live, not expired)
    from datetime import datetime, UTC
    assert datetime.fromisoformat(mine[0]["expires_at"]) > datetime.now(UTC)


def test_expired_note_excluded_from_live_section(client, auth, tmp_notes):
    """A note with an expired expires_at must not count as 'live ephemeral'
    (the frontend filters on expires_at > now; the sweep removes it later)."""
    from datetime import datetime, timedelta, UTC
    from backend.main import build_index
    r = client.post("/api/notes", json={"content": "snart borta"}, headers=auth)
    nid = r.json()["id"]
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    path = tmp_notes / f"{nid}.md"
    nl = chr(10)
    raw = path.read_text().replace('---' + nl, '---' + nl + f'expires_at: {past}' + nl, 1)
    path.write_text(raw)
    build_index()
    lst = client.get("/api/notes", headers=auth).json()
    mine = [n for n in lst if n["id"] == nid]
    assert mine and datetime.fromisoformat(mine[0]["expires_at"]) <= datetime.now(UTC)


def test_health_reports_version(client):
    r = client.get("/health")
    assert re.fullmatch(r"\d+\.\d+", r.json()["version"])

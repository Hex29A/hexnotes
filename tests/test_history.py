# === Versionshistorik ===
import re


def _create(client, auth, content, filename="hist.md"):
    return client.post("/api/notes", json={"content": content, "filename": filename}, headers=auth).json()


def test_history_requires_auth(client):
    r = client.get("/api/notes/whatever/history")
    assert r.status_code == 401


def test_history_note_not_found_returns_404(client, auth):
    r = client.get("/api/notes/finns-inte/history", headers=auth)
    assert r.status_code == 404


def test_history_empty_for_new_note(client, auth):
    created = _create(client, auth, "Hej")
    r = client.get(f"/api/notes/{created['id']}/history", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_patch_creates_history_version(client, auth, tmp_notes):
    created = _create(client, auth, "Version ett")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Version två"}, headers=auth)
    r = client.get(f"/api/notes/{created['id']}/history", headers=auth)
    versions = r.json()
    assert len(versions) == 1
    assert versions[0]["preview"] == "Version ett"
    assert (tmp_notes / ".history" / created["id"]).is_dir()


def test_history_sorted_newest_first(client, auth):
    created = _create(client, auth, "Ett")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Två"}, headers=auth)
    client.patch(f"/api/notes/{created['id']}", json={"content": "Tre"}, headers=auth)
    versions = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()
    assert [v["preview"] for v in versions] == ["Två", "Ett"]


def test_history_entry_fields(client, auth):
    created = _create(client, auth, "Version ett")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Version två"}, headers=auth)
    entry = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()[0]
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}$", entry["version"])
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", entry["timestamp"])
    assert "preview" in entry


def test_get_specific_version_returns_content(client, auth):
    created = _create(client, auth, "Version ett")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Version två"}, headers=auth)
    version = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()[0]["version"]
    r = client.get(f"/api/notes/{created['id']}/history/{version}", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["content"] == "Version ett"
    assert data["version"] == version


def test_get_version_content_excludes_frontmatter(client, auth):
    created = _create(client, auth, "Text #docker")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Nytt"}, headers=auth)
    version = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()[0]["version"]
    r = client.get(f"/api/notes/{created['id']}/history/{version}", headers=auth)
    assert "---" not in r.json()["content"]


def test_get_version_not_found_returns_404(client, auth):
    created = _create(client, auth, "Text")
    r = client.get(f"/api/notes/{created['id']}/history/2020-01-01T00-00-00-000000", headers=auth)
    assert r.status_code == 404


def test_get_version_invalid_name_returns_404(client, auth):
    created = _create(client, auth, "Text")
    r = client.get(f"/api/notes/{created['id']}/history/inte-en-version", headers=auth)
    assert r.status_code == 404


def test_patch_unchanged_content_creates_no_version(client, auth):
    created = _create(client, auth, "Samma text")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Samma text"}, headers=auth)
    versions = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()
    assert versions == []


def test_trash_via_empty_patch_creates_snapshot(client, auth, tmp_notes):
    created = _create(client, auth, "Snart borta")
    client.patch(f"/api/notes/{created['id']}", json={"content": ""}, headers=auth)
    hist_dir = tmp_notes / ".history" / created["id"]
    snapshots = list(hist_dir.glob("*.md"))
    assert len(snapshots) == 1
    assert "Snart borta" in snapshots[0].read_text()


def test_rename_moves_history(client, auth, tmp_notes):
    created = _create(client, auth, "Version ett", filename="gammal.md")
    client.patch("/api/notes/gammal", json={"content": "Version två"}, headers=auth)
    client.post("/api/notes/gammal/rename", json={"new_filename": "ny.md"}, headers=auth)
    versions = client.get("/api/notes/ny/history", headers=auth).json()
    assert len(versions) == 1
    assert versions[0]["preview"] == "Version ett"
    assert not (tmp_notes / ".history" / "gammal").exists()


def test_restore_via_patch_adds_new_version(client, auth):
    """Återställning görs som en vanlig PATCH med gammalt innehåll."""
    created = _create(client, auth, "Version ett")
    client.patch(f"/api/notes/{created['id']}", json={"content": "Version två"}, headers=auth)
    version = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()[0]["version"]
    old = client.get(f"/api/notes/{created['id']}/history/{version}", headers=auth).json()["content"]
    r = client.patch(f"/api/notes/{created['id']}", json={"content": old}, headers=auth)
    assert r.status_code == 200
    assert r.json()["content"] == "Version ett"
    versions = client.get(f"/api/notes/{created['id']}/history", headers=auth).json()
    assert [v["preview"] for v in versions] == ["Version två", "Version ett"]

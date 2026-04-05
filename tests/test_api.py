# === Auth ===

def test_no_token_returns_401(client):
    r = client.get("/api/notes")
    assert r.status_code == 401


def test_wrong_token_returns_401(client):
    r = client.get("/api/notes", headers={"Authorization": "Bearer fel_token"})
    assert r.status_code == 401


def test_valid_token_returns_200(client, auth):
    r = client.get("/api/notes", headers=auth)
    assert r.status_code == 200


def test_admin_endpoint_requires_admin_secret(client, auth):
    r = client.get("/admin/tokens", headers=auth)
    assert r.status_code == 401


def test_admin_endpoint_with_admin_secret(client, admin_auth):
    r = client.get("/admin/tokens", headers=admin_auth)
    assert r.status_code == 200


# === Create note (POST) ===

def test_create_note_basic(client, auth):
    r = client.post("/api/notes", json={"content": "Hej världen\n#test"}, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["tags"] == ["test"]


def test_create_note_custom_filename(client, auth):
    r = client.post("/api/notes", json={"content": "Ideas", "filename": "ideas.md"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["filename"] == "ideas.md"


def test_create_note_collision_returns_409(client, auth):
    client.post("/api/notes", json={"content": "First", "filename": "ideas.md"}, headers=auth)
    r = client.post("/api/notes", json={"content": "Second", "filename": "ideas.md"}, headers=auth)
    assert r.status_code == 409


def test_create_note_generates_date_filename(client, auth):
    r = client.post("/api/notes", json={"content": "Docker tips\n#docker"}, headers=auth)
    import re
    assert re.match(r"\d{4}-\d{2}-\d{2}\.md", r.json()["filename"])


def test_create_note_writes_frontmatter(client, auth, tmp_notes):
    r = client.post("/api/notes", json={"content": "Test\n#docker"}, headers=auth)
    note_id = r.json()["id"]
    raw = (tmp_notes / f"{note_id}.md").read_text()
    assert "tags:" in raw
    assert "docker" in raw


def test_create_note_content_excludes_frontmatter(client, auth):
    r = client.post("/api/notes", json={"content": "Test\n#docker"}, headers=auth)
    assert "---" not in r.json()["content"]


# === Get note (GET) ===

def test_get_note(client, auth):
    created = client.post("/api/notes", json={"content": "Hej"}, headers=auth).json()
    r = client.get(f"/api/notes/{created['id']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["content"] == "Hej"


def test_get_note_not_found(client, auth):
    r = client.get("/api/notes/finns-inte", headers=auth)
    assert r.status_code == 404


# === Update note (PATCH) ===

def test_patch_updates_content(client, auth):
    created = client.post("/api/notes", json={"content": "Original"}, headers=auth).json()
    r = client.patch(f"/api/notes/{created['id']}", json={"content": "Uppdaterad"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["content"] == "Uppdaterad"


def test_patch_updates_tags_in_frontmatter(client, auth, tmp_notes):
    created = client.post("/api/notes", json={"content": "Text #python"}, headers=auth).json()
    client.patch(f"/api/notes/{created['id']}", json={"content": "Text #rust"}, headers=auth)
    raw = (tmp_notes / f"{created['id']}.md").read_text()
    assert "rust" in raw
    assert "python" not in raw


def test_patch_empty_content_moves_to_trash(client, auth, tmp_notes):
    created = client.post("/api/notes", json={"content": "Text"}, headers=auth).json()
    r = client.patch(f"/api/notes/{created['id']}", json={"content": ""}, headers=auth)
    assert r.status_code == 204
    assert not (tmp_notes / f"{created['id']}.md").exists()
    assert (tmp_notes / ".trash" / f"{created['id']}.md").exists()


def test_patch_does_not_change_filename(client, auth):
    created = client.post("/api/notes", json={"content": "Text", "filename": "ideas.md"}, headers=auth).json()
    r = client.patch("/api/notes/ideas", json={"content": "Nytt"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["filename"] == "ideas.md"


# === Rename (POST /rename) ===

def test_rename_note(client, auth):
    created = client.post("/api/notes", json={"content": "Text", "filename": "old.md"}, headers=auth).json()
    r = client.post("/api/notes/old/rename", json={"new_filename": "new.md"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["filename"] == "new.md"
    assert r.json()["id"] == "new"


def test_rename_collision_returns_409(client, auth):
    client.post("/api/notes", json={"content": "A", "filename": "a.md"}, headers=auth)
    client.post("/api/notes", json={"content": "B", "filename": "b.md"}, headers=auth)
    r = client.post("/api/notes/a/rename", json={"new_filename": "b.md"}, headers=auth)
    assert r.status_code == 409


def test_rename_adds_md_extension(client, auth):
    client.post("/api/notes", json={"content": "Text", "filename": "old.md"}, headers=auth)
    r = client.post("/api/notes/old/rename", json={"new_filename": "new"}, headers=auth)
    assert r.json()["filename"] == "new.md"


def test_rename_updates_index(client, auth):
    client.post("/api/notes", json={"content": "Text", "filename": "old.md"}, headers=auth)
    client.post("/api/notes/old/rename", json={"new_filename": "new.md"}, headers=auth)
    r_old = client.get("/api/notes/old", headers=auth)
    assert r_old.status_code == 404
    r_new = client.get("/api/notes/new", headers=auth)
    assert r_new.status_code == 200


# === Delete note (DELETE) ===

def test_delete_moves_to_trash(client, auth, tmp_notes):
    created = client.post("/api/notes", json={"content": "Text", "filename": "del.md"}, headers=auth).json()
    r = client.delete(f"/api/notes/{created['id']}", headers=auth)
    assert r.status_code == 200
    assert not (tmp_notes / "del.md").exists()
    assert (tmp_notes / ".trash" / "del.md").exists()


def test_delete_not_found_returns_404(client, auth):
    r = client.delete("/api/notes/finns-inte", headers=auth)
    assert r.status_code == 404


def test_delete_trash_collision_overwrites(client, auth, tmp_notes):
    client.post("/api/notes", json={"content": "First", "filename": "del.md"}, headers=auth)
    client.delete("/api/notes/del", headers=auth)
    client.post("/api/notes", json={"content": "Second", "filename": "del.md"}, headers=auth)
    r = client.delete("/api/notes/del", headers=auth)
    assert r.status_code == 200
    trash_content = (tmp_notes / ".trash" / "del.md").read_text()
    assert "Second" in trash_content


# === Search ===

def test_search_by_content(client, auth):
    client.post("/api/notes", json={"content": "Proxmox setup guide"}, headers=auth)
    client.post("/api/notes", json={"content": "Docker tips"}, headers=auth)
    r = client.get("/api/notes?q=proxmox", headers=auth)
    results = r.json()
    assert len(results) == 1
    assert "proxmox" in results[0]["content"].lower()


def test_search_by_tag(client, auth):
    client.post("/api/notes", json={"content": "Text #docker"}, headers=auth)
    client.post("/api/notes", json={"content": "Text #linux"}, headers=auth)
    r = client.get("/api/notes?tag=docker", headers=auth)
    results = r.json()
    assert all("docker" in n["tags"] for n in results)


def test_search_case_insensitive(client, auth):
    client.post("/api/notes", json={"content": "PROXMOX guide"}, headers=auth)
    r = client.get("/api/notes?q=proxmox", headers=auth)
    assert len(r.json()) == 1


def test_search_empty_returns_all(client, auth):
    client.post("/api/notes", json={"content": "A"}, headers=auth)
    client.post("/api/notes", json={"content": "B"}, headers=auth)
    r = client.get("/api/notes", headers=auth)
    assert len(r.json()) == 2


# === Token management (admin) ===

def test_create_token(client, admin_auth):
    r = client.post("/admin/tokens", json={"name": "nyenhet"}, headers=admin_auth)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "nyenhet"
    assert "token" in data
    assert data["token"].startswith("tok_")


def test_created_token_is_immediately_valid(client, admin_auth):
    r = client.post("/admin/tokens", json={"name": "newdevice"}, headers=admin_auth)
    new_token = r.json()["token"]
    r2 = client.get("/api/notes", headers={"Authorization": f"Bearer {new_token}"})
    assert r2.status_code == 200


def test_revoke_token(client, admin_auth):
    client.post("/admin/tokens", json={"name": "temp"}, headers=admin_auth)
    r = client.delete("/admin/tokens/temp", headers=admin_auth)
    assert r.status_code == 200


def test_revoked_token_returns_401(client, admin_auth):
    r = client.post("/admin/tokens", json={"name": "temp"}, headers=admin_auth)
    token = r.json()["token"]
    client.delete("/admin/tokens/temp", headers=admin_auth)
    r2 = client.get("/api/notes", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 401


def test_list_tokens_hides_values(client, admin_auth):
    r = client.get("/admin/tokens", headers=admin_auth)
    for t in r.json()["tokens"]:
        assert "token" not in t


# === Health ===

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "notes_count" in r.json()

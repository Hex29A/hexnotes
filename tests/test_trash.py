# === Papperskorg ===


def _create(client, auth, content, filename="t.md"):
    return client.post("/api/notes", json={"content": content, "filename": filename}, headers=auth).json()


def _trash_first(client, auth):
    return client.get("/api/trash", headers=auth).json()[0]


def test_trash_requires_auth(client):
    assert client.get("/api/trash").status_code == 401
    assert client.post("/api/trash/x.md/restore").status_code == 401
    assert client.delete("/api/trash/x.md").status_code == 401


def test_trash_empty_list(client, auth):
    r = client.get("/api/trash", headers=auth)
    assert r.status_code == 200
    assert r.json() == []


def test_deleted_note_appears_in_trash(client, auth):
    _create(client, auth, "Hemlig text", filename="kastad.md")
    client.delete("/api/notes/kastad", headers=auth)
    entries = client.get("/api/trash", headers=auth).json()
    assert len(entries) == 1
    assert entries[0]["original_filename"] == "kastad.md"
    assert entries[0]["preview"] == "Hemlig text"
    assert "deleted_at" in entries[0]


def test_get_trash_entry_content(client, auth):
    _create(client, auth, "Innehåll här", filename="kastad.md")
    client.delete("/api/notes/kastad", headers=auth)
    name = _trash_first(client, auth)["name"]
    r = client.get(f"/api/trash/{name}", headers=auth)
    assert r.status_code == 200
    assert r.json()["content"] == "Innehåll här"
    assert "---" not in r.json()["content"]


def test_restore_brings_note_back(client, auth, tmp_notes):
    _create(client, auth, "Räddad text", filename="raddad.md")
    client.delete("/api/notes/raddad", headers=auth)
    name = _trash_first(client, auth)["name"]
    r = client.post(f"/api/trash/{name}/restore", headers=auth)
    assert r.status_code == 200
    assert r.json()["filename"] == "raddad.md"
    assert r.json()["content"] == "Räddad text"
    # Borta ur papperskorgen, tillbaka i index
    assert client.get("/api/trash", headers=auth).json() == []
    assert client.get("/api/notes/raddad", headers=auth).status_code == 200
    assert (tmp_notes / "raddad.md").exists()


def test_restore_never_overwrites_live_note(client, auth):
    _create(client, auth, "Gammal", filename="krock.md")
    client.delete("/api/notes/krock", headers=auth)
    _create(client, auth, "Ny levande", filename="krock.md")
    name = _trash_first(client, auth)["name"]
    r = client.post(f"/api/trash/{name}/restore", headers=auth)
    assert r.status_code == 200
    assert r.json()["filename"] == "krock-2.md"
    # Den levande noten är orörd
    assert client.get("/api/notes/krock", headers=auth).json()["content"] == "Ny levande"


def test_history_follows_note_to_trash_and_back(client, auth):
    _create(client, auth, "Version ett", filename="medhist.md")
    client.patch("/api/notes/medhist", json={"content": "Version två"}, headers=auth)
    client.delete("/api/notes/medhist", headers=auth)
    name = _trash_first(client, auth)["name"]
    client.post(f"/api/trash/{name}/restore", headers=auth)
    versions = client.get("/api/notes/medhist/history", headers=auth).json()
    # Snapshot vid patch + slutlig snapshot vid radering
    assert [v["preview"] for v in versions] == ["Version två", "Version ett"]


def test_new_note_with_same_name_gets_clean_history(client, auth):
    _create(client, auth, "Gammalt innehåll", filename="ideas.md")
    client.patch("/api/notes/ideas", json={"content": "Gammalt v2"}, headers=auth)
    client.delete("/api/notes/ideas", headers=auth)
    _create(client, auth, "Helt ny not", filename="ideas.md")
    versions = client.get("/api/notes/ideas/history", headers=auth).json()
    assert versions == []


def test_purge_removes_file_and_history(client, auth, tmp_notes):
    _create(client, auth, "Topphemligt api-nyckel-innehåll", filename="hemlis.md")
    client.patch("/api/notes/hemlis", json={"content": "Redigerad"}, headers=auth)
    client.delete("/api/notes/hemlis", headers=auth)
    name = _trash_first(client, auth)["name"]
    r = client.delete(f"/api/trash/{name}", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "purged"
    # Inget spår kvar på disk — varken fil eller historik
    leftovers = [
        p for p in tmp_notes.rglob("*")
        if p.is_file() and "hemlis" in p.name
    ]
    assert leftovers == []
    assert client.get("/api/trash", headers=auth).json() == []


def test_trash_name_traversal_rejected(client, auth):
    # %2F-varianten normaliseras redan av routern (405/404), övriga ska ge 404
    for bad in ["..%2F..%2Ftokens.json", "..evil.md", ".hidden.md", "ingen-md-fil"]:
        assert client.get(f"/api/trash/{bad}", headers=auth).status_code in (404, 405)
        assert client.post(f"/api/trash/{bad}/restore", headers=auth).status_code in (404, 405)
        assert client.delete(f"/api/trash/{bad}", headers=auth).status_code in (404, 405)


def test_trash_entry_not_found(client, auth):
    r = client.post("/api/trash/2020-01-01T00-00-00-000000__x.md/restore", headers=auth)
    assert r.status_code == 404


def test_legacy_trash_file_listed_and_restorable(client, auth, tmp_notes):
    # Filer från tiden före timestampade namn ligger som <namn>.md direkt
    (tmp_notes / ".trash" / "gammal-fil.md").write_text("Legacy-innehåll", encoding="utf-8")
    entries = client.get("/api/trash", headers=auth).json()
    assert entries[0]["original_filename"] == "gammal-fil.md"
    r = client.post("/api/trash/gammal-fil.md/restore", headers=auth)
    assert r.status_code == 200
    assert r.json()["filename"] == "gammal-fil.md"
    assert client.get("/api/notes/gammal-fil", headers=auth).json()["content"] == "Legacy-innehåll"


def test_trash_sorted_newest_first(client, auth):
    _create(client, auth, "Första", filename="a.md")
    client.delete("/api/notes/a", headers=auth)
    _create(client, auth, "Andra", filename="b.md")
    client.delete("/api/notes/b", headers=auth)
    entries = client.get("/api/trash", headers=auth).json()
    assert [e["original_filename"] for e in entries] == ["b.md", "a.md"]

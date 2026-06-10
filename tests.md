# tests.md – HexNotes

> Testspecifikation för HexNotes. Körs separat från byggspecen (agents.md).
> Fokus: backend unit-tester och API-integrationstester. Frontend-tester är out of scope för v1.

---

## Testmiljö

```
tests/
├── conftest.py          # pytest fixtures: tmp notes-mapp, test-klient
├── test_unit.py         # Unit-tester för ren logik
├── test_api.py          # Integrationstester för API-endpoints
├── test_history.py      # Versionshistorik: snapshots, restore, rename-migrering
└── test_trash.py        # Papperskorg: lista, återställ, permanent radering
```

> **Obs:** Detta dokument är den ursprungliga testspecifikationen. Sviten har
> vuxit sedan dess (86 tester) — `tests/`-katalogen är källan till sanning,
> och README beskriver vad varje fil täcker.

Kör lokalt inuti Docker:

```bash
docker compose run --rm hexnotes pytest tests/ -v
```

Eller som ett separat steg i byggordningen:

```bash
docker compose run --rm hexnotes pytest tests/ -v --tb=short
```

Inga externa beroenden – testerna använder en temporär notes-mapp i minnet och en in-process FastAPI-testklient.

---

## Fixtures (`conftest.py`)

```python
import pytest
import tempfile
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
```

---

## Unit-tester (`test_unit.py`)

Testar ren logik utan nätverk eller filsystem.

### Slug-generering

```python
from backend.main import generate_slug

def test_slug_basic():
    assert generate_slug("Docker compose tips") == "docker-compose-tips"

def test_slug_strips_tags():
    assert generate_slug("Min anteckning #docker #linux") == "min-anteckning"

def test_slug_strips_special_chars():
    assert generate_slug("Hej! Vad händer?") == "hej-vad-händer"

def test_slug_max_length():
    long = "a" * 100
    assert len(generate_slug(long)) <= 60

def test_slug_empty_returns_untitled():
    assert generate_slug("") == "untitled"
    assert generate_slug("   ") == "untitled"

def test_slug_only_tags_returns_untitled():
    assert generate_slug("#docker #linux") == "untitled"
```

### Tag-extrahering

```python
from backend.main import extract_tags

def test_extract_tags_basic():
    assert extract_tags("hello #docker #linux") == ["docker", "linux"]

def test_extract_tags_none():
    assert extract_tags("ingen taggar här") == []

def test_extract_tags_deduplication():
    assert extract_tags("#docker #docker #linux") == ["docker", "linux"]

def test_extract_tags_ignores_urls():
    # Ska inte extrahera fragment-identifierare ur URLs
    assert "example" not in extract_tags("https://example.com/#section")

def test_extract_tags_case_preserved():
    assert extract_tags("#Docker") == ["Docker"]
```

### Frontmatter-parsning

```python
from backend.main import parse_frontmatter, strip_frontmatter

FRONTMATTER_DOC = """---
tags: [docker, linux]
created: 2025-04-03
---
Innehåll här
"""

def test_parse_frontmatter_tags():
    meta, _ = parse_frontmatter(FRONTMATTER_DOC)
    assert meta["tags"] == ["docker", "linux"]

def test_parse_frontmatter_created():
    meta, _ = parse_frontmatter(FRONTMATTER_DOC)
    assert meta["created"] == "2025-04-03"

def test_strip_frontmatter_returns_content():
    _, body = parse_frontmatter(FRONTMATTER_DOC)
    assert body.strip() == "Innehåll här"

def test_parse_frontmatter_missing():
    meta, body = parse_frontmatter("Ingen frontmatter här\n#docker")
    assert meta == {}
    assert "Ingen frontmatter" in body

def test_parse_frontmatter_empty_tags():
    doc = "---\ntags: []\ncreated: 2025-04-03\n---\nInnehåll"
    meta, _ = parse_frontmatter(doc)
    assert meta["tags"] == []
```

### created_at från filnamn

```python
from backend.main import created_at_from_filename

def test_created_at_datumprefix():
    assert created_at_from_filename("2025-04-03-docker-tips.md") == "2025-04-03"

def test_created_at_timeless():
    # Tidlösa noter utan datumprefix
    assert created_at_from_filename("ideas.md") is None

def test_created_at_invalid_prefix():
    assert created_at_from_filename("notadate-docker.md") is None

def test_created_at_only_date():
    assert created_at_from_filename("2025-04-03.md") == "2025-04-03"
```

### Filnamnsvalidering

```python
from backend.main import sanitize_filename

def test_sanitize_adds_md_extension():
    assert sanitize_filename("ideas") == "ideas.md"

def test_sanitize_preserves_md():
    assert sanitize_filename("ideas.md") == "ideas.md"

def test_sanitize_strips_path_traversal():
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert ".." not in sanitize_filename("../../etc/passwd")

def test_sanitize_strips_leading_dot():
    # Ska inte skapa dolda filer
    assert not sanitize_filename(".hidden").startswith(".")
```

---

## API-integrationstester (`test_api.py`)

Testar endpoints end-to-end med en riktig FastAPI-testklient och temporär notes-mapp.

### Auth

```python
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
```

### Skapa note (POST)

```python
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

def test_create_note_generates_slug_from_content(client, auth):
    r = client.post("/api/notes", json={"content": "Docker tips\n#docker"}, headers=auth)
    assert "docker-tips" in r.json()["filename"]

def test_create_note_writes_frontmatter(client, auth, tmp_notes):
    r = client.post("/api/notes", json={"content": "Test\n#docker"}, headers=auth)
    note_id = r.json()["id"]
    raw = (tmp_notes / f"{note_id}.md").read_text()
    assert "tags:" in raw
    assert "docker" in raw

def test_create_note_content_excludes_frontmatter(client, auth):
    r = client.post("/api/notes", json={"content": "Test\n#docker"}, headers=auth)
    assert "---" not in r.json()["content"]
```

### Hämta note (GET)

```python
def test_get_note(client, auth):
    created = client.post("/api/notes", json={"content": "Hej"}, headers=auth).json()
    r = client.get(f"/api/notes/{created['id']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["content"] == "Hej"

def test_get_note_not_found(client, auth):
    r = client.get("/api/notes/finns-inte", headers=auth)
    assert r.status_code == 404
```

### Uppdatera note (PATCH)

```python
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
    r = client.patch("/api/notes/ideas", json={"content": "Nytt", "filename": "annat.md"}, headers=auth)
    # filename i body ignoreras – endast content uppdateras
    assert r.status_code == 200
    assert r.json()["filename"] == "ideas.md"
```

### Rename (POST /rename)

```python
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
    # Gammalt ID ska vara borta
    r_old = client.get("/api/notes/old", headers=auth)
    assert r_old.status_code == 404
    # Nytt ID ska finnas
    r_new = client.get("/api/notes/new", headers=auth)
    assert r_new.status_code == 200
```

### Radera note (DELETE)

```python
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
    # Skapa och radera "del.md" → hamnar i trash
    client.post("/api/notes", json={"content": "First", "filename": "del.md"}, headers=auth)
    client.delete("/api/notes/del", headers=auth)
    # Skapa ny "del.md" och radera igen → ska skriva över i trash
    client.post("/api/notes", json={"content": "Second", "filename": "del.md"}, headers=auth)
    r = client.delete("/api/notes/del", headers=auth)
    assert r.status_code == 200
    trash_content = (tmp_notes / ".trash" / "del.md").read_text()
    assert "Second" in trash_content
```

### Sökning

```python
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
```

### Token-hantering (admin)

```python
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
        assert "token" not in t  # token-värdet ska aldrig exponeras i lista
```

### Health

```python
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "notes_count" in r.json()
```

---

## Köra specifika tester

```bash
# Alla tester
docker compose run --rm hexnotes pytest tests/ -v

# Bara unit-tester
docker compose run --rm hexnotes pytest tests/test_unit.py -v

# Bara API-tester
docker compose run --rm hexnotes pytest tests/test_api.py -v

# Ett specifikt test
docker compose run --rm hexnotes pytest tests/test_api.py::test_rename_updates_index -v

# Med coverage-rapport
docker compose run --rm hexnotes pytest tests/ --cov=backend --cov-report=term-missing
```

---

## Requirements för tester

Lägg till i `requirements.txt`:

```
pytest
pytest-asyncio
httpx        # krävs av FastAPI TestClient
pytest-cov   # valfritt, för coverage
```

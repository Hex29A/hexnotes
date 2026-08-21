import asyncio
import json
import os
import re
import secrets
import shutil
import unicodedata
from datetime import datetime, date, UTC
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_VERSION = "1.20.3"  # bump minor for features, major for breaking changes — see CHANGELOG.md

NOTES_PATH = Path("/app/notes")
TRASH_PATH = NOTES_PATH / ".trash"
TOKENS_FILE = Path("/app/tokens.json")

app = FastAPI(title="HexNotes", version=APP_VERSION, docs_url="/docs", redoc_url=None)

# ---------------------------------------------------------------------------
# In-memory token list (source of truth at runtime)
# ---------------------------------------------------------------------------
TOKENS: list[dict] = []

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class NoteOut(BaseModel):
    id: str
    filename: str
    content: str
    tags: list[str]
    created_at: Optional[str]
    updated_at: str
    preview: str
    is_timeless: bool
    pinned: bool
    expires_at: Optional[str] = None
    snippet: Optional[str] = None

class NoteCreate(BaseModel):
    content: str = ""
    filename: Optional[str] = None
    ttl_hours: Optional[int] = None  # ephemeral note: auto-trash after N hours (24/48)

class NoteUpdate(BaseModel):
    content: str

class NoteRename(BaseModel):
    new_filename: str

class TrashEntryOut(BaseModel):
    name: str
    original_filename: str
    deleted_at: str
    preview: str

class TrashContentOut(BaseModel):
    name: str
    original_filename: str
    deleted_at: str
    content: str

class HistoryEntryOut(BaseModel):
    version: str
    timestamp: str
    preview: str

class HistoryVersionOut(BaseModel):
    version: str
    timestamp: str
    content: str

class TokenCreate(BaseModel):
    name: str

class TokenOut(BaseModel):
    name: str
    token: str
    created_at: str

# ---------------------------------------------------------------------------
# In-memory index
# ---------------------------------------------------------------------------
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
TAG_RE = re.compile(r"(?:^|(?<=\s))#([a-zA-Z0-9_\-åäöÅÄÖ]+)", re.MULTILINE)

notes_index: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Public helper functions (used by tests)
# ---------------------------------------------------------------------------

def created_at_from_filename(filename: str) -> Optional[str]:
    stem = filename.replace(".md", "") if filename.endswith(".md") else filename
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:-|$)", stem)
    return m.group(1) if m else None


def extract_tags(text: str) -> list[str]:
    return sorted(set(TAG_RE.findall(text)))


def strip_frontmatter(raw: str) -> str:
    m = FRONTMATTER_RE.match(raw)
    if m:
        return raw[m.end():]
    return raw


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(raw)
    meta = {}
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
    body = raw[m.end():] if m else raw
    return meta, body


def generate_slug(text: str, max_len: int = 60) -> str:
    text = TAG_RE.sub("", text)
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9åäö]+", "-", text)
    text = text.strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:max_len] if text else "untitled"


def sanitize_filename(filename: str) -> str:
    filename = filename.replace("\\", "/")
    filename = filename.split("/")[-1]
    filename = filename.replace("..", "")
    filename = filename.lstrip(".")
    if not filename or filename == ".md":
        filename = "untitled"
    if not filename.endswith(".md"):
        filename += ".md"
    return filename


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_frontmatter(tags: list[str], created: Optional[str], pinned: bool = False, expires_at: Optional[str] = None) -> str:
    lines = ["---"]
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append(f"created: {created if created else 'null'}")
    if pinned:
        lines.append("pinned: true")
    if expires_at:
        lines.append(f"expires_at: {expires_at}")
    lines.append("---")
    return chr(10).join(lines) + chr(10)


def _write_note_with_frontmatter(path: Path, content: str, created: Optional[str], pinned: bool = False, expires_at: Optional[str] = None):
    tags = extract_tags(content)
    fm = _build_frontmatter(tags, created, pinned, expires_at)
    path.write_text(fm + content, encoding="utf-8")



def parse_note(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta, content = parse_frontmatter(raw)

    stem = path.stem
    stat = path.stat()
    updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")

    date_str = created_at_from_filename(path.name)
    if date_str:
        created_at = date_str + "T00:00:00"
    elif meta.get("created"):
        created_at = str(meta["created"]) + "T00:00:00" if isinstance(meta["created"], date) else str(meta["created"])
    else:
        created_at = updated_at

    tags = extract_tags(content)
    pinned = bool(meta.get("pinned", False))
    expires_at = str(meta["expires_at"]) if meta.get("expires_at") else None

    first_line = ""
    for line in content.strip().splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break
    preview = first_line[:80] if first_line else ""

    return {
        "id": stem,
        "filename": path.name,
        "content": content,
        "tags": tags,
        "created_at": created_at,
        "updated_at": updated_at,
        "preview": preview,
        "is_timeless": date_str is None,
        "pinned": pinned,
        "expires_at": expires_at,
    }


def build_index():
    notes_index.clear()
    for f in sorted(NOTES_PATH.glob("*.md")):
        if f.name.startswith("."):
            continue
        try:
            notes_index[f.stem] = parse_note(f)
        except Exception:
            pass


def invalidate(note_id: str):
    p = NOTES_PATH / f"{note_id}.md"
    if p.exists():
        notes_index[note_id] = parse_note(p)


def invalidate_rename(old_id: str, new_id: str):
    notes_index.pop(old_id, None)
    p = NOTES_PATH / f"{new_id}.md"
    if p.exists():
        notes_index[new_id] = parse_note(p)


def invalidate_delete(note_id: str):
    notes_index.pop(note_id, None)


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------
HISTORY_DIRNAME = ".history"
VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}$")


def _history_dir(note_id: str) -> Path:
    return NOTES_PATH / HISTORY_DIRNAME / note_id


def _snapshot_note(note_id: str):
    """Spara nuvarande version av noten till .history/<note_id>/<timestamp>.md"""
    path = NOTES_PATH / f"{note_id}.md"
    if not path.exists():
        return
    hist = _history_dir(note_id)
    hist.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%f")
    (hist / f"{ts}.md").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def _version_timestamp(version: str) -> str:
    """2026-06-10T08-30-00-123456 → 2026-06-10T08:30:00 (UTC)"""
    date_part, time_part = version.split("T")
    h, m, s, _us = time_part.split("-")
    return f"{date_part}T{h}:{m}:{s}"


# ---------------------------------------------------------------------------
# Trash
# ---------------------------------------------------------------------------
TRASH_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6})__(.+\.md)$")


def _move_to_trash(note_id: str) -> str:
    """Flytta noten till papperskorgen med timestampat namn (skriver aldrig
    över) och ta historiken med till .trash/.history/. En sista snapshot tas
    först så att historiken är komplett."""
    path = NOTES_PATH / f"{note_id}.md"
    _snapshot_note(note_id)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%f")
    trash_name = f"{ts}__{path.name}"
    TRASH_PATH.mkdir(parents=True, exist_ok=True)
    path.rename(TRASH_PATH / trash_name)
    hist = _history_dir(note_id)
    if hist.is_dir():
        dest = TRASH_PATH / ".history" / f"{ts}__{note_id}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        hist.rename(dest)
    return trash_name


def _trash_entry_path(name: str) -> Path:
    """Validera trash-namn strikt och returnera sökvägen, annars 404."""
    if (
        "/" in name or "\\" in name or ".." in name
        or name.startswith(".") or not name.endswith(".md")
    ):
        raise HTTPException(status_code=404, detail="Not found in trash")
    p = TRASH_PATH / name
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Not found in trash")
    return p


def _trash_meta(p: Path) -> tuple[str, str]:
    """(ursprungligt filnamn, raderingstidpunkt) för en trash-fil.
    Filer från tiden före timestampade namn faller tillbaka på mtime."""
    m = TRASH_NAME_RE.match(p.name)
    if m:
        return m.group(2), _version_timestamp(m.group(1))
    mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return p.name, mtime


def _first_line(content: str) -> str:
    for line in content.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:80]
    return ""


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _load_tokens_from_file():
    global TOKENS
    try:
        data = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
        TOKENS[:] = data.get("tokens", [])
    except Exception:
        pass


def _save_tokens_to_file():
    try:
        TOKENS_FILE.write_text(
            json.dumps({"tokens": TOKENS}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

async def require_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth[7:]
    valid = {t["token"] for t in TOKENS}
    if token not in valid:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


async def require_admin(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth[7:]
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    if not admin_secret or token != admin_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


# ---------------------------------------------------------------------------
# Unique filename
# ---------------------------------------------------------------------------

def _unique_filename(desired: str) -> str:
    if not desired.endswith(".md"):
        desired += ".md"
    if not (NOTES_PATH / desired).exists():
        return desired
    stem = desired[:-3]
    for i in range(2, 10000):
        candidate = f"{stem}-{i}.md"
        if not (NOTES_PATH / candidate).exists():
            return candidate
    raise HTTPException(status_code=500, detail="Could not generate unique filename")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

# Seeded into a completely empty notes directory so a fresh install opens on
# a start page instead of an empty list. Never touched if any note exists.
HOME_SEED = """# Welcome to HexNotes

This is your **home note** — it opens every time you start the app.
Make it yours: fill it with [[wiki-links]] to your important notes.

## Quick start

- **+ New** (or `Ctrl+N`) creates a note. `#tags` anywhere in the text become sidebar groups.
- **📅** (or `Ctrl+D`) opens today's daily note.
- Notes open rendered — **double-click** (or `Ctrl+M`) to edit.
- Type `[[` in the editor to link to another note, with autocomplete.
- Task lists are live in the rendered view:
  - [ ] try ticking this checkbox
- **←** in the note header (or the browser/phone back button) returns to the previous note.
"""


def _sweep_expired() -> int:
    """Flytta noter med utgången expires_at till papperskorgen. Returnerar antal."""
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")
    count = 0
    for note_id, note in list(notes_index.items()):
        exp = note.get("expires_at")
        if not exp:
            continue
        try:
            if str(exp) <= now_iso:
                _move_to_trash(note_id)
                invalidate_delete(note_id)
                count += 1
        except Exception:
            pass
    return count


async def _expiry_loop():
    while True:
        await asyncio.sleep(600)
        try:
            _sweep_expired()
        except Exception:
            pass


@app.on_event("startup")
async def startup():
    if not TOKENS_FILE.exists():
        try:
            TOKENS_FILE.write_text('{"tokens": []}', encoding="utf-8")
        except Exception:
            pass
    _load_tokens_from_file()
    TRASH_PATH.mkdir(parents=True, exist_ok=True)
    if not any(NOTES_PATH.glob("*.md")):
        try:
            (NOTES_PATH / "home.md").write_text(HOME_SEED, encoding="utf-8")
        except Exception:
            pass
    build_index()
    expired = _sweep_expired()
    if expired:
        print(f"[startup] {expired} ephemeral note(s) expired → trash", flush=True)
    asyncio.create_task(_expiry_loop())


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "notes_count": len(notes_index), "version": APP_VERSION}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@app.post("/admin/tokens", response_model=TokenOut)
async def create_token(body: TokenCreate, _=Depends(require_admin)):
    for t in TOKENS:
        if t["name"] == body.name:
            raise HTTPException(status_code=409, detail=f"Token with name '{body.name}' already exists")
    new_token = {
        "name": body.name,
        "token": "tok_" + secrets.token_hex(16),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    TOKENS.append(new_token)
    _save_tokens_to_file()
    return new_token


@app.delete("/admin/tokens/{name}")
async def revoke_token(name: str, _=Depends(require_admin)):
    original_len = len(TOKENS)
    TOKENS[:] = [t for t in TOKENS if t["name"] != name]
    if len(TOKENS) == original_len:
        raise HTTPException(status_code=404, detail=f"Token '{name}' not found")
    _save_tokens_to_file()
    return {"status": "revoked", "name": name}


@app.get("/admin/tokens")
async def list_tokens(_=Depends(require_admin)):
    return {"tokens": [{"name": t["name"], "created_at": t["created_at"]} for t in TOKENS]}


# ---------------------------------------------------------------------------
# Note endpoints
# ---------------------------------------------------------------------------

@app.get("/api/notes", response_model=list[NoteOut])
async def list_notes(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    _=Depends(require_token),
):
    results = list(notes_index.values())

    if tag:
        results = [n for n in results if tag.lower() in [t.lower() for t in n["tags"]]]

    if q:
        q_lower = q.lower()
        results = [
            n for n in results
            if q_lower in n["content"].lower()
            or q_lower in n["filename"].lower()
            or any(q_lower in t.lower() for t in n["tags"])
        ]

    pinned_notes = sorted([n for n in results if n["pinned"]], key=lambda n: n["updated_at"], reverse=True)
    unpinned_notes = sorted([n for n in results if not n["pinned"]], key=lambda n: n["updated_at"], reverse=True)
    results = pinned_notes + unpinned_notes
    paged = results[offset : offset + limit]

    if q:
        q_lower = q.lower()
        out = []
        for n in paged:
            snippet = None
            for line in n["content"].splitlines():
                if q_lower in line.lower():
                    idx = line.lower().index(q_lower)
                    start = max(0, idx - 30)
                    chunk = line[start:start + 90].strip()
                    if start > 0:
                        chunk = "…" + chunk
                    if start + 90 < len(line):
                        chunk = chunk + "…"
                    snippet = chunk
                    break
            out.append({**n, "snippet": snippet})
        return out

    return paged


@app.post("/api/notes", response_model=NoteOut)
async def create_note(body: NoteCreate, _=Depends(require_token)):
    content = body.content or ""

    if body.filename:
        filename = sanitize_filename(body.filename)
        if (NOTES_PATH / filename).exists():
            raise HTTPException(status_code=409, detail="Conflict")
    else:
        today = date.today().isoformat()
        filename = _unique_filename(f"{today}.md")

    path = NOTES_PATH / filename
    stem = path.stem

    date_str = created_at_from_filename(path.name)
    created = date_str if date_str else date.today().isoformat()

    expires_at = None
    if body.ttl_hours:
        expires_at = (datetime.now(UTC).isoformat(timespec="seconds"))
        from datetime import timedelta
        expires_at = (datetime.now(UTC) + timedelta(hours=body.ttl_hours)).isoformat(timespec="seconds")

    _write_note_with_frontmatter(path, content, created, expires_at=expires_at)
    notes_index[stem] = parse_note(path)
    return notes_index[stem]


@app.get("/api/notes/{note_id}", response_model=NoteOut)
async def get_note(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")
    return notes_index[note_id]


@app.patch("/api/notes/{note_id}", response_model=Optional[NoteOut])
async def update_note(note_id: str, body: NoteUpdate, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    path = NOTES_PATH / f"{note_id}.md"

    # Empty content → move to trash
    if not body.content or not body.content.strip():
        _move_to_trash(note_id)
        invalidate_delete(note_id)
        return JSONResponse(status_code=204, content=None)

    # Read existing frontmatter for created date and pinned state
    meta, old_body = parse_frontmatter(path.read_text(encoding="utf-8"))
    if old_body != body.content:
        _snapshot_note(note_id)
    created = meta.get("created")
    if created is not None:
        created = str(created)
    else:
        date_str = created_at_from_filename(f"{note_id}.md")
        created = date_str if date_str else None
    pinned = bool(meta.get("pinned", False))
    expires_at = str(meta["expires_at"]) if meta.get("expires_at") else None

    _write_note_with_frontmatter(path, body.content, created, pinned, expires_at)
    invalidate(note_id)
    return notes_index[note_id]


@app.post("/api/notes/{note_id}/rename", response_model=NoteOut)
async def rename_note(note_id: str, body: NoteRename, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    new_filename = sanitize_filename(body.new_filename)

    new_path = NOTES_PATH / new_filename
    if new_path.exists():
        raise HTTPException(status_code=409, detail="A note with that name already exists")

    old_path = NOTES_PATH / f"{note_id}.md"
    old_path.rename(new_path)

    new_id = new_path.stem
    old_hist = _history_dir(note_id)
    if old_hist.is_dir() and not _history_dir(new_id).exists():
        old_hist.rename(_history_dir(new_id))
    invalidate_rename(note_id, new_id)
    return notes_index[new_id]


@app.post("/api/notes/{note_id}/pin", response_model=NoteOut)
async def pin_note(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    path = NOTES_PATH / f"{note_id}.md"
    meta, content = parse_frontmatter(path.read_text(encoding="utf-8"))

    created = meta.get("created")
    if created is not None:
        created = str(created)
    else:
        date_str = created_at_from_filename(f"{note_id}.md")
        created = date_str if date_str else None

    new_pinned = not bool(meta.get("pinned", False))
    expires_at = str(meta["expires_at"]) if meta.get("expires_at") else None
    _write_note_with_frontmatter(path, content, created, new_pinned, expires_at)
    invalidate(note_id)
    return notes_index[note_id]


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    _move_to_trash(note_id)
    invalidate_delete(note_id)
    return {"status": "deleted", "id": note_id}


@app.get("/api/notes/{note_id}/history", response_model=list[HistoryEntryOut])
async def list_note_history(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    hist = _history_dir(note_id)
    entries = []
    if hist.is_dir():
        for f in sorted(hist.glob("*.md"), reverse=True):
            version = f.stem
            if not VERSION_RE.match(version):
                continue
            _meta, content = parse_frontmatter(f.read_text(encoding="utf-8"))
            first_line = ""
            for line in content.strip().splitlines():
                stripped = line.strip()
                if stripped:
                    first_line = stripped
                    break
            entries.append({
                "version": version,
                "timestamp": _version_timestamp(version),
                "preview": first_line[:80],
            })
    return entries


@app.get("/api/notes/{note_id}/history/{version}", response_model=HistoryVersionOut)
async def get_note_history_version(note_id: str, version: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")
    if not VERSION_RE.match(version):
        raise HTTPException(status_code=404, detail="Version not found")

    f = _history_dir(note_id) / f"{version}.md"
    if not f.exists():
        raise HTTPException(status_code=404, detail="Version not found")

    _meta, content = parse_frontmatter(f.read_text(encoding="utf-8"))
    return {
        "version": version,
        "timestamp": _version_timestamp(version),
        "content": content,
    }


@app.get("/api/notes/{note_id}/raw")
async def get_note_raw(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")
    path = NOTES_PATH / f"{note_id}.md"
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Trash endpoints
# ---------------------------------------------------------------------------

@app.delete("/api/trash")
async def empty_trash(_=Depends(require_token)):
    """Töm papperskorgen permanent — alla filer och all deras historik."""
    purged = 0
    if TRASH_PATH.is_dir():
        for f in TRASH_PATH.glob("*.md"):
            if f.name.startswith("."):
                continue
            f.unlink()
            purged += 1
        hist_root = TRASH_PATH / ".history"
        if hist_root.is_dir():
            shutil.rmtree(hist_root)
    return {"status": "purged", "count": purged}


@app.get("/api/trash", response_model=list[TrashEntryOut])
async def list_trash(_=Depends(require_token)):
    entries = []
    if TRASH_PATH.is_dir():
        for f in TRASH_PATH.glob("*.md"):
            if f.name.startswith("."):
                continue
            original, deleted_at = _trash_meta(f)
            _meta, content = parse_frontmatter(f.read_text(encoding="utf-8"))
            entries.append({
                "name": f.name,
                "original_filename": original,
                "deleted_at": deleted_at,
                "preview": _first_line(content),
            })
    entries.sort(key=lambda e: (e["deleted_at"], e["name"]), reverse=True)
    return entries


@app.get("/api/trash/{name}", response_model=TrashContentOut)
async def get_trash_entry(name: str, _=Depends(require_token)):
    p = _trash_entry_path(name)
    original, deleted_at = _trash_meta(p)
    _meta, content = parse_frontmatter(p.read_text(encoding="utf-8"))
    return {
        "name": p.name,
        "original_filename": original,
        "deleted_at": deleted_at,
        "content": content,
    }


@app.post("/api/trash/{name}/restore", response_model=NoteOut)
async def restore_trash_entry(name: str, _=Depends(require_token)):
    p = _trash_entry_path(name)
    original, _deleted_at = _trash_meta(p)

    # Never overwrite a live note — restore under a unique name if taken
    dest_filename = _unique_filename(sanitize_filename(original))
    dest = NOTES_PATH / dest_filename
    p.rename(dest)
    new_id = dest.stem

    trash_hist = TRASH_PATH / ".history" / p.stem
    if trash_hist.is_dir() and not _history_dir(new_id).exists():
        _history_dir(new_id).parent.mkdir(parents=True, exist_ok=True)
        trash_hist.rename(_history_dir(new_id))

    notes_index[new_id] = parse_note(dest)
    return notes_index[new_id]


@app.delete("/api/trash/{name}")
async def purge_trash_entry(name: str, _=Depends(require_token)):
    """Radera permanent — tar bort både filen och dess historik."""
    p = _trash_entry_path(name)
    hist = TRASH_PATH / ".history" / p.stem
    p.unlink()
    if hist.is_dir():
        shutil.rmtree(hist)
    return {"status": "purged", "name": name}


# ---------------------------------------------------------------------------
# Static files – must be last
# ---------------------------------------------------------------------------

STATIC_DIR = os.environ.get("HEXNOTES_STATIC", "/app/static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

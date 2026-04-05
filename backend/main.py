import json
import os
import re
import secrets
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
NOTES_PATH = Path("/app/notes")
TRASH_PATH = NOTES_PATH / ".trash"
TOKENS_FILE = Path("/app/tokens.json")

app = FastAPI(title="HexNotes", docs_url="/docs", redoc_url=None)

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

class NoteCreate(BaseModel):
    content: str = ""
    filename: Optional[str] = None

class NoteUpdate(BaseModel):
    content: str

class NoteRename(BaseModel):
    new_filename: str

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

def _build_frontmatter(tags: list[str], created: Optional[str], pinned: bool = False) -> str:
    lines = ["---"]
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append(f"created: {created if created else 'null'}")
    if pinned:
        lines.append("pinned: true")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _write_note_with_frontmatter(path: Path, content: str, created: Optional[str], pinned: bool = False):
    tags = extract_tags(content)
    fm = _build_frontmatter(tags, created, pinned)
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

@app.on_event("startup")
async def startup():
    if not TOKENS_FILE.exists():
        try:
            TOKENS_FILE.write_text('{"tokens": []}', encoding="utf-8")
        except Exception:
            pass
    _load_tokens_from_file()
    TRASH_PATH.mkdir(parents=True, exist_ok=True)
    build_index()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "notes_count": len(notes_index)}


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
    return results[offset : offset + limit]


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

    _write_note_with_frontmatter(path, content, created)
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
        trash_dest = TRASH_PATH / path.name
        if trash_dest.exists():
            trash_dest.unlink()
        path.rename(trash_dest)
        invalidate_delete(note_id)
        return JSONResponse(status_code=204, content=None)

    # Read existing frontmatter for created date and pinned state
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    created = meta.get("created")
    if created is not None:
        created = str(created)
    else:
        date_str = created_at_from_filename(f"{note_id}.md")
        created = date_str if date_str else None
    pinned = bool(meta.get("pinned", False))

    _write_note_with_frontmatter(path, body.content, created, pinned)
    invalidate(note_id)
    return notes_index[note_id]


@app.post("/api/notes/{note_id}/rename", response_model=NoteOut)
async def rename_note(note_id: str, body: NoteRename, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    new_filename = body.new_filename
    if not new_filename.endswith(".md"):
        new_filename += ".md"

    new_path = NOTES_PATH / new_filename
    if new_path.exists():
        raise HTTPException(status_code=409, detail="A note with that name already exists")

    old_path = NOTES_PATH / f"{note_id}.md"
    old_path.rename(new_path)

    new_id = new_path.stem
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
    _write_note_with_frontmatter(path, content, created, new_pinned)
    invalidate(note_id)
    return notes_index[note_id]


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")

    path = NOTES_PATH / f"{note_id}.md"
    trash_dest = TRASH_PATH / path.name
    if trash_dest.exists():
        trash_dest.unlink()
    path.rename(trash_dest)
    invalidate_delete(note_id)
    return {"status": "deleted", "id": note_id}


@app.get("/api/notes/{note_id}/raw")
async def get_note_raw(note_id: str, _=Depends(require_token)):
    if note_id not in notes_index:
        raise HTTPException(status_code=404, detail="Note not found")
    path = NOTES_PATH / f"{note_id}.md"
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Static files – must be last
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")

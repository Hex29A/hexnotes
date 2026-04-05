# HexNotes

Self-hosted, lightweight note-taking app. Notes are stored as plain `.md` files on disk. No database. Exposes a REST API for browser, mobile (PWA), and AI-agent access.

---

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — set a strong ASCII-only ADMIN_SECRET

# 2. Create empty token file if it doesn't exist
echo '{"tokens": []}' > tokens.json

# 3. Build and start
docker compose up -d --build

# 4. Create your first token
docker exec hexnotes python3 -c "
import urllib.request, os, json
admin = os.environ.get('ADMIN_SECRET','')
req = urllib.request.Request(
    'http://localhost:8000/admin/tokens',
    data=json.dumps({'name': 'my-device'}).encode(),
    headers={'Authorization': f'Bearer {admin}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.read().decode())
"

# 5. Open the app
# http://localhost:8100
# Paste the token when prompted
```

> **Note:** Use an ASCII-only `ADMIN_SECRET` (no special characters). HTTP headers don't reliably carry non-ASCII values, so admin API calls from curl/external tools will fail with special characters in the secret.

---

## Architecture

| Component | Detail |
|-----------|--------|
| Backend   | Python 3.12 + FastAPI |
| Frontend  | Single-file Vanilla HTML/JS/CSS |
| Storage   | `.md` files in `notes/` (Docker bind mount) |
| Port      | `8100` on host → `8000` inside container |
| Networks  | `hexnote_default` + `nginx_proxy_manager_default` |

**File layout:**
```
notes/
├── 2026-04-04.md        ← auto-named with creation date
├── ideas.md             ← manually renamed
└── .trash/              ← deleted notes (not permanent)
```

---

## Authentication

All API requests require a Bearer token in the `Authorization` header:

```
Authorization: Bearer tok_abc123...
```

Tokens are stored in `tokens.json` (persisted via Docker volume). Each token has a name for traceability. A separate `ADMIN_SECRET` (from `.env`) is required for token management.

---

## REST API Reference

Base URL: `http://<host>:8100`

### Notes

#### `GET /api/notes`
List all notes, sorted by last updated (descending).

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Full-text search (content + filename + tags) |
| `tag` | string | Filter by tag name |
| `limit` | int | Max results (default: 50) |
| `offset` | int | Pagination offset |

**Response:**
```json
[
  {
    "id": "2026-04-04",
    "filename": "2026-04-04.md",
    "content": "My note content #tag",
    "tags": ["tag"],
    "created_at": "2026-04-04T00:00:00",
    "updated_at": "2026-04-04T10:15:15",
    "preview": "My note content #tag",
    "is_timeless": false,
    "pinned": false
  }
]
```

- `id` — filename without `.md` extension
- `is_timeless` — `true` if the filename has no `YYYY-MM-DD` prefix
- `pinned` — `true` if the note is pinned to the top of the list
- `content` — raw text, **never includes YAML frontmatter**

---

#### `POST /api/notes`
Create a new note.

**Body:**
```json
{
  "content": "Note text #tag",
  "filename": "ideas.md"
}
```

- `content` — optional, can be empty string
- `filename` — optional. If omitted, auto-generated as `YYYY-MM-DD.md` (e.g. `2026-04-04.md`). Collisions get a suffix: `2026-04-04-2.md`

**Returns:** full note object (200)  
**Conflict:** 409 if filename already exists

---

#### `GET /api/notes/{id}`
Get a single note by ID (filename without `.md`).

```
GET /api/notes/2026-04-04
GET /api/notes/ideas
```

**Returns:** note object (200) or 404

---

#### `PATCH /api/notes/{id}`
Update note content. Always send the **full content**, not a diff.

```json
{ "content": "Updated full content #newtag" }
```

- Tags in frontmatter are updated automatically from `#tags` in text
- If `content` is empty or whitespace → note is moved to `.trash/` → returns `204 No Content`

---

#### `POST /api/notes/{id}/rename`
Rename a note file.

```json
{ "new_filename": "docker-cheatsheet.md" }
```

- `.md` is appended automatically if missing
- Returns updated note object with new `id` and `filename`
- **Important for AI agents:** update your reference to the note's `id` after a successful rename — the old `id` becomes invalid

**Conflict:** 409 with message `"A note with that name already exists"`

---

#### `POST /api/notes/{id}/pin`
Toggle pin state. Pinned notes appear at the top of the list, sorted by `updated_at` within the pinned group.

Returns updated note object with `pinned: true` or `pinned: false`.

---

#### `DELETE /api/notes/{id}`
Move note to `.trash/`. Not a permanent delete.

Returns `204 No Content`.

---

#### `GET /api/notes/{id}/raw`
Returns raw file content as `text/plain` (includes YAML frontmatter).

---

### Health

#### `GET /health`
```json
{ "status": "ok", "notes_count": 42 }
```

No auth required.

---

### Admin – Token Management

All admin endpoints require `Authorization: Bearer <ADMIN_SECRET>`.

#### `POST /admin/tokens`
Create a new named token.

```json
{ "name": "work-laptop" }
```

**Response:**
```json
{
  "name": "work-laptop",
  "token": "tok_abc123...",
  "created_at": "2026-04-04T10:00:00+00:00"
}
```

#### `DELETE /admin/tokens/{name}`
Revoke a token by name. Other tokens are unaffected.

#### `GET /admin/tokens`
List all tokens — shows names and dates, **never the token values**.

---

## AI Agent Usage (Claude Code / MCP)

HexNotes is designed as a readable/writable note store for AI agents.

### Suggested workflow

```
# Read all notes
GET /api/notes

# Search for notes about a topic
GET /api/notes?q=docker

# Get notes with a specific tag
GET /api/notes?tag=todo

# Create a new note
POST /api/notes
{ "content": "Agent observation: deployment went ok #deploy #log" }

# Update a note
PATCH /api/notes/2026-04-04
{ "content": "Updated content with new findings #deploy #log" }

# Rename a note to something meaningful
POST /api/notes/2026-04-04/rename
{ "new_filename": "deploy-log-april.md" }
```

### Tips for agents

- Use `#tags` in content to categorize notes — they are indexed automatically
- `id` = filename without `.md` — use this in all endpoint paths
- After a `rename`, the old `id` is gone — always use the new `id` returned in the response
- Empty `PATCH` content moves the note to trash (no undo via API)
- `GET /api/notes/{id}/raw` returns the file with YAML frontmatter if you need structured metadata

### Example: Claude Code token creation

```
"Create a token called claude-code"
→ POST /admin/tokens {"name": "claude-code"}
← {"token": "tok_xyz..."}
```

---

## Nginx Proxy Manager

In NPM, set the Proxy Host to:
- **Forward Hostname:** `hexnotes`
- **Forward Port:** `8000`

This works because HexNotes is on the `nginx_proxy_manager_default` Docker network.

---

## Tokens

Tokens are stored in `tokens.json`, which is **bind-mounted** from the host into the container. This means:
- Tokens survive `docker compose up -d --build` and image rebuilds
- Tokens survive container restarts
- Tokens are only lost if you delete `tokens.json` from the host

The `tokens.json` file is **not** copied into the Docker image.

---

## Auto-sync Behavior

The frontend keeps notes up to date via multiple mechanisms:

| Trigger | Behavior |
|---------|----------|
| Typing stops (1s) | Autosave current note |
| Switch back to tab/app | Reload note list |
| Browser window regains focus | Reload note list |
| Every 60 seconds (idle) | Background reload of note list |
| Manual ↻ button (mobile) | Force reload |
| Reconnect after offline | Save pending content, reload list |

---

## Running Tests

```bash
docker compose run --rm hexnotes pytest tests/ -v --tb=short
```

58 tests covering auth, CRUD, search, rename, trash, token management, slug generation, frontmatter parsing, and filename sanitization.

---

## Notes on `.env`

```env
ADMIN_SECRET=your-strong-ascii-secret
```

- Must be ASCII-only (no `ö`, `å`, `ä` or other non-ASCII characters)
- Never use the same value as a regular API token
- Change from the default before exposing the app externally

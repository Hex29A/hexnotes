# HexNotes

Self-hosted, lightweight note-taking app. Notes are stored as plain `.md` files on disk. No database. Exposes a REST API for browser, mobile (PWA), and AI-agent access.

Current version: see `APP_VERSION` in `backend/main.py`, exposed via `GET /health` and shown in the topbar. Release notes in [CHANGELOG.md](CHANGELOG.md).

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
# http://localhost:8888
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
| Port      | `8888` on host → `8000` inside container |
| Networks  | `hexnotes_default` + `nginx_proxy_manager_default` |

**File layout:**
```
notes/
├── 2026-04-04.md        ← auto-named with creation date
├── ideas.md             ← manually renamed
├── .history/            ← version history, one dir per note
│   └── ideas/
│       └── 2026-06-10T07-30-00-123456.md   ← snapshot (UTC timestamp)
└── .trash/              ← deleted notes (restorable, see Trash API)
    ├── 2026-06-10T08-00-00-654321__old.md  ← timestamped: never overwrites
    └── .history/
        └── 2026-06-10T08-00-00-654321__old/  ← the note's history follows it
```

Everything lives under `notes/`, so backing up that one bind mount captures notes, history and trash alike.

---

## Authentication

All API requests require a Bearer token in the `Authorization` header:

```
Authorization: Bearer tok_abc123...
```

Tokens are stored in `tokens.json` (persisted via Docker volume). Each token has a name for traceability. A separate `ADMIN_SECRET` (from `.env`) is required for token management.

---

## REST API Reference

Base URL: `http://<host>:8888`

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
    "pinned": false,
    "snippet": null
  }
]
```

- `id` — filename without `.md` extension
- `is_timeless` — `true` if the filename has no `YYYY-MM-DD` prefix
- `pinned` — `true` if the note is pinned to the top of the list
- `content` — raw text, **never includes YAML frontmatter**
- `snippet` — `null` normally. When `?q=` is provided, contains a ~90-char excerpt from the first matching line in the note body, with `…` ellipsis if truncated. Useful for AI agents to surface relevant context without reading full content.

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
- The previous version is snapshotted to `.history/<id>/` before the write (skipped if content is unchanged)
- If `content` is empty or whitespace → note is moved to trash → returns `204 No Content` (restorable via the Trash API)

---

#### `POST /api/notes/{id}/rename`
Rename a note file.

```json
{ "new_filename": "docker-cheatsheet.md" }
```

- `.md` is appended automatically if missing
- The filename is sanitized (path separators and `..` are stripped)
- The note's version history follows the new name
- Returns updated note object with new `id` and `filename`
- **Important for AI agents:** update your reference to the note's `id` after a successful rename — the old `id` becomes invalid

**Conflict:** 409 with message `"A note with that name already exists"`

---

#### `POST /api/notes/{id}/pin`
Toggle pin state. Pinned notes appear at the top of the list, sorted by `updated_at` within the pinned group.

Returns updated note object with `pinned: true` or `pinned: false`.

---

#### `DELETE /api/notes/{id}`
Move note to trash. Not a permanent delete — restore it via the Trash API. A final history snapshot is taken first, and the note's history moves to `.trash/.history/` so a new note reusing the name starts with clean history.

Returns `{ "status": "deleted", "id": "..." }`.

---

#### `GET /api/notes/{id}/raw`
Returns raw file content as `text/plain` (includes YAML frontmatter).

---

### Version History

Every save snapshots the previous version to `.history/<id>/<utc-timestamp>.md`. Unchanged saves are skipped. In the UI: the 🕘 button in the filename row.

#### `GET /api/notes/{id}/history`
List versions, newest first.

```json
[
  { "version": "2026-06-10T07-30-00-123456", "timestamp": "2026-06-10T07:30:00", "preview": "First line of that version" }
]
```

#### `GET /api/notes/{id}/history/{version}`
Content of a specific version (frontmatter stripped). Version names are strictly validated.

```json
{ "version": "...", "timestamp": "...", "content": "..." }
```

There is no dedicated restore endpoint — restoring is a plain `PATCH` with the old content, which itself snapshots the current state first, so nothing is ever lost.

---

### Trash

Deleted notes land in `.trash/` under a timestamped name (`<utc-ts>__<filename>.md`), so deleting two notes with the same name never overwrites anything. In the UI: the 🗑 button at the bottom of the sidebar.

#### `GET /api/trash`
List trashed notes, newest first.

```json
[
  { "name": "2026-06-10T08-00-00-654321__ideas.md", "original_filename": "ideas.md", "deleted_at": "2026-06-10T08:00:00", "preview": "First line" }
]
```

`name` is the identifier for the other trash endpoints. Legacy (pre-timestamp) trash files are listed too, with `deleted_at` from file mtime.

#### `GET /api/trash/{name}`
View the content of a trashed note (frontmatter stripped).

#### `POST /api/trash/{name}/restore`
Move the note back. If a live note already has the name, the restored note gets a unique name (`ideas-2.md`) — **a restore never overwrites anything**. The note's history comes back with it. Returns the restored note object.

#### `DELETE /api/trash/{name}`
**Permanent** delete — removes both the file and its entire version history from disk. This is the way to truly destroy sensitive content (e.g. a note that contained a leaked API key): delete the note, then purge it from trash.

Returns `{ "status": "purged", "name": "..." }`.

#### `DELETE /api/trash`
**Permanently empty the trash** — removes every trashed note and all of their version history.

Returns `{ "status": "purged", "count": 7 }`.

---

### Health

#### `GET /health`
```json
{ "status": "ok", "notes_count": 42, "version": "1.5" }
```

No auth required. `version` is handy for verifying what a client or server is actually running.

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
- Empty `PATCH` content moves the note to trash — undo via `GET /api/trash` + `POST /api/trash/{name}/restore`
- `GET /api/notes/{id}/history` shows earlier versions of a note; fetch one and `PATCH` it back to restore
- `[[note-name]]` in content becomes a clickable wiki-link in the UI preview — useful for cross-referencing notes
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

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New note |
| `Ctrl+P` | Command palette — fuzzy-search and open any note |
| `Ctrl+F` | Find in current note (match navigation with ↑↓, Shift+Enter/Enter) |
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+M` | Toggle Markdown preview |
| `Ctrl+Delete` | Delete active note (confirmation dialog) |
| `Escape` | Close palette / find bar / clear search |
| `Tab` | Insert 2 spaces in editor |

---

## Sidebar

Notes are organized into collapsible groups:

- **📌 Pinned** — notes pinned via the 📌 button in the filename bar
- **📥 Inbox** — untagged notes (no `#tags` in content)
- **🏷 Tags** — parent group containing one sub-group per `#tag`

Group collapse state is saved per-group in `localStorage`. A **collapse all / expand all** toggle is available at the top of the list.

To organize notes into a tag group, add `#tagname` anywhere in the note body. Notes with multiple tags appear in each relevant group.

At the bottom of the sidebar: **🗑 Trash** opens the trash dialog. The running app version is shown in the topbar next to the HexNotes title.

---

## Markdown Preview & Wiki Links

`Ctrl+M` (or the 👁 button) toggles a rendered Markdown preview of the current note.

`[[note-name]]` in note text renders as a clickable link in the preview (matched case-insensitively against the note id, with or without `.md`). Clicking it opens that note and stays in preview mode, so you can browse linked notes like a wiki. Links to notes that don't exist are shown red/dashed. Implemented as a `marked` inline extension, so wiki links inside code blocks are left alone.

---

## Version History & Trash (UI)

- **🕘 in the filename row** — lists earlier versions of the note (timestamp + preview). Click one to read it; **Restore** saves it back as the current content (the replaced state is snapshotted first, so a restore is always undoable).
- **🗑 at the bottom of the sidebar** — lists deleted notes. Click one to read it; **Restore** moves it back (under a unique name if taken), **Delete forever** destroys the note *and* its history. **Empty trash** purges everything at once. All destructive buttons require a confirming second click.

---

## Search

- **Topbar search** — live-filters the note list (300ms debounce). Clears with the `✕` button. When active, shows a flat results list (no grouping) with matching text highlighted in the filename and a content snippet showing the matching line. Matched text is highlighted in accent color.
- **Command palette** (`Ctrl+P`) — floating overlay, fuzzy-searches filename + tags + content, opens note on Enter. Arrow keys navigate results.
- **In-note find** (`Ctrl+F`) — find bar below filename row. Navigate matches with Enter / Shift+Enter or ↑↓ buttons. Shows `X / Y` match counter.

---

## Running Tests

```bash
docker compose run --rm hexnotes pytest tests/ -v --tb=short
```

86 tests across four files:

| File | Covers |
|------|--------|
| `tests/test_unit.py` | Slug generation, tag extraction, frontmatter parsing, filename sanitization |
| `tests/test_api.py` | Auth, CRUD, search, rename (incl. path traversal), tokens, health |
| `tests/test_history.py` | Version history: snapshots, ordering, restore round-trip, rename migration, traversal rejection |
| `tests/test_trash.py` | Trash: listing, restore (incl. collision), purge, history migration, legacy files, traversal rejection |

Frontend features (sidebar, palette, find bar, preview, dialogs) are pure client-side and do not have automated tests.

---

## Security & Data Lifecycle

**Deleted ≠ destroyed.** A deleted note lives on in `.trash/` and its version history in `.trash/.history/` — and anyone with a valid API token can list and restore it. Likewise, editing a secret *out* of a live note keeps it in the note's history. To truly destroy sensitive content (e.g. a note that contained an API key):

1. Delete the note (moves it to trash, history included)
2. `DELETE /api/trash/{name}` — or **Radera permanent** in the trash dialog — removes the file *and* its entire history from disk

Also keep in mind that filesystem backups of `notes/` contain copies of everything, including trash and history.

**Other guarantees:**
- All filenames from clients are sanitized; history versions and trash names are strictly validated — no path traversal into or out of `notes/`
- Nothing is ever overwritten: trash entries are timestamped, restores get a unique name on collision, history snapshots have microsecond timestamps
- All tokens have full access (there are no scopes) — trash and history sit at the same trust level as the notes themselves

---

## Versioning

`major.minor`, kept in `APP_VERSION` in `backend/main.py` — single source of truth, exposed via `GET /health` and shown in the topbar. Bump **minor** for new features, **major** for breaking changes (API incompatibility or storage format changes requiring migration). Document each release in [CHANGELOG.md](CHANGELOG.md).

The service worker cache name (`hexnotes-vN` in `static/sw.js`) is deliberately **not** tied to the app version: since the app shell is fetched network-first, deploys reach clients without cache bumps. Only bump it when the caching strategy itself changes.

---

## Notes on `.env`

```env
ADMIN_SECRET=your-strong-ascii-secret
```

- Must be ASCII-only (no `ö`, `å`, `ä` or other non-ASCII characters)
- Never use the same value as a regular API token
- Change from the default before exposing the app externally

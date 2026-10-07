# agents.md – HexNotes

> Detailed build specification for a self-hosted Google Keep clone with Markdown files and a REST API.

---

## Project overview

**HexNotes** is a lightweight, self-hosted note-taking app inspired by Google Keep.
All data is stored as plain `.md` files on disk. No database.
The app exposes a REST API for integration with Claude Code and other tools.

**Target environment: Docker.** The project is built and run exclusively as a Docker container. There should be no need to install Python or other dependencies locally – everything happens inside the image.

### Goals

- Quick input of short snippets from mobile and desktop
- Autosave without a manual save button
- Search and filtering via `#tags`
- Available in the browser – no app to install
- Installable as a PWA (docked app on Windows, home screen on mobile)
- Claude Code can read and write via the REST API

---

## Tech stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | Python 3.12 + FastAPI | Light, fast, auto-generated API docs |
| Frontend | Vanilla HTML/CSS/JS | No build step, easy to maintain |
| File storage | `.md` files on disk | Plain text, readable by Claude Code |
| Container | Docker + docker-compose | Simple deploy on a VPS |
| Reverse proxy | Nginx Proxy Manager | Already in the existing stack |

---

## File structure

```
hexnotes/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── tokens.json              # named API tokens (see Auth)
├── backend/
│   └── main.py              # FastAPI app, all backend logic
├── scripts/
│   └── generate_icons.py    # Generates PWA icons during docker build
├── static/
│   ├── index.html           # The whole frontend (single file)
│   ├── manifest.json        # PWA manifest
│   ├── sw.js                # Service Worker (minimal)
│   ├── icon-192.png         # PWA icon (generated with Pillow)
│   └── icon-512.png         # PWA icon (generated with Pillow)
└── notes/                   # Mounted volume – your .md files
    └── .trash/              # Deleted notes end up here
```

---

## Filename convention

The filename is generated on creation but can be changed manually at any time via the rename function in the UI or via `POST /api/notes/{id}/rename`. The date in the default filename is always the creation date – neither the system nor autosave ever changes the filename automatically. Only the user can rename.

### Default: date

> **Note:** slug generation from the first line of text was never finished and
> was removed in 1.24. The default filename is just the date – which is also
> what makes `Ctrl+D` (today's note) possible, since today's file must have a
> predictable name. `README.md` describes the actual behaviour.

```
2025-04-03.md
2025-04-03-2.md               ← on a collision the same day
```

### Timeless note (no date)

If the user changes the filename on creation, that name is used as is:

```
ideas.md
todo.md
snippets.md
```

### Rules for default filenames (only used if the user has not given a filename)

- Today's date, `YYYY-MM-DD.md`
- Collision with an existing file → suffix `-2`, `-3`
- The `.md` extension is always added automatically if missing

---

## Backend – FastAPI (`backend/main.py`)

### Authentication – named tokens

Instead of a single shared token, a list of named tokens in `tokens.json` is used:

```json
{
  "tokens": [
    { "name": "desktop",    "token": "tok_abc123", "created_at": "2025-04-03T10:00:00" },
    { "name": "iphone",     "token": "tok_def456", "created_at": "2025-04-03T10:01:00" },
    { "name": "claude-code","token": "tok_ghi789", "created_at": "2025-04-03T10:02:00" }
  ]
}
```

Every API endpoint requires the header:
```
Authorization: Bearer <token>
```

The backend accepts every token in the list. The token name is logged per request for traceability. A single token can be revoked without affecting the others. `tokens.json` is loaded at startup and on every change via the admin endpoint.

### Admin endpoints

Protected by `ADMIN_SECRET` from `.env` – never the same value as a regular token.

#### `POST /admin/tokens`
Create a new named token.
```
Authorization: Bearer <admin-secret>
Body: { "name": "work-laptop" }
Response: { "name": "work-laptop", "token": "tok_xyz999", "created_at": "..." }
```
The token is saved straight to `tokens.json` and is active immediately.

#### `DELETE /admin/tokens/{name}`
Revoke the token with the given name.

#### `GET /admin/tokens`
List all tokens – shows name and date, never the token value.

**Typical Claude Code flow:**
```
You: "Create a token for my new laptop, call it work-laptop"
Claude Code → POST /admin/tokens {"name": "work-laptop"}
Claude Code: "Your token: tok_xyz999"
```

### Note endpoints

#### `GET /api/notes`
List all notes, sorted by `updated_at` descending.

Query params: `q` (free text), `tag`, `limit` (default 50), `offset`

Response per note:
```json
{
  "id": "2025-04-03-docker-tips",
  "filename": "2025-04-03-docker-tips.md",
  "content": "Docker tips\n\n#docker #snippets",
  "tags": ["docker", "snippets"],
  "created_at": "2025-04-03T14:22:00",
  "updated_at": "2025-04-03T14:25:00",
  "preview": "Docker tips",
  "is_timeless": false
}
```

`is_timeless: true` if the filename has no date prefix (`YYYY-MM-DD-`).

#### `POST /api/notes`
Create a new note.
```json
{ "content": "Text\n\n#tag", "filename": "ideas.md" }
```
`filename` is optional. If omitted, `YYYY-MM-DD.md` is generated.
A collision returns `409 Conflict`.

#### `GET /api/notes/{id}`
Get a specific note. `id` = the filename without `.md`.

#### `PATCH /api/notes/{id}`
Update the content. The filename is **not** changed through this endpoint.

```json
{ "content": "Updated text" }
```

Content is **always the whole note content**, never a diff. The backend writes the file as is.

If `content` is an empty string or only whitespace → move the file to `.trash/` and return `204 No Content`.

**NOTE:** The frontend must **not** trigger this through autosave in the middle of typing. Auto-trash is only triggered when the user leaves the note (blur event on the textarea) and the content is empty. Autosave during ongoing typing never sends a PATCH with empty content.

If a file with the same name already exists in `.trash/` it is overwritten (same behaviour as DELETE).

`updated_at` is taken from the file's `mtime` – the backend never writes timestamps manually.
`created_at` is extracted from the date prefix in the filename (`2025-04-03-...`) if there is one. Otherwise `mtime` is used. ctime is **not** used – it is unreliable in Docker volumes and is updated by metadata changes such as chmod and moves.

#### `POST /api/notes/{id}/rename`
Rename an existing note.

```json
{ "new_filename": "docker-cheatsheet.md" }
```

Backend:
1. Validates that `new_filename` does not already exist → `409 Conflict` with the message "A note with that name already exists"
2. `os.rename(old_path, new_path)`
3. Returns the updated note object with the new `id` and `filename`

`.md` is added automatically if missing.

The frontend **must** immediately update `activeNoteId` and every reference to the old ID when a rename succeeds. Otherwise subsequent PATCH calls will return 404.

#### `DELETE /api/notes/{id}`
Move to `notes/.trash/{filename}`. Not a permanent delete.

If a file with the same name already exists in `.trash/` it is overwritten – the trash is not an archive but a safety buffer.

#### `GET /api/notes/{id}/raw`
Returns the file content as `text/plain`.

#### `GET /health`
```json
{ "status": "ok", "notes_count": 42 }
```

### File handling

- Notes: `/app/notes/` (mounted Docker volume)
- Trash: `/app/notes/.trash/`
- Files starting with `.` are ignored when listing
- Search: done against the in-memory index (see below)

### Startup logic

At startup the backend does the following before it starts accepting requests:

1. Create `tokens.json` if the file is missing (`{ "tokens": [] }`)
2. Create `/app/notes/.trash/` if the folder is missing
3. Build the in-memory index from every `.md` file in `/app/notes/`

```python
@app.on_event("startup")
async def startup():
    # Make sure tokens.json exists
    if not TOKENS_PATH.exists():
        TOKENS_PATH.write_text('{"tokens": []}')
    # Make sure the trash folder exists (the volume may be new)
    TRASH_PATH.mkdir(parents=True, exist_ok=True)
    # Build the index
    await build_index()
```

### In-memory index

The backend builds an index of all notes at startup. The index is kept in memory and invalidated on every write, rename or delete. Search always runs against the index – never directly against disk per request.

```python
# Pseudocode
notes_index: dict[str, NoteEntry] = {}  # id → NoteEntry

@app.on_event("startup")
async def build_index():
    for f in Path("/app/notes").glob("*.md"):
        notes_index[f.stem] = parse_note(f)

def invalidate(note_id: str):
    # Update the existing entry (write/PATCH)
    notes_index[note_id] = parse_note(Path(f"/app/notes/{note_id}.md"))

def invalidate_rename(old_id: str, new_id: str):
    # Remove the old entry, add the new one
    notes_index.pop(old_id, None)
    notes_index[new_id] = parse_note(Path(f"/app/notes/{new_id}.md"))

def invalidate_delete(note_id: str):
    notes_index.pop(note_id, None)
```

The index reads each file once at startup. At 500 files this is negligible. After that, search is O(n) in memory – no disk reads per keystroke.

### Frontmatter

The backend **writes** YAML frontmatter when each note is created:

```markdown
---
tags: [docker, snippets]
created: 2025-04-03
---
Docker compose – persistent volumes

Content here...
```

- `#tags` in the text are **always the source of truth** for tags
- On every PATCH, `#tags` are extracted from the text and the frontmatter is rewritten – regardless of what the frontmatter contained before
- `created` is set from the date prefix in the filename if there is one, otherwise today's date – it is never rewritten
- The backend **reads** frontmatter if present but does not **require** it – files without frontmatter work fully
- `content` in the API response does **not** include the frontmatter block – only the plain text
- Timeless notes (`ideas.md`) without a date prefix get `created: null` in the frontmatter

**Benefit for Claude Code:** structured metadata is easier to parse than grepping for `#tags` in free text. Tags and dates are available without interpreting the content.

---

## Frontend (`static/index.html`)

Single-file app. All HTML, CSS and JavaScript in one file, organised in clear sections with comments: `// === SECTION: AUTH ===`, `// === SECTION: API ===` etc.

### Typography

- **Font:** `JetBrains Mono` via Google Fonts
- Fallback: `Consolas, 'Courier New', monospace`
- Font size: 14px base, 13px in the list

### Colour palette

| Token | Dark theme | Light theme |
|-------|-----------|------------|
| `--bg-primary` | `#0d0d0d` | `#f5f5f5` |
| `--bg-sidebar` | `#141414` | `#ebebeb` |
| `--bg-card` | `#1a1a1a` | `#e0e0e0` |
| `--bg-card-active` | `#222222` | `#d4d4d4` |
| `--text-primary` | `#e8e8e8` | `#1a1a1a` |
| `--text-muted` | `#666666` | `#888888` |
| `--accent` | `#a855f7` | `#7c3aed` |
| `--accent-dim` | `#3b1f5e` | `#ddd6fe` |
| `--border` | `#2a2a2a` | `#cccccc` |
| `--error-bg` | `#3b0a0a` | `#fee2e2` |
| `--error-text` | `#f87171` | `#b91c1c` |

The theme follows `prefers-color-scheme`. No manual toggle in v1.

### Desktop layout

```
┌─────────────────────────────────────────────────┐
│ [☰]  🔍 Search...                     [+ New]  │  ← top bar
├───────────────────┬─────────────────────────────┤
│                   │ 📄 2025-04-03-docker.md  ✎  │  ← filename bar (always clickable)
│   SIDEBAR         ├─────────────────────────────┤
│   (collapsible)   │ ⚠ Could not save...         │  ← red error bar (hidden)
│                   ├─────────────────────────────┤
│  ┌─────────────┐  │                             │
│  │ Preview...  │  │   textarea                  │
│  │ #chip #chip │  │   (JetBrains Mono)          │
│  │ today       │  │                        ✓    │
│  └─────────────┘  │                             │
│  ┌─────────────┐  │                             │
│  │ Preview...  │  │                             │
│  │ #chip       │  │                             │
│  │ yesterday   │  │                             │
│  └─────────────┘  │                             │
└───────────────────┴─────────────────────────────┘
```

- Sidebar collapsible via `[☰]` – state saved in `localStorage`
- When the sidebar is hidden: the editor expands to full width
- Active note: `3px` left border in `--accent` + `--bg-card-active`
- Sidebar width: `300px`, fixed

### Filename bar

Always shown at the top of the editor, above the error bar.

```
📄 2025-04-03-docker-tips.md  ✎
```

- The filename is **always clickable** – a click activates inline editing
- The `✎` icon has a generous click area (`padding: 8px 12px`) to work on mobile
- Click on the filename or `✎` → `<input>` with the current filename filled in, selected
- Enter confirms → `POST /api/notes/{id}/rename`
- Escape cancels without changes
- `.md` is added automatically if missing
- Empty field → cancel, keep the current name
- On a collision: an error message is shown inline under the input in `--error-text`
- During the rename request: input disabled, small spinner
- On a successful rename: the sidebar updates with the new filename

### Red error bar

Directly under the filename bar:

```
⚠ Could not save – check the connection
```

- `display: none` by default
- Shown immediately on a failed save (network error or a non-2xx response)
- Disappears on the next successful save
- Auto-retry: tries again after 5s, at most 3 attempts in total
- After 3 failed attempts: the error bar stays until the page is reloaded
- The error counter is reset on a successful save

### Sidebar – the note card

```
┌──────────────────────────────┐
│ First line of the text...    │  ← truncated at ~55 characters
│ #docker #snippets            │  ← coloured chips
│ today                        │  ← relative date
└──────────────────────────────┘
```

- Chips: `--accent-dim` background, `--accent` text, `border-radius: 9999px`, padding `2px 8px`
- Hover: `--bg-card`

### New note

- Button `[+ New]` in the top bar + `Ctrl+N`
- Creates an empty note object locally (the POST does not happen until the first autosave)
- Focuses the editor immediately
- If the user leaves the note (blur) without having typed anything → do nothing, never create the file

### The editor

- `<textarea>` without a toolbar, `flex: 1`, `resize: none`
- Tab → 2 spaces
- No Markdown rendering
- Saved indicator at the bottom right: `···` (pulsing) → `✓` (fades out over 2s) → hidden

### Search

- Always visible in the top bar
- Live filter with a 300ms debounce
- Searches content + tags + filename
- `Ctrl+F` focuses, `Escape` clears

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New note |
| `Ctrl+F` | Focus the search field |
| `Ctrl+Shift+B` | Toggle sidebar (plain `Ctrl+B` outside the editor; bold inside it since 1.42) |
| `Ctrl+B` / `Ctrl+I` / `Ctrl+Shift+X` / `Ctrl+E` | Bold / italic / strikethrough / inline code in the editor (1.42, see README) |
| `Ctrl+K` / `Ctrl+Shift+7` / `Ctrl+Enter` | Link / bullet list / tick checkbox in the editor (1.42) |
| `Ctrl+Delete` | Delete the active note (confirmation dialog) |
| `Escape` | Clear search |

---

### Mobile view (≤768px)

Two-view model. Default view on opening: **editor** (the last opened note, saved in `localStorage` as `lastNoteId`).

**Fallback:** If `lastNoteId` no longer exists (note deleted, renamed, or first time) → show an empty new note ready to type in. Never show a 404 error to the user at startup.

**Editor view:**
```
┌─────────────────────────┐
│ [←]  HexNotes           │
├─────────────────────────┤
│ 📄 ideas.md           ✎ │  ← always clickable
├─────────────────────────┤
│ ⚠ Could not save...    │  ← hidden until an error
├─────────────────────────┤
│   textarea         ✓    │
│                    [+]  │  ← FAB
└─────────────────────────┘
```

**List view (`[←]` in the top bar):**
```
┌─────────────────────────┐
│ 🔍 Search...            │
├─────────────────────────┤
│ ┌─────────────────────┐ │
│ │ Preview...          │ │
│ │ #chip #chip  today  │ │
│ └─────────────────────┘ │
│                    [+]  │  ← FAB
└─────────────────────────┘
```

- **FAB:** `position: fixed`, `bottom: 24px`, `right: 24px`, `56px` circular, `--accent`
- The FAB creates a new note and opens the editor
- Tapping a note in the list → editor view

---

## Autosave – detailed flow

```
The user types
        ↓
pendingContent = content          ← always updated, regardless of network status
clearTimeout(saveTimer)
        ↓
isOnline?
  No  → show the offline indicator, wait for the online event (no timer)
  Yes → saveTimer = setTimeout(save, 1000)
        ↓  (1 second without a keystroke)
save(pendingContent)
  ├── isSaving === true?
  │     → wait, pendingContent is already updated
  ├── isNew === true?
  │     → POST /api/notes (with a manual filename, if any)
  │     → on success: isNew = false
  └── isNew === false?
        → PATCH /api/notes/{id}

NOTE: Autosave never sends empty content. Empty note → trash is handled
      only via the blur event (see "Auto-trash" below), never via this flow.

  Success:
    isSaving = false
    pendingContent = null
    Show ✓, hide the error bar and the offline indicator
    Reset retryCount

  Failure (online but an error):
    isSaving = false
    Show the red error bar
    retryCount++
    retryCount <= 3 → retry after 5s
    retryCount >  3 → the error bar stays, no more retries
```

---

## Offline handling

### The state machine

The frontend keeps three variables:

```javascript
let isOnline      = navigator.onLine; // initial value
let pendingContent = null;            // latest unsaved content
let healthInterval = null;            // polling timer, only runs offline
```

`isOnline` is **not** the same as `navigator.onLine` as is – it is updated through a combination of browser events and actual request results (see below).

### Online/offline events

```javascript
window.addEventListener('offline', () => goOffline());
window.addEventListener('online',  () => checkHealth());
```

We do not trust the `online` event blindly – it triggers a health check before we declare ourselves online again.

### Health check + polling

```javascript
async function checkHealth() {
  try {
    const r = await fetch('/health', { signal: AbortSignal.timeout(3000) });
    if (r.ok) goOnline();
  } catch {
    // still offline, polling continues
  }
}

function goOffline() {
  isOnline = false;
  showOfflineBar();
  clearTimeout(saveTimer);
  // Poll every 30s – ONLY while offline
  if (!healthInterval) {
    healthInterval = setInterval(checkHealth, 30000);
  }
}

function goOnline() {
  isOnline = true;
  clearInterval(healthInterval);
  healthInterval = null;
  hideOfflineBar();
  // Save right away if there is pending content
  if (pendingContent !== null) save(pendingContent);
}
```

Polling runs **only offline** – zero extra requests when everything works normally.

### Request errors as an offline detector

If a save call fails with a network error (not 4xx/5xx but a connection error):

```javascript
} catch (err) {
  if (!navigator.onLine) {
    goOffline(); // the network went away during the request
  } else {
    showErrorBar(); // online but a backend error
    scheduleRetry();
  }
}
```

This catches the case where the network disappears in the middle of an ongoing request.

### Visual feedback hierarchy

Distinct states – never overlapping:

| State | UI signal | Colour | Placement |
|-------|-----------|--------|-----------|
| Saving | `···` pulsing | `--accent` | Corner of the editor |
| Saved | `✓` fades out over 2s | `--accent` | Corner of the editor |
| **Offline** | status bar | yellow `#854d0e` / `#fef08a` | Bottom edge of the app |
| Save error (online) | error bar | red `--error-*` | Under the filename bar |

**Offline is not an error** – yellow signals a waiting state, not a disaster. The red error bar is reserved for when the network is up but the backend still answers with an error.

### The offline indicator (desktop + mobile)

```
┌─────────────────────────────────────────────────┐
│ ● Offline – changes are saved when you're online│
└─────────────────────────────────────────────────┘
```

- `position: fixed`, `bottom: 0`, `left: 0`, `right: 0`
- Height: `32px`, centred text
- Background: `#422006` (dark theme) / `#fef9c3` (light theme)
- Text: `#fef08a` / `#854d0e`
- Hidden by default (`display: none`)
- On mobile: sits above the FAB (the FAB gets `bottom: 58px` while the offline bar is shown, otherwise `bottom: 24px`)
- `z-index` hierarchy: offline bar `z-index: 200`, FAB `z-index: 100` – the offline bar never covers the FAB but is always visible

---

## PWA

### `static/manifest.json`

```json
{
  "name": "HexNotes",
  "short_name": "HexNotes",
  "description": "Self-hosted markdown notes",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0d0d0d",
  "theme_color": "#a855f7",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### `static/sw.js`

The Service Worker caches static assets so that the app can **start offline**. Without it the app cannot be opened without a network connection, which makes all the JS offline logic pointless.

```javascript
const CACHE = 'hexnotes-v1';
const STATIC = ['/', '/index.html', '/manifest.json', '/icon-192.png', '/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // API calls always go to the network
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/admin')) {
    e.respondWith(fetch(e.request));
    return;
  }
  // Static assets: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
```

The cache is invalidated automatically on a new deploy via `CACHE = 'hexnotes-v2'` etc. The JetBrains Mono font is loaded via Google Fonts and is not cached – the app falls back to `Consolas` when offline.

### Icons

Generated by `scripts/generate_icons.py` as a `RUN` step in the Dockerfile. The script therefore runs **inside the Docker build**, not locally.

```python
# scripts/generate_icons.py
from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size):
    img = Image.new("RGB", (size, size), "#a855f7")
    draw = ImageDraw.Draw(img)
    # Draw a white "M", centred
    font_size = size // 2
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "M", font=font)
    x = (size - (bbox[2] - bbox[0])) // 2
    y = (size - (bbox[3] - bbox[1])) // 2
    draw.text((x, y), "M", fill="white", font=font)
    return img

os.makedirs("static", exist_ok=True)
make_icon(192).save("static/icon-192.png")
make_icon(512).save("static/icon-512.png")
print("Icons generated.")
```

Pillow is included in `requirements.txt`. The icons end up in `static/` and are copied into the image.

### Installation

- **Windows Chrome/Edge:** `⊕` icon in the address bar → install → dockable in the taskbar
- **Android:** Share → Add to Home screen
- **iOS:** Safari → Share → Add to Home Screen

---

## Docker

### `Dockerfile`

Icons are generated as a `RUN` step inside the Docker build via a separate script, `scripts/generate_icons.py`. This keeps the build fully self-contained – no local dependencies are needed.

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend/ ./backend/
COPY static/ ./static/
COPY scripts/ ./scripts/

# Generate PWA icons during the build
RUN python scripts/generate_icons.py

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The `.trash/` folder is **not** created via `mkdir` in the Dockerfile – the mounted volume overrides `/app/notes/` and makes the mkdir pointless. Instead the backend creates `.trash/` at startup if it is missing (see Backend – startup logic).

### `docker-compose.yml`

```yaml
services:
  hexnotes:
    build: .
    container_name: hexnotes
    restart: unless-stopped
    environment:
      - ADMIN_SECRET=${ADMIN_SECRET}
    volumes:
      - ./notes:/app/notes
      - ./tokens.json:/app/tokens.json
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

### `.env.example`

```
ADMIN_SECRET=replace-this-with-a-strong-password
```

### `tokens.json` (initial empty file)

```json
{ "tokens": [] }
```

The first token is created via `POST /admin/tokens` right after deploy.

The backend creates `tokens.json` automatically if the file is missing at startup (`{ "tokens": [] }`). This prevents Docker from creating a directory with that name if the volume is empty.

---

## Security

- Every note endpoint requires a valid Bearer token from `tokens.json`
- Admin endpoints require `ADMIN_SECRET` (separate, never the same as a regular token)
- The token is stored in the frontend's `localStorage` – an acceptable risk for single-user self-hosting
- Nginx handles TLS via Nginx Proxy Manager
- The `notes/` folder is never exposed directly on the web
- `.trash/` is never listed via the API

---

## Auth – setup flow per device

The app has no login page with a username/password. Auth is a Bearer token that is pasted once per device and saved in `localStorage`.

### The first time the app is opened (no token)

The frontend shows a token prompt instead of the app:

```
┌─────────────────────────────┐
│        HexNotes             │
│                             │
│  Enter your API token       │
│  ┌───────────────────────┐  │
│  │ tok_...               │  │
│  └───────────────────────┘  │
│         [Connect]           │
│                             │
└─────────────────────────────┘
```

The token is saved in `localStorage` → the app loads straight away. On the next visit the prompt is skipped.

### Step by step per device

**Step 1 – Create a token (once per device)**

Via Claude Code:
```
"Create a token called iphone"
→ tok_xyz999
```

Via curl:
```bash
curl -X POST https://notes.yourdomain.com/admin/tokens \
  -H "Authorization: Bearer <admin-secret>" \
  -H "Content-Type: application/json" \
  -d '{"name": "iphone"}'
```

**Step 2 – Open `https://notes.yourdomain.com` in the browser**

The token prompt is shown. Paste the token → Connect.

**Step 3 – Install as a PWA (optional)**

- **Windows Chrome/Edge:** `⊕` icon in the address bar → "Install HexNotes" → its own window, dockable in the taskbar. The PWA shares `localStorage` with the browser – the token comes along automatically.
- **Android Chrome:** Menu `⋮` → "Add to Home screen"
- **iOS Safari:** Share → "Add to Home Screen"

**Log out / switch token:** Clear `localStorage` in the browser's devtools, or add a "Log out" button in settings (out of scope for v1).

---

## Non-requirements (out of scope for v1)

- Markdown rendering in the editor
- Attachments and images
- Sharing notes
- Version history
- Notifications

---

## Future extensions

- **Git commit per save** – automatic version history
- **Emptying the trash** – via an admin endpoint or on a schedule
- **Webhook** – trigger automation on a `#tag`
- **MCP server** – if the REST API is not enough for Claude Code
- **Offline cache** – extend the Service Worker with note data for full offline reading

---

## Quick start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env and set ADMIN_SECRET

# 2. Create an empty tokens file if it does not exist
echo '{"tokens": []}' > tokens.json

# 3. Build and start
docker compose up -d

# 4. Create the first token
curl -X POST http://localhost:8000/admin/tokens \
  -H "Authorization: Bearer <admin-secret>" \
  -H "Content-Type: application/json" \
  -d '{"name": "desktop"}'

# 5. Open the app
# http://localhost:8000  (or via Nginx Proxy Manager)
```

Nginx Proxy Manager: add a Proxy Host pointing at `hexnotes:8000` with SSL.

---

## Build order for the agent

1. Create the project structure, `docker-compose.yml`, `.env.example`, an empty `tokens.json`
2. Build `backend/main.py`:
   - Token loading and validation from `tokens.json`
   - Admin endpoints (create, revoke, list tokens)
   - In-memory index built at startup and invalidated on write/rename/delete
   - Frontmatter: write on POST, read + update on PATCH if the tags changed
   - Note endpoints incl. `POST /api/notes/{id}/rename`
   - Empty content → trash logic in PATCH (blur-based, not autosave)
3. Write `scripts/generate_icons.py` – generates `icon-192.png` and `icon-512.png` with Pillow into `static/`
4. Build `static/manifest.json` and `static/sw.js`
5. Build `static/index.html`:
   - CSS with the colour palette and `prefers-color-scheme`
   - Token prompt when there is no `localStorage` token
   - Desktop layout with a collapsible sidebar
   - Filename bar always clickable, with inline rename + collision error
   - Red error bar with auto-retry (at most 3 attempts)
   - Autosave with an `isSaving` flag and a `pendingContent` variable (no queue – the latest value wins)
   - Mobile view with a FAB
   - Clear JS section comments
6. Build the `Dockerfile` and `requirements.txt`
7. Verify: the offline bar shows/hides correctly, pendingContent is saved on reconnect
8. Verify: rename works, a collision gives an inline error message
9. Verify: the error bar shows on a network error (online but a backend error) and disappears on a successful save
10. Verify: race condition (fast typing, two requests)
11. Verify: 404 at startup → fallback to an empty new note
12. Verify: PWA installation in Chrome/Edge

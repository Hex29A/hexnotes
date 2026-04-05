# agents.md – HexNotes

> Detaljerad byggspecifikation för en självhostad Google Keep-klon med Markdown-filer och REST API.

---

## Projektöversikt

**HexNotes** är en lättviktig, självhostad anteckningsapp inspirerad av Google Keep.
All data lagras som plain `.md`-filer på disk. Ingen databas.
Appen exponerar ett REST API för integration med Claude Code och andra verktyg.

**Målmiljö: Docker.** Projektet byggs och körs uteslutande som Docker-container. Det ska inte finnas något behov av att installera Python eller andra beroenden lokalt – allt sker inuti imagen.

### Mål

- Snabb input av korta snippets från mobil och desktop
- Autospar utan manuell spara-knapp
- Sökning och filtrering via `#taggar`
- Tillgänglig via webbläsaren – ingen app att installera
- Installerbar som PWA (dockad app i Windows, hemskärm på mobil)
- Claude Code kan läsa och skriva via REST API

---

## Teknikstack

| Komponent | Val | Motivering |
|-----------|-----|------------|
| Backend | Python 3.12 + FastAPI | Lätt, snabbt, autogenererad API-docs |
| Frontend | Vanilla HTML/CSS/JS | Ingen build-step, enkel att underhålla |
| Fillagring | `.md`-filer på disk | Plain text, Claude Code-läsbart |
| Container | Docker + docker-compose | Enkel deploy på VPS |
| Reverse proxy | Nginx Proxy Manager | Redan i befintlig stack |

---

## Filstruktur

```
hexnotes/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── tokens.json              # namngivna API-tokens (se Auth)
├── backend/
│   └── main.py              # FastAPI app, all backend-logik
├── scripts/
│   └── generate_icons.py    # Genererar PWA-ikoner vid docker build
├── static/
│   ├── index.html           # Hela frontend (single file)
│   ├── manifest.json        # PWA-manifest
│   ├── sw.js                # Service Worker (minimal)
│   ├── icon-192.png         # PWA-ikon (genererad via Pillow)
│   └── icon-512.png         # PWA-ikon (genererad via Pillow)
└── notes/                   # Monterad volym – dina .md-filer
    └── .trash/              # Raderade notes hamnar här
```

---

## Filnamnkonvention

Filnamnet genereras vid skapandet men kan när som helst ändras manuellt via rename-funktionen i UI:t eller via `POST /api/notes/{id}/rename`. Datumet i default-filnamnet är alltid skapandedatum – systemet eller autospar ändrar aldrig filnamnet automatiskt. Endast användaren kan byta namn.

### Default: datum + slug

```
2025-04-03-docker-compose-tips.md
2025-04-03-untitled.md        ← om användaren inte angett namn
```

### Tidlös note (inget datum)

Om användaren ändrar filnamnet vid skapandet används det namnet rakt av:

```
ideas.md
todo.md
snippets.md
```

### Regler för slug-generering (används bara om användaren inte angett filnamn)

- Första raden i texten används som slug
- Lowercase, mellanslag → bindestreck
- Specialtecken och `#taggar` stripas
- Max 60 tecken i slug-delen
- Kollision med befintlig fil → suffix `-2`, `-3`
- `.md`-extension läggs alltid till automatiskt om den saknas

---

## Backend – FastAPI (`backend/main.py`)

### Autentisering – namngivna tokens

Istället för en enda delad token används en lista med namngivna tokens i `tokens.json`:

```json
{
  "tokens": [
    { "name": "desktop",    "token": "tok_abc123", "created_at": "2025-04-03T10:00:00" },
    { "name": "iphone",     "token": "tok_def456", "created_at": "2025-04-03T10:01:00" },
    { "name": "claude-code","token": "tok_ghi789", "created_at": "2025-04-03T10:02:00" }
  ]
}
```

Alla API-endpoints kräver headern:
```
Authorization: Bearer <token>
```

Backend accepterar alla tokens i listan. Token-namnet loggas per request för spårbarhet. En enskild token kan revokeras utan att påverka övriga. `tokens.json` laddas vid start och vid varje ändring via admin-endpointen.

### Admin-endpoints

Skyddas av `ADMIN_SECRET` från `.env` – aldrig samma värde som en vanlig token.

#### `POST /admin/tokens`
Skapa ny namngiven token.
```
Authorization: Bearer <admin-secret>
Body: { "name": "work-laptop" }
Response: { "name": "work-laptop", "token": "tok_xyz999", "created_at": "..." }
```
Token sparas direkt i `tokens.json` och är aktiv omedelbart.

#### `DELETE /admin/tokens/{name}`
Revokera token med angivet namn.

#### `GET /admin/tokens`
Lista alla tokens – visar namn och datum, aldrig token-värdet.

**Typiskt Claude Code-flöde:**
```
Du: "Skapa en token för min nya laptop, kalla den work-laptop"
Claude Code → POST /admin/tokens {"name": "work-laptop"}
Claude Code: "Din token: tok_xyz999"
```

### Note-endpoints

#### `GET /api/notes`
Lista alla notes, sorterade efter `updated_at` fallande.

Query params: `q` (fritext), `tag`, `limit` (default 50), `offset`

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

`is_timeless: true` om filnamnet saknar datumprefix (`YYYY-MM-DD-`).

#### `POST /api/notes`
Skapa ny note.
```json
{ "content": "Text\n\n#tagg", "filename": "ideas.md" }
```
`filename` är valfritt. Om det utelämnas genereras `YYYY-MM-DD-slug.md`.
Kollision returnerar `409 Conflict`.

#### `GET /api/notes/{id}`
Hämta specifik note. `id` = filnamnet utan `.md`.

#### `PATCH /api/notes/{id}`
Uppdatera innehållet. Filnamnet ändras **inte** via denna endpoint.

```json
{ "content": "Uppdaterad text" }
```

Content är **alltid hela noteinnehållet**, aldrig en diff. Backend skriver filen rakt av.

Om `content` är tom sträng eller enbart whitespace → flytta filen till `.trash/` och returnera `204 No Content`.

**OBS:** Frontend får **inte** trigga detta via autospar mitt i skrivandet. Auto-trash triggas endast när användaren lämnar noten (blur-event på textarea) och innehållet är tomt. Autospar under pågående skrivning skickar aldrig PATCH med tomt innehåll.

Om en fil med samma namn redan finns i `.trash/` skrivs den över (samma beteende som DELETE).

`updated_at` hämtas från filens `mtime` – backend skriver aldrig timestamps manuellt.
`created_at` extraheras från datumprefixet i filnamnet (`2025-04-03-...`) om det finns. Annars används `mtime`. ctime används **inte** – den är opålitlig i Docker-volymer och uppdateras vid metadata-ändringar som chmod och flytt.

#### `POST /api/notes/{id}/rename`
Byt filnamn på en befintlig note.

```json
{ "new_filename": "docker-cheatsheet.md" }
```

Backend:
1. Validerar att `new_filename` inte redan existerar → `409 Conflict` med meddelandet "En note med det namnet finns redan"
2. `os.rename(gamla_path, nya_path)`
3. Returnerar uppdaterat note-objekt med nytt `id` och `filename`

`.md` läggs till automatiskt om det saknas.

Frontend **måste** omedelbart uppdatera `activeNoteId` och alla referenser till det gamla ID:t när rename lyckas. Annars kommer efterföljande PATCH-anrop att returnera 404.

#### `DELETE /api/notes/{id}`
Flytta till `notes/.trash/{filename}`. Inte permanent delete.

Om en fil med samma namn redan finns i `.trash/` skrivs den över – trash är inte ett arkiv utan en säkerhetsbuffert.

#### `GET /api/notes/{id}/raw`
Returnerar filinnehållet som `text/plain`.

#### `GET /health`
```json
{ "status": "ok", "notes_count": 42 }
```

### Filhantering

- Notes: `/app/notes/` (monterad Docker-volym)
- Trash: `/app/notes/.trash/`
- Filer som börjar med `.` ignoreras vid listning
- Sökning: görs mot in-memory index (se nedan)

### Startup-logik

Vid start utför backend följande innan den börjar ta emot requests:

1. Skapa `tokens.json` om filen saknas (`{ "tokens": [] }`)
2. Skapa `/app/notes/.trash/` om mappen saknas
3. Bygga in-memory index från alla `.md`-filer i `/app/notes/`

```python
@app.on_event("startup")
async def startup():
    # Säkerställ att tokens.json finns
    if not TOKENS_PATH.exists():
        TOKENS_PATH.write_text('{"tokens": []}')
    # Säkerställ att trash-mappen finns (volymen kan vara ny)
    TRASH_PATH.mkdir(parents=True, exist_ok=True)
    # Bygg index
    await build_index()
```

### In-memory index

Backend bygger ett index över alla notes vid start. Indexet hålls i minnet och invalideras vid varje write, rename eller delete. Sökning sker alltid mot indexet – aldrig direkt mot disk per request.

```python
# Pseudokod
notes_index: dict[str, NoteEntry] = {}  # id → NoteEntry

@app.on_event("startup")
async def build_index():
    for f in Path("/app/notes").glob("*.md"):
        notes_index[f.stem] = parse_note(f)

def invalidate(note_id: str):
    # Uppdatera befintligt entry (write/PATCH)
    notes_index[note_id] = parse_note(Path(f"/app/notes/{note_id}.md"))

def invalidate_rename(old_id: str, new_id: str):
    # Ta bort gammalt entry, lägg till nytt
    notes_index.pop(old_id, None)
    notes_index[new_id] = parse_note(Path(f"/app/notes/{new_id}.md"))

def invalidate_delete(note_id: str):
    notes_index.pop(note_id, None)
```

Indexet läser varje fil en gång vid start. Vid 500 filer är detta försumbart. Sökning är därefter O(n) i minnet – inga disk-reads per tangenttryckning.

### Frontmatter

Backend **skriver** YAML frontmatter vid skapandet av varje note:

```markdown
---
tags: [docker, snippets]
created: 2025-04-03
---
Docker compose – persistent volumes

Innehåll här...
```

- `#taggar` i texten är **alltid källan till sanning** för tags
- Vid varje PATCH extraheras `#taggar` från texten och frontmatter skrivs om – oavsett vad frontmatter innehöll tidigare
- `created` sätts från datumprefixet i filnamnet om det finns, annars dagens datum – skrivs aldrig om
- Backend **läser** frontmatter om det finns men **kräver** det inte – filer utan frontmatter fungerar fullt ut
- `content` i API-responsen inkluderar **inte** frontmatter-blocket – bara den rena texten
- Tidlösa notes (`ideas.md`) utan datumprefix får `created: null` i frontmatter

**Fördel för Claude Code:** strukturerad metadata är lättare att parsa än att grep:a `#taggar` i fritext. Tags och datum finns tillgängliga utan att tolka innehållet.

---

## Frontend (`static/index.html`)

Single-file app. All HTML, CSS och JavaScript i en fil, organiserad i tydliga sektioner med kommentarer: `// === SECTION: AUTH ===`, `// === SECTION: API ===` etc.

### Typografi

- **Font:** `JetBrains Mono` via Google Fonts
- Fallback: `Consolas, 'Courier New', monospace`
- Fontstorlek: 14px bas, 13px i listan

### Färgpalett

| Token | Mörkt tema | Ljust tema |
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

Tema följer `prefers-color-scheme`. Ingen manuell toggle i v1.

### Desktop-layout

```
┌─────────────────────────────────────────────────┐
│ [☰]  🔍 Sök...                        [+ Ny]   │  ← topbar
├───────────────────┬─────────────────────────────┤
│                   │ 📄 2025-04-03-docker.md  ✎  │  ← filnamnsrad (alltid klickbart)
│   SIDEBAR         ├─────────────────────────────┤
│   (collapsible)   │ ⚠ Kunde inte spara...       │  ← röd felbar (dold)
│                   ├─────────────────────────────┤
│  ┌─────────────┐  │                             │
│  │ Preview...  │  │   textarea                  │
│  │ #chip #chip │  │   (JetBrains Mono)          │
│  │ idag        │  │                        ✓    │
│  └─────────────┘  │                             │
│  ┌─────────────┐  │                             │
│  │ Preview...  │  │                             │
│  │ #chip       │  │                             │
│  │ igår        │  │                             │
│  └─────────────┘  │                             │
└───────────────────┴─────────────────────────────┘
```

- Sidebar collapsible via `[☰]` – state sparas i `localStorage`
- När sidebar är gömd: editor expanderar till full bredd
- Aktiv note: `3px` vänsterbård i `--accent` + `--bg-card-active`
- Sidebar-bredd: `300px`, fast

### Filnamnsrad

Visas alltid överst i editorn, ovanför felbaren.

```
📄 2025-04-03-docker-tips.md  ✎
```

- Filnamnet är **alltid klickbart** – klick aktiverar inline-redigering
- `✎`-ikonen har generös klickyta (`padding: 8px 12px`) för att fungera på mobil
- Klick på filnamn eller `✎` → `<input>` med nuvarande filnamn ifyllt, markerat
- Enter bekräftar → `POST /api/notes/{id}/rename`
- Escape avbryter utan ändring
- `.md` läggs till automatiskt om det saknas
- Tomt fält → avbryt, behåll nuvarande namn
- Vid kollision: felmeddelande visas inline under inputfältet i `--error-text`
- Under rename-request: input disabled, liten spinner
- Vid lyckat rename: sidebar uppdateras med nytt filnamn

### Röd felbar

Direkt under filnamnsraden:

```
⚠ Kunde inte spara – kontrollera anslutningen
```

- `display: none` som default
- Visas omedelbart vid misslyckat save (nätverksfel eller icke-2xx svar)
- Försvinner vid nästa lyckade save
- Auto-retry: försöker igen efter 5s, max 3 försök totalt
- Efter 3 misslyckade försök: felbar stannar kvar tills sidan laddas om
- Felräknaren nollställs vid lyckat save

### Sidebar – notekortet

```
┌──────────────────────────────┐
│ Första raden i texten...     │  ← trunkeras ~55 tecken
│ #docker #snippets            │  ← färgade chips
│ idag                         │  ← relativt datum
└──────────────────────────────┘
```

- Chips: `--accent-dim` bakgrund, `--accent` text, `border-radius: 9999px`, padding `2px 8px`
- Hover: `--bg-card`

### Ny note

- Knapp `[+ Ny]` i topbaren + `Ctrl+N`
- Skapar tomt note-objekt lokalt (POST sker inte förrän vid första autospar)
- Fokuserar editorn direkt
- Om användaren lämnar noten (blur) utan att ha skrivit något → gör ingenting, skapa aldrig filen

### Editorn

- `<textarea>` utan toolbar, `flex: 1`, `resize: none`
- Tab → 2 mellanslag
- Ingen markdown-rendering
- Sparat-indikator nere till höger: `···` (pulserar) → `✓` (tonar ut 2s) → dolt

### Sökning

- Alltid synligt i topbaren
- Live-filter med debounce 300ms
- Söker i innehåll + taggar + filnamn
- `Ctrl+F` fokuserar, `Escape` rensar

### Tangentbordsgenvägar

| Genväg | Funktion |
|--------|----------|
| `Ctrl+N` | Ny note |
| `Ctrl+F` | Fokus på sökfält |
| `Ctrl+B` | Toggla sidebar |
| `Ctrl+Delete` | Radera aktiv note (bekräftelsedialog) |
| `Escape` | Rensa sökning |

---

### Mobilvy (≤768px)

Två-vy-modell. Standardvy vid öppning: **editor** (senast öppnad note, sparas i `localStorage` som `lastNoteId`).

**Fallback:** Om `lastNoteId` inte längre existerar (note raderad, omdöpt, eller första gången) → visa en tom ny note redo att skriva i. Försök aldrig visa ett 404-fel för användaren vid start.

**Editorvy:**
```
┌─────────────────────────┐
│ [←]  HexNotes           │
├─────────────────────────┤
│ 📄 ideas.md           ✎ │  ← alltid klickbart
├─────────────────────────┤
│ ⚠ Kunde inte spara...  │  ← dold tills fel
├─────────────────────────┤
│   textarea         ✓    │
│                    [+]  │  ← FAB
└─────────────────────────┘
```

**Listvy (`[←]` i topbaren):**
```
┌─────────────────────────┐
│ 🔍 Sök...               │
├─────────────────────────┤
│ ┌─────────────────────┐ │
│ │ Preview...          │ │
│ │ #chip #chip   idag  │ │
│ └─────────────────────┘ │
│                    [+]  │  ← FAB
└─────────────────────────┘
```

- **FAB:** `position: fixed`, `bottom: 24px`, `right: 24px`, `56px` cirkulär, `--accent`
- FAB skapar ny note och öppnar editorn
- Tryck på note i lista → editorvy

---

## Autospar – detaljerat flöde

```
Användaren skriver
        ↓
pendingContent = content          ← alltid uppdateras, oavsett nätverksstatus
clearTimeout(saveTimer)
        ↓
isOnline?
  Nej → visa offline-indikator, vänta på online-event (inget timer)
  Ja  → saveTimer = setTimeout(save, 1000)
        ↓  (1 sekund utan knapptryckning)
save(pendingContent)
  ├── isSaving === true?
  │     → avvakta, pendingContent är redan uppdaterat
  ├── isNew === true?
  │     → POST /api/notes (med ev. manuellt filnamn)
  │     → vid lyckat: isNew = false
  └── isNew === false?
        → PATCH /api/notes/{id}

OBS: Autospar skickar aldrig tomt content. Tom note → trash hanteras
     enbart via blur-event (se "Auto-trash" nedan), aldrig via detta flöde.

  Lyckat:
    isSaving = false
    pendingContent = null
    Visa ✓, dölj felbar och offline-indikator
    Nollställ retryCount

  Misslyckat (online men fel):
    isSaving = false
    Visa röd felbar
    retryCount++
    retryCount <= 3 → retry efter 5s
    retryCount >  3 → felbar stannar, inga fler retries
```

---

## Offline-hantering

### Tillståndsmaskinen

Frontend håller tre variabler:

```javascript
let isOnline      = navigator.onLine; // startvärde
let pendingContent = null;            // senaste osparade innehåll
let healthInterval = null;            // polling-timer, körs bara offline
```

`isOnline` är **inte** samma sak som `navigator.onLine` rakt av – den uppdateras via en kombination av browser-events och faktiska request-resultat (se nedan).

### Online/offline-events

```javascript
window.addEventListener('offline', () => goOffline());
window.addEventListener('online',  () => checkHealth());
```

`online`-eventet litar vi inte på blint – det triggar ett health-check-anrop innan vi deklarerar oss online igen.

### Health-check + polling

```javascript
async function checkHealth() {
  try {
    const r = await fetch('/health', { signal: AbortSignal.timeout(3000) });
    if (r.ok) goOnline();
  } catch {
    // fortfarande offline, polling fortsätter
  }
}

function goOffline() {
  isOnline = false;
  showOfflineBar();
  clearTimeout(saveTimer);
  // Starta polling var 30s – BARA när offline
  if (!healthInterval) {
    healthInterval = setInterval(checkHealth, 30000);
  }
}

function goOnline() {
  isOnline = true;
  clearInterval(healthInterval);
  healthInterval = null;
  hideOfflineBar();
  // Spara direkt om det finns väntande innehåll
  if (pendingContent !== null) save(pendingContent);
}
```

Polling körs **enbart offline** – noll extra requests när allt fungerar normalt.

### Request-fel som offline-detektor

Om ett save-anrop misslyckas med nätverksfel (inte 4xx/5xx utan connection error):

```javascript
} catch (err) {
  if (!navigator.onLine) {
    goOffline(); // nätverket försvann under request
  } else {
    showErrorBar(); // online men backend-fel
    scheduleRetry();
  }
}
```

Det fångar scenariot där nätverket försvinner mitt i ett pågående request.

### Visuell feedback-hierarki

Tre distinkta tillstånd – aldrig överlappande:

| Tillstånd | UI-signal | Färg | Placering |
|-----------|-----------|------|-----------|
| Sparar | `···` pulserar | `--accent` | Hörnet i editorn |
| Sparat | `✓` tonar ut 2s | `--accent` | Hörnet i editorn |
| **Offline** | statusrad | gul `#854d0e` / `#fef08a` | Nedre kanten av appen |
| Sparfel (online) | felbar | röd `--error-*` | Under filnamnsraden |

**Offline är inte ett fel** – gul färg signalerar väntetillstånd, inte katastrof. Röd felbar reserveras för när nätverket är uppe men backend ändå svarar fel.

### Offline-indikatorn (desktop + mobil)

```
┌─────────────────────────────────────────────────┐
│ ● Offline – ändringar sparas när du är online   │
└─────────────────────────────────────────────────┘
```

- `position: fixed`, `bottom: 0`, `left: 0`, `right: 0`
- Höjd: `32px`, centrerad text
- Bakgrund: `#422006` (mörkt tema) / `#fef9c3` (ljust tema)
- Text: `#fef08a` / `#854d0e`
- Dold som default (`display: none`)
- På mobil: hamnar ovanför FAB:en (FAB får `bottom: 58px` när offline-bar visas, annars `bottom: 24px`)
- `z-index` hierarki: offline-bar `z-index: 200`, FAB `z-index: 100` – offline-baren täcker aldrig FAB men syns alltid

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

Service Worker cachar statiska assets så att appen kan **starta offline**. Utan detta kan appen inte öppnas utan nätverksanslutning, vilket gör all JS-offline-logik meningslös.

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
  // API-anrop går alltid till nätverket
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/admin')) {
    e.respondWith(fetch(e.request));
    return;
  }
  // Statiska assets: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
```

Cache invalideras automatiskt vid ny deploy via `CACHE = 'hexnotes-v2'` etc. JetBrains Mono-fonten laddas via Google Fonts och cachas inte – appen faller tillbaka på `Consolas` om offline.

### Ikoner

Genereras av `scripts/generate_icons.py` som ett `RUN`-steg i Dockerfile. Skriptet körs alltså **inuti Docker-bygget**, inte lokalt.

```python
# scripts/generate_icons.py
from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size):
    img = Image.new("RGB", (size, size), "#a855f7")
    draw = ImageDraw.Draw(img)
    # Rita vit "M" centrerad
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

Pillow ingår i `requirements.txt`. Ikonerna hamnar i `static/` och kopieras med i imagen.

### Installation

- **Windows Chrome/Edge:** `⊕`-ikon i adressfältet → installera → dockningsbar i taskbaren
- **Android:** Dela → Lägg till på hemskärmen
- **iOS:** Safari → Dela → Lägg till på hemskärmen

---

## Docker

### `Dockerfile`

Ikoner genereras som ett `RUN`-steg inuti Docker-bygget via ett separat skript `scripts/generate_icons.py`. På så sätt är bygget helt self-contained – inga lokala beroenden krävs.

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# Installera beroenden
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiera källkod
COPY backend/ ./backend/
COPY static/ ./static/
COPY scripts/ ./scripts/

# Generera PWA-ikoner under bygget
RUN python scripts/generate_icons.py

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.trash/`-mappen skapas **inte** via `mkdir` i Dockerfile – den monterade volymen åsidosätter `/app/notes/` och gör mkdir meningslöst. Backend skapar istället `.trash/` vid startup om den saknas (se Backend – startup-logik).

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
ADMIN_SECRET=byt-ut-detta-till-ett-starkt-lösenord
```

### `tokens.json` (initial tom fil)

```json
{ "tokens": [] }
```

Första token skapas via `POST /admin/tokens` direkt efter deploy.

Backend skapar `tokens.json` automatiskt om filen saknas vid start (`{ "tokens": [] }`). Detta förhindrar att Docker skapar en katalog med det namnet om volymen är tom.

---

## Säkerhet

- Alla note-endpoints kräver giltig Bearer token från `tokens.json`
- Admin-endpoints kräver `ADMIN_SECRET` (separat, aldrig samma som en vanlig token)
- Token lagras i frontend `localStorage` – acceptabel risk för single-user self-hosted
- Nginx hanterar TLS via Nginx Proxy Manager
- `notes/`-mappen exponeras aldrig direkt via webben
- `.trash/` listas aldrig via API

---

## Auth – installationsflöde per enhet

Appen har ingen login-sida med användarnamn/lösenord. Auth är en Bearer token som klistras in en gång per enhet och sparas i `localStorage`.

### Första gången appen öppnas (token saknas)

Frontend visar en token-prompt istället för appen:

```
┌─────────────────────────────┐
│        HexNotes             │
│                             │
│  Ange din API-token         │
│  ┌───────────────────────┐  │
│  │ tok_...               │  │
│  └───────────────────────┘  │
│         [Anslut]            │
│                             │
└─────────────────────────────┘
```

Token sparas i `localStorage` → appen laddas direkt. Vid nästa besök hoppas prompten över.

### Steg-för-steg per enhet

**Steg 1 – Skapa en token (en gång per enhet)**

Via Claude Code:
```
"Skapa en token som heter iphone"
→ tok_xyz999
```

Via curl:
```bash
curl -X POST https://notes.dindomän.se/admin/tokens \
  -H "Authorization: Bearer <admin-secret>" \
  -H "Content-Type: application/json" \
  -d '{"name": "iphone"}'
```

**Steg 2 – Öppna `https://notes.dindomän.se` i webbläsaren**

Token-prompten visas. Klistra in token → Anslut.

**Steg 3 – Installera som PWA (valfritt)**

- **Windows Chrome/Edge:** `⊕`-ikon i adressfältet → "Installera HexNotes" → eget fönster, dockningsbar i taskbaren. PWA delar `localStorage` med webbläsaren – token följer med automatiskt.
- **Android Chrome:** Meny `⋮` → "Lägg till på hemskärmen"
- **iOS Safari:** Dela → "Lägg till på hemskärmen"

**Logga ut / byta token:** Rensa `localStorage` i webbläsarens devtools, eller lägg till en "Logga ut"-knapp i settings (out of scope v1).

---

## Icke-krav (ut ur scope för v1)

- Markdown-rendering i editorn
- Bilagor och bilder
- Delning av notes
- Versionshistorik
- Notifikationer

---

## Framtida utbyggnad

- **Git-commit per save** – automatisk versionshistorik
- **Tömning av trash** – via admin-endpoint eller schemalagt
- **Webhook** – trigga automation på `#tagg`
- **MCP-server** – om REST API inte räcker för Claude Code
- **Offline-cache** – utöka Service Worker med notes-data för fullständig offline-läsning

---

## Snabbstart

```bash
# 1. Klona och konfigurera
cp .env.example .env
# Redigera .env och sätt ADMIN_SECRET

# 2. Skapa tom tokens-fil om den inte finns
echo '{"tokens": []}' > tokens.json

# 3. Bygg och starta
docker compose up -d

# 4. Skapa första token
curl -X POST http://localhost:8000/admin/tokens \
  -H "Authorization: Bearer <admin-secret>" \
  -H "Content-Type: application/json" \
  -d '{"name": "desktop"}'

# 5. Öppna appen
# http://localhost:8000  (eller via Nginx Proxy Manager)
```

Nginx Proxy Manager: lägg till en Proxy Host mot `hexnotes:8000` med SSL.

---

## Byggordning för agenten

1. Skapa projektstruktur, `docker-compose.yml`, `.env.example`, tom `tokens.json`
2. Bygg `backend/main.py`:
   - Token-laddning och validering från `tokens.json`
   - Admin-endpoints (skapa, revokera, lista tokens)
   - In-memory index med startup-byggande och invalidering vid write/rename/delete
   - Frontmatter: skriv vid POST, läs + uppdatera vid PATCH om tags ändrats
   - Note-endpoints inkl. `POST /api/notes/{id}/rename`
   - Tom content → trash-logik i PATCH (blur-baserat, ej autospar)
3. Skriv `scripts/generate_icons.py` – genererar `icon-192.png` och `icon-512.png` via Pillow till `static/`
4. Bygg `static/manifest.json` och `static/sw.js`
5. Bygg `static/index.html`:
   - CSS med färgpalett och `prefers-color-scheme`
   - Token-prompt vid saknad `localStorage`-token
   - Desktop-layout med collapsible sidebar
   - Filnamnsrad alltid klickbar med inline rename + kollisionsfel
   - Röd felbar med auto-retry (max 3 försök)
   - Autospar med `isSaving`-flagga och `pendingContent`-variabel (ej kö – senaste värde gäller)
   - Mobilvy med FAB
   - Tydliga JS-sektionskommentarer
6. Bygg `Dockerfile` och `requirements.txt`
7. Verifiera: offline-bar visas/döljs korrekt, pendingContent sparas vid reconnect
8. Verifiera: rename fungerar, kollision ger felmeddelande inline
9. Verifiera: felbar visas vid nätverksfel (online men backend-fel), försvinner vid lyckat save
10. Verifiera: race condition (snabb typing, två requests)
11. Verifiera: 404 vid start → fallback till tom ny note
12. Verifiera: PWA-installation i Chrome/Edge

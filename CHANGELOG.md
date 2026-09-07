# Changelog – HexNotes

Versionsschema: `major.minor`. Minor bumpas vid nya funktioner, major vid
brytande ändringar (API-inkompatibilitet eller ändrat lagringsformat som
kräver migrering). Aktuell version sätts i `APP_VERSION` i `backend/main.py`,
exponeras via `GET /health` och visas längst ner i sidofältet.

Service workerns cachenamn (`hexnotes-vN` i `static/sw.js`) är **inte** kopplat
till appversionen — det bumpas bara när cachestrategin i sig ändras. Sedan 1.4
är app-skalet network-first, så deployer når klienter utan cache-bump.

## 1.24 (2026-09-07)

Security and cleanup pass. No behaviour changes.

- **Markdown libraries are now served locally.** `marked` and `DOMPurify` were
  loaded from jsDelivr at a floating "latest" version with no integrity check.
  Whoever controls that CDN could have replaced `purify.min.js` — disabling the
  XSS sanitizer and reading the API token out of `localStorage` in the same
  move. Both are now pinned, committed under `static/vendor/`, and cached by the
  service worker, so the rendered preview also works fully offline. See
  `static/vendor/README.md` for versions, hashes and upgrade steps.
- **Security headers on every response.** A Content-Security-Policy plus
  `X-Content-Type-Options`, `Referrer-Policy` and `X-Frame-Options`. The CSP's
  `connect-src 'self'` means that even a successful XSS cannot post your token
  or notes to another host. `/docs` is exempt so Swagger UI still works.
- **Constant-time token comparison.** Token and admin-secret checks use
  `secrets.compare_digest`, removing a (marginal) timing side channel. As a
  side effect, a token containing non-ASCII characters now returns `401`
  instead of `500`.
- **`tokens.json` is written with mode `0600`** instead of inheriting the
  default umask.
- **Failed token writes are logged** rather than silently swallowed — such a
  failure produced a token that worked until the next restart, then vanished.
- **Redundant code removed:** unused `unicodedata` import, a dead
  double-assignment of `expires_at` and a function-local `timedelta` import in
  `create_note`, three copies of the "first non-blank line" preview loop
  (now one `_first_line` helper), and four copies of the search-highlight
  markup in the frontend (now one `setHighlighted` helper).
- **Dead functions removed:** `generate_slug()` and `strip_frontmatter()`.
  Neither was reachable from the app — only from tests. Slug filenames were
  superseded by plain `YYYY-MM-DD.md` names (a slug would break `Ctrl+D`, which
  needs today's filename to be predictable), and `strip_frontmatter` duplicated
  the body that `parse_frontmatter` already returns. The stale slug section in
  `agents.md` has been corrected to match the shipped behaviour.

## 1.23 (2026-09-07)

- **New-note focus.** Creating a note now puts focus directly in the editor on
  iOS and desktop. The normal date-and-slug filename is still generated on the
  first save; filename editing remains available through the rename control.
- **Ephemeral confirmation.** A visible `Ephemeral - 48h` badge now appears in
  the editor header as soon as a long-press creates an ephemeral note. After
  saving, it becomes a live remaining-time indicator, matching the sidebar
  card badge.
- **Long-press reliability.** Releasing the mobile FAB after a successful hold
  now correctly suppresses its synthetic normal-click event.

## 1.22 (2026-09-07)

_Changelog entries are in English from this version on._

- **Live sync of the open note.** The note you are reading now updates when it
  changes on the server — an AI agent writing over the API, or another device.
  Previously only the sidebar refreshed, so an open note could sit stale
  indefinitely. The refresh reuses the list poll (which already carries full
  content), so it costs no extra requests. Caret and scroll position are
  preserved; an editor with unsaved changes is never overwritten.
- **Conflict detection (no more silent overwrites).** `PATCH /api/notes/{id}`
  accepts an optional `base_version`; if the note changed since that version the
  write is rejected with `409` instead of clobbering. This closes a real
  data-loss path: open a note, let an agent write to it, type one character, and
  the agent's work was silently replaced. The frontend sends `base_version`
  automatically and offers **Load theirs** / **Keep mine**.
- **New `version` field** on every note object — a short content hash. Hashes the
  body only, so pinning a note does not invalidate an open editor. Deliberately
  not `updated_at`, which only has second resolution and cannot distinguish two
  writes in the same second.
- `base_version` is optional, so existing API clients keep working unchanged.
- **Save-path hardening** found while reviewing the above:
  - Keystrokes typed while a save was in flight could be marked saved and then
    discarded by an incoming refresh. The buffer is now only cleared if it still
    matches what was actually sent.
  - Switching notes mid-save wrote the old note's version into the newly opened
    one, causing a bogus conflict on the next keystroke. Save continuations now
    verify they still own the editor before touching shared state.
  - Naming a new note via the filename field never recorded its version, so that
    note saved unconditionally for the rest of the session — precisely the case
    where an agent write got overwritten. Fixed.
  - A list response fetched before a local write could roll the editor (and its
    version) backwards. List fetches now carry a write sequence number and stale
    payloads are discarded.
- 16 new tests (120 total passing), plus browser verification of the sync and
  conflict UI and of each race above.

## 1.21.1 (2026-08-21)

- **Bugfix**: ephemeral-flaggan tappades nar man namngav en ny not (doRename skapade noten utan ttl_hours och nollstalde flaggan) - drabbade mobilens FAB-langtryck dar namnfrasen kommer forst. doRename skickar nu med ttl_hours = 48 nar ephemeral ar armerad. 104 tester passerar.

## 1.21 (2026-08-21)

- **Mobil UX - langtryck pa +-knappen (FAB)** skapar en ephemeral not (48h). FAB:n lysnar gul under holdet med hint ⏳ Ephemeral not, kort vibration bekräftar. Kort tryck = vanlig not som vanligt.
- Topbar-⏳-knappen goms på små skärmar (FAB-langtryck tar över); den finns kvar på desktop.
- JS-syntax verifieras nu med esprima före deploy (efter 1.20.x-haveriet). 102 tester passerar.

## 1.20.3 (2026-08-21)

- KRITISK bugfix del 2: hourglass-strangen saknade aven avslutande apostrof (1.20.2 lagg bara till komma). JS-parse verifierad med esprima fore deploy. 99 tester passerar.

## 1.20.2 (2026-08-21)

- KRITISK bugfix: saknat komma i hourglass-ikonens SVG-strang (fr 1.20.1) kraschade hela app-JS:et - ingen kunde logga in. Fixat. 99 tester passerar.

## 1.20.1 (2026-08-21)

- Bugfix mobil: hourglass-knappen (ephemeral) var osynlig/trang pa sma skarmar. Visas nu kompakt i topbaren pa mobil med hourglass-ikon; Today-knappen goms pa mobil. 99 tester passerar.

## 1.20 – 2026-08-21

- **UI — Ephemeral-sektionen överst**: kortlivade noter med levande TTL visas i en egen ⏳-sektion högst upp i sidofäljen (över Pinned). De exkluderas från Pinned/Inbox/taggar sänge de lever.
- **Gul markering**: ephemeral-kort får gul vänsterkant och svag gul toning.
- **Nedräknings-badge**: varje kort visar ⏳ 'Xh kvar' / 'Xm kvar', uppdateras varje minut.
- 3 nya tester (99 totalt passerar).

## 1.19 – 2026-08-21

- **Ny funktion — kortlivade (ephemeral) noter**: ny knapp i topbar (tidsglas-ikon, bredvid “+ New”) skapar en not som automatiskt flyttas till papperskorgen efter 48 timmar. TTL skickas som `ttl_hours` vid `POST /api/notes` (valfritt, heltimmar), lagras som `expires_at` i frontmatter och överlever redigeringar och pin-växling. Bakgrundssvep var 10:e minut + vid omstart städar utgångna noter.

## 1.18 – 2026-07-24

- **Bugfix — ny not tappade sin titel om man klickade i texten före Enter**:
  filnamnsfältet vid namngivning av en ny not committade bara namnet på
  Enter. Klickade man istället direkt i editorn (utan Enter) triggade det
  bara ett blur som TOG BORT det skrivna namnet utan att spara det — noten
  skapades sedan utan filnamn, och backend föll tillbaka på dagens datum som
  filnamn. Blur committar nu namnet (samma no-op-skydd som Enter om fältet är
  tomt/oförändrat) istället för att kasta det. Skyddade även mot en möjlig
  dubbel-POST-race mot autosaven genom att låta namn-committen använda samma
  isSaving-spärr.

## 1.17 – 2026-07-24

- **Bugfix — borttaget auto-trash-on-blur i editorn**: när textarean tappade
  fokus medan den var tom PATCHades noten med tomt innehåll, vilket
  server-sidan tolkar som "flytta till papperskorgen". Blur är inget bevis på
  avsikt — den triggas av avbrott (notis, appväxling, telefonlås,
  autocomplete som stjäl fokus), även mitt i en redigering (t.ex.
  markera-allt-och-skriv-om). Orsakade en riktig radering av home.md
  2026-07-13. Radering sker nu bara via den explicita delete-knappen.

## 1.16 – 2026-07-07

- **Auto-uppdaterad fillista**: sidofältet pollar `/api/notes` var 30:e sekund
  (bara när fliken är synlig) och direkt när fliken får fokus igen. Ritar bara
  om när listan faktiskt ändrats — scrolläge och pågående redigering störs inte.
  Noter skapade via API:t (t.ex. från Claude) dyker upp utan manuell reload.

## 1.15 – 2026-06-26

- **Checklista i editorn**: ny ☑-knapp i filnamnsraden som lägger `- [ ] ` på
  aktuell rad, eller på varje markerad rad om flera är markerade.
- **Auto-fortsätt på lista**: Enter på en checkbox- eller punktrad skapar nästa
  punkt automatiskt; Enter på en tom punkt avslutar listan.

## 1.14 – 2026-06-11

- **Tematoggle**: diskret knapp längst ner i sidofältet (bredvid Trash)
  som cyklar auto → mörk → ljus. Auto följer systemet (som tidigare),
  de andra två låser temat via data-theme-attribut. Valet sparas i
  localStorage och appliceras före första render (ingen blink).
  theme-color-metataggen (PWA-statusfältet på Android) följer med

## 1.13 – 2026-06-11

- **Lucide-ikoner**: alla emoji-knappar (📌🕘👁🗑✎📅 m.fl.) ersatta med
  inline-SVG från Lucide (ISC-licens) — konsekvent utseende på alla
  plattformar, ärver färg via currentColor så hover/aktiv-tillstånd
  färgas på riktigt. Ingen CDN i drift; path-data inbäddad i index.html
- **Ny PWA-appikon**: violett gradient på rundad kvadrat med vitt
  H-monogram (geometriskt ritat, inget typsnittsberoende) — ersätter
  gamla hexagon/anteckningsdesignen. Service worker-cache bumpad till v4
  så klienter hämtar de nya ikonerna

## 1.12 – 2026-06-11

- **Tagg-autocomplete**: `#` följt av minst ett tecken föreslår befintliga
  taggar (minimum ett tecken så den inte triggar på markdown-rubriker);
  samma dropdown och tangentstyrning som [[-autocomplete
- **Backlinks**: diskret rad längst ner i preview — "Linked from: x · y" —
  med klickbara länkar till noter som [[länkar]] hit; visas bara när minst
  en annan not länkar till den aktuella

## 1.11 – 2026-06-11

- **Seed-not vid tom installation**: en helt tom notes-mapp får en
  förifylld `home.md` (välkomsttext + funktionsguide) vid uppstart, så
  nya installationer öppnar på en startsida istället för en tom lista.
  Rörs aldrig om det redan finns noter

- **Bakåtnavigering**: varje öppnad not får en hash-URL (#not-id) i
  webbläsarhistoriken — telefonens bakåtgest, webbläsarens bakåt/framåt och
  Alt+← går till föregående not istället för att lämna appen. Synlig
  ←-knapp i filnamnsraden (visas bara när det finns något att gå tillbaka
  till). Hash-URL:er fungerar som deep-links: ladda sidan med #not-id så
  öppnas den noten direkt. Rename uppdaterar URL:en; borttagna noter i
  historiken faller tillbaka till home-noten

## 1.10 – 2026-06-11

- **[[ -autocomplete**: skriv `[[` i editorn så öppnas en dropdown som
  filtrerar notnamn medan du skriver; piltangenter navigerar, Enter/Tab
  infogar länken (med avslutande `]]`), Escape stänger
- **Klickbara checkboxar i preview**: `- [ ]`-rader renderas som riktiga
  checkboxar som kan bockas av direkt i läsläget — ändringen sparas till
  filen (n:te checkboxen mappas till n:te task-raden, kodblock hoppas över)
- **Dagens not**: 📅-knapp i topbaren (även mobil) och `Ctrl+D` öppnar
  dagens `YYYY-MM-DD.md`, eller skapar den om den inte finns

## 1.9 – 2026-06-11

- **Dubbelklick/dubbeltapp för redigering**: dubbelklick (desktop) eller
  dubbeltapp (mobil) på den renderade texten växlar till editorn; länkar
  undantagna — de navigerar som vanligt

## 1.8 – 2026-06-11

- **Noter öppnas i preview-läge**: alla noter med innehåll renderas som
  markdown direkt vid öppning; Ctrl+M eller 👁 växlar till redigering.
  Tomma noter öppnas direkt i editorn
- **Buggfix**: "ny not" gjorde ingenting när aktiv not var i preview-läge —
  `createNewNote()` återställde aldrig preview-flaggan, så editorn förblev
  dold bakom gamla notens renderade HTML

## 1.7 – 2026-06-10

- **Startsida via hem-not**: finns en not `home.md` öppnas den i preview-läge
  vid appstart (med klickbara wiki-länkar) istället för senast öppnade noten;
  klick på HexNotes-titeln i toppbaren går alltid hem
- Synlig på-markering för emoji-knappar (📌 pin, 👁 preview): bakgrundschip
  med accentram — emojis ignorerar CSS-färg, så färgbytet syntes aldrig

## 1.6 – 2026-06-10

- **Empty trash**: `DELETE /api/trash` raderar allt i papperskorgen permanent
  (filer + historik); "Empty trash"-knapp i trash-dialogen med tvåklicksskydd
- Konsekvent engelska i hela UI:t (dialoger, knappar, datumformat)
- Versionsnumret visas i toppbaren bredvid HexNotes-titeln (flyttat från
  sidofältet)

## 1.5 – 2026-06-10

- **Papperskorg med UI**: lista, förhandsvisa, återställ och radera permanent
  (`GET /api/trash`, `GET/POST/DELETE /api/trash/{name}(/restore)`)
- Radering använder timestampade namn i `.trash/` — namnkrockar skriver aldrig
  över något (tidigare förlorades äldsta filen)
- Versionshistoriken följer med noten till papperskorgen och tillbaka vid
  återställning; en ny not med samma namn startar med ren historik
- Återställning krockar aldrig med levande noter — får unikt namn (`namn-2.md`)
- Permanent radering tar bort både fil och historik (för innehåll som måste
  förstöras på riktigt, t.ex. läckta hemligheter)
- **Säkerhetsfix**: path traversal i rename-endpointen (filnamn saniterades inte)
- Version exponeras i `/health` och visas i sidofältet

## 1.4 – 2026-06-10

- Service workern network-first för app-skalet — deployer når PWA-klienter
  automatiskt utan cache-bump
- Bugfix: att namnge en ny not skapar den direkt, även med tomt innehåll
- Bugfix: en not som aldrig haft innehåll papperskorgas inte vid tappat fokus

## 1.3 – 2026-06-10

- **Versionshistorik per not**: tidigare versioner sparas i `.history/<id>/`
  vid varje sparning (`GET /api/notes/{id}/history(/{version})`), med
  readonly-vy och Återställ-knapp i UI
- **Wiki-länkar**: `[[notnamn]]` renderas som klickbar länk i förhandsgranskningen;
  saknade noter visas röda/streckade
- Filnamnsfältet redigerbart direkt när en ny not skapas, med autofokus

## 1.2 – 2026-04/05

- Kommandopalett (`Ctrl+P`), sök-i-not (`Ctrl+F`), sökrensning,
  träffmarkering och innehållssnippets i sökresultat
- Platt resultatlista vid sökning

## 1.1 – 2026-04

- Taggbaserade sidofältsgrupper med filterchips, Pinned/Inbox/Tags-sektioner,
  collapse all

## 1.0 – 2026-04-05

- Första versionen: FastAPI-backend, noter som `.md`-filer med YAML-frontmatter,
  token-auth, PWA-frontend i en enda HTML-fil, markdown-förhandsgranskning
  (`Ctrl+M`), autospar, offline-läge, papperskorg på disk

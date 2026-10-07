# Changelog – HexNotes

Version scheme: `major.minor`. Minor is bumped for new features, major for
breaking changes (API incompatibility or a changed storage format that needs a
migration). The current version is set in `APP_VERSION` in `backend/main.py`,
exposed via `GET /health` and shown in the top bar.

The service worker cache name (`hexnotes-vN` in `static/sw.js`) is **not** tied
to the app version — it is only bumped when the caching strategy itself
changes. Since 1.4 the app shell is network-first, so deploys reach clients
without a cache bump.

The whole project — changelog, commits, code comments, tests and UI — is
written in English (entries before 1.22 and between 1.33 and 1.40 were
originally in Swedish and have been translated).

## 1.41 (2026-10-07)

- **Last Swedish UI strings translated.** The ephemeral countdown badge said
  `29h kvar` / `expired` read `utgången`; it now says `29h left`, `5m left` and
  `expired`. The checklist button's tooltip is `Insert checklist`.
- Changelog translated to English throughout.

## 1.40 (2026-10-07)

- **The date on a note card counts calendar days** instead of 24-hour spans.
  A note edited at 18:00 yesterday said "today" under the Yesterday heading in
  All notes; card and heading now agree (across daylight-saving changes too).
- New screenshot in `docs/screenshot.png`, made with invented demo notes.

## 1.39 (2026-10-07)

- **Inbox is now All notes and holds every unpinned note**, tagged or not.
  Previously a tagged note only landed in its tag group under Tags, which
  starts collapsed, so a new journal note tagged `#GROT` did not show at the
  top after a refresh. Tagged notes now appear both in All notes and in their
  tag group.
- **All notes is sorted by last edit**, newest first, under the date headings
  Today, Yesterday, Last 7 days and Older (local calendar day; empty headings
  are skipped). A note you save moves straight up under Today. Pinned,
  Ephemeral and the tag groups are still sorted by created date (#14).
- The collapsed state of All notes is stored under a new key, so an old
  collapsed Inbox does not hide the new group.
- New tests in `tests/test_list_ui.py`; behaviour verified in headless Chromium
  (order, date headings, tagged note in both groups, saving moves a note up,
  remembered collapse, search, mobile view).

## 1.38 (2026-10-06)

- **The note list shows an error instead of going empty** (#13). `loadNotes`
  and `pollNotes` swallowed every error, so when the proxy was down on
  2026-10-06 the sidebar looked as if all notes were gone. An error box at the
  top of the list now names the cause (server unreachable / 401 / other
  status) with a Try again button; the last loaded list stays on screen. A
  network failure also raises the offline bar, and the list reloads by itself
  when the server answers again. On mobile the app switches to the list view
  so the error is seen when no note is open.
- **Notes in each group are sorted by when they were created, newest first**
  (#14). Applies to Ephemeral, Pinned, Inbox and every tag. An old note that
  gets edited no longer jumps to the top. Notes created the same day
  (midnight `created_at`) are ordered by last edit. Search results are
  unchanged.
- New tests in `tests/test_list_ui.py`; behaviour verified in headless Chromium
  (502, 401, network down from the start, recovery, mobile view, ordering).

## 1.37 (2026-09-17)

- **The note list is fetched page by page instead of with a hardcoded cap**
  (#12). The frontend asked for `limit=200` in five places and never paged, so
  once the collection passed 200 the oldest notes would silently stop showing
  in the sidebar — no error, nothing hinting that the list was cut off.
  Production was at 161. `fetchAllNotes()` now fetches pages of
  `NOTES_PAGE_SIZE` until a short page arrives, which removes the ceiling
  instead of moving it; `loadNotes`, `pollNotes` and the three list refreshes
  after writes all go through it. The token check's `limit=1` is unchanged.

  The whole list is still fetched, not one page at a time for the UI: the
  sidebar groups and sorts locally, and backlinks and wiki autocomplete read
  the content of every note.

## 1.36 (2026-09-17)

- **The port is bound to loopback instead of every interface** (#10).
  `8888:8000` published the app on `0.0.0.0` even though the reverse proxy
  reaches it as `hexnotes:8000` over the shared docker network — the mapping
  is only needed for debugging from the host. Checked before the change: the
  port did not answer from outside, but the host's `iptables INPUT` policy is
  ACCEPT, so the cloud firewall was the only layer. Now `127.0.0.1:8888:8000`.
- **The README explains why the token file must exist before first start**
  (#10). `tokens.json` is bind-mounted as a file; if it is missing Docker
  creates a directory in its place, and the app starts but silently loses
  every token on restart.

## 1.35 (2026-09-17)

- **Version history has a cap per note** (#6). `_snapshot_note` wrote a new
  file on every change and nothing ever cleaned up: 1140 versions, 4.8 MB, for
  161 notes, one of which accounted for 215. `HISTORY_MAX_VERSIONS` is 50 and
  pruning happens on the next save, so old history disappears gradually rather
  than in one sweep. Run against a copy of production's history: six notes
  affected, 344 of 1140 versions pruned, the newest version always kept, and
  files that do not match the version pattern left alone.

## 1.34 (2026-09-17)

Continuation of the review (issues #7, #8, #9).

- **`updated_at` and `created_at` are UTC instead of naive local time** (#7).
  `expires_at` and the trash timestamps have always been UTC, so one response
  carried two time bases without saying which was which; a client in another
  zone than the container read `updated_at` as its own local time. All three
  fields can now be compared directly. History and trash timestamps are
  unchanged (naive UTC, which the frontend already reads with a `Z` appended).
- **`GET /api/notes` has bounds on `limit` and `offset`** (#8). Every item
  carries the note's full `content`, and `limit` had no ceiling. Negative
  values sliced the list from the end and gave a silently wrong answer
  instead of 422. The ceiling (`MAX_PAGE_SIZE`) is 500; the frontend asks for
  200. `q` and `tag` have length limits.
- **`lifespan` instead of the deprecated `on_event("startup")`** (#9). The
  sweep task lives on `app.state` — `asyncio` only keeps a weak reference to
  running tasks, so a bare `create_task()` can be garbage-collected mid-loop —
  and is cancelled on shutdown.
- **Empty content answers 204 without a body** (#9). `JSONResponse(204, None)`
  sent a literal `null`, which 204 does not allow.

## 1.33 (2026-09-17)

Bug fixes from a review of the backend (issues #4, #5, #11).

- **Ephemeral notes died at midnight UTC instead of at their TTL** (#4).
  `expires_at` was written unquoted in the frontmatter, so YAML read it back
  as a `datetime` whose `str()` is space-separated. `_sweep_expired` compared
  that string with `datetime.now(UTC).isoformat()`, where `" "` sorts before
  `"T"` — as soon as the date part matched, the note counted as expired, up to
  a day early. The comparison is now done as `datetime` via `parse_expiry()`,
  and an unreadable value lets the note live instead of discarding it. The
  same bug made `expires_at` in the API response invalid ISO 8601, which gave
  `NaNh left` in the countdown badge on Safari/iOS.
- **Frontmatter is built with `yaml.safe_dump`, not f-strings** (#5). A
  newline in `created` used to open a frontmatter line of its own, so a note
  could gain fields (`pinned`, a new `expires_at`) that no API call had set.
  Ordinary notes are written byte for byte as before — checked against all
  161 notes in production; the only difference is that a numeric tag is now
  quoted correctly (`tags: ['40', argus]`).
- **`parse_frontmatter` ate the first character of the body** (#11). `\s*`
  after the closing `---` line matches newlines as readily as spaces, so a
  note starting with a space or a blank line lost it on every save. Three
  notes in production were already affected. An older bug than the two above.

## 1.32 (2026-09-17)

- **Swagger UI and `/openapi.json` are off by default.** They were reachable without a token and listed every route; set `HEXNOTES_DOCS=1` to enable them in a local dev container.

## 1.31 (2026-09-09)

- **Rebranded from violet to green**, matching the new app-icon family
  (hexagon-shaped, shared with docs.29a.se, dash and others). `--accent`/
  `--accent-dim` swapped in all three theme blocks; `scripts/generate_icons.py`
  (the build-time PNG generator) now draws the same green "emalj" hexagon
  with a folded-page glyph instead of the old violet square + "H" monogram.
  `manifest.json` `theme_color` updated to match; service worker cache
  bumped to `v8` so installed clients pick up the new icon.

## 1.30 (2026-09-09)

- **Theme toggle no longer buried at the end of the note list, and no
  longer hidden under the FAB on mobile.** `#trash-bar` (Trash + theme
  toggle) lived inside the same scrolling container as the note list, so
  reaching it meant scrolling past every note — and on mobile it then sat
  right under the "+" FAB, which visually covered the theme button. The
  sidebar is now a flex column with the note list in its own scrolling
  `#sidebar-scroll` region and `#trash-bar` docked as a footer outside it,
  always visible with no scrolling. On mobile the footer gets extra
  right-padding to clear the FAB's 56px circle.

## 1.29 (2026-09-09)

- **Fixed the note "floating"/dragging sideways on iOS.** `#editor` and the
  other text inputs were 14px, under iOS Safari's 16px threshold for
  disabling auto-zoom-on-focus. Tapping into the editor zoomed the whole
  page in, which is what made it possible to drag the note sideways — the
  zoomed state lingered when switching to preview too, so it looked wrong
  there as well. Bumped to 16px on mobile (`#editor`, `#search-input`,
  `#filename-input`, `#find-input`, `#palette-input`, `#auth-token`).

## 1.28 (2026-09-09)

- **Even darker `--text-muted` in light theme, and fixed the pinned-light
  variant.** 1.27 only darkened the `prefers-color-scheme: light` (auto)
  definition to `#707070` — the `:root[data-theme="light"]` block used when
  the theme is explicitly pinned to light was untouched and still `#888888`.
  Both are now `#575757`.

## 1.27 (2026-09-09)

- **Darker muted text for readability.** `--text-muted` (filenames in the
  sidebar note list, dates, secondary labels) was `#888888` in light theme —
  low contrast on `#f5f5f5`, and combined with JetBrains Mono's regular
  weight it read as too thin/hard to read, particularly on iOS. Darkened to
  `#707070`.

## 1.26 (2026-09-09)

- **Fixed: vendored font actually applying on iOS.** The 1.25 fix vendored
  the `.woff2` files but the container's mimetypes database has no `.woff2`
  entry, so `StaticFiles` served them as `text/plain`. Combined with
  `X-Content-Type-Options: nosniff`, Safari refused to apply a font served
  with the wrong MIME type and silently fell back to a system font — Chrome/
  Firefox are more lenient, so it only showed on iOS. `mimetypes.add_type`
  now registers `font/woff2` explicitly. Service worker cache bumped to
  force a refetch of the previously-mis-served files.

## 1.25 (2026-09-09)

- **JetBrains Mono is now vendored, not loaded from Google Fonts.** The
  Google-hosted stylesheet serves whatever build of the font is current, so
  the rendered weight could drift under us with no commit to point at — that
  looked like a "thinner" typeface after a routine update on Google's end.
  Regular (400) and Bold (700) `.woff2` are now pinned under `static/vendor/`
  and cached by the service worker, same as `marked`/`DOMPurify`. CSP's
  `style-src`/`font-src` no longer need the `fonts.googleapis.com` /
  `fonts.gstatic.com` exceptions.

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

- **Bug fix**: the ephemeral flag was lost when naming a new note (`doRename`
  created the note without `ttl_hours` and reset the flag) — this hit the
  mobile FAB long-press, where the naming step comes first. `doRename` now
  sends `ttl_hours = 48` when ephemeral is armed. 104 tests passing.

## 1.21 (2026-08-21)

- **Mobile UX — long-press on the + button (FAB)** creates an ephemeral note
  (48h). The FAB glows yellow during the hold with the hint ⏳ Ephemeral note,
  and a short vibration confirms. A short tap creates a normal note as before.
- The top-bar ⏳ button is hidden on small screens (the FAB long-press takes
  over); it stays on desktop.
- JS syntax is now checked with esprima before deploy (after the 1.20.x
  breakage). 102 tests passing.

## 1.20.3 (2026-08-21)

- CRITICAL bug fix, part 2: the hourglass string was also missing its closing
  quote (1.20.2 only added the comma). JS parse verified with esprima before
  deploy. 99 tests passing.

## 1.20.2 (2026-08-21)

- CRITICAL bug fix: a missing comma in the hourglass icon's SVG string (from
  1.20.1) crashed the whole app JS — nobody could log in. Fixed. 99 tests
  passing.

## 1.20.1 (2026-08-21)

- Mobile bug fix: the hourglass (ephemeral) button was invisible/cramped on
  small screens. It now shows compactly in the top bar on mobile with an
  hourglass icon; the Today button is hidden on mobile. 99 tests passing.

## 1.20 (2026-08-21)

- **UI — Ephemeral section at the top**: short-lived notes with a live TTL are
  shown in their own ⏳ section at the top of the sidebar (above Pinned). They
  are excluded from Pinned/Inbox/tags while they live.
- **Yellow highlight**: ephemeral cards get a yellow left edge and a faint
  yellow tint.
- **Countdown badge**: every card shows ⏳ `Xh left` / `Xm left`, updated every
  minute.
- 3 new tests (99 passing in total).

## 1.19 (2026-08-21)

- **New feature — short-lived (ephemeral) notes**: a new top-bar button
  (hourglass icon, next to "+ New") creates a note that is moved to the trash
  automatically after 48 hours. The TTL is sent as `ttl_hours` on
  `POST /api/notes` (optional, whole hours), stored as `expires_at` in the
  frontmatter, and survives edits and pin toggles. A background sweep every
  10 minutes and on restart cleans up expired notes.

## 1.18 (2026-07-24)

- **Bug fix — a new note lost its title if you clicked into the text before
  pressing Enter**: when naming a new note, the filename field only committed
  the name on Enter. Clicking straight into the editor instead (no Enter) only
  triggered a blur that REMOVED the typed name without saving it — the note
  was then created without a filename, and the backend fell back to today's
  date as the filename. Blur now commits the name (with the same no-op guard
  as Enter when the field is empty/unchanged) instead of discarding it. Also
  guarded against a possible double-POST race with autosave by letting the
  name commit use the same `isSaving` lock.

## 1.17 (2026-07-24)

- **Bug fix — removed auto-trash-on-blur in the editor**: when the textarea
  lost focus while empty, the note was PATCHed with empty content, which the
  server interprets as "move to trash". A blur is no proof of intent — it is
  triggered by interruptions (a notification, switching apps, locking the
  phone, autocomplete stealing focus), even in the middle of an edit (e.g.
  select-all-and-retype). It caused a real deletion of home.md on 2026-07-13.
  Deleting now only happens through the explicit delete button.

## 1.16 (2026-07-07)

- **Auto-refreshing note list**: the sidebar polls `/api/notes` every 30
  seconds (only while the tab is visible) and immediately when the tab regains
  focus. It only re-renders when the list actually changed — scroll position
  and ongoing edits are not disturbed. Notes created through the API (e.g. by
  Claude) appear without a manual reload.

## 1.15 (2026-06-26)

- **Checklist in the editor**: a new ☑ button in the filename bar that puts
  `- [ ] ` on the current line, or on every selected line when several are
  selected.
- **List auto-continue**: Enter on a checkbox or bullet line creates the next
  item automatically; Enter on an empty item ends the list.

## 1.14 (2026-06-11)

- **Theme toggle**: a discreet button at the bottom of the sidebar (next to
  Trash) that cycles auto → dark → light. Auto follows the system (as before);
  the other two lock the theme via a `data-theme` attribute. The choice is
  saved in localStorage and applied before first render (no flash). The
  `theme-color` meta tag (the PWA status bar on Android) follows along.

## 1.13 (2026-06-11)

- **Lucide icons**: all emoji buttons (📌🕘👁🗑✎📅 and more) replaced with
  inline SVG from Lucide (ISC licence) — a consistent look on every platform,
  inheriting colour via `currentColor` so hover/active states are actually
  coloured. No CDN at runtime; path data is embedded in index.html.
- **New PWA app icon**: a violet gradient on a rounded square with a white
  H monogram (drawn geometrically, no font dependency) — replaces the old
  hexagon/note design. Service worker cache bumped to v4 so clients fetch the
  new icons.

## 1.12 (2026-06-11)

- **Tag autocomplete**: `#` followed by at least one character suggests
  existing tags (at least one character so it does not trigger on Markdown
  headings); the same dropdown and keyboard handling as `[[` autocomplete.
- **Backlinks**: a discreet line at the bottom of the preview — "Linked from:
  x · y" — with clickable links to notes that `[[link]]` here; only shown when
  at least one other note links to the current one.

## 1.11 (2026-06-11)

- **Seed note on an empty install**: a completely empty notes folder gets a
  prefilled `home.md` (welcome text + feature guide) on startup, so new
  installs open on a start page instead of an empty list. Never touched if
  notes already exist.
- **Back navigation**: every opened note gets a hash URL (`#note-id`) in the
  browser history — the phone's back gesture, the browser's back/forward and
  Alt+← go to the previous note instead of leaving the app. A visible ←
  button in the filename bar (only shown when there is something to go back
  to). Hash URLs work as deep links: load the page with `#note-id` and that
  note opens directly. Rename updates the URL; deleted notes in the history
  fall back to the home note.

## 1.10 (2026-06-11)

- **`[[` autocomplete**: typing `[[` in the editor opens a dropdown that
  filters note names as you type; arrow keys navigate, Enter/Tab insert the
  link (with closing `]]`), Escape closes.
- **Clickable checkboxes in preview**: `- [ ]` lines render as real
  checkboxes that can be ticked directly in reading mode — the change is saved
  to the file (the nth checkbox maps to the nth task line, code blocks are
  skipped).
- **Today's note**: a 📅 button in the top bar (mobile too) and `Ctrl+D` open
  today's `YYYY-MM-DD.md`, or create it if it does not exist.

## 1.9 (2026-06-11)

- **Double-click/double-tap to edit**: double-clicking (desktop) or
  double-tapping (mobile) the rendered text switches to the editor; links are
  exempt — they navigate as usual.

## 1.8 (2026-06-11)

- **Notes open in preview mode**: every note with content is rendered as
  Markdown on opening; Ctrl+M or 👁 switches to editing. Empty notes open
  straight in the editor.
- **Bug fix**: "new note" did nothing when the active note was in preview mode
  — `createNewNote()` never reset the preview flag, so the editor stayed
  hidden behind the old note's rendered HTML.

## 1.7 (2026-06-10)

- **Start page via a home note**: if a note `home.md` exists it opens in
  preview mode at app start (with clickable wiki links) instead of the last
  opened note; clicking the HexNotes title in the top bar always goes home.
- Visible on-state for emoji buttons (📌 pin, 👁 preview): a background chip
  with an accent border — emojis ignore CSS colour, so the colour change never
  showed.

## 1.6 (2026-06-10)

- **Empty trash**: `DELETE /api/trash` permanently deletes everything in the
  trash (files + history); an "Empty trash" button in the trash dialog with a
  two-click guard.
- Consistent English throughout the UI (dialogs, buttons, date format).
- The version number is shown in the top bar next to the HexNotes title (moved
  from the sidebar).

## 1.5 (2026-06-10)

- **Trash with a UI**: list, preview, restore and delete permanently
  (`GET /api/trash`, `GET/POST/DELETE /api/trash/{name}(/restore)`).
- Deletion uses timestamped names in `.trash/` — name collisions never
  overwrite anything (previously the oldest file was lost).
- Version history follows the note into the trash and back on restore; a new
  note with the same name starts with a clean history.
- Restoring never collides with live notes — it gets a unique name
  (`name-2.md`).
- Permanent deletion removes both file and history (for content that really
  has to be destroyed, e.g. leaked secrets).
- **Security fix**: path traversal in the rename endpoint (filenames were not
  sanitized).
- The version is exposed in `/health` and shown in the sidebar.

## 1.4 (2026-06-10)

- The service worker is network-first for the app shell — deploys reach PWA
  clients automatically without a cache bump.
- Bug fix: naming a new note creates it immediately, even with empty content.
- Bug fix: a note that never had content is not trashed on lost focus.

## 1.3 (2026-06-10)

- **Version history per note**: earlier versions are saved in
  `.history/<id>/` on every save (`GET /api/notes/{id}/history(/{version})`),
  with a read-only view and a Restore button in the UI.
- **Wiki links**: `[[note name]]` renders as a clickable link in the preview;
  missing notes are shown red/dashed.
- The filename field is editable directly when a new note is created, with
  autofocus.

## 1.2 (2026-04/05)

- Command palette (`Ctrl+P`), find in note (`Ctrl+F`), search clearing, match
  highlighting and content snippets in search results.
- Flat result list when searching.

## 1.1 (2026-04)

- Tag-based sidebar groups with filter chips, Pinned/Inbox/Tags sections,
  collapse all.

## 1.0 (2026-04-05)

- First version: FastAPI backend, notes as `.md` files with YAML frontmatter,
  token auth, a PWA frontend in a single HTML file, Markdown preview
  (`Ctrl+M`), autosave, offline mode, trash on disk.

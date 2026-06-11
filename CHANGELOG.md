# Changelog – HexNotes

Versionsschema: `major.minor`. Minor bumpas vid nya funktioner, major vid
brytande ändringar (API-inkompatibilitet eller ändrat lagringsformat som
kräver migrering). Aktuell version sätts i `APP_VERSION` i `backend/main.py`,
exponeras via `GET /health` och visas längst ner i sidofältet.

Service workerns cachenamn (`hexnotes-vN` i `static/sw.js`) är **inte** kopplat
till appversionen — det bumpas bara när cachestrategin i sig ändras. Sedan 1.4
är app-skalet network-first, så deployer når klienter utan cache-bump.

## 1.11 – 2026-06-11

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

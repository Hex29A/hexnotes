# Changelog – HexNotes

Versionsschema: `major.minor`. Minor bumpas vid nya funktioner, major vid
brytande ändringar (API-inkompatibilitet eller ändrat lagringsformat som
kräver migrering). Aktuell version sätts i `APP_VERSION` i `backend/main.py`,
exponeras via `GET /health` och visas längst ner i sidofältet.

Service workerns cachenamn (`hexnotes-vN` i `static/sw.js`) är **inte** kopplat
till appversionen — det bumpas bara när cachestrategin i sig ändras. Sedan 1.4
är app-skalet network-first, så deployer når klienter utan cache-bump.

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

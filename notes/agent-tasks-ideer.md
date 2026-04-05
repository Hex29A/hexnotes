---
tags: []
created: 2026-04-04
pinned: true
---
# Idéer: HexNotes som uppgiftslista för Claude

Kreativa sätt att använda HexNotes för att ge Claude uppgifter som körs och bockas av.

---

## Alternativ 1 — tasks.md med checkboxar

Enkelt format med checkboxar. Claude läser, utför och uppdaterar:

```
- [ ] Kolla om Occultus svarar
- [ ] Sammanfatta veckans openbrain-noter
- [x] Inventera frysen (stugan) — klar 2026-04-04
```

Pros: enkelt och läsbart
Cons: måste aktivt be Claude kolla filen

---

## Alternativ 2 — agent.md med resultatlogg

Uppgifter + löpande logg i samma fil. Claude lägger till tidsstämplade rader:

```
## Att göra
- [ ] Ping alla servrar

## Logg
2026-04-04 14:00 — Pingade servrar: alla up utom Obvault (timeout)
```

Bra för att följa vad Claude faktiskt gjort.

---

## Alternativ 3 — Cron-liknande (mest ambitiöst)

Schemalagd trigger via Claude Code cron-verktyg. Kör var X timme:
1. Läs tasks.md
2. Utför öppna uppgifter
3. Uppdatera filen med resultat

Helt automatiserat — ingen manuell trigger behövs.

---

## Alternativ 4 — "Briefing"-format

En brief.md som uppdateras varje morgon med frågor och uppgifter.
Nästa gång du skriver "kör brief" i Telegram läser Claude filen och jobbar av allt på en gång.

---

## Favorit

Kombination av alt 1 + 2: en tasks.md med checkboxar och en logg-sektion.
Enkelt att skriva, tydligt att läsa, Claude kan jobba av flera saker i en körning.

Alt 3 (cron) är kraftfullt men kräver väldefinierade uppgifter som kan köras utan kontext.
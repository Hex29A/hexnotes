---
tags: []
created: 2026-04-04
pinned: true
---
# Systemöversikt — verktyg och när de används

En guide för Martin (och Claude) om vilket verktyg som passar för vad.

---

## 📌 Todoist — saker att göra

**Används för:** Uppgifter med deadline eller påminnelse.

Exempel:
- Beställ mezuzah tisdag 07:05
- Betala faktura fredag
- Ring tandläkaren måndag

Tumregel: *Ska göras vid en specifik tidpunkt → Todoist*

Tillgång: Claude lägger till via REST API. Martin får push-notis.

---

## 🧠 Openbrain — minne och kontext

**Används för:** Fakta, händelser och saker som är bra att komma ihåg — utan att göra något åt dem.

Exempel:
- Iris fick hörlurar som belöning för att hon passade Elton
- Martin bröt kaffefastan 2026-04-04
- Börjes skatt klar, hjälpte med deklarationen
- Loke köpte Samsung Galaxy A56 5G på Power

Format: `[Kategori - Ämne]: innehåll`

Tumregel: *Hänt / bra att veta / relationskontext → Openbrain*

Tillgång: Claude söker automatiskt här när du frågar om något som kan ha hänt.

---

## 📝 HexNotes — anteckningar och dokument

**Används för:** Längre texter, idéer, checklistor, dokumentation. Saker du aktivt skriver och redigerar.

Exempel:
- TODO.md — löpande att-göra-lista
- system.md — den här filen
- Projektanteckningar, resedagbok, recept

Tumregel: *Längre text / lista / levande dokument → HexNotes*

Tillgång: Claude läser och skriver via REST API. Du läser i appen på https://hexnotes.29a.se

---

## 🗂 Notion — strukturerad information och databaser

**Används för:** Mer permanent och strukturerad information — inventeringar, familjeinfo, projekt med tabeller.

Exempel:
- Frysinnehåll (Frysarna)
- Barnens prylar (Prylar-sidan)
- Förrådsboxar (Källaren-databasen)
- Tvålingredienser

Tumregel: *Strukturerad data / tabeller / hushållsinfo → Notion*

Tillgång: Claude navigerar via känd sidstruktur (sparad i minnet).

---

## Snabbguide

| Situation | Verktyg |
|---|---|
| Ska göras + deadline | Todoist |
| Hänt / bra att veta | Openbrain |
| Längre text / lista | HexNotes |
| Tabell / strukturerad data | Notion |
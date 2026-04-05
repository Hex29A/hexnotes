---
tags: []
created: 2026-04-04
pinned: true
---
# Backupstrategi för alla system

Analys baserad på ~/infra/inventory.yml. Uppdaterad 2026-04-04.

---

## Vad som behöver backas upp

### Kritiskt (data som inte går att återskapa)
- **Openbrain DB** — PostgreSQL + pgvector på oraclesmall. Innehåller hela personliga minnet. → **Mega.nz** ✅
- **Fragrance Tracker** — appdata/databas på oracle16gb.
- **HexNotes** — notes/-mappen (md-filer) på oraclesmall.
- **n8n** — workflows och credentials på oraclesmall.
- **Fredagskakan (fkapi)** — API + data på oracle16gb.
- **Home Assistant (Croniers + Alphyddan)** — konfiguration, automationer, lovelace. → **Google Drive** ✅
- **Manager (S3/assets)** — bilder och filer för fragrance-tracker och fredagskakan.

### Viktigt men återställningsbart
- Docker Compose-filer och .env för alla stacks
- Nginx Proxy Manager-konfiguration (SSL-certs, proxy hosts)
- Källaren-appdata

### Lägre prioritet
- Plex (mediebibliotek pekar på NAS/disk — metadata kan återskapas)
- PiHole-konfiguration (blocklistor laddas om automatiskt)
- Statiska sajter på invenies (troligen i git)

---

## Befintliga backuplösningar

| System | Destination | Status |
|---|---|---|
| Home Assistant x2 | Google Drive | ✅ Aktivt |
| Openbrain DB | Mega.nz | ✅ Aktivt |

---

## Strategier

### Strategi A — Restic till Oracle Object Storage (rekommenderas)
Restic är ett modernt backup-verktyg med deduplicering, kryptering och bra schema-stöd.
Oracle Cloud har gratis Object Storage (10 GB, kan utökas).

```bash
# Exempel: backup av HexNotes notes/
restic -r s3:https://objectstorage.eu-stockholm-1.oraclecloud.com/<bucket> backup /path/to/notes
```

Pros: krypterat, deduplikerat, versionerat, gratis lagring på Oracle
Cons: kräver setup av OCI credentials

---

### Strategi B — Schemalagda pg_dump + rsync till annan VPS
Direkt och enkelt. PostgreSQL-dumps schemalagda med cron, skickas med rsync till t.ex. invenies eller Aleph.

```bash
# Daglig dump av openbrain
pg_dump -U postgres openbrain > /backup/openbrain-$(date +%Y%m%d).sql
rsync /backup/ hex29a@invenies:/backups/oraclesmall/
```

Pros: enkelt, inga extra tjänster
Cons: kräver disk på mottagande server, ingen kryptering by default

---

### Strategi C — Proxmox Backup Server
Bygga en PBS-instans (t.ex. som LXC på Malkuth eller Ialdabaoth).
Säkerhetskopierar hela VMs och containers med inkrementell backup.

Pros: hanterar hela servrar, inbyggt i Proxmox
Cons: kräver extra resurser, täcker inte VPS på Oracle

---

### Strategi D — Applikationsspecifika backups
Många appar har inbyggd backup:
- **Home Assistant**: inbyggd snapshot → Google Drive ✅
- **n8n**: export workflows via UI/API
- **Portainer**: exportera stack-definitioner

Pros: appmedveten backup, enkel att testa restore
Cons: täcker inte databasen direkt

---

## Rekommenderad plan

### Fas 1 — Databaser och filer (viktigast)
1. Sätt upp daglig `pg_dump` för Fragrance Tracker och Fredagskakan på oracle16gb
2. Skicka dump + HexNotes notes/ + n8n data till Aleph (Croniers) med rsync
3. Behåll 7 dagars historik

### Fas 2 — Hela stacks
4. Samla alla docker-compose.yml + .env i ett privat git-repo (känsliga env-filer krypteras med git-crypt)
5. Commit automatiskt vid förändring med watch-script

### Fas 3 — Offsite
6. Restic mot Oracle Object Storage för kritisk data
7. Alternativt: Backblaze B2 (gratis upp till 10 GB)

---

## Verktyg att titta på
- **Restic** — https://restic.net
- **Duplicati** — GUI-baserat, bra för nybörjare
- **BorgBackup** — effektivt med deduplicering
- **Litestream** — streaming backup för SQLite-databaser
- **pgBackRest** — avancerat för PostgreSQL

---

## Status

- [x] Home Assistant x2 → Google Drive
- [x] Openbrain DB → Mega.nz
- [ ] Fragrance Tracker — backup saknas
- [ ] Fredagskakan (fkapi) — backup saknas
- [ ] HexNotes notes/ — backup saknas
- [ ] n8n workflows — backup saknas
- [ ] Manager/S3-assets — backup saknas
- [ ] Git-repo för compose-filer
- [ ] Testa restore av minst en tjänst
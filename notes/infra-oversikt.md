---
tags: []
created: 2026-04-05
pinned: true
---
# Infrastrukturöversikt

Genererad från ~/infra/inventory.yml · Uppdaterad 2026-04-05

---

## ☁️ VPS — Oracle Cloud

### oraclesmall (79.76.51.14)

| Tjänst | URL | Beskrivning |
|---|---|---|
| n8n | https://nathan.29a.se | Automation & workflows |
| HexNotes | https://hexnotes.29a.se | Notes-app |
| Occultus | https://occultus.29a.se | Learning hub |
| Openbrain MCP | :6174 (Tailscale) | Personligt minne / MCP SSE |
| Openbrain Cortex | :6173 (Tailscale) | AI inference layer |
| Openbrain DB | :5432 | PostgreSQL + pgvector |
| Manager | :3100 (Tailscale) | S3/asset manager |
| Källaren | :8080 (Tailscale) | Källarutrymmen-app |
| Obvault | :65080 (Tailscale) | Obsidian vault viewer |
| Nginx Proxy Manager | :81 (Tailscale) | Reverse proxy & SSL |
| Portainer | :9443 (Tailscale) | Docker management |
| Dockge | :5001 (Tailscale) | Compose stack manager |

### oracle16gb (79.76.58.226)

| Tjänst | URL | Beskrivning |
|---|---|---|
| Fragrance Tracker | :1982 (Tailscale) | Parfymspårning (frontend) |
| Fredagskakan API | https://api.fredagskakan.se | REST API |
| Fredagskakan Stats | https://api.fredagskakan.se/stats/ | Statistik |
| Nginx Proxy Manager | :81 (Tailscale) | Reverse proxy & SSL |
| Portainer | :9443 (Tailscale) | Docker management |

### invenies (129.151.211.138)

| Tjänst | URL | Beskrivning |
|---|---|---|
| invenies.29a.se | https://invenies.29a.se | Statisk filserver (Caddy) |
| inveni.29a.se | https://inveni.29a.se | Statisk filserver (Caddy) |

---

## 🏠 Alphyddan (192.168.8.0/24)

### Malkuth — Proxmox (192.168.8.88)

| VM/LXC | IP | Beskrivning |
|---|---|---|
| Home Assistant | 192.168.8.3 · https://alphyddan.29a.se | Hemautomation |
| Plex | 192.168.8.12 | Mediaserver |
| ADMx | 192.168.8.5 | Axis Device Manager (kameror) |

### Tulpamancer — Docker host (192.168.8.4)

| Tjänst | URL | Beskrivning |
|---|---|---|
| Uptime Kuma | :3001 | Uptime-övervakning |
| Dockge | :5001 | Compose stack manager |
| Portainer | :9443 | Docker management |

### Övrigt

| Enhet | IP | Beskrivning |
|---|---|---|
| PiHole | 192.168.8.2 | DNS & annonsblockerare |
| Router (Huawei B525s) | 192.168.8.1 | Gateway & DHCP |
| Switch T8508 (Axis PoE+) | 192.168.8.6 | 10-port PoE+ switch |
| Kamera West (Axis M2035-LE) | 192.168.8.20 | |
| Kamera Entrén (Axis M3128-LVE) | 192.168.8.21 | |
| Kamera Nyckelskåp (Axis M2036-LE) | 192.168.8.22 | |
| Kamera Trädgården (Axis Q3556-LVE) | 192.168.8.23 | |

---

## 🏡 Croniers (192.168.88.0/24)

### Aleph — Docker host (192.168.88.5)

| Tjänst | URL | Beskrivning |
|---|---|---|
| Homepage | :3000 | Dashboard / startpage |
| Beszel | :8090 | Server & container monitoring |
| Uptime Kuma | :3001 | Uptime-övervakning |
| Patchmon | :3003 | Patch/update monitoring |
| Portainer | :9000 | Docker management |
| Dockge | :5001 | Compose stack manager |

### Ialdabaoth — Proxmox (192.168.88.7)

| VM | IP | Beskrivning |
|---|---|---|
| Home Assistant | 192.168.88.3 · http://192.168.88.3:8123 | Hemautomation |

### Övrigt

| Enhet | IP | Beskrivning |
|---|---|---|
| PiHole | 192.168.88.4 | DNS & annonsblockerare |
| UniFi USG | 192.168.88.1 | Gateway & brandvägg |
| UniFi Controller | 192.168.88.8 | Nätverkshantering |
| Brother skrivare | 192.168.88.23 | Nätverksskrivare |
# Himalayan Suite Hotel — Custom Dashboard
### Project History & Status

> **Project location:** `/Users/withamrit/Repos/hms-dashboard/`
> **GitHub:** `https://github.com/mac-guru/hms-dashboard`
> **Live URL:** `https://dashboard.himalayansuite.com`

---

## What This Project Is

A custom web dashboard for **Himalayan Suite Hotel** that reads data directly from the hotel's HMS (Hotel Management Software) database and displays it in a clean, real-time web interface — accessible from any browser, phone, or device, anywhere in the world.

---

## Architecture

```
Browser / iPhone (anywhere)
        ↓ HTTPS
https://dashboard.himalayansuite.com
        ↓ Cloudflare (SSL + proxy)
110.44.123.234:80 (port forward)
        ↓ MikroTik router
172.16.10.10:5055 (Flask / waitress — Windows server)
        ↓ localhost
SQL Server Express (172.16.10.10:1433) → hotel database
```

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask backend — all API routes |
| `templates/index.html` | Frontend dashboard — tabbed UI |
| `templates/login.html` | Login page |
| `static/manifest.json` | PWA manifest (installable as phone app) |
| `static/icons/` | App icons (192×192, 512×512) |
| `requirements.txt` | Python dependencies |
| `render.yaml` | Render.com deployment config (unused) |
| `HISTORY.md` | This file |

---

## Infrastructure

### Windows Server (`172.16.10.10`)
- **OS:** Windows Server 2019
- **SQL Server Express:** port 1433 — hotel database
- **Flask app:** runs as Windows service via **NSSM**
  - Service name: `HMSDashboard`
  - Start command: `waitress-serve --port=5055 app:app`
  - App directory: `C:\hms-dashboard`
  - Auto-starts on boot
- **Auto-deploy:** Windows Task Scheduler runs `C:\hms-update.ps1` every 1 minute
  - Downloads latest zip from GitHub → extracts → restarts service
  - **No AnyDesk needed to deploy updates**

### MikroTik Router
| Rule | Type | External Port | Internal |
|------|------|--------------|---------|
| HMS Web | dstnat | 8982 | 172.16.10.10:8982 |
| HMS Dashboard | dstnat | 5055 | 172.16.10.10:5055 |
| HMS Dashboard HTTP | dstnat | 80 | 172.16.10.10:5055 |
| Hairpin NAT | srcnat | — | 172.16.10.0/24 → masquerade |
| Block guest hotspot | filter/drop | — | 10.5.35.0/24 blocked |

### Cloudflare DNS (`himalayansuite.com`)
| Record | Type | Value | Proxy |
|--------|------|-------|-------|
| `dashboard` | A | `110.44.123.234` | ✅ Orange (proxied) |

- SSL mode: **Flexible** (configuration rule for `dashboard.himalayansuite.com`)
- Main site SSL: **Full** (unchanged)

### Windows Firewall
- Port `5055` open (TCP inbound) — rule name: `HMS Dashboard`

---

## Database

```
Server:   172.16.10.10, port 1433
Instance: SQLexpress
Database: hotel
User:     sa
Password: webbook@321
```

### Key Tables Used

| Table | Purpose |
|-------|---------|
| `Bills` | All hotel charges — primary source for revenue & occupancy |
| `Audit` | Night audit snapshot (revenue / occupancy _T/_M/_Y columns) |
| `Rooms` | Live room rack status |
| `RmAvl` | Room status code definitions |
| `Guests` | Guest master records |
| `FRSVDet` | Reservation details |
| `FRSVHDR` | Reservation headers |

---

## Dashboard Features

### Tabs
1. **Occupancy** — Today % / Yesterday % / This Month (MTD) % / Fiscal Year %
2. **Revenue** — Today vs Yesterday: Room Sales, Meal Plan, Room Revenue subtotal, Food, Beverage, Restaurant Sales subtotal, SPA/Transport, Laundry, Misc, Total

### Date Navigation
- ◀ ▶ arrow buttons — go back/forward one day
- Date picker — jump to any date
- Today button — return to current date

### Other
- Login protected (`amrit` / `Nepal@213`)
- Auto-refreshes every 5 minutes (today only)
- Installable as PWA on iPhone (Add to Home Screen in Safari)
- Responsive — works on phone and desktop

---

## How to Deploy Updates

On your **Mac** (edit code, then):
```bash
cd /Users/withamrit/Repos/hms-dashboard
git add -A
git commit -m "describe your change"
git push
```
The Windows server picks it up automatically within **1 minute**. No AnyDesk needed.

---

## How to Restart the Service Manually (if needed)

Via AnyDesk on Windows server, open Command Prompt:
```
C:\nssm\nssm-2.24\win64\nssm.exe restart HMSDashboard
```

---

## Important Numbers

| Config | Value |
|--------|-------|
| Total rooms | **27** (`TOTAL_ROOMS = 27` in app.py) |
| Fiscal year start | **July 17, 2025** |
| Dashboard URL | `https://dashboard.himalayansuite.com` |
| HMS internal URL | `http://172.16.10.10:8982/himalayansuite` |
| HMS public URL | `http://110.44.123.234:8982/himalayansuite` |
| Dashboard login | user: `amrit` / pass: `Nepal@213` |
| GitHub repo | `https://github.com/mac-guru/hms-dashboard` |

---

## Key Technical Decisions

| Decision | Why |
|----------|-----|
| Bills table (not Audit) for revenue | Audit = snapshot at midnight; Bills = live including post-audit entries |
| `COUNT(BillRmNo)` not `COUNT(DISTINCT BillRmNo)` | Matches HMS report — counts day-use + overnight separately (allows >100%) |
| FX conversion for OTA rooms | Rooms 302/303/306/406 billed in USD; `BillRC × BillFxRate` for NPR |
| BillCode `SPA` = Flight/Transport | Confusingly named in HMS; mapped to "SPA / Transport" in dashboard |
| Flask on Windows server | Zero cloud cost; server always on; 1-hop latency (faster than cloud) |
| NSSM for service management | Runs Flask as Windows service with auto-restart and boot start |
| Cloudflare proxy | Free SSL, no cert needed on origin server |

---

## Bug Fixes History

| Bug | Fix |
|-----|-----|
| Total rooms showed 25 | Added `TOTAL_ROOMS = 27` constant |
| Revenue didn't match printed report | Switched from Audit table to Bills table with FX conversion |
| OTA room revenue wrong | Multiply `BillRC × BillFxRate` for USD rooms |
| SPA/Transport showed 0 | No `SPL` BillCode exists; use `SPA` BillCode instead |
| Occupancy showed 18 instead of 19 | Use Bills `COUNT(BillRmNo)` instead of Audit `Occ_T` |
| Occupancy capped at 100% | Removed `DISTINCT` — count all RC transactions per day |
| Date nav went back 2 days | Fixed timezone bug — replaced `toISOString()` with local date formatter |
| Next button always disabled | Same timezone bug in comparison — fixed with `getToday()` helper |
| Guest list empty | `BillVoid = 0` wrong; changed to `BillVoid IS NULL OR BillVoid = 0` |
| Service wouldn't start (NSSM) | Wrong Python path — used `where waitress-serve` to find correct path |

---

## Phase Roadmap

- [x] Phase 1 — Revenue section matching printed night audit report
- [x] Phase 2 — Occupancy matching HMS Room Occupancy History report
- [x] Phase 3 — Deployed to Windows server, accessible from anywhere
- [x] Phase 4 — Login, PWA (installable on iPhone), HTTPS via Cloudflare
- [ ] Phase 5 — Additional sections (guest list, arrivals/departures, etc.)

---

*Last updated: April 22, 2026*

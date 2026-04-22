# Himalayan Suite — Custom Dashboard
### Project History & Status

> **Project location:** `/Users/withamrit/Repos/hms-dashboard/`
> **NOT related to:** HSJ Helicopter project (`/Users/withamrit/Repos/hsj-heli/`)

---

## What This Project Is

A custom web dashboard for **Himalayan Suite hotel** that reads data directly from the hotel's HMS (Himalayan Suite Hotel Management Software) database and displays it in a clean, real-time web interface accessible from any browser — including your phone from another city.

---

## The Journey (How We Got Here)

### Phase 1 — Trying to find an API
- Himalayan Suite HMS has **no public REST API**
- Investigated the ASP.NET WebForms app at `http://172.16.10.10:8982/himalayansuite`
- Found ONE real JSON endpoint: `Dashboard.aspx/GetActivityList` (used for activity feed)
- Everything else required HTML scraping

### Phase 2 — HTML Scraping (first working version)
Built a Flask app that:
- Logged into HMS using session cookies + ViewState
- Scraped `AuditSummary.aspx` for revenue data
- Scraped `RoomRack` page for room status
- Scraped `RoomDashboard.aspx` for guest list
- Scraped `DashboardVishuwa.aspx` for front desk counts

**Problems with scraping:**
- Room total showed 25 (wrong) — only counted OCC + VAC, missed OOO/OOS
- Revenue total didn't match printed reports (missing walk-in cash sales)
- Slow (had to login + load multiple pages per request)
- Could break if HMS updates its HTML

### Phase 3 — Direct Database Connection (current)
- Accessed Windows server via **AnyDesk**
- Found **SQL Server Express** running on the same machine (`172.16.10.10`)
- Enabled **TCP/IP** in SQL Server Configuration Manager
- Set **static port 1433** (was using random port 58623)
- Enabled **SQL Server Browser** service
- Opened **Windows Firewall** for port 1433
- Connected directly from Mac using `pymssql`

**Database details:**
```
Server:   172.16.10.10, port 1433
Instance: SQLexpress
Database: hotel
User:     sa
Password: webbook@321
```

---

## Current Architecture

```
Your Mac (localhost:5055)
    └── Flask app (app.py)
            ├── /api/dashboard  ──→  SQL Server (172.16.10.10:1433) → hotel DB
            ├── /api/activity   ──→  HMS Web scraping (activity feed only)
            └── /               ──→  templates/index.html
```

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask backend — all API routes |
| `templates/index.html` | Frontend dashboard UI |
| `HISTORY.md` | This file |

---

## Key Database Tables Used

| Table | What it contains |
|-------|-----------------|
| `Audit` | Night audit — ALL revenue & occupancy metrics (today / MTD / YTD) |
| `Rooms` | Live room status (Occupied, Vacant, Dirty, OOO, etc.) |
| `RmAvl` | Room status code definitions |
| `Bills` | All hotel bills — used for in-house guest list |
| `Guests` | Guest master records (names) |
| `FRSVDet` | Reservation details — arrivals & departures |
| `FRSVHDR` | Reservation header records |

---

## Dashboard Sections

1. **Room Status** — Occupied / Vacant / Arrivals today / Departures today
2. **Front Desk** — Reservations / Checked-in / Total guests
3. **Occupancy** — Today % / Yesterday % / MTD % / PAX
4. **Key Metrics** — ADR / RevPAR (today and yesterday)
5. **Revenue Breakdown** — Room Sales, Meal Plan, Food, Beverage, SPA, Laundry, Misc, Total (today / yesterday / MTD / YTD)
6. **In-house Guest List** — Room, Name, Plan, Type, Arrival, Departure, Status
7. **Activity Feed** — Real-time check-ins, restaurant bills, SPA, purchases

---

## Important Numbers

| Config | Value |
|--------|-------|
| Total rooms | **27** (set as `TOTAL_ROOMS = 27` in app.py) |
| HMS internal URL | `http://172.16.10.10:8982/himalayansuite` |
| HMS public URL | `http://110.44.123.234:8982/himalayansuite` |
| Dashboard URL | `http://localhost:5055` |
| HMS login | user: `amrit` / pass: `Nepal@213` |

---

## How to Run

```bash
cd /Users/withamrit/Repos/hms-dashboard
python3 app.py
```

Then open: `http://localhost:5055`

---

## How to Access from Phone / Another City

**Option A — Cloudflare Tunnel (quick, free):**
```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:5055
```
Copy the URL it gives you → open on phone.
**Requires:** Mac must be on and connected to office network.

**Option B — Deploy to cloud (permanent):**
- Change `HMS_URL` in app.py to `http://110.44.123.234:8982/himalayansuite`
- Deploy to Render.com (free) → always accessible, Mac doesn't need to be on

---

## Known Issues / Improvements To Do

- [ ] Guest list sometimes shows duplicate rows (same guest, multiple bill rows)
- [ ] Revenue "today" from Audit table = previous night's audit. Live intra-day revenue requires querying Bills table directly
- [ ] Activity feed still uses HTML scraping (the only part not yet on DB)
- [ ] No authentication on the dashboard (anyone with the URL can see it)
- [ ] Auto-start on Mac boot not configured yet

---

## What Was Fixed During Build

| Bug | Fix |
|-----|-----|
| Total rooms showed 25 | Added `TOTAL_ROOMS = 27` constant, stopped summing OCC+VAC |
| Revenue didn't match printed report | Switched from AuditSummary scraping to direct Audit table query |
| SQL Server not reachable | Enabled TCP/IP, set static port 1433, opened Windows Firewall |
| `g.status` JS error | Old scraping returned `status` field; updated HTML to derive status from arrival/departure dates |
| `fd.reservations` JS error | Added `frontdesk` object back to API response |
| `plan` SQL reserved word error | Renamed alias to `meal_plan` |
| Guest list empty | `BillVoid = 0` was wrong; changed to `BillVoid IS NULL OR BillVoid = 0` |

---

*Last updated: April 21, 2026*

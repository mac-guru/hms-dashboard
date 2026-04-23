from flask import Flask, jsonify, render_template, request, session, redirect, url_for, Response
from functools import wraps
import pymssql, requests, re, json, os
from datetime import datetime, timedelta
from nepali_datetime import date as NepaliDate

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hms-dashboard-key-2025')

DASH_USER    = os.environ.get('DASH_USER',    'amrit')
DASH_PASS    = os.environ.get('DASH_PASS',    'Nepal@213')
DASH_HK_USER = os.environ.get('DASH_HK_USER', 'abhi')
DASH_HK_PASS = os.environ.get('DASH_HK_PASS', 'abhii')

HOUSEKEEPING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>HMS — Room Status</title>
  <link rel="manifest" href="/static/manifest.json"/>
  <meta name="apple-mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
  <meta name="apple-mobile-web-app-title" content="HMS Rooms"/>
  <link rel="apple-touch-icon" href="/static/icons/icon-192.png"/>
  <meta name="theme-color" content="#1a3c5e"/>
  <style>
    :root { --primary:#1a3c5e; --accent:#e8a020; --green:#27ae60; --red:#e74c3c;
            --purple:#7b5ea7; --bg:#f0f4f8; --card:#fff; --text:#2c3e50; --muted:#7f8c8d; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:'Segoe UI',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
    header { background:linear-gradient(135deg,var(--primary),#2c5f8a); color:white;
             padding:16px 20px; display:flex; align-items:center; justify-content:space-between;
             box-shadow:0 2px 10px rgba(0,0,0,.2); }
    header h1 { font-size:1.2rem; font-weight:700; }
    header h1 span { color:var(--accent); }
    header p { font-size:.75rem; opacity:.75; margin-top:2px; }
    .logout-btn { background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.3);
                  color:white; padding:7px 14px; border-radius:20px; font-size:.8rem;
                  cursor:pointer; text-decoration:none; }
    main { padding:20px 32px; width:100%; }
    .legend { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
    .lc { padding:4px 12px; border-radius:20px; font-size:.72rem; font-weight:600; }
    .summary { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
    .sc { padding:6px 14px; border-radius:20px; font-size:.8rem; font-weight:700; }
    .grid { display:grid; gap:8px; grid-template-columns:repeat(auto-fill,minmax(90px,1fr)); }
    .card { border-radius:10px; padding:10px 8px; text-align:center; border:2px solid transparent; transition:transform .15s; }
    .card:hover { transform:translateY(-2px); }
    .rno  { font-size:1.45rem; font-weight:800; line-height:1; }
    .rst  { font-size:.6rem; font-weight:700; text-transform:uppercase; letter-spacing:.6px; margin-top:3px; }
    .rg   { font-size:.65rem; margin-top:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .rd   { font-size:.6rem; margin-top:1px; opacity:.75; }
    .rm-occupied  { background:#dbeafe; border-color:#1a3c5e; color:#1a3c5e; }
    .rm-vacant    { background:#dcfce7; border-color:#27ae60; color:#27ae60; }
    .rm-dirty     { background:#fef9c3; border-color:#d97706; color:#92400e; }
    .rm-ooo       { background:#fee2e2; border-color:#e74c3c; color:#c0392b; }
    .rm-inspect   { background:#f3e8ff; border-color:#7b5ea7; color:#5b21b6; }
    .rm-departure { background:#ccfbf1; border-color:#0d9488; color:#0f766e; }
    .rm-houseuse  { background:#f1f5f9; border-color:#94a3b8; color:#475569; }
    #msg  { text-align:center; padding:40px; color:var(--muted); }
    .foot { text-align:center; color:var(--muted); font-size:.74rem; margin:24px 0 12px; }
    @media(max-width:600px){
      main { padding:10px; }
      .legend { gap:5px; margin-bottom:10px; }
      .lc { padding:3px 9px; font-size:.68rem; }
      .summary { gap:6px; margin-bottom:12px; }
      .sc { padding:5px 10px; font-size:.75rem; }
      .grid { grid-template-columns:repeat(3,1fr); gap:6px; }
      .card { padding:8px 5px; border-radius:8px; }
      .rno { font-size:1.15rem; }
      .rst { font-size:.55rem; letter-spacing:.4px; }
      .rg  { font-size:.6rem; margin-top:4px; }
      .rd  { font-size:.58rem; }
    }
    @media(max-width:360px){
      .grid { grid-template-columns:repeat(2,1fr); }
    }
  </style>
</head>
<body>
<header>
  <div>
    <h1>&#127968; <span>Himalayan Suite</span> Hotel</h1>
    <p>Housekeeping &mdash; Room Status</p>
  </div>
  <a href="/logout" class="logout-btn">Sign Out</a>
</header>
<main>
  <div class="legend">
    <span class="lc rm-occupied">Occupied</span>
    <span class="lc rm-departure">Departure</span>
    <span class="lc rm-vacant">Vacant</span>
    <span class="lc rm-dirty">Dirty</span>
    <span class="lc rm-inspect">Inspect</span>
    <span class="lc rm-ooo">Out of Order</span>
    <span class="lc rm-houseuse">House Use</span>
  </div>
  <div class="summary" id="summary"></div>
  <div id="msg">Loading rooms&hellip;</div>
  <div class="grid" id="grid"></div>
  <div class="foot" id="foot"></div>
</main>
<script>
async function load() {
  try {
    const res  = await fetch('/api/rooms');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    render(data);
  } catch(e) {
    document.getElementById('msg').textContent = '\\u26a0\\ufe0f ' + e.message;
  }
}
function render(rooms) {
  const cnt = {};
  rooms.forEach(r => { cnt[r.css] = (cnt[r.css]||0)+1; });
  const order = [
    {k:'occupied',l:'Occupied'},{k:'departure',l:'Departure'},
    {k:'dirty',l:'Dirty'},{k:'inspect',l:'Inspect'},
    {k:'vacant',l:'Vacant'},{k:'ooo',l:'OOO'},{k:'houseuse',l:'House Use'}
  ];
  document.getElementById('summary').innerHTML = order
    .map(s => cnt[s.k] ? `<span class="sc rm-${s.k}">${cnt[s.k]} ${s.l}</span>` : '')
    .join('');
  document.getElementById('grid').innerHTML = rooms.map(r => {
    const g = r.guest ? `<div class="rg" title="${r.guest}">${r.guest}</div>` : '';
    const d = r.checkout && (r.css==='occupied'||r.css==='departure') ? `<div class="rd">&#8629; ${r.checkout}</div>` : '';
    return `<div class="card rm-${r.css}"><div class="rst">${r.label}</div><div class="rno">${r.room}</div>${g}${d}</div>`;
  }).join('');
  document.getElementById('msg').style.display = 'none';
  document.getElementById('foot').textContent = 'Live \\u00b7 Updated: ' + new Date().toLocaleTimeString() + ' \\u2014 auto-refreshes every 2 min';
}
load();
setInterval(load, 120000);
</script>
</body>
</html>"""

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── Database Config ───────────────────────────────────────
DB = {
    'server':   os.environ.get('DB_SERVER',   '172.16.10.10'),
    'port':     int(os.environ.get('DB_PORT', 1433)),
    'user':     os.environ.get('DB_USER',     'sa'),
    'password': os.environ.get('DB_PASSWORD', 'webbook@321'),
    'database': os.environ.get('DB_NAME',     'hotel'),
    'timeout':  10,
}
TOTAL_ROOMS = 27   # confirmed from Audit.TRmH_T

# ── HMS Web (only for activity feed) ─────────────────────
HMS_URL  = os.environ.get('HMS_URL', 'http://172.16.10.10:8982/himalayansuite')
USERNAME = os.environ.get('HMS_USER', 'amrit')
PASSWORD = os.environ.get('HMS_PASS', 'Nepal@213')

# ── Helpers ──────────────────────────────────────────────
def get_db():
    return pymssql.connect(**DB)

def fv(v):
    """Safe float, returns 0.0 for None/empty."""
    try:
        return float(v or 0)
    except:
        return 0.0

# ── HMS Session (for activity feed only) ─────────────────
def get_session():
    s = requests.Session()
    resp = s.get(f"{HMS_URL}/Default.aspx", timeout=10)
    vs  = re.search(r'id="__VIEWSTATE" value="([^"]+)"', resp.text).group(1)
    vsg = re.search(r'id="__VIEWSTATEGENERATOR" value="([^"]+)"', resp.text).group(1)
    ev  = re.search(r'id="__EVENTVALIDATION" value="([^"]+)"', resp.text).group(1)
    s.post(f"{HMS_URL}/Default.aspx", data={
        "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg,
        "__EVENTVALIDATION": ev,
        "txtUserID": USERNAME, "txtPassword": PASSWORD, "btnValidate": "Login"
    })
    return s

# ── API Routes ───────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        if u == DASH_USER and p == DASH_PASS:
            session['logged_in'] = True
            session['role'] = 'admin'
            return redirect(url_for('index'))
        elif u == DASH_HK_USER and p == DASH_HK_PASS:
            session['logged_in'] = True
            session['role'] = 'housekeeping'
            return redirect(url_for('index'))
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    if session.get('role') == 'housekeeping':
        return jsonify({'error': 'Access denied'}), 403
    try:
        date_param = request.args.get("date")
        selected   = datetime.strptime(date_param, "%Y-%m-%d") if date_param else datetime.now()
        is_today   = selected.date() == datetime.now().date()
        previous   = selected - timedelta(days=1)

        conn   = get_db()
        cur    = conn.cursor(as_dict=True)

        # ── Night Audit rows ─────────────────────────────
        cur.execute("SELECT * FROM Audit WHERE CAST(AuditDate AS DATE) = %s",
                    (selected.date(),))
        t = cur.fetchone() or {}

        cur.execute("SELECT * FROM Audit WHERE CAST(AuditDate AS DATE) = %s",
                    (previous.date(),))
        y = cur.fetchone() or {}

        # ── Live Room Rack ───────────────────────────────
        cur.execute("""
            SELECT RmAvl, COUNT(*) as cnt
            FROM Rooms
            GROUP BY RmAvl
        """)
        rack = {r['RmAvl']: r['cnt'] for r in cur.fetchall()}
        # RmAvl codes: 0=Occupied 1=Vacant 2=Dirty 3=OOO 4=Inspect 5=Departure 6=OOS 7=HouseUse

        # ── Today's Arrivals & Departures (from reservations) ──
        cur.execute("""
            SELECT
                SUM(CASE WHEN CAST(d.RsvDetArrDt AS DATE) = %s THEN 1 ELSE 0 END) as arr,
                SUM(CASE WHEN CAST(d.RsvDetDepDt AS DATE) = %s THEN 1 ELSE 0 END) as dep
            FROM FRSVDet d
            JOIN FRSVHDR h ON h.RsvHdrId = d.RsvDetHdrId
            WHERE d.RsvDetStat = 'open'
        """, (selected.date(), selected.date()))
        rsv = cur.fetchone() or {}

        # ── Revenue from Bills table (matches printed report) ─
        # OTA rooms are billed in USD; multiply BillTot * BillFxRate for NPR value.
        def bills_revenue(date):
            cur.execute("""
                SELECT
                  SUM(CASE WHEN BillCode='RC' AND (BillCurr='NRS' OR BillCurr IS NULL)
                               THEN ISNULL(BillRC,0) ELSE 0 END
                    + CASE WHEN BillCode='RC' AND BillCurr NOT IN ('NRS') AND BillCurr IS NOT NULL
                               THEN ISNULL(BillRC,0)*ISNULL(BillFxRate,1) ELSE 0 END) as RmChg,
                  SUM(CASE WHEN BillCode='RC' AND (BillCurr='NRS' OR BillCurr IS NULL)
                               THEN ISNULL(BillPlanAmt,0) ELSE 0 END
                    + CASE WHEN BillCode='RC' AND BillCurr NOT IN ('NRS') AND BillCurr IS NOT NULL
                               THEN ISNULL(BillPlanAmt,0)*ISNULL(BillFxRate,1) ELSE 0 END) as RmPlan,
                  SUM(CASE WHEN BillCode='RES' THEN ISNULL(BillTot,0) ELSE 0 END) as RES,
                  SUM(CASE WHEN BillCode='BAR' THEN ISNULL(BillTot,0) ELSE 0 END) as BAR,
                  SUM(CASE WHEN BillCode='SPA' THEN ISNULL(BillTot,0) ELSE 0 END) as FLT,
                  SUM(CASE WHEN BillCode='LAU' THEN ISNULL(BillTot,0) ELSE 0 END) as LAU,
                  SUM(CASE WHEN BillCode='MIS' THEN ISNULL(BillTot,0) ELSE 0 END) as MISC
                FROM Bills
                WHERE CAST(BillDt AS DATE) = %s
                  AND (BillVoid IS NULL OR BillVoid = 0)
            """, (date,))
            row = cur.fetchone() or {}
            return {k: fv(v) for k, v in row.items()}

        b_today = bills_revenue(selected.date())
        b_yest  = bills_revenue(previous.date())

        # ── Cash Received: BillPmode=1 across all codes matches HMS report exactly ──
        def cash_received(date_from, date_to):
            cur.execute("""
                SELECT ISNULL(SUM(BillTot), 0) AS cash
                FROM Bills
                WHERE CAST(BillDt AS DATE) >= %s
                  AND CAST(BillDt AS DATE) <= %s
                  AND (BillVoid IS NULL OR BillVoid = 0)
                  AND BillPmode = 1
            """, (date_from, date_to))
            row = cur.fetchone()
            return float((row or {}).get('cash') or 0)

        cash_today = cash_received(selected.date(), selected.date())

        # ── Room count from Bills (matches printed report, includes day-use) ──
        def bills_room_count(date):
            cur.execute("""
                SELECT COUNT(BillRmNo) as cnt
                FROM Bills
                WHERE CAST(BillDt AS DATE) = %s
                  AND BillCode = 'RC'
                  AND (BillVoid IS NULL OR BillVoid = 0)
            """, (date,))
            row = cur.fetchone()
            return int((row or {}).get('cnt') or 0)

        rooms_today = bills_room_count(selected.date())
        rooms_yest  = bills_room_count(previous.date())

        # ── Convert selected date to Nepali (BS) ─────────
        today_bs     = NepaliDate.from_datetime_date(datetime.now().date())
        selected_bs  = NepaliDate.from_datetime_date(selected.date())

        # ── MTD ───────────────────────────────────────────
        # If selected date is in the same BS month as today → end = today (MTD doesn't move)
        # If selected date is in a different BS month → end = selected date
        same_bs_month = (selected_bs.year  == today_bs.year and
                         selected_bs.month == today_bs.month)
        mtd_end      = datetime.now().date() if same_bs_month else selected.date()

        mtd_start_bs = NepaliDate(selected_bs.year, selected_bs.month, 1)
        mtd_start_ad = mtd_start_bs.to_datetime_date()
        mtd_days     = (mtd_end - mtd_start_ad).days + 1
        mtd_avail_bs = TOTAL_ROOMS * mtd_days

        cur.execute("""
            SELECT ISNULL(SUM(dc), 0) as total
            FROM (
                SELECT CAST(BillDt AS DATE) as d, COUNT(BillRmNo) as dc
                FROM Bills
                WHERE CAST(BillDt AS DATE) >= %s
                  AND CAST(BillDt AS DATE) <= %s
                  AND BillCode = 'RC'
                  AND (BillVoid IS NULL OR BillVoid = 0)
                GROUP BY CAST(BillDt AS DATE)
            ) x
        """, (mtd_start_ad, mtd_end))
        mtd_room_nights = int((cur.fetchone() or {}).get('total') or 0)

        # ── Fiscal Year ───────────────────────────────────
        # FY starts Shrawan 1 (BS month 4)
        def get_fy_start_bs(bs_date):
            if bs_date.month >= 4:
                return NepaliDate(bs_date.year, 4, 1)
            else:
                return NepaliDate(bs_date.year - 1, 4, 1)

        selected_fy_start_bs = get_fy_start_bs(selected_bs)
        today_fy_start_bs    = get_fy_start_bs(today_bs)

        # If selected date is in the same fiscal year as today → end = today (FY doesn't move)
        # If selected date is in a different fiscal year → end = selected date
        same_fy  = (selected_fy_start_bs.year == today_fy_start_bs.year)
        fy_end   = datetime.now().date() if same_fy else selected.date()

        fy_start_bs = selected_fy_start_bs
        fy_start    = fy_start_bs.to_datetime_date()
        fy_days     = (fy_end - fy_start).days + 1
        fy_avail    = TOTAL_ROOMS * fy_days

        cur.execute("""
            SELECT ISNULL(SUM(dc), 0) as total
            FROM (
                SELECT CAST(BillDt AS DATE) as d, COUNT(BillRmNo) as dc
                FROM Bills
                WHERE CAST(BillDt AS DATE) >= %s
                  AND CAST(BillDt AS DATE) <= %s
                  AND BillCode = 'RC'
                  AND (BillVoid IS NULL OR BillVoid = 0)
                GROUP BY CAST(BillDt AS DATE)
            ) x
        """, (fy_start, fy_end))
        fy_room_nights = int((cur.fetchone() or {}).get('total') or 0)

        # MTD cash (same BS-month logic as occupancy MTD)
        cash_mtd = cash_received(mtd_start_ad, mtd_end)

        conn.close()

        # ── Revenue table (today/yesterday from Bills, MTD/YTD from Audit) ──
        # MTD/YTD use Audit columns; FLT replaces SPL (flight/transfer billed under SPA code)
        revenue_defs = [
            ("Room Sales",      "RmChg", "RmChg"),
            ("Meal Plan",       "RmPlan","RmPlan"),
            ("Food",            "RES",   "RES"),
            ("Beverage",        "BAR",   "BAR"),
            ("SPA / Transport", "FLT",   "FLT"),
            ("Laundry",         "LAU",   "LAU"),
            ("Miscellaneous",   "MISC",  "MISC"),
        ]
        revenue = []
        for label, bills_col, audit_col in revenue_defs:
            td = b_today.get(bills_col, 0.0)
            yd = b_yest.get(bills_col, 0.0)
            revenue.append({
                "label":     label,
                "today":     round(td, 2),
                "yesterday": round(yd, 2),
                "change":    round(td - yd, 2),
                "subtotal":  False,
            })
            # Insert Room Revenue subtotal after Meal Plan
            if bills_col == "RmPlan":
                rm_td = b_today.get("RmChg", 0.0) + td
                rm_yd = b_yest.get("RmChg", 0.0) + yd
                revenue.append({
                    "label":     "Room Revenue",
                    "today":     round(rm_td, 2),
                    "yesterday": round(rm_yd, 2),
                    "change":    round(rm_td - rm_yd, 2),
                    "subtotal":  True,
                })
            # Insert Restaurant Sales subtotal after Beverage
            if bills_col == "BAR":
                rs_td = b_today.get("RES", 0.0) + td
                rs_yd = b_yest.get("RES", 0.0) + yd
                revenue.append({
                    "label":     "Restaurant Sales",
                    "today":     round(rs_td, 2),
                    "yesterday": round(rs_yd, 2),
                    "change":    round(rs_td - rs_yd, 2),
                    "subtotal":  True,
                })

        t_total = sum(r["today"]     for r in revenue if not r["subtotal"])
        y_total = sum(r["yesterday"] for r in revenue if not r["subtotal"])
        revenue.append({
            "label":     "Total",
            "today":     round(t_total, 2),
            "yesterday": round(y_total, 2),
            "change":    round(t_total - y_total, 2),
            "subtotal":  False,
        })

        # ── Occupancy metrics ────────────────────────────
        t_occ = rooms_today
        y_occ = rooms_yest

        return jsonify({
            "date":         selected.strftime("%A, %B %d, %Y"),
            "today_str":    selected.strftime("%m/%d/%Y"),
            "prev_str":     previous.strftime("%m/%d/%Y"),
            "is_today":     is_today,
            "nepali_date":  f"{selected_bs.day} {selected_bs.strftime('%B')} {selected_bs.year}",
            "bs": {
                "year":  selected_bs.year,
                "month": selected_bs.month,
                "day":   selected_bs.day,
            },
            "frontdesk": {
                "reservations": int(fv(rsv.get("arr"))),
                "checkins":     int(fv(t.get("ArrRm_T"))),
                "guests":       int(fv(t.get("Pax_T"))),
            },
            "rooms": {
                "total":       TOTAL_ROOMS,
                "occupied":    rack.get(0, 0),
                "vacant":      rack.get(1, 0),
                "dirty":       rack.get(2, 0),
                "inspect":     rack.get(4, 0),
                "house_use":   rack.get(7, 0),
                "out_of_order":rack.get(3, 0) + rack.get(6, 0),
                "departures":  rack.get(5, 0),
                "arrivals":    int(fv(rsv.get("arr"))),
                "inhouse":     rack.get(0, 0),
            },
            "occupancy": {
                "today":         t_occ,
                "yesterday":     y_occ,
                "today_pct":     round(t_occ / TOTAL_ROOMS * 100, 1),
                "yest_pct":      round(y_occ / TOTAL_ROOMS * 100, 1),
                "today_pax":     fv(t.get("Pax_T")),
                "yest_pax":      fv(y.get("Pax_T")),
                "mtd_rooms":     mtd_room_nights,
                "mtd_avail":     mtd_avail_bs,
                "mtd_pct":       round(mtd_room_nights / mtd_avail_bs * 100, 1) if mtd_avail_bs else 0,
                "fy_rooms":      fy_room_nights,
                "fy_avail":      fy_avail,
                "fy_pct":        round(fy_room_nights / fy_avail * 100, 1) if fy_avail else 0,
                "mtd_label":     f"{selected_bs.strftime('%B')} {selected_bs.year} (MTD)",
                "fy_label":      f"FY {fy_start_bs.year}/{fy_start_bs.year + 1}",
            },
            "revenue": revenue,
            "cash": {
                "today": round(cash_today),
                "mtd":   round(cash_mtd),
                "mtd_label": f"{selected_bs.strftime('%B')} {selected_bs.year}",
            },
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/activity")
@login_required
def api_activity():
    """Activity feed — still from HMS web (real-time notifications)."""
    try:
        s = get_session()
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        type_names = {
            "1": {"label": "Check-in / Check-out", "icon": "🏨"},
            "2": {"label": "Restaurant Bills",      "icon": "🍽️"},
            "3": {"label": "Purchases & Issues",    "icon": "📦"},
            "4": {"label": "SPA Bills",             "icon": "💆"},
        }
        all_items = []
        for t, meta in type_names.items():
            resp  = s.post(f"{HMS_URL}/Dashboard.aspx/GetActivityList",
                           data=f'{{"type": "{t}"}}', headers=headers, timeout=10)
            inner = json.loads(json.loads(resp.text)["d"])
            for item in inner.get("GetDataResult", []):
                all_items.append({
                    "type":    t,
                    "icon":    meta["icon"],
                    "label":   meta["label"],
                    "title":   item.get("title",   ""),
                    "msg":     item.get("msg",     ""),
                    "entryby": item.get("entryby", ""),
                    "timeago": item.get("timeago", ""),
                })
        return jsonify(all_items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rooms")
@login_required
def api_rooms():
    """Live room status grid — always current, not date-filtered."""
    try:
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                r.RmNo,
                r.RmAvl,
                g.GName      AS guest_name,
                CAST(g.GDepDt AS DATE) AS checkout_date
            FROM Rooms r
            LEFT JOIN Guests g
                ON g.GRmNo = r.RmNo
               AND CAST(g.GDepDt AS DATE) >= CAST(GETDATE() AS DATE)
            ORDER BY r.RmNo
        """)
        rooms = cur.fetchall()
        conn.close()

        status_map = {
            0: ('Occupied',       'occupied'),
            1: ('Vacant',         'vacant'),
            2: ('Dirty',          'dirty'),
            3: ('Out of Order',   'ooo'),
            4: ('Inspect',        'inspect'),
            5: ('Departure',      'departure'),
            6: ('Out of Service', 'ooo'),
            7: ('House Use',      'houseuse'),
        }

        result = []
        for rm in rooms:
            code = rm.get('RmAvl') if rm.get('RmAvl') is not None else 1
            label, css = status_map.get(code, ('Unknown', 'vacant'))
            chk = rm.get('checkout_date')
            result.append({
                'room':     str(rm['RmNo']).strip(),
                'status':   code,
                'label':    label,
                'css':      css,
                'guest':    (rm.get('guest_name') or '').strip(),
                'checkout': chk.strftime('%b %d') if chk else '',
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/api/bs-to-ad")
@login_required
def api_bs_to_ad():
    """Convert a Bikram Sambat date to an AD date string (YYYY-MM-DD)."""
    try:
        y = int(request.args.get("y", 0))
        m = int(request.args.get("m", 0))
        d = int(request.args.get("d", 0))
        bs_date = NepaliDate(y, m, d)
        ad_date = bs_date.to_datetime_date()
        if ad_date > datetime.now().date():
            return jsonify({"error": "Future dates are not allowed"}), 400
        return jsonify({"ad": ad_date.strftime("%Y-%m-%d")})
    except Exception as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400


@app.route("/analysis")
@login_required
def analysis():
    if session.get('role') == 'housekeeping':
        return redirect(url_for('index'))
    return render_template("hsh_analysis.html")

@app.route("/")
@login_required
def index():
    if session.get('role') == 'housekeeping':
        return Response(HOUSEKEEPING_PAGE, content_type='text/html')
    return render_template("index.html", role='admin')


if __name__ == "__main__":
    app.run(debug=True, port=5055)

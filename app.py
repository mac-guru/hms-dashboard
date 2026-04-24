from flask import Flask, jsonify, render_template, request, session, redirect, url_for, Response
from functools import wraps
import pymssql, requests, re, json, os
from datetime import datetime, timedelta
from nepali_datetime import date as NepaliDate

# ── CORS helper ───────────────────────────────────────────
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

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

# ── API Key auth (for AMRIT HMS+ → Flask) ────────────────
API_KEY = os.environ.get('HMS_API_KEY', 'hms-amrit-2026')

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('key')
        if key != API_KEY:
            return add_cors(jsonify({'error': 'Unauthorized'})), 401
        return f(*args, **kwargs)
    return decorated

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
    path = os.path.join(app.root_path, 'templates', 'hsh_analysis.html')
    with open(path, 'rb') as f:
        content = f.read()
    return Response(content, content_type='text/html')

@app.route("/")
@login_required
def index():
    if session.get('role') == 'housekeeping':
        return Response(HOUSEKEEPING_PAGE, content_type='text/html')
    return render_template("index.html", role='admin')


# ═══════════════════════════════════════════════════════════
#  AMRIT HMS+ API  (v2 — API key auth, CORS enabled)
# ═══════════════════════════════════════════════════════════

@app.route('/api/v2/rooms', methods=['GET','OPTIONS'])
@api_key_required
def v2_rooms():
    """Full room rack — status, guest, type, dates."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                r.RmNo        AS room_no,
                r.RmAvl       AS status_code,
                ra.RmAvlDesc  AS status_label,
                ra.RmAvlColor AS status_color,
                r.RmOcc       AS occupancy_type,
                r.RmArrDt     AS arr_date,
                r.RmDepDt     AS dep_date,
                r.RmPax       AS pax,
                r.RmRate      AS rate,
                r.RmFloor     AS floor,
                rt.RmTyp      AS room_type,
                rt.RmTypCode  AS room_type_code,
                COALESCE(g.GName, rsv.RsvHdrName, b.BillGuestName) AS guest_name,
                g.GNat        AS nationality,
                g.GId         AS guest_id
            FROM Rooms r
            LEFT JOIN RmAvl ra ON r.RmAvl = ra.RmAvl
            LEFT JOIN RoomType rt ON TRY_CAST(r.RmType AS INT) = rt.RmTypSeq
            LEFT JOIN Guests g ON g.GRmNo = r.RmNo AND g.GGone = 0
            LEFT JOIN (
                SELECT r2.RmNo, h.RsvHdrName,
                       ROW_NUMBER() OVER (PARTITION BY r2.RmNo ORDER BY d.RsvDetArrDt DESC) AS rn
                FROM FRSVDet d
                JOIN FRSVHDR h  ON h.RsvHdrId = d.RsvDetHdrId
                JOIN Rooms r2   ON r2.RmId = d.RsvRmId
                WHERE CAST(d.RsvDetArrDt AS DATE) <= CAST(GETDATE() AS DATE)
                  AND CAST(d.RsvDetDepDt AS DATE) >= CAST(GETDATE() AS DATE)
                  AND d.RsvDetStat != 'X'
            ) rsv ON rsv.RmNo = r.RmNo AND rsv.rn = 1
            LEFT JOIN (
                SELECT BillRmNo, MAX(BillGuestName) AS BillGuestName
                FROM Bills
                WHERE CAST(BillDt AS DATE) = CAST(GETDATE() AS DATE)
                  AND BillCode = 'RC'
                  AND (BillVoid IS NULL OR BillVoid = 0)
                GROUP BY BillRmNo
            ) b ON b.BillRmNo = r.RmNo
            ORDER BY r.RmNo
        """)
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'room_no':       str(row['room_no'] or '').strip(),
                'status_code':   row['status_code'],
                'status_label':  row['status_label'] or 'Vacant',
                'status_color':  row['status_color'] or '#8deb85',
                'occupancy_type':row['occupancy_type'] or '',
                'arr_date':      row['arr_date'].strftime('%Y-%m-%d') if row['arr_date'] else None,
                'dep_date':      row['dep_date'].strftime('%Y-%m-%d') if row['dep_date'] else None,
                'pax':           row['pax'] or 0,
                'rate':          float(row['rate'] or 0),
                'floor':         row['floor'],
                'room_type':     row['room_type'] or '',
                'room_type_code':row['room_type_code'] or '',
                'guest_name':    (row['guest_name'] or '').strip(),
                'nationality':   row['nationality'] or '',
                'guest_id':      row['guest_id'],
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/guests', methods=['GET','OPTIONS'])
@api_key_required
def v2_guests():
    """In-house guests (GGone=0) + expected arrivals."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                g.GId         AS guest_id,
                g.GRmNo       AS room_no,
                g.GName       AS guest_name,
                g.GFName      AS first_name,
                g.GSName      AS last_name,
                g.GNat        AS nationality,
                g.GArrDt      AS arr_date,
                g.GDepDt      AS dep_date,
                g.GNo         AS pax,
                g.GPpNo       AS passport_no,
                g.GIdentity   AS id_type,
                g.GGone       AS gone,
                g.GBalance    AS balance,
                g.GRem        AS remarks,
                g.GRsvHdrId   AS rsv_hdr_id,
                g.GMbId       AS mb_id,
                r.RmAvl       AS room_status_code,
                ra.RmAvlDesc  AS room_status,
                rt.RmTyp      AS room_type,
                h.RsvHdrSrc   AS source,
                h.RsvHdrPlan  AS meal_plan,
                h.RsvHdrAgt   AS agent
            FROM Guests g
            LEFT JOIN Rooms r  ON r.RmNo = g.GRmNo
            LEFT JOIN RmAvl ra ON r.RmAvl = ra.RmAvl
            LEFT JOIN RoomType rt ON TRY_CAST(r.RmType AS INT) = rt.RmTypSeq
            LEFT JOIN FRSVHDR h ON h.RsvHdrId = g.GRsvHdrId
            WHERE g.GGone = 0
            ORDER BY g.GRmNo
        """)
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'guest_id':    row['guest_id'],
                'room_no':     (row['room_no'] or '').strip(),
                'guest_name':  (row['guest_name'] or '').strip(),
                'nationality': row['nationality'] or '',
                'arr_date':    row['arr_date'].strftime('%Y-%m-%d') if row['arr_date'] else None,
                'dep_date':    row['dep_date'].strftime('%Y-%m-%d') if row['dep_date'] else None,
                'pax':         row['pax'] or 1,
                'passport_no': row['passport_no'] or '',
                'id_type':     row['id_type'] or '',
                'balance':     float(row['balance'] or 0),
                'room_status': row['room_status'] or '',
                'room_type':   row['room_type'] or '',
                'source':      row['source'] or '',
                'meal_plan':   row['meal_plan'] or '',
                'agent':       row['agent'] or '',
                'remarks':     row['remarks'] or '',
                'mb_id':       row['mb_id'],
                'rsv_hdr_id':  row['rsv_hdr_id'],
                'status':      'In-House',
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/reservations', methods=['GET','OPTIONS'])
@api_key_required
def v2_reservations():
    """Reservations — upcoming, today, or all open."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        status = request.args.get('status', '')  # today | upcoming | all
        days   = int(request.args.get('days', 30))
        conn   = get_db()
        cur    = conn.cursor(as_dict=True)

        where = "(BillVoid IS NULL OR BillVoid = 0)"
        if status == 'today':
            where = "CAST(d.RsvDetArrDt AS DATE) = CAST(GETDATE() AS DATE)"
        elif status == 'upcoming':
            where = "CAST(d.RsvDetArrDt AS DATE) >= CAST(GETDATE() AS DATE)"
        elif status == 'inhouse':
            where = ("CAST(d.RsvDetArrDt AS DATE) <= CAST(GETDATE() AS DATE) "
                     "AND CAST(d.RsvDetDepDt AS DATE) >= CAST(GETDATE() AS DATE)")
        else:
            where = f"CAST(d.RsvDetArrDt AS DATE) >= DATEADD(day, -{days}, CAST(GETDATE() AS DATE))"

        cur.execute(f"""
            SELECT
                h.RsvHdrId        AS rsv_id,
                d.RsvDetId        AS det_id,
                h.RsvHdrName      AS guest_name,
                d.RsvRmType       AS room_type,
                d.RsvDetArrDt     AS arr_date,
                d.RsvDetDepDt     AS dep_date,
                d.RsvDetPax       AS pax,
                d.RsvDetPlan      AS meal_plan,
                d.RsvRmRate       AS rate,
                d.RsvDetStat      AS status,
                d.RsvDetCheckIn   AS checked_in,
                h.RsvHdrSrc       AS source,
                h.RsvHdrAgt       AS agent,
                h.RsvHdrMarket    AS market,
                h.RsvHdrEmail     AS email,
                h.RsvHdrRem       AS remarks,
                h.RsvHdrCountry   AS country,
                d.RsvRmId         AS room_id,
                r.RmNo            AS room_no
            FROM FRSVDet d
            JOIN FRSVHDR h ON h.RsvHdrId = d.RsvDetHdrId
            LEFT JOIN Rooms r ON r.RmId = d.RsvRmId
            WHERE {where}
              AND d.RsvDetStat != 'X'
            ORDER BY d.RsvDetArrDt
        """)
        rows = cur.fetchall()
        conn.close()

        def nights(arr, dep):
            try: return (dep - arr).days
            except: return 0

        result = []
        for row in rows:
            arr = row['arr_date'].date() if hasattr(row['arr_date'], 'date') else row['arr_date']
            dep = row['dep_date'].date() if hasattr(row['dep_date'], 'date') else row['dep_date']
            result.append({
                'rsv_id':     row['rsv_id'],
                'det_id':     row['det_id'],
                'guest_name': (row['guest_name'] or '').strip(),
                'room_no':    (row['room_no'] or '').strip(),
                'room_type':  row['room_type'] or '',
                'arr_date':   arr.strftime('%Y-%m-%d') if arr else None,
                'dep_date':   dep.strftime('%Y-%m-%d') if dep else None,
                'nights':     nights(arr, dep),
                'pax':        row['pax'] or 1,
                'meal_plan':  row['meal_plan'] or '',
                'rate':       float(row['rate'] or 0),
                'status':     'Expected' if not row['checked_in'] else 'In-House',
                'source':     row['source'] or '',
                'agent':      row['agent'] or '',
                'market':     row['market'] or '',
                'email':      row['email'] or '',
                'remarks':    row['remarks'] or '',
                'country':    row['country'] or '',
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/bills', methods=['GET','OPTIONS'])
@api_key_required
def v2_bills():
    """Bills / folio for a room or date range. Also supports mb_id for MasterBill folio."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        mb_id = request.args.get('mb_id', '').strip()
        room  = request.args.get('room', '')
        days  = int(request.args.get('days', 90))
        conn  = get_db()
        cur   = conn.cursor(as_dict=True)

        # ── MasterBill folio (by MbId) ─────────────────────────────
        if mb_id:
            # Get room + stay dates from MBLink
            cur.execute("""
                SELECT MBL_RMLST, MBL_ARRDT, MBL_DEPDT
                FROM MBLink
                WHERE MBL_MBID = %s
            """, (int(mb_id),))
            link = cur.fetchone()
            if not link:
                conn.close()
                return add_cors(jsonify([]))

            # MBL_RMLST may be comma-separated; take the first room
            mb_room  = (link['MBL_RMLST'] or '').strip().split(',')[0].strip()
            arr_dt   = link['MBL_ARRDT']
            dep_dt   = link['MBL_DEPDT']

            # F&B / Spa bills for this room within the stay dates
            cur.execute("""
                SELECT b.BillRmNo AS room_no, b.BillDt AS bill_date,
                       b.BillCode AS bill_code, bd.BD_DES AS bill_desc,
                       ISNULL(b.BillTot,0)*ISNULL(b.BillFxRate,1) AS bill_total_npr,
                       b.BillPmode AS payment_mode, b.BillReceiptNo AS receipt_no
                FROM Bills b
                LEFT JOIN BillDesc bd ON bd.BD_CODE = b.BillCode
                WHERE b.BillRmNo = %s
                  AND CAST(b.BillDt AS DATE) >= CAST(%s AS DATE)
                  AND CAST(b.BillDt AS DATE) <= DATEADD(day, 1, CAST(%s AS DATE))
                  AND (b.BillVoid IS NULL OR b.BillVoid = 0)
                ORDER BY b.BillDt
            """, (mb_room, arr_dt, dep_dt))
            bill_rows = cur.fetchall()

            # Room charges from BillsNights (linked by BillMbId)
            cur.execute("""
                SELECT bn.BillRmNo AS room_no, bn.BillDt AS bill_date,
                       'RC'           AS bill_code,
                       'Room Charge'  AS bill_desc,
                       ISNULL(bn.BillTot,0)*ISNULL(bn.BillFxRate,1) AS bill_total_npr,
                       '0'            AS payment_mode,
                       NULL           AS receipt_no
                FROM BillsNights bn
                WHERE bn.BillMbId = %s
                  AND (bn.BillVoid IS NULL OR bn.BillVoid = 0)
                ORDER BY bn.BillDt
            """, (int(mb_id),))
            night_rows = cur.fetchall()

            conn.close()
            result = []
            for row in bill_rows + night_rows:
                result.append({
                    'room_no':        (row['room_no'] or '').strip(),
                    'bill_date':      row['bill_date'].strftime('%Y-%m-%d') if row['bill_date'] else None,
                    'bill_time':      row['bill_date'].strftime('%H:%M')    if row['bill_date'] else None,
                    'bill_code':      (row['bill_code'] or '').strip(),
                    'bill_desc':      (row['bill_desc'] or row['bill_code'] or '').strip(),
                    'bill_total_npr': round(float(row['bill_total_npr'] or 0), 2),
                    'payment_mode':   str(row['payment_mode'] or '0'),
                    'receipt_no':     row['receipt_no'],
                })
            result.sort(key=lambda x: x['bill_date'] or '')
            return add_cors(jsonify(result))

        # ── Legacy: folio by room + days ──────────────────────────
        where = f"CAST(BillDt AS DATE) >= DATEADD(day, -{days}, CAST(GETDATE() AS DATE))"
        if room:
            where += f" AND BillRmNo = '{room}'"

        cur.execute(f"""
            SELECT
                BillRmNo       AS room_no,
                BillDt         AS bill_date,
                BillCode       AS bill_code,
                bd.BD_DES      AS bill_desc,
                BillTot        AS bill_total,
                BillFxRate     AS fx_rate,
                BillCurr       AS currency,
                ISNULL(BillTot,0) * ISNULL(BillFxRate,1) AS bill_total_npr,
                BillRC         AS room_charge,
                BillPlanAmt    AS plan_amt,
                BillVat        AS vat_amt,
                BillTT         AS tax_amt,
                BillPmode      AS payment_mode,
                BillReceiptNo  AS receipt_no,
                BillGuestName  AS guest_name,
                BillVoid       AS is_void,
                BillNts        AS nights,
                BillRmArrDate  AS arr_date,
                BillRmDepDate  AS dep_date
            FROM Bills b
            LEFT JOIN BillDesc bd ON bd.BD_CODE = b.BillCode
            WHERE {where}
              AND (BillVoid IS NULL OR BillVoid = 0)
            ORDER BY BillDt DESC
        """)
        rows = cur.fetchall()
        conn.close()

        result = []
        for row in rows:
            result.append({
                'room_no':       (row['room_no'] or '').strip(),
                'bill_date':     row['bill_date'].strftime('%Y-%m-%d') if row['bill_date'] else None,
                'bill_time':     row['bill_date'].strftime('%H:%M') if row['bill_date'] else None,
                'bill_code':     row['bill_code'] or '',
                'bill_desc':     row['bill_desc'] or row['bill_code'] or '',
                'bill_total':    float(row['bill_total'] or 0),
                'fx_rate':       float(row['fx_rate'] or 1),
                'currency':      row['currency'] or 'NRS',
                'bill_total_npr':round(float(row['bill_total'] or 0) * float(row['fx_rate'] or 1), 2),
                'plan_amt':      float(row['plan_amt'] or 0),
                'vat_amt':       float(row['vat_amt'] or 0),
                'tax_amt':       float(row['tax_amt'] or 0),
                'payment_mode':  str(row['payment_mode'] or 0),
                'receipt_no':    row['receipt_no'],
                'guest_name':    (row['guest_name'] or '').strip(),
                'nights':        row['nights'] or 0,
                'arr_date':      row['arr_date'].strftime('%Y-%m-%d') if row['arr_date'] else None,
                'dep_date':      row['dep_date'].strftime('%Y-%m-%d') if row['dep_date'] else None,
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/search', methods=['GET','OPTIONS'])
@api_key_required
def v2_search():
    """Global search across Guests, Bills, BillsNights."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        q = request.args.get('q', '').strip()
        if len(q) < 2:
            return add_cors(jsonify([]))

        like = f'%{q}%'
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        results = []

        # Guests — only those with a master bill (active or checked-out)
        cur.execute("""
            SELECT TOP 6 GId, GName, GRmNo, GNat, GCountry,
                         GArrDt, GDepDt, GGone, GMbId, GPpNo
            FROM Guests
            WHERE (GName LIKE %s OR GPpNo LIKE %s OR GRmNo LIKE %s)
              AND GMbId IS NOT NULL
            ORDER BY GArrDt DESC
        """, (like, like, like))
        for row in cur.fetchall():
            results.append({
                'type':       'guest',
                'id':         row['GId'],
                'title':      (row['GName']    or '').strip(),
                'room':       (row['GRmNo']    or '').strip(),
                'nationality':(row['GNat']     or row['GCountry'] or '').strip(),
                'arr_date':   str(row['GArrDt'])  if row['GArrDt']  else None,
                'dep_date':   str(row['GDepDt'])  if row['GDepDt']  else None,
                'is_gone':    bool(row['GGone']),
                'mb_id':      row['GMbId'],
                'passport':   (row['GPpNo'] or '').strip(),
            })

        # Bills
        cur.execute("""
            SELECT TOP 6
                BillNo, BillGuestName, BillCustomerName,
                ISNULL(BillTot,0) * ISNULL(BillFxRate,1) AS amount,
                BillRmNo, BillDt, BillCode, BillPmode,
                ISNULL(BillVat,0) AS vat_amt,
                ISNULL(BillDiscount,0) AS discount_amt
            FROM Bills
            WHERE (BillNo LIKE %s OR BillGuestName LIKE %s
                   OR BillCustomerName LIKE %s OR BillRmNo LIKE %s)
              AND (BillVoid IS NULL OR BillVoid = 0)
            ORDER BY BillDt DESC
        """, (like, like, like, like))
        for row in cur.fetchall():
            pmode = str(row['BillPmode'] or '')
            pay_label = {'0':'Room/Charge','1':'Cash','3':'Complimentary'}.get(pmode, 'Other')
            results.append({
                'type':       'bill',
                'id':         (row['BillNo'] or '').strip(),
                'title':      (row['BillGuestName'] or row['BillCustomerName'] or '').strip(),
                'bill_no':    (row['BillNo'] or '').strip(),
                'room_no':    (row['BillRmNo'] or '').strip(),
                'amount':     round(float(row['amount']       or 0), 2),
                'vat_amt':    round(float(row['vat_amt']      or 0), 2),
                'discount':   round(float(row['discount_amt'] or 0), 2),
                'bill_code':  (row['BillCode'] or '').strip(),
                'pay_label':  pay_label,
                'date':       row['BillDt'].strftime('%Y-%m-%d') if row['BillDt'] else None,
                'time':       row['BillDt'].strftime('%H:%M')    if row['BillDt'] else None,
            })

        # BillsNights (room charge history)
        cur.execute("""
            SELECT TOP 6
                bn.BillRmNo, bn.BillDt, bn.BillPlan, bn.BillRmType,
                ISNULL(bn.BillTot,0)*ISNULL(bn.BillFxRate,1) AS total_amt,
                ISNULL(bn.BillRC,0)  AS room_charge,
                ISNULL(bn.BillVat,0) AS vat_amt,
                COALESCE(g.GName, h.RsvHdrName) AS guest_name,
                bn.BillGId
            FROM BillsNights bn
            LEFT JOIN Guests  g ON g.GId        = bn.BillGId
            LEFT JOIN FRSVHDR h ON h.RsvHdrId   = bn.BillMbId
            WHERE (bn.BillRmNo LIKE %s OR g.GName LIKE %s OR h.RsvHdrName LIKE %s)
              AND (bn.BillVoid IS NULL OR bn.BillVoid = 0)
            ORDER BY bn.BillDt DESC
        """, (like, like, like))
        for row in cur.fetchall():
            results.append({
                'type':       'room_charge',
                'id':         f"{row['BillRmNo']}_{row['BillDt']}",
                'title':      (row['guest_name'] or row['BillRmNo'] or '').strip(),
                'room_no':    (row['BillRmNo']   or '').strip(),
                'plan':       (row['BillPlan']   or '').strip(),
                'room_type':  (row['BillRmType'] or '').strip(),
                'amount':     round(float(row['total_amt']   or 0), 2),
                'room_charge':round(float(row['room_charge'] or 0), 2),
                'vat_amt':    round(float(row['vat_amt']     or 0), 2),
                'date':       row['BillDt'].strftime('%Y-%m-%d') if row['BillDt'] else None,
                'guest_id':   row['BillGId'],
            })

        conn.close()
        return add_cors(jsonify(results))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/overview/revenue', methods=['GET','OPTIONS'])
@api_key_required
def v2_overview_revenue():
    """Combined revenue summary: Room + Spa + Restaurant for a date range."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to   = request.args.get('date_to',   datetime.now().strftime('%Y-%m-%d'))
        conn = get_db()
        cur  = conn.cursor(as_dict=True)

        # Room revenue from Bills (BillCode='RC') — matches WebHMS night audit report.
        # NRS rooms: BillRC + BillPlanAmt  |  Foreign: (BillRC + BillPlanAmt) * BillFxRate
        cur.execute("""
            SELECT
                ISNULL(SUM(
                    CASE WHEN BillCurr = 'NRS' OR BillCurr IS NULL
                         THEN ISNULL(BillRC,0) + ISNULL(BillPlanAmt,0)
                         ELSE (ISNULL(BillRC,0) + ISNULL(BillPlanAmt,0)) * ISNULL(BillFxRate,1)
                    END
                ), 0) AS room_revenue,
                COUNT(*) AS room_count
            FROM Bills
            WHERE BillCode = 'RC'
              AND CAST(BillDt AS DATE) >= %s
              AND CAST(BillDt AS DATE) <= %s
              AND (BillVoid IS NULL OR BillVoid = 0)
        """, (date_from, date_to))
        room = cur.fetchone()

        # Spa revenue from Bills
        cur.execute("""
            SELECT
                ISNULL(SUM(ISNULL(BillTot,0) * ISNULL(BillFxRate,1)), 0) AS spa_revenue,
                COUNT(*) AS spa_count
            FROM Bills
            WHERE CAST(BillDt AS DATE) >= %s
              AND CAST(BillDt AS DATE) <= %s
              AND BillCode = 'SPA'
              AND (BillVoid IS NULL OR BillVoid = 0)
        """, (date_from, date_to))
        spa = cur.fetchone()

        # Restaurant revenue from Bills
        cur.execute("""
            SELECT
                ISNULL(SUM(ISNULL(BillTot,0) * ISNULL(BillFxRate,1)), 0) AS restaurant_revenue,
                COUNT(*) AS restaurant_count
            FROM Bills
            WHERE CAST(BillDt AS DATE) >= %s
              AND CAST(BillDt AS DATE) <= %s
              AND BillCode IN ('RES','BAR')
              AND (BillVoid IS NULL OR BillVoid = 0)
        """, (date_from, date_to))
        res = cur.fetchone()
        conn.close()

        room_rev = round(float(room['room_revenue'] or 0), 2)
        spa_rev  = round(float(spa['spa_revenue']   or 0), 2)
        res_rev  = round(float(res['restaurant_revenue'] or 0), 2)

        return add_cors(jsonify({
            'room_revenue':       room_rev,
            'spa_revenue':        spa_rev,
            'restaurant_revenue': res_rev,
            'total_revenue':      round(room_rev + spa_rev + res_rev, 2),
            'room_count':         room['room_count'],
            'spa_count':          spa['spa_count'],
            'restaurant_count':   res['restaurant_count'],
        }))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/rooms/revenue', methods=['GET','OPTIONS'])
@api_key_required
def v2_rooms_revenue():
    """Room revenue detail from Bills (BillCode='RC') — per-room per-day rows."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to   = request.args.get('date_to',   datetime.now().strftime('%Y-%m-%d'))
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                CAST(b.BillDt AS DATE)                           AS bill_date,
                b.BillRmNo                                       AS room_no,
                ISNULL(b.BillRC,  0)                             AS room_charge,
                ISNULL(b.BillPlanAmt, 0)                         AS plan_amt,
                ISNULL(b.BillVat, 0)                             AS vat_amt,
                ISNULL(b.BillTT,  0)                             AS tt_amt,
                CASE WHEN b.BillCurr = 'NRS' OR b.BillCurr IS NULL
                     THEN ISNULL(b.BillRC,0) + ISNULL(b.BillPlanAmt,0)
                     ELSE (ISNULL(b.BillRC,0) + ISNULL(b.BillPlanAmt,0)) * ISNULL(b.BillFxRate,1)
                END                                              AS total_amt,
                b.BillCurr                                       AS currency,
                ISNULL(b.BillFxRate, 1)                          AS fx_rate,
                CASE WHEN b.BillPmode = 3 THEN 1 ELSE 0 END     AS is_comp,
                ISNULL(b.BillGuestName, b.BillRmNo)              AS guest_name
            FROM Bills b
            WHERE b.BillCode = 'RC'
              AND CAST(b.BillDt AS DATE) >= %s
              AND CAST(b.BillDt AS DATE) <= %s
              AND (b.BillVoid IS NULL OR b.BillVoid = 0)
            ORDER BY b.BillDt ASC, b.BillRmNo ASC
        """, (date_from, date_to))
        rows = cur.fetchall()
        conn.close()

        result = []
        for row in rows:
            result.append({
                'bill_date':   str(row['bill_date']),
                'room_no':     (row['room_no']    or '').strip(),
                'room_type':   '',
                'plan':        '',
                'room_charge': round(float(row['room_charge'] or 0), 2),
                'plan_amt':    round(float(row['plan_amt']    or 0), 2),
                'vat_amt':     round(float(row['vat_amt']     or 0), 2),
                'tt_amt':      round(float(row['tt_amt']      or 0), 2),
                'total_amt':   round(float(row['total_amt']   or 0), 2),
                'currency':    (row['currency']   or 'NRS').strip(),
                'fx_rate':     round(float(row['fx_rate']     or 1),  4),
                'is_comp':     bool(row['is_comp']),
                'guest_name':  (row['guest_name'] or '').strip(),
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/accounts/pl', methods=['GET','OPTIONS'])
@api_key_required
def v2_accounts_pl():
    """Profit & Loss report: revenue from Bills + expenses from GL ledger."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        # Default: current Nepal fiscal year (mid-July to today)
        today      = datetime.now()
        fy_start   = datetime(today.year if today.month >= 7 else today.year - 1, 7, 17)
        date_from  = request.args.get('date_from', fy_start.strftime('%Y-%m-%d'))
        date_to    = request.args.get('date_to',   today.strftime('%Y-%m-%d'))

        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        fv   = lambda v: round(float(v or 0), 2)

        # ── 1. Revenue from Bills (operational codes only) ──────────
        # Excluded accounting/payment codes:
        #   ACR=Agent Credit Receipt, PMT=Payment, RCT=Receipt,
        #   MB=Master Bill transfer, CR=Credit Note, ADV=Advance, CADV=Cash Advance
        cur.execute("""
            SELECT
                BillCode,
                SUM(CASE
                    WHEN BillCode = 'RC' AND (BillCurr = 'NRS' OR BillCurr IS NULL)
                        THEN ISNULL(BillRC,0) + ISNULL(BillPlanAmt,0)
                    WHEN BillCode = 'RC' AND BillCurr NOT IN ('NRS') AND BillCurr IS NOT NULL
                        THEN (ISNULL(BillRC,0) + ISNULL(BillPlanAmt,0)) * ISNULL(BillFxRate,1)
                    ELSE ISNULL(BillTot,0)
                END) AS total_revenue,
                SUM(CASE WHEN BillCode='RC'
                    THEN CASE WHEN BillCurr='NRS' OR BillCurr IS NULL
                              THEN ISNULL(BillRC,0)
                              ELSE ISNULL(BillRC,0)*ISNULL(BillFxRate,1) END
                    ELSE 0 END) AS tariff,
                SUM(CASE WHEN BillCode='RC'
                    THEN CASE WHEN BillCurr='NRS' OR BillCurr IS NULL
                              THEN ISNULL(BillPlanAmt,0)
                              ELSE ISNULL(BillPlanAmt,0)*ISNULL(BillFxRate,1) END
                    ELSE 0 END) AS plan_amt
            FROM Bills
            WHERE CAST(BillDt AS DATE) >= %s
              AND CAST(BillDt AS DATE) <= %s
              AND (BillVoid IS NULL OR BillVoid = 0)
              AND (BillCode IS NULL OR BillCode NOT IN (
                      'ACR','PMT','RCT','MB','CR','ADV','CADV'
                  ))
            GROUP BY BillCode
            ORDER BY BillCode
        """, (date_from, date_to))
        bill_rows = cur.fetchall()

        revenue_by_code = {}
        for row in bill_rows:
            code = (row['BillCode'] or 'MIS').strip().upper()
            revenue_by_code[code] = {
                'total':   fv(row['total_revenue']),
                'tariff':  fv(row['tariff']),
                'plan':    fv(row['plan_amt']),
            }

        def rev(code):
            return revenue_by_code.get(code, {}).get('total', 0.0)

        room_tariff  = revenue_by_code.get('RC', {}).get('tariff', 0.0)
        room_plan    = revenue_by_code.get('RC', {}).get('plan',   0.0)
        room_total   = rev('RC')
        food_total   = rev('RES')
        bev_total    = rev('BAR') + rev('MBAR')
        spa_total    = rev('SPA') + rev('FLT')
        lau_total    = rev('LAU')
        bak_total    = rev('BAK')
        cof_total    = rev('COF')
        # Other operational codes (MIS, SHP, TPL, etc.) — accounting codes already excluded above
        known_codes  = {'RC','RES','BAR','MBAR','SPA','FLT','LAU','BAK','COF'}
        mis_total    = sum(v['total'] for k, v in revenue_by_code.items()
                           if k not in known_codes)

        total_revenue = room_total + food_total + bev_total + spa_total + \
                        lau_total + bak_total + cof_total + mis_total

        revenue = {
            'room':         {'tariff': room_tariff, 'plan': room_plan, 'total': room_total},
            'food':         food_total,
            'beverage':     bev_total,
            'spa':          spa_total,
            'laundry':      lau_total,
            'bakery':       bak_total,
            'coffee':       cof_total,
            'other':        mis_total,
            'total':        round(total_revenue, 2),
            'by_code':      {k: v['total'] for k, v in revenue_by_code.items()},
        }

        # ── 2. Expenses from GL ledger (dual date source) ────────────
        # Two GL posting paths in WebHMS:
        #   A) Store/inventory module:  Transactions.T_DES → GLTRAN_DETL.VCH_NO  (JV005xxx, Purxxx)
        #   B) Manual journal vouchers: GLTRAN_MAST.VCH_NO → GLTRAN_DETL.VCH_NO (JV004xxx)
        # Both share the same GLTRAN_DETL table, so combine via OR EXISTS.
        cur.execute("""
            SELECT
                ac.GL_CODE,
                ac.GL_NAME,
                ISNULL(ac.MAST_GL_CODE,'') AS MAST_GL_CODE,
                ac.GL_TYPE,
                ISNULL(ac.GL_GROUP_LEVEL, 0) AS GL_GROUP_LEVEL,
                SUM(CASE WHEN gtd.GL_DR_CR='DR' THEN ISNULL(gtd.GL_LC_AMT,0) ELSE 0 END) AS dr_amt,
                SUM(CASE WHEN gtd.GL_DR_CR='CR' THEN ISNULL(gtd.GL_LC_AMT,0) ELSE 0 END) AS cr_amt
            FROM GLTRAN_DETL gtd
            JOIN AC_CHART ac ON ac.GL_CODE = gtd.GL_CODE
            WHERE ac.GL_TYPE IN ('E','I')
              AND (
                  -- Path A: store/inventory module (JV005xxx, Purxxx) — date from Transactions
                  EXISTS (
                      SELECT 1 FROM Transactions t
                      WHERE t.T_DES = gtd.VCH_NO
                        AND CAST(t.T_DT AS DATE) >= %s
                        AND CAST(t.T_DT AS DATE) <= %s
                  )
                  OR
                  -- Path B: manual journal vouchers (JV004xxx) — date from GLTRAN_MAST
                  EXISTS (
                      SELECT 1 FROM GLTRAN_MAST gtm
                      WHERE gtm.VCH_NO = gtd.VCH_NO
                        AND CAST(gtm.VCH_EDATE AS DATE) >= %s
                        AND CAST(gtm.VCH_EDATE AS DATE) <= %s
                  )
              )
            GROUP BY ac.GL_CODE, ac.GL_NAME, ac.MAST_GL_CODE, ac.GL_TYPE, ac.GL_GROUP_LEVEL
            ORDER BY ac.GL_CODE
        """, (date_from, date_to, date_from, date_to))
        gl_rows = cur.fetchall()

        gl_entries = []
        for row in gl_rows:
            dr  = fv(row['dr_amt'])
            cr  = fv(row['cr_amt'])
            typ = (row['GL_TYPE'] or '').strip().upper()
            # Income: net = CR - DR  |  Expense: net = DR - CR
            # Note: GL_DR_CR uses full words 'DR'/'CR' (not 'D'/'C')
            net = (cr - dr) if typ == 'I' else (dr - cr)
            gl_entries.append({
                'gl_code':     (row['GL_CODE']      or '').strip(),
                'gl_name':     (row['GL_NAME']      or '').strip(),
                'parent_code': (row['MAST_GL_CODE'] or '').strip(),
                'gl_type':     typ,
                'gl_level':    int(row['GL_GROUP_LEVEL'] or 0),
                'dr_amt':      dr,
                'cr_amt':      cr,
                'net_amount':  round(net, 2),
            })

        # ── 3. Payroll (salary / indirect labour expenses) ───────────
        payroll_total = 0.0
        payroll_rows  = []
        try:
            cur.execute("""
                SELECT
                    ISNULL(PRL_DEPT,'Unknown') AS dept,
                    SUM(ISNULL(PRL_AMT, 0)) AS total_amt
                FROM Payroll
                WHERE CAST(PRL_DT AS DATE) >= %s
                  AND CAST(PRL_DT AS DATE) <= %s
                GROUP BY PRL_DEPT
                ORDER BY PRL_DEPT
            """, (date_from, date_to))
            payroll_rows  = cur.fetchall()
            payroll_total = sum(fv(r['total_amt']) for r in payroll_rows)
        except Exception:
            payroll_total = 0.0
            payroll_rows  = []

        # GL_TYPE='I' entries: revenue recognized in accounting books (most accurate for P&L)
        # GL_TYPE='E' entries: expenses
        income_gl  = [e for e in gl_entries if e['gl_type'] == 'I']
        expense_gl = [e for e in gl_entries if e['gl_type'] == 'E' and e['net_amount'] != 0]

        # Separate "Loss & Gain" / FX adjustment accounts (below-the-line in WebHMS P&L)
        # Typically GL codes 400016-ish — anything that isn't a direct revenue centre
        below_line_codes = {'400016'}   # extend if needed
        operational_income_gl = [e for e in income_gl if e['gl_code'] not in below_line_codes]
        below_line_gl         = [e for e in income_gl if e['gl_code'] in below_line_codes]

        # Primary revenue figure = GL income accounts (matches WebHMS P&L)
        gl_revenue_total  = sum(e['net_amount'] for e in income_gl)
        operational_income = sum(e['net_amount'] for e in operational_income_gl)

        # ── Classify expenses as Direct (300015 tree) or Indirect (300016 tree) ──
        # WebHMS P&L labels: 300015 subtree = "Direct Expenses", 300016 subtree = "Indirect Expenses"
        cur.execute("SELECT GL_CODE, ISNULL(MAST_GL_CODE,'') AS MAST_GL_CODE FROM AC_CHART WHERE GL_TYPE='E'")
        parent_map = {r['GL_CODE'].strip(): r['MAST_GL_CODE'].strip() for r in cur.fetchall()}
        conn.close()

        def get_expense_category(gl_code):
            code = gl_code.strip()
            for _ in range(10):
                parent = parent_map.get(code, '')
                if not parent:
                    return 'OTHER'
                if parent == '300015':
                    return 'INDIRECT'  # AC_CHART name: INDIRECT EXPENSES → WebHMS "INDIRECT EXPENSES"
                if parent == '300016':
                    return 'DIRECT'    # AC_CHART name: DIRECT EXPENSES → WebHMS "DIRECT EXPENSES"
                code = parent
            return 'OTHER'

        for e in expense_gl:
            e['expense_category'] = get_expense_category(e['gl_code'])

        expense_direct   = [e for e in expense_gl if e['expense_category'] == 'DIRECT']
        expense_indirect = [e for e in expense_gl if e['expense_category'] == 'INDIRECT']
        total_direct     = round(sum(e['net_amount'] for e in expense_direct), 2)
        total_indirect   = round(sum(e['net_amount'] for e in expense_indirect), 2)

        total_gl_expenses = sum(e['net_amount'] for e in expense_gl)
        total_expenses    = round(total_gl_expenses + payroll_total, 2)
        # Net profit uses full GL revenue (incl. below-line) minus expenses
        net_profit        = round(gl_revenue_total - total_expenses, 2)

        return add_cors(jsonify({
            'date_from':            date_from,
            'date_to':              date_to,
            # Bills-based breakdown (department detail, may differ slightly from GL totals)
            'revenue':              revenue,
            'bills_total_revenue':  round(total_revenue, 2),
            # GL-based figures (accounting books — used for P&L totals)
            'gl_entries':           gl_entries,
            'income_gl':            income_gl,
            'operational_income_gl': operational_income_gl,
            'below_line_gl':        below_line_gl,
            'expense_gl':           expense_gl,
            'expense_direct':       expense_direct,
            'expense_indirect':     expense_indirect,
            'payroll_total':        round(payroll_total, 2),
            'payroll_rows':         [{'dept': r['dept'], 'amount': fv(r['total_amt'])} for r in payroll_rows],
            # Totals — use GL as authoritative source
            'total_revenue':        round(gl_revenue_total, 2),
            'operational_income':   round(operational_income, 2),
            'total_direct':         total_direct,
            'total_indirect':       total_indirect,
            'total_expenses':       total_expenses,
            'net_profit':           net_profit,
        }))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/debug/columns', methods=['GET','OPTIONS'])
@api_key_required
def v2_debug_columns():
    """Return column names for a given table, or list all tables if table=* (debug use)."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        table = request.args.get('table', 'Bills')
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        if table == '*':
            cur.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            tables = [r['TABLE_NAME'] for r in cur.fetchall()]
            conn.close()
            return add_cors(jsonify(tables))
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (table,))
        cols = [{'name': r['COLUMN_NAME'], 'type': r['DATA_TYPE']} for r in cur.fetchall()]
        conn.close()
        return add_cors(jsonify(cols))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/debug/sample', methods=['GET','OPTIONS'])
@api_key_required
def v2_debug_sample():
    """Sample TOP N rows from any table (debug)."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        table   = request.args.get('table', 'GLTRAN_MAST')
        n       = min(int(request.args.get('n', 5)), 50)
        order   = request.args.get('order', '')   # e.g. "T_DT DESC"
        where   = request.args.get('where', '')   # e.g. "T_DES IS NOT NULL"
        conn    = get_db()
        cur     = conn.cursor(as_dict=True)
        sql = f"SELECT TOP {n} * FROM [{table}]"
        if where:
            sql += f" WHERE {where}"
        if order:
            sql += f" ORDER BY {order}"
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            r = {}
            for k, v in row.items():
                if hasattr(v, 'strftime'):
                    r[k] = v.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    r[k] = v
            result.append(r)
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/debug/pl_detail', methods=['GET','OPTIONS'])
@api_key_required
def v2_debug_pl_detail():
    """Diagnose P&L data: count Transactions by REF type and GLTRAN_DETL GL types."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_from = request.args.get('date_from', '2026-03-15')
        date_to   = request.args.get('date_to',   '2026-04-13')
        conn = get_db()
        cur  = conn.cursor(as_dict=True)

        # 1. Count/sum Transactions by REF type for the date range
        cur.execute("""
            SELECT T_REF,
                   COUNT(*) AS cnt,
                   SUM(ISNULL(T_AMT,0)) AS total_amt,
                   SUM(CASE WHEN T_DES IS NOT NULL THEN 1 ELSE 0 END) AS with_des
            FROM Transactions
            WHERE CAST(T_DT AS DATE) >= %s AND CAST(T_DT AS DATE) <= %s
            GROUP BY T_REF
        """, (date_from, date_to))
        trx_by_ref = [dict(r) for r in cur.fetchall()]

        # 2. Count GLTRAN_DETL entries matching Transactions by VCH_NO in date range
        cur.execute("""
            SELECT ac.GL_TYPE,
                   COUNT(DISTINCT gtd.VCH_NO) AS vch_count,
                   COUNT(*) AS line_count,
                   SUM(CASE WHEN gtd.GL_DR_CR='DR' THEN ISNULL(gtd.GL_LC_AMT,0) ELSE 0 END) AS dr_total,
                   SUM(CASE WHEN gtd.GL_DR_CR='CR' THEN ISNULL(gtd.GL_LC_AMT,0) ELSE 0 END) AS cr_total
            FROM GLTRAN_DETL gtd
            JOIN AC_CHART ac ON ac.GL_CODE = gtd.GL_CODE
            WHERE EXISTS (
                SELECT 1 FROM Transactions t
                WHERE t.T_DES = gtd.VCH_NO
                  AND CAST(t.T_DT AS DATE) >= %s
                  AND CAST(t.T_DT AS DATE) <= %s
            )
            GROUP BY ac.GL_TYPE
        """, (date_from, date_to))
        gl_by_type = [dict(r) for r in cur.fetchall()]

        # 3. Check VCH_NO prefixes in GLTRAN_DETL that match Transactions dates
        cur.execute("""
            SELECT LEFT(gtd.VCH_NO, 3) AS vch_prefix,
                   COUNT(DISTINCT gtd.VCH_NO) AS vch_count,
                   COUNT(*) AS line_count
            FROM GLTRAN_DETL gtd
            WHERE EXISTS (
                SELECT 1 FROM Transactions t
                WHERE t.T_DES = gtd.VCH_NO
                  AND CAST(t.T_DT AS DATE) >= %s
                  AND CAST(t.T_DT AS DATE) <= %s
            )
            GROUP BY LEFT(gtd.VCH_NO, 3)
        """, (date_from, date_to))
        vch_prefixes = [dict(r) for r in cur.fetchall()]

        # 4. Total Transactions.T_AMT for the date range (by REF), full picture
        cur.execute("""
            SELECT T_REF,
                   SUM(ISNULL(T_AMT,0)) AS total_t_amt
            FROM Transactions
            WHERE CAST(T_DT AS DATE) >= %s AND CAST(T_DT AS DATE) <= %s
              AND T_DES IS NOT NULL
            GROUP BY T_REF
        """, (date_from, date_to))
        trx_with_des = [dict(r) for r in cur.fetchall()]

        # 5. Check if there are Iss-type entries in GLTRAN_DETL
        cur.execute("""
            SELECT TOP 5 VCH_NO, GL_CODE, GL_DR_CR, GL_LC_AMT
            FROM GLTRAN_DETL
            WHERE VCH_NO LIKE 'Iss%'
        """)
        iss_sample = [dict(r) for r in cur.fetchall()]

        conn.close()
        return add_cors(jsonify({
            'date_from':      date_from,
            'date_to':        date_to,
            'trx_by_ref':     trx_by_ref,
            'trx_with_des':   trx_with_des,
            'gl_by_type':     gl_by_type,
            'vch_prefixes':   vch_prefixes,
            'iss_sample':     iss_sample,
        }))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/spa/sales', methods=['GET','OPTIONS'])
@api_key_required
def v2_spa_sales():
    """Spa sales history — date range, BillCode='SPA' only."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to   = request.args.get('date_to',   datetime.now().strftime('%Y-%m-%d'))

        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                BillDt            AS bill_date,
                BillCode          AS bill_code,
                BillRmNo          AS to_ref,
                BillNo            AS bill_no,
                ISNULL(BillTot,0) * ISNULL(BillFxRate,1) AS amount,
                ISNULL(BillVat,0)      AS vat_amt,
                ISNULL(BillDiscount,0) AS discount_amt,
                ISNULL(BillComp,0)     AS compl_amt,
                ISNULL(BillCashAmt,0)  AS cash_amt,
                ISNULL(BillCrAmt,0)    AS credit_amt,
                BillGuestName     AS customer,
                BillCustomerName  AS customer_name,
                BillPmode         AS payment_mode,
                BillReceiptNo     AS cr_no
            FROM Bills
            WHERE CAST(BillDt AS DATE) >= %s
              AND CAST(BillDt AS DATE) <= %s
              AND BillCode = 'SPA'
              AND (BillVoid IS NULL OR BillVoid = 0)
            ORDER BY BillDt ASC, BillNo ASC
        """, (date_from, date_to))
        rows = cur.fetchall()
        conn.close()

        result = []
        for row in rows:
            pmode = str(row['payment_mode'] or 0)
            pay_label = {
                '0': 'Room/Charge', '1': 'Cash',
                '2': 'Cash',        '3': 'Complimentary',
            }.get(pmode, f'Mode{pmode}')

            result.append({
                'bill_date':    row['bill_date'].strftime('%Y-%m-%d') if row['bill_date'] else None,
                'bill_time':    row['bill_date'].strftime('%H:%M')    if row['bill_date'] else None,
                'outlet':       'Spa',
                'to_ref':       (row['to_ref'] or '').strip(),
                'bill_no':      (row['bill_no'] or '').strip() or None,
                'amount':       round(float(row['amount']       or 0), 2),
                'vat_amt':      round(float(row['vat_amt']      or 0), 2),
                'discount_amt': round(float(row['discount_amt'] or 0), 2),
                'compl_amt':    round(float(row['compl_amt']    or 0), 2),
                'cash_amt':     round(float(row['cash_amt']     or 0), 2),
                'credit_amt':   round(float(row['credit_amt']   or 0), 2),
                'customer':     (row['customer_name'] or row['customer'] or '').strip(),
                'payment_mode': pmode,
                'pay_label':    pay_label,
                'cr_no':        row['cr_no'],
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/restaurant/dish-report', methods=['GET','OPTIONS'])
@api_key_required
def v2_restaurant_dish_report():
    """Dish-wise sales report — qty sold and amount per menu item."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to   = request.args.get('date_to',   datetime.now().strftime('%Y-%m-%d'))
        outlet    = request.args.get('outlet', '')   # RES | BAR | '' = all

        if outlet == 'RES':
            pos_filter = "AND bi.BItmPOS = 'RES'"
        elif outlet == 'BAR':
            pos_filter = "AND bi.BItmPOS = 'BAR'"
        else:
            pos_filter = "AND bi.BItmPOS IN ('RES','BAR')"

        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute(f"""
            SELECT
                m.MenuName                                   AS dish_name,
                bi.BItmPOS                                   AS pos_code,
                SUM(ISNULL(bi.BItmQty, 0))                  AS total_qty,
                AVG(ISNULL(bi.BItmPrice, 0))                AS avg_price,
                SUM(ISNULL(bi.BitmTotAmt, 0))               AS total_amount
            FROM BillItems bi
            JOIN Menu   m ON m.MenuId = bi.BItmMenuId
            JOIN Covers c ON c.CvId   = bi.BItmCvId
            WHERE CAST(c.CvDt AS DATE) >= %s
              AND CAST(c.CvDt AS DATE) <= %s
              {pos_filter}
            GROUP BY m.MenuName, bi.BItmPOS
            ORDER BY SUM(ISNULL(bi.BitmTotAmt, 0)) DESC
        """, (date_from, date_to))
        rows = cur.fetchall()
        conn.close()

        result = []
        for row in rows:
            result.append({
                'dish_name':    (row['dish_name'] or '').strip(),
                'outlet':       'Restaurant' if row['pos_code'] == 'RES' else 'Bar',
                'total_qty':    round(float(row['total_qty']    or 0), 2),
                'avg_price':    round(float(row['avg_price']    or 0), 2),
                'total_amount': round(float(row['total_amount'] or 0), 2),
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/restaurant/sales', methods=['GET','OPTIONS'])
@api_key_required
def v2_restaurant_sales():
    """Restaurant sales history — date range, outlet filter."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_from = request.args.get('date_from', datetime.now().strftime('%Y-%m-%d'))
        date_to   = request.args.get('date_to',   datetime.now().strftime('%Y-%m-%d'))
        outlet    = request.args.get('outlet', '')   # RES | BAR | '' = all

        if outlet == 'RES':
            code_filter = "AND BillCode = 'RES'"
        elif outlet == 'BAR':
            code_filter = "AND BillCode = 'BAR'"
        else:
            code_filter = "AND BillCode IN ('RES','BAR')"

        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute(f"""
            SELECT
                BillDt            AS bill_date,
                BillCode          AS bill_code,
                BillRmNo          AS to_ref,
                BillNo            AS bill_no,
                ISNULL(BillTot,0) * ISNULL(BillFxRate,1) AS amount,
                ISNULL(BillRES,0) AS food_amt,
                ISNULL(BillBAR,0) AS bev_amt,
                ISNULL(BillVat,0) AS vat_amt,
                ISNULL(BillDiscount,0) AS discount_amt,
                ISNULL(BillComp,0)    AS compl_amt,
                ISNULL(BillCashAmt,0) AS cash_amt,
                ISNULL(BillCrAmt,0)   AS credit_amt,
                BillGuestName     AS customer,
                BillCustomerName  AS customer_name,
                BillPmode         AS payment_mode,
                BillReceiptNo     AS cr_no
            FROM Bills
            WHERE CAST(BillDt AS DATE) >= %s
              AND CAST(BillDt AS DATE) <= %s
              {code_filter}
              AND (BillVoid IS NULL OR BillVoid = 0)
            ORDER BY BillDt ASC, BillNo ASC
        """, (date_from, date_to))
        rows = cur.fetchall()
        conn.close()

        result = []
        for row in rows:
            pmode = str(row['payment_mode'] or 0)
            pay_label = {
                '0': 'Room/Charge', '1': 'Cash',
                '2': 'Cash',        '3': 'Complimentary',
            }.get(pmode, f'Mode{pmode}')

            result.append({
                'bill_date':    row['bill_date'].strftime('%Y-%m-%d') if row['bill_date'] else None,
                'bill_time':    row['bill_date'].strftime('%H:%M')    if row['bill_date'] else None,
                'outlet':       'Restaurant' if row['bill_code'] == 'RES' else 'Bar',
                'to_ref':       (row['to_ref'] or '').strip(),
                'bill_no':      (row['bill_no'] or '').strip() or None,
                'amount':       round(float(row['amount']       or 0), 2),
                'food_amt':     round(float(row['food_amt']     or 0), 2),
                'bev_amt':      round(float(row['bev_amt']      or 0), 2),
                'vat_amt':      round(float(row['vat_amt']      or 0), 2),
                'discount_amt': round(float(row['discount_amt'] or 0), 2),
                'compl_amt':    round(float(row['compl_amt']    or 0), 2),
                'cash_amt':     round(float(row['cash_amt']     or 0), 2),
                'credit_amt':   round(float(row['credit_amt']   or 0), 2),
                'customer':     (row['customer_name'] or row['customer'] or '').strip(),
                'payment_mode': pmode,
                'pay_label':    pay_label,
                'cr_no':        row['cr_no'],
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/stats', methods=['GET','OPTIONS'])
@api_key_required
def v2_stats():
    """Dashboard stats — occupancy, revenue, arrivals for a given date."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        date_param = request.args.get('date')
        selected   = datetime.strptime(date_param, '%Y-%m-%d') if date_param else datetime.now()

        conn = get_db()
        cur  = conn.cursor(as_dict=True)

        # Live room rack counts
        cur.execute("SELECT RmAvl, COUNT(*) as cnt FROM Rooms GROUP BY RmAvl")
        rack = {r['RmAvl']: r['cnt'] for r in cur.fetchall()}

        # Today arrivals from reservations
        cur.execute("""
            SELECT COUNT(*) as arr FROM FRSVDet
            WHERE CAST(RsvDetArrDt AS DATE) = %s AND RsvDetCheckIn = 0 AND RsvDetStat != 'X'
        """, (selected.date(),))
        arrivals = (cur.fetchone() or {}).get('arr', 0)

        # Today departures
        cur.execute("""
            SELECT COUNT(*) as dep FROM FRSVDet
            WHERE CAST(RsvDetDepDt AS DATE) = %s AND RsvDetStat != 'X'
        """, (selected.date(),))
        departures = (cur.fetchone() or {}).get('dep', 0)

        # Revenue from Bills
        cur.execute("""
            SELECT
              SUM(CASE WHEN BillCode='RC' THEN ISNULL(BillRC,0)*ISNULL(BillFxRate,1) ELSE 0 END) as room_rev,
              SUM(CASE WHEN BillCode='RC' THEN ISNULL(BillPlanAmt,0)*ISNULL(BillFxRate,1) ELSE 0 END) as plan_rev,
              SUM(CASE WHEN BillCode='RES' THEN ISNULL(BillTot,0) ELSE 0 END) as food_rev,
              SUM(CASE WHEN BillCode='BAR' THEN ISNULL(BillTot,0) ELSE 0 END) as bev_rev,
              SUM(CASE WHEN BillCode='SPA' THEN ISNULL(BillTot,0) ELSE 0 END) as spa_rev,
              SUM(CASE WHEN BillCode='LAU' THEN ISNULL(BillTot,0) ELSE 0 END) as lau_rev,
              SUM(CASE WHEN BillCode='MBAR' THEN ISNULL(BillTot,0) ELSE 0 END) as mbar_rev,
              SUM(CASE WHEN BillPmode=1 THEN ISNULL(BillTot,0) ELSE 0 END) as cash_received
            FROM Bills
            WHERE CAST(BillDt AS DATE) = %s
              AND (BillVoid IS NULL OR BillVoid = 0)
        """, (selected.date(),))
        rev = cur.fetchone() or {}

        # In-house count
        cur.execute("SELECT COUNT(*) as cnt FROM Guests WHERE GGone = 0")
        in_house = (cur.fetchone() or {}).get('cnt', 0)

        conn.close()

        room_rev  = fv(rev.get('room_rev'))
        plan_rev  = fv(rev.get('plan_rev'))
        food_rev  = fv(rev.get('food_rev'))
        bev_rev   = fv(rev.get('bev_rev'))
        spa_rev   = fv(rev.get('spa_rev'))
        lau_rev   = fv(rev.get('lau_rev'))
        mbar_rev  = fv(rev.get('mbar_rev'))
        total_rev = room_rev + plan_rev + food_rev + bev_rev + spa_rev + lau_rev + mbar_rev

        occupied  = rack.get(0, 0)
        occ_pct   = round(occupied / TOTAL_ROOMS * 100, 1) if TOTAL_ROOMS else 0

        return add_cors(jsonify({
            'date':        selected.strftime('%Y-%m-%d'),
            'total_rooms': TOTAL_ROOMS,
            'rack': {
                'occupied':      occupied,
                'vacant':        rack.get(1, 0),
                'dirty':         rack.get(2, 0),
                'out_of_order':  rack.get(3, 0) + rack.get(6, 0),
                'inspect':       rack.get(4, 0),
                'departure':     rack.get(5, 0),
                'house_use':     rack.get(7, 0),
            },
            'occupancy_pct': occ_pct,
            'in_house':      int(in_house),
            'arrivals':      int(arrivals),
            'departures':    int(departures),
            'revenue': {
                'room':          round(room_rev),
                'meal_plan':     round(plan_rev),
                'food':          round(food_rev),
                'beverage':      round(bev_rev),
                'spa_transport': round(spa_rev),
                'laundry':       round(lau_rev),
                'mini_bar':      round(mbar_rev),
                'total':         round(total_rev),
                'cash_received': round(fv(rev.get('cash_received'))),
            },
        }))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/agents', methods=['GET','OPTIONS'])
@api_key_required
def v2_agents():
    """Agent / sundry debtor list with outstanding balances."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                a.AgtId          AS agent_id,
                a.AgtComp        AS company,
                a.AgtName        AS contact_name,
                a.AgtCode        AS code,
                a.AgtEmail       AS email,
                a.AgtTel1        AS phone,
                a.AgtMobile      AS mobile,
                a.AgtCreditLimit AS credit_limit,
                a.AgtCom         AS commission_pct,
                a.AgtFDBal       AS fd_balance,
                a.AgtFBBal       AS fb_balance,
                a.AgtInactive    AS inactive
            FROM Agents a
            WHERE ISNULL(a.AgtInactive, 0) = 0
            ORDER BY a.AgtComp
        """)
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'agent_id':       row['agent_id'],
                'company':        (row['company'] or '').strip(),
                'contact_name':   (row['contact_name'] or '').strip(),
                'code':           row['code'] or '',
                'email':          row['email'] or '',
                'phone':          row['phone'] or '',
                'mobile':         row['mobile'] or '',
                'credit_limit':   float(row['credit_limit'] or 0),
                'commission_pct': float(row['commission_pct'] or 0),
                'fd_balance':     float(row['fd_balance'] or 0),
                'fb_balance':     float(row['fb_balance'] or 0),
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/lost-found', methods=['GET','OPTIONS'])
@api_key_required
def v2_lost_found():
    """Lost and found items."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT
                lf.LFId            AS id,
                lf.LFLoc           AS location,
                lf.LFDate          AS date_found,
                lf.LFComment       AS description,
                lf.LFStatus        AS status,
                lf.LFHandOverDept  AS dept_id,
                u1.UserName        AS found_by,
                u2.UserName        AS handed_to
            FROM LostFound lf
            LEFT JOIN USERS u1 ON u1.UserId = lf.LFBy
            LEFT JOIN USERS u2 ON u2.UserId = lf.LFHandOverTo
            ORDER BY lf.LFDate DESC
        """)
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            status_map = {0: 'Found', 1: 'Handed Over', 2: 'Claimed', 3: 'Disposed'}
            result.append({
                'id':          row['id'],
                'location':    row['location'] or '',
                'date_found':  row['date_found'].strftime('%Y-%m-%d %H:%M') if row['date_found'] else None,
                'description': row['description'] or '',
                'status':      status_map.get(row['status'], 'Unknown'),
                'found_by':    row['found_by'] or '',
                'handed_to':   row['handed_to'] or '',
            })
        return add_cors(jsonify(result))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


@app.route('/api/v2/room-types', methods=['GET','OPTIONS'])
@api_key_required
def v2_room_types():
    """Room types with rates."""
    if request.method == 'OPTIONS':
        return add_cors(jsonify({}))
    try:
        conn = get_db()
        cur  = conn.cursor(as_dict=True)
        cur.execute("""
            SELECT RmTypId, RmTyp, RmTypCode, RmTypSGL, RmTypDBL, RmTypTPL, RmCurrency
            FROM RoomType ORDER BY RmTypSeq
        """)
        rows = cur.fetchall()
        conn.close()
        return add_cors(jsonify([{
            'id':       r['RmTypId'],
            'name':     r['RmTyp'] or '',
            'code':     r['RmTypCode'] or '',
            'rate_sgl': float(r['RmTypSGL'] or 0),
            'rate_dbl': float(r['RmTypDBL'] or 0),
            'rate_tpl': float(r['RmTypTPL'] or 0),
            'currency': r['RmCurrency'] or 'NRS',
        } for r in rows]))
    except Exception as e:
        return add_cors(jsonify({'error': str(e)})), 500


if __name__ == "__main__":
    app.run(debug=True, port=5055)

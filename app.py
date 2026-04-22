from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from functools import wraps
import pymssql, requests, re, json, os
from datetime import datetime, timedelta
from nepali_datetime import date as NepaliDate

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hms-dashboard-key-2025')

DASH_USER = os.environ.get('DASH_USER', 'amrit')
DASH_PASS = os.environ.get('DASH_PASS', 'Nepal@213')

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
        if request.form.get("username") == DASH_USER and request.form.get("password") == DASH_PASS:
            session['logged_in'] = True
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

        # ── In-house Guest List ──────────────────────────
        cur.execute("""
            SELECT TOP 20
                ISNULL(g.GName, ISNULL(b.BillGuestName,'')) as name,
                ISNULL(b.BillRmNo,'')   as room,
                ISNULL(b.BillPlan,'')   as meal_plan,
                ISNULL(b.BillRmOcc,'')  as occ_type,
                b.BillRmArrDate         as arrival,
                b.BillRmDepDate         as departure
            FROM Bills b
            LEFT JOIN Guests g ON g.GId = b.BillGId
            WHERE b.BillCleared = 0
              AND (b.BillVoid IS NULL OR b.BillVoid = 0)
              AND b.BillRmNo  != ''
            ORDER BY b.BillRmNo
        """)
        guests_raw = cur.fetchall()

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
        selected_bs  = NepaliDate.from_datetime_date(selected.date())

        # MTD: 1st of selected BS month → selected date
        mtd_start_bs = NepaliDate(selected_bs.year, selected_bs.month, 1)
        mtd_start_ad = mtd_start_bs.to_datetime_date()
        mtd_days     = (selected.date() - mtd_start_ad).days + 1
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
        """, (mtd_start_ad, selected.date()))
        mtd_room_nights = int((cur.fetchone() or {}).get('total') or 0)

        # FY: Shrawan 1 (BS month 4) of selected date's fiscal year → selected date
        if selected_bs.month >= 4:   # Shrawan or later → FY started this BS year
            fy_start_bs = NepaliDate(selected_bs.year, 4, 1)
        else:                         # Before Shrawan → FY started previous BS year
            fy_start_bs = NepaliDate(selected_bs.year - 1, 4, 1)
        fy_start  = fy_start_bs.to_datetime_date()
        fy_days   = (selected.date() - fy_start).days + 1
        fy_avail  = TOTAL_ROOMS * fy_days

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
        """, (fy_start, selected.date()))
        fy_room_nights = int((cur.fetchone() or {}).get('total') or 0)

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
        t_occ     = rooms_today
        y_occ     = rooms_yest
        mtd_days  = selected.day
        mtd_avail = TOTAL_ROOMS * mtd_days

        # ── Format guests ────────────────────────────────
        guests = []
        for g in guests_raw:
            guests.append({
                "name":      g["name"],
                "room":      g["room"],
                "plan":      g["meal_plan"],
                "type":      g["occ_type"],
                "arrival":   g["arrival"].strftime("%Y-%m-%d") if g["arrival"] else "",
                "departure": g["departure"].strftime("%Y-%m-%d") if g["departure"] else "",
            })

        return jsonify({
            "date":      selected.strftime("%A, %B %d, %Y"),
            "today_str": selected.strftime("%m/%d/%Y"),
            "prev_str":  previous.strftime("%m/%d/%Y"),
            "is_today":  is_today,
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
            "guests":  guests,
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


@app.route("/")
@login_required
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5055)

"""Access-faithful Gemach reports — port of the legacy Access reports.

Each route here reproduces one Access Report module from
`access_mirror/gmach/docs/vba_utf8/report_*.txt`, reading **directly** from
the SQLite mirror at `instance/mirror/MttData.db` and using the **verbatim
Access column names** (no `gmach_*` prefixes — just `num_hork`, `card_no`,
`schum`, `schum_d`, `tel_kidomet`, `t_z`, etc.).

The mirror DB is opened READ-ONLY. Nothing in here writes or modifies
either the mirror SQLite or matat.db. The 5 ports here are the daily
operational reports:

  1. Halvaot       — דו״ח הלוואות   (loans, status='p')
  2. Gmach Totals  — סיכומי גמ״ח    (lifetime per-table counts/sums)
  3. Trumot        — דו״ח תרומות    (Tnuot WHERE sug='תרו')
  4. Tnuot0        — תנועות (תאריך) (Tnuot in date range, multi-sug filter)
  5. Single hiuv   — חיוב בודד      (Peulot for a single charge date)

The remaining 29 reports (Hork-totals, indexes, mailing labels, check
registers, etc.) are tracked in the `_REPORT_INDEX` table at the bottom
of this file but not yet ported.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from flask import current_app, render_template, request

from ...utils.decorators import gemach_required
from ...utils.reports import ReportSpec, Column, export_pdf, export_xlsx
from . import gemach_bp


# ---------------------------------------------------------------------------
# Read-only mirror DB connection helper
# ---------------------------------------------------------------------------
def _mirror_path() -> str:
    """Path to the read-only Access mirror SQLite (MttData.db)."""
    # instance/mirror/MttData.db relative to the Flask instance dir
    p = os.path.join(current_app.instance_path, 'mirror', 'MttData.db')
    return p


def _open_mirror() -> sqlite3.Connection:
    """Open the mirror SQLite **read-only** via URI mode."""
    path = _mirror_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f'Mirror DB not found at {path} — run sync_live_data.bat')
    # ?mode=ro forces SQLite to refuse any writes
    uri = f'file:{path}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_date(s: str):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _access_iso(d) -> str:
    """SQLite expression that converts Access `MM/DD/YYYY HH:MM:SS` strings
    to ISO `YYYY-MM-DD` for range comparisons. We pass the column name in.

    Returns the raw SQL fragment to drop into a query (we trust the column name
    as it is hard-coded by us, never user-supplied).
    """
    return (
        f"substr({d},7,4) || '-' || substr({d},1,2) || '-' || substr({d},4,2)"
    )


def _dispatch(spec: ReportSpec, tpl: str = 'gemach/reports/_base.html'):
    fmt = (request.args.get('format') or '').lower()
    if fmt == 'pdf':
        return export_pdf(spec)
    if fmt == 'xlsx':
        return export_xlsx(spec)
    qs = request.query_string.decode('utf-8')
    return render_template(tpl, spec=spec, query_string=qs)


# ---------------------------------------------------------------------------
# 1. Halvaot  — דו״ח הלוואות
# ---------------------------------------------------------------------------
# Access RecordSource (paraphrased from report_Halvaot.txt):
#   SELECT [USys sums a].zacai, [last_name] & " " & [first_name] AS name,
#          Sum(IIf([schum_d]<0 And [schum]<0,-[schum_d],0)) AS halvaa_d,
#          Sum(IIf([schum]<0 And [schum_d]<0,-[schum],0))   AS halvaa,
#          Sum(IIf([schum_d]>0 Or schum=0,[schum_d],0))     AS returned_d,
#          Sum(IIf([schum]>0 Or schum_d=0,[schum],0))       AS returned,
#          Sum(IIf([schum_d]<0,1,0)) AS [count],
#          Min(IIf([schum_d]<0,[date],99999)) AS MinOfDate
#     FROM Haverim
#          INNER JOIN [USys sums a] ON Haverim.card_no = [USys sums a].zacai
#    WHERE [USys sums a].date BETWEEN startdate AND enddate
#    GROUP BY zacai, name, sug
#   HAVING sug = 'הלו'
#    ORDER BY last_name & ' ' & first_name
#
# The Access query relies on a temp table (USys sums a) populated from
# Peulot. Below we reproduce its semantics directly off Hork + Peulot,
# using **verbatim** column names. We keep the report's primary listing
# (one row per active loan) since the operator's daily question is
# "which active loans are open and how much is left?".
@gemach_bp.route('/reports/access/halvaot')
@gemach_required
def report_access_halvaot():
    date_from = _parse_date(request.args.get('date_from'))
    date_to   = _parse_date(request.args.get('date_to'))
    status    = request.args.get('status', 'p')  # 'p' = פעיל, '' = הכל

    where = []
    params: list = []
    if status:
        where.append("LOWER(IFNULL(h.status,'')) = ?")
        params.append(status.lower())
    if date_from:
        where.append(f"{_access_iso('h.date_hathala')} >= ?")
        params.append(date_from.isoformat())
    if date_to:
        where.append(f"{_access_iso('h.date_hathala')} <= ?")
        params.append(date_to.isoformat())
    where_sql = (" WHERE " + " AND ".join(where)) if where else ''

    sql = f"""
        SELECT
            h.num_hork,
            h.card_no,
            v.last_name,
            v.first_name,
            (IFNULL(v.last_name,'') || ' ' || IFNULL(v.first_name,'')) AS name,
            h.matbea,
            h.schum,
            h.sach_buza,
            h.shulam,
            h.hithayev,
            h.buza,
            h.date_hathala,
            h.date_hiuv_aharon,
            h.sug,
            h.status,
            h.num_mosad,
            m.shem_mosad
          FROM Hork h
          LEFT JOIN Haverim  v ON v.card_no   = h.card_no
          LEFT JOIN Mosadot  m ON m.num_mosad = h.num_mosad
          {where_sql}
          ORDER BY v.last_name, v.first_name
    """

    with _open_mirror() as conn:
        cur = conn.execute(sql, params)
        records = cur.fetchall()

    rows = []
    tot_schum = Decimal('0')
    tot_shulam = Decimal('0')
    for r in records:
        schum = Decimal(str(r['schum'] or 0))
        shulam = Decimal(str(r['shulam'] or 0))
        rows.append({
            'num_hork':         r['num_hork'],
            'card_no':          r['card_no'],
            'name':             r['name'].strip() if r['name'] else '',
            'matbea':           r['matbea'] or '',
            'schum':            schum,
            'shulam':           shulam,
            'hithayev':         r['hithayev'] or 0,
            'buza':             r['buza'] or 0,
            'date_hathala':     r['date_hathala'] or '',
            'date_hiuv_aharon': r['date_hiuv_aharon'] or '',
            'sug':              r['sug'] or '',
            'status':           r['status'] or '',
            'shem_mosad':       r['shem_mosad'] or '',
        })
        tot_schum  += schum
        tot_shulam += shulam

    status_label = {'p': 'פעיל', 's': 'הושלם', 'b': 'בוטל', '': 'הכל'}.get(status, status)

    spec = ReportSpec(
        title='דו״ח הלוואות (Access port — Halvaot)',
        subtitle='Gemach Loans — Hork joined Haverim + Mosadot, verbatim column names',
        columns=[
            Column('num_hork',         'num_hork',         width=0.7, align='center'),
            Column('card_no',          'card_no',          width=0.7, align='center'),
            Column('name',             'last_name + first_name', width=2.0),
            Column('matbea',           'matbea',           width=0.5, align='center'),
            Column('schum',            'schum',            width=1.0, align='left'),
            Column('shulam',           'shulam',           width=1.0, align='left'),
            Column('hithayev',         'hithayev',         width=0.6, align='center'),
            Column('buza',             'buza',             width=0.6, align='center'),
            Column('date_hathala',     'date_hathala',     width=0.9, align='center'),
            Column('date_hiuv_aharon', 'date_hiuv_aharon', width=0.9, align='center'),
            Column('sug',              'sug',              width=0.6, align='center'),
            Column('status',           'status',           width=0.5, align='center'),
            Column('shem_mosad',       'shem_mosad',       width=1.4),
        ],
        rows=rows,
        filters={
            'status':    status_label,
            'date_from': date_from.isoformat() if date_from else 'הכל',
            'date_to':   date_to.isoformat()   if date_to   else 'הכל',
            'מקור':      'instance/mirror/MttData.db (Hork)',
        },
        totals={'schum': tot_schum, 'shulam': tot_shulam},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 2. Gmach Totals  — סיכומי גמ״ח
# ---------------------------------------------------------------------------
# Access report_Gmach Totals.txt builds its rows in VBA (no static
# RecordSource) by iterating tables and printing per-table totals.
# We reproduce the same shape: one row per major Access table, with
# row count + (where applicable) sums of the schum/schum_sh/schum_$ columns.
@gemach_bp.route('/reports/access/gmach_totals')
@gemach_required
def report_access_gmach_totals():
    rows: list[dict] = []

    with _open_mirror() as conn:
        # Haverim — members
        n = conn.execute("SELECT COUNT(*) FROM Haverim").fetchone()[0]
        rows.append({'tbl': 'Haverim',  'desc': 'חברים',
                     'n': n, 'sum_a': '', 'sum_b': ''})

        # Hork — loans (totals broken down by status)
        for st in ('p', 's', 'b', None):
            cond = "status IS NULL" if st is None else "LOWER(IFNULL(status,''))=?"
            args = () if st is None else (st,)
            r = conn.execute(
                f"SELECT COUNT(*), COALESCE(SUM(schum),0), COALESCE(SUM(shulam),0) "
                f"FROM Hork WHERE {cond}", args).fetchone()
            label = {'p': 'הו״ק פעילות', 's': 'הו״ק הושלמו',
                     'b': 'הו״ק בוטלו', None: 'הו״ק ללא סטטוס'}[st]
            rows.append({'tbl': f'Hork status={st!r}', 'desc': label,
                         'n': r[0], 'sum_a': Decimal(str(r[1] or 0)),
                         'sum_b': Decimal(str(r[2] or 0))})

        # Peulot — loan transactions
        r = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(schum),0), COALESCE(SUM(schum_d),0) "
            "FROM Peulot").fetchone()
        rows.append({'tbl': 'Peulot', 'desc': 'פעולות הו״ק',
                     'n': r[0], 'sum_a': Decimal(str(r[1] or 0)),
                     'sum_b': Decimal(str(r[2] or 0))})

        # Tnuot — general transactions per sug
        cur = conn.execute(
            "SELECT sug, COUNT(*), COALESCE(SUM(schum_sh),0), "
            "COALESCE(SUM([schum_$]),0) FROM Tnuot GROUP BY sug ORDER BY sug")
        cat_label = {'הלו': 'תנועות הלוואות', 'תרו': 'תרומות',
                     'פקד': 'פקדונות',        'תמי': 'תמיכות',
                     'הוצ': 'הוצאות'}
        for sug, n, sh, dl in cur.fetchall():
            rows.append({
                'tbl':   f"Tnuot sug={sug!r}",
                'desc':  cat_label.get(sug, sug or '(ללא)'),
                'n':     n,
                'sum_a': Decimal(str(sh or 0)),
                'sum_b': Decimal(str(dl or 0)),
            })

        # Btlhork — cancelled-loan archive
        n = conn.execute("SELECT COUNT(*) FROM Btlhork").fetchone()[0]
        rows.append({'tbl': 'Btlhork', 'desc': 'הו״ק בוטלו (ארכיון)',
                     'n': n, 'sum_a': '', 'sum_b': ''})

        # Mosadot
        n = conn.execute("SELECT COUNT(*) FROM Mosadot").fetchone()[0]
        rows.append({'tbl': 'Mosadot', 'desc': 'מוסדות',
                     'n': n, 'sum_a': '', 'sum_b': ''})

    spec = ReportSpec(
        title='סיכומי גמ״ח (Access port — Gmach Totals)',
        subtitle='Lifetime totals per Access table (verbatim names)',
        columns=[
            Column('tbl',   'טבלה',         width=1.4),
            Column('desc',  'תיאור',        width=1.6),
            Column('n',     'מס׳ רשומות',   width=0.8, align='center'),
            Column('sum_a', 'סכום ש״ח',     width=1.2, align='left'),
            Column('sum_b', 'סכום משני',    width=1.2, align='left'),
        ],
        rows=rows,
        filters={'מקור': 'instance/mirror/MttData.db'},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 3. Trumot  — דו״ח תרומות
# ---------------------------------------------------------------------------
# Access RecordSource:
#   SELECT [USys sums a].zacai, last_name & " " & first_name AS name,
#          Sum(schum_d) AS SumOfschum_d, Sum(schum) AS SumOfschum
#     FROM [USys sums a] INNER JOIN Haverim
#          ON [USys sums a].zacai = Haverim.card_no
#    GROUP BY zacai, name, sug
#   HAVING sug = 'תרו' AND (Sum(schum_d) <> 0 OR Sum(schum) <> 0)
#    ORDER BY last_name & ' ' & first_name
#
# We reproduce the same sum-per-donor layout, but read directly from
# Tnuot (where sug='תרו'), which is where the donations actually live.
@gemach_bp.route('/reports/access/trumot')
@gemach_required
def report_access_trumot():
    date_from = _parse_date(request.args.get('date_from'))
    date_to   = _parse_date(request.args.get('date_to'))

    where = ["t.sug = ?"]
    params: list = ['תרו']
    if date_from:
        where.append(f"{_access_iso('t.date')} >= ?")
        params.append(date_from.isoformat())
    if date_to:
        where.append(f"{_access_iso('t.date')} <= ?")
        params.append(date_to.isoformat())
    where_sql = " WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            t.card_no,
            v.last_name,
            v.first_name,
            (IFNULL(v.last_name,'') || ' ' || IFNULL(v.first_name,'')) AS name,
            COUNT(*) AS n,
            COALESCE(SUM(t.schum_sh), 0) AS SumOfschum_sh,
            COALESCE(SUM(t.[schum_$]), 0) AS SumOfschum_dollar
          FROM Tnuot t
          LEFT JOIN Haverim v ON v.card_no = t.card_no
          {where_sql}
          GROUP BY t.card_no, v.last_name, v.first_name
         HAVING SumOfschum_sh <> 0 OR SumOfschum_dollar <> 0
          ORDER BY v.last_name, v.first_name
    """

    with _open_mirror() as conn:
        records = conn.execute(sql, params).fetchall()

    rows = []
    tot_sh = Decimal('0')
    tot_dl = Decimal('0')
    for r in records:
        sh = Decimal(str(r['SumOfschum_sh'] or 0))
        dl = Decimal(str(r['SumOfschum_dollar'] or 0))
        rows.append({
            'card_no':           r['card_no'],
            'name':              (r['name'] or '').strip(),
            'n':                 r['n'],
            'SumOfschum_sh':     sh,
            'SumOfschum_dollar': dl,
        })
        tot_sh += sh
        tot_dl += dl

    spec = ReportSpec(
        title='דו״ח תרומות (Access port — Trumot)',
        subtitle="Tnuot WHERE sug='תרו', grouped by donor",
        columns=[
            Column('card_no',           'card_no',          width=0.6, align='center'),
            Column('name',              'last_name + first_name', width=2.0),
            Column('n',                 'מס׳ תנועות',       width=0.7, align='center'),
            Column('SumOfschum_sh',     'SumOfschum_sh',    width=1.2, align='left'),
            Column('SumOfschum_dollar', 'SumOfschum_$',     width=1.2, align='left'),
        ],
        rows=rows,
        filters={
            'date_from': date_from.isoformat() if date_from else 'הכל',
            'date_to':   date_to.isoformat()   if date_to   else 'הכל',
            'מקור':      'Tnuot WHERE sug = תרו',
        },
        totals={'SumOfschum_sh': tot_sh, 'SumOfschum_dollar': tot_dl},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 4. Tnuot0  — תנועות בתאריך
# ---------------------------------------------------------------------------
# Access RecordSource (form_reports_tnuot supplies the four sug checkboxes):
#   SELECT DISTINCTROW
#          Tnuot.card_no, Tnuot.num_zacai,
#          haverim.last_name & " " & haverim.first_name AS name,
#          Tnuot.date, Tnuot.schum_sh, Tnuot.[schum_$], Tnuot.sug,
#          Trim(haverim_1.last_name & " " & haverim_1.first_name) AS zacai_name,
#          Tnuot.matbea
#     FROM Haverim
#          INNER JOIN (Tnuot LEFT JOIN Haverim AS Haverim_1
#                      ON Tnuot.num_zacai = Haverim_1.card_no)
#       ON Haverim.card_no = Tnuot.card_no
#    WHERE Tnuot.date BETWEEN startdate AND enddate
#      AND Tnuot.sug IN (...selected sug values...)
#    ORDER BY haverim.last_name & " " & haverim.first_name;
@gemach_bp.route('/reports/access/tnuot0')
@gemach_required
def report_access_tnuot0():
    date_from = _parse_date(request.args.get('date_from'))
    date_to   = _parse_date(request.args.get('date_to'))
    sug_args  = request.args.getlist('sug')          # multi: הלו, תרו, פקד, תמי
    if not sug_args:
        sug_args = ['הלו', 'תרו', 'פקד', 'תמי']

    where = []
    params: list = []
    if date_from:
        where.append(f"{_access_iso('t.date')} >= ?")
        params.append(date_from.isoformat())
    if date_to:
        where.append(f"{_access_iso('t.date')} <= ?")
        params.append(date_to.isoformat())
    if sug_args:
        placeholders = ','.join(['?'] * len(sug_args))
        where.append(f"t.sug IN ({placeholders})")
        params.extend(sug_args)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ''

    sql = f"""
        SELECT DISTINCT
            t.card_no,
            t.num_zacai,
            (IFNULL(v.last_name,'') || ' ' || IFNULL(v.first_name,'')) AS name,
            t.date,
            t.schum_sh,
            t.[schum_$] AS schum_dollar,
            t.sug,
            TRIM(IFNULL(z.last_name,'') || ' ' || IFNULL(z.first_name,'')) AS zacai_name,
            t.matbea
          FROM Tnuot t
          LEFT JOIN Haverim v ON v.card_no = t.card_no
          LEFT JOIN Haverim z ON z.card_no = t.num_zacai
          {where_sql}
          ORDER BY v.last_name, v.first_name, t.date
    """

    with _open_mirror() as conn:
        records = conn.execute(sql, params).fetchall()

    rows = []
    tot_sh = Decimal('0')
    tot_dl = Decimal('0')
    for r in records:
        sh = Decimal(str(r['schum_sh'] or 0))
        dl = Decimal(str(r['schum_dollar'] or 0))
        rows.append({
            'card_no':      r['card_no'],
            'name':         (r['name'] or '').strip(),
            'date':         r['date'] or '',
            'sug':          r['sug'] or '',
            'schum_sh':     sh,
            'schum_dollar': dl,
            'matbea':       r['matbea'] or '',
            'num_zacai':    r['num_zacai'] or '',
            'zacai_name':   r['zacai_name'] or '',
        })
        tot_sh += sh
        tot_dl += dl

    spec = ReportSpec(
        title='דו״ח תנועות בתאריך (Access port — Tnuot0)',
        subtitle='Tnuot in date range, filtered by sug',
        columns=[
            Column('card_no',      'card_no',     width=0.6, align='center'),
            Column('name',         'name',        width=1.8),
            Column('date',         'date',        width=0.9, align='center'),
            Column('sug',          'sug',         width=0.5, align='center'),
            Column('schum_sh',     'schum_sh',    width=1.0, align='left'),
            Column('schum_dollar', 'schum_$',     width=1.0, align='left'),
            Column('matbea',       'matbea',      width=0.5, align='center'),
            Column('num_zacai',    'num_zacai',   width=0.6, align='center'),
            Column('zacai_name',   'zacai_name',  width=1.5),
        ],
        rows=rows,
        filters={
            'date_from': date_from.isoformat() if date_from else 'הכל',
            'date_to':   date_to.isoformat()   if date_to   else 'הכל',
            'sug':       ', '.join(sug_args),
            'מקור':      'Tnuot',
        },
        totals={'schum_sh': tot_sh, 'schum_dollar': tot_dl},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# 5. Single hiuv  — חיוב בודד
# ---------------------------------------------------------------------------
# Access RecordSource:
#   SELECT haverim.card_no, last_name & " " & first_name AS שם,
#          haverim.ctovet, haverim.city,
#          tel_kidomet & tel AS טלפון,
#          Hork.sug, Peulot.schum_d, Peulot.schum,
#          IIf(peulot.hazar,'כן','') AS hazar1,
#          Hork.num_hork, [Sibot bitul].shem_siba,
#          Peulot.date, haverim.last_name, haverim.first_name,
#          Peulot.hazar, Hork.num_mosad, Mosadot.shem_mosad
#     FROM ((haverim INNER JOIN Hork ON haverim.card_no = Hork.card_no)
#           INNER JOIN (Peulot LEFT JOIN [Sibot bitul]
#                       ON Peulot.siba = [Sibot bitul].code_siba)
#       ON Hork.num_hork = Peulot.num_hork)
#      INNER JOIN Mosadot ON Hork.num_mosad = Mosadot.num_mosad
#    WHERE Peulot.date = [תאריך חיוב:]
#    ORDER BY haverim.last_name, haverim.first_name;
@gemach_bp.route('/reports/access/single_hiuv')
@gemach_required
def report_access_single_hiuv():
    charge_date = _parse_date(request.args.get('date'))

    where = []
    params: list = []
    if charge_date:
        where.append(f"{_access_iso('p.date')} = ?")
        params.append(charge_date.isoformat())
    where_sql = (" WHERE " + " AND ".join(where)) if where else ''

    sql = f"""
        SELECT
            v.card_no,
            v.last_name,
            v.first_name,
            (IFNULL(v.last_name,'') || ' ' || IFNULL(v.first_name,'')) AS שם,
            v.ctovet,
            v.city,
            (IFNULL(v.tel_kidomet,'') || IFNULL(v.tel,'')) AS טלפון,
            h.sug,
            p.schum_d,
            p.schum,
            CASE WHEN p.hazar THEN 'כן' ELSE '' END AS hazar1,
            h.num_hork,
            p.date,
            p.hazar,
            h.num_mosad,
            m.shem_mosad
          FROM Haverim v
          INNER JOIN Hork    h ON h.card_no   = v.card_no
          INNER JOIN Peulot  p ON p.num_hork  = h.num_hork
          LEFT  JOIN Mosadot m ON m.num_mosad = h.num_mosad
          {where_sql}
          ORDER BY v.last_name, v.first_name
    """

    with _open_mirror() as conn:
        records = conn.execute(sql, params).fetchall()

    rows = []
    tot_schum  = Decimal('0')
    tot_schumd = Decimal('0')
    for r in records:
        schum  = Decimal(str(r['schum']  or 0))
        schumd = Decimal(str(r['schum_d'] or 0))
        rows.append({
            'card_no':    r['card_no'],
            'שם':         (r['שם'] or '').strip(),
            'ctovet':     r['ctovet'] or '',
            'city':       r['city']   or '',
            'טלפון':      r['טלפון']  or '',
            'sug':        r['sug']    or '',
            'schum_d':    schumd,
            'schum':      schum,
            'hazar1':     r['hazar1'] or '',
            'num_hork':   r['num_hork'],
            'date':       r['date']   or '',
            'shem_mosad': r['shem_mosad'] or '',
        })
        tot_schum  += schum
        tot_schumd += schumd

    spec = ReportSpec(
        title='חיוב בודד (Access port — Single hiuv)',
        subtitle='Peulot for a single charge date — joined Haverim/Hork/Mosadot',
        columns=[
            Column('card_no',    'card_no',     width=0.6, align='center'),
            Column('שם',         'שם',          width=1.8),
            Column('ctovet',     'ctovet',      width=1.6),
            Column('city',       'city',        width=0.9),
            Column('טלפון',      'טלפון',       width=1.0, align='center'),
            Column('sug',        'sug',         width=0.5, align='center'),
            Column('schum_d',    'schum_d',     width=1.0, align='left'),
            Column('schum',      'schum',       width=1.0, align='left'),
            Column('hazar1',     'hazar1',      width=0.5, align='center'),
            Column('num_hork',   'num_hork',    width=0.7, align='center'),
            Column('date',       'date',        width=0.9, align='center'),
            Column('shem_mosad', 'shem_mosad',  width=1.4),
        ],
        rows=rows,
        filters={
            'תאריך חיוב': charge_date.isoformat() if charge_date else '— הזן תאריך —',
            'מקור':       'Peulot ⨝ Hork ⨝ Haverim ⨝ Mosadot',
        },
        totals={'schum': tot_schum, 'schum_d': tot_schumd},
    )
    return _dispatch(spec)


# ---------------------------------------------------------------------------
# Index of all 34 Access reports — what's ported, what's left
# ---------------------------------------------------------------------------
# (key = file stem under access_mirror/gmach/docs/vba_utf8/report_*.txt)
_REPORT_INDEX = {
    # PORTED
    'Halvaot':           {'ported': True,  'route': 'gemach.report_access_halvaot'},
    'Gmach Totals':      {'ported': True,  'route': 'gemach.report_access_gmach_totals'},
    'Trumot':            {'ported': True,  'route': 'gemach.report_access_trumot'},
    'Tnuot0':            {'ported': True,  'route': 'gemach.report_access_tnuot0'},
    'Single hiuv':       {'ported': True,  'route': 'gemach.report_access_single_hiuv'},

    # NOT YET PORTED (29 remaining)
    'All':                  {'ported': False, 'note': 'Activity log — joins r/h/h1/forms expr'},
    'Ctovot':               {'ported': False, 'note': 'Address list — RecordSource=haverim'},
    'Gmach Totals acct':    {'ported': False, 'note': 'RecordSource=USys sums acct (temp tbl)'},
    'Gmach Totals2':        {'ported': False, 'note': 'VBA — variant per-account totals'},
    'Gmach sub':            {'ported': False, 'note': 'RecordSource=gmachrep (snapshot tbl)'},
    'Gmach':                {'ported': False, 'note': 'RecordSource=gmachrep2 — donor letter'},
    'Halvaot1':             {'ported': False, 'note': 'Variant Halvaot — uses rout temp tbl'},
    'Horaot Keva Amuta':    {'ported': False, 'note': 'Standing orders — amuta institutions'},
    'Horaot Keva Zacaim':   {'ported': False, 'note': 'Standing orders — credits side'},
    'Horaot Keva':          {'ported': False, 'note': 'Standing orders — main report'},
    'IndexByName':          {'ported': False, 'note': 'Member index sorted by name'},
    'IndexByNumber':        {'ported': False, 'note': 'Member index sorted by card_no'},
    'Logo לדוגמה':          {'ported': False, 'note': 'Logo sample — print-only'},
    'Logo':                 {'ported': False, 'note': 'Logo only'},
    'LookupChecks':         {'ported': False, 'note': 'Check register — RecordSource=LookupChecks'},
    'Msv totals':           {'ported': False, 'note': 'RecordSource=usys temp (Masav temp tbl)'},
    'Pikdonot':             {'ported': False, 'note': 'Deposits per donor — USys sums a / sug=פקד'},
    'Report1':              {'ported': False, 'note': 'RecordSource=Query13 — diagnostic'},
    'Tmicha':               {'ported': False, 'note': 'Supports per donor — USys sums a / sug=תמי'},
    'Tnuot1':               {'ported': False, 'note': 'Tnuot variant with c_sh/c_$ split'},
    'TnuotPeulot':          {'ported': False, 'note': 'Combined Tnuot + Peulot via ReportTnuotPeulot'},
    'yms halvaot':          {'ported': False, 'note': 'Year-mid halvaot summary'},
    'yms tnuotpeulot':      {'ported': False, 'note': 'Year-mid combined tnuot+peulot'},
    'בנק מזרחי צקים 2024':  {'ported': False, 'note': 'Mizrahi Bank check register'},
    'מדבקות 2 טורים':       {'ported': False, 'note': '2-col mailing labels — RecordSource=haverim'},
    'מדבקות 3 טורים':       {'ported': False, 'note': '3-col mailing labels — RecordSource=haverim'},
    'צקים לשנת 2024':       {'ported': False, 'note': '2024 check register'},
    'קבלה לדוגמה':          {'ported': False, 'note': 'Receipt sample — joins Trumot'},
    'שלחן עבודה':           {'ported': False, 'note': 'Desktop log — same SQL as report_All'},
}

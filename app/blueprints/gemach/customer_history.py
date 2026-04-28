"""Customer-history module — verbatim Access mirror reader.

Reads directly from the read-only SQLite mirror produced by the Access-sync
process:

    C:\\matat\\instance\\mirror\\MttData.db   (gmach side: Haverim/Hork/Peulot/Tnuot)
    C:\\matat\\instance\\mirror\\ztormdata.db (ZTorm side: Tormim/Trumot/Tashlumim/Kabalot/Tnuot)

Given a Haverim.card_no (the natural Access PK on the gmach side), it returns a
unified, chronologically-sorted timeline of every relevant Access row from BOTH
mirrors. Cross-source linking is via Haverim.num_torem -> Tormim.num_torem
(NOT t_z, which is mostly empty for foreign donors).

Read-only. Does not touch matat.db / SQLAlchemy / app/models. Pure sqlite3.

All Access column names are kept verbatim:
    Haverim.card_no, num_torem, t_z
    Hork.num_hork, card_no, schum, matbea, sug, status, date_hathala
    Peulot.num_hork, date, asmachta, schum, schum_d, sug, kabala
    Tnuot (gmach).card_no, date, schum_sh, schum_$, matbea, sug, ofen, kabala, num_check, num_transfer
    Tormim.num_torem
    Trumot.num_truma, num_torem, ofen, status, shulam_d, shulam_s
    Tashlumim.num_tashlum, num_truma, date, ofen, schum, matbea, num_kabala, schum_nis, mispar, asmachta
    Kabalot.num_kabala, mispar_kabala, date, matbea, sum_total, num_torem, name, canceled, ezcount_doc_num
    Tnuot (ztorm).num_tnua, num_heshbon, date, sug, schum, matbea, pratim
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any

# Paths to the two mirror DBs. Read-only.
_INSTANCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'instance', 'mirror',
)
MTT_DATA_PATH = os.path.join(_INSTANCE_DIR, 'MttData.db')
ZTORM_DATA_PATH = os.path.join(_INSTANCE_DIR, 'ztormdata.db')


def _open_mirror() -> sqlite3.Connection:
    """Open MttData.db read-only and ATTACH ztormdata.db read-only."""
    # `mode=ro` URI keeps both files immutable even if a writer tries.
    con = sqlite3.connect(f'file:{MTT_DATA_PATH}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    # Default text_factory is bytes-decoded-as-utf-8 in Python 3 sqlite3.
    # Hebrew strings come through fine.
    con.execute(f"ATTACH DATABASE 'file:{ZTORM_DATA_PATH}?mode=ro' AS ztorm")
    return con


def _parse_date(s: Any):
    """Access stores dates as 'MM/DD/YYYY 00:00:00' or 'MM/DD/YYYY HH:MM:SS'.

    Returns a datetime, or None if unparseable. Used only for sorting/display.
    """
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        s = str(s).strip()
        # Try with time
        for fmt in ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                pass
    except Exception:
        return None
    return None


def _fmt_date(dt) -> str:
    if not dt:
        return ''
    return dt.strftime('%d/%m/%Y')


def _amount_for(matbea, schum_sh, schum_d):
    """Pick (amount, currency) given an Access (matbea/schum_sh/schum_$) tuple.

    Access uses '$' for USD and a Hebrew shekel glyph for ILS in matbea.
    """
    cur = (matbea or '').strip()
    try:
        sh = float(schum_sh) if schum_sh not in (None, '') else 0.0
    except (TypeError, ValueError):
        sh = 0.0
    try:
        usd = float(schum_d) if schum_d not in (None, '') else 0.0
    except (TypeError, ValueError):
        usd = 0.0
    if cur == '$' and usd:
        return usd, 'USD'
    if sh:
        return sh, 'ILS'
    return usd, 'USD' if usd else 'ILS'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_member_header(card_no: int) -> dict | None:
    """Return basic Haverim row for the card_no, or None."""
    con = _open_mirror()
    try:
        row = con.execute(
            "SELECT * FROM Haverim WHERE card_no = ? LIMIT 1",
            (str(card_no),),
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        con.close()


def get_history(card_no: int) -> dict:
    """Return a unified timeline + per-source row counts for `card_no`.

    Result shape:
        {
            'header': <Haverim row dict or None>,
            'num_torem': <linked Tormim id or None>,
            'counts': {'peulot': N, 'tnuot_gmach': N, 'trumot': N,
                       'tashlumim': N, 'kabalot': N, 'tnuot_ztorm': N},
            'events': [ {date, source, kind, amount, currency,
                         description, asmachta, ref, link}, ... ]   # sorted desc
        }
    """
    con = _open_mirror()
    try:
        header_row = con.execute(
            "SELECT * FROM Haverim WHERE card_no = ? LIMIT 1",
            (str(card_no),),
        ).fetchone()
        if not header_row:
            return {
                'header': None, 'num_torem': None,
                'counts': dict.fromkeys(
                    ['peulot', 'tnuot_gmach', 'trumot',
                     'tashlumim', 'kabalot', 'tnuot_ztorm'], 0),
                'events': [],
            }
        header = dict(header_row)
        num_torem = header.get('num_torem') or None
        # num_torem is a string in Haverim, REAL in Tormim — coerce numeric.
        num_torem_num = None
        if num_torem not in (None, ''):
            try:
                num_torem_num = float(num_torem)
            except (TypeError, ValueError):
                num_torem_num = None

        events: list[dict] = []

        # ---- 1. Peulot (gmach loan transactions, via Hork.num_hork chain) ----
        peulot_rows = con.execute("""
            SELECT p.*, h.card_no AS h_card_no
              FROM Peulot p
              JOIN Hork h ON p.num_hork = h.num_hork
             WHERE h.card_no = ?
        """, (str(card_no),)).fetchall()
        for r in peulot_rows:
            d = dict(r)
            dt = _parse_date(d.get('date'))
            try:
                amt = float(d.get('schum') or 0)
            except (TypeError, ValueError):
                amt = 0.0
            try:
                amt_d = float(d.get('schum_d') or 0)
            except (TypeError, ValueError):
                amt_d = 0.0
            currency = 'USD' if amt_d and not amt else 'ILS'
            events.append({
                'sort_dt': dt,
                'date': _fmt_date(dt),
                'source': 'gmach',
                'kind': 'peulot',
                'kind_he': 'פעולת הו"ק',
                'amount': amt or amt_d,
                'currency': currency,
                'description': f"הו״ק #{d.get('num_hork')} — {d.get('sug') or ''}",
                'asmachta': d.get('asmachta') or '',
                'ref': d.get('num_hork') or '',
                'link': '',
                'raw': d,
            })

        # ---- 2. Tnuot (gmach general transactions) ----
        tnuot_g_rows = con.execute(
            "SELECT * FROM Tnuot WHERE card_no = ?",
            (str(card_no),),
        ).fetchall()
        for r in tnuot_g_rows:
            d = dict(r)
            dt = _parse_date(d.get('date'))
            amount, currency = _amount_for(d.get('matbea'), d.get('schum_sh'), d.get('schum_$'))
            kabala_flag = (d.get('kabala') or '').strip().lower() == 'true'
            asmachta = d.get('num_check') or d.get('num_transfer') or ''
            desc_bits = []
            if d.get('sug'):
                desc_bits.append(str(d['sug']))
            if d.get('ofen'):
                desc_bits.append(str(d['ofen']))
            if d.get('pratim'):
                desc_bits.append(str(d['pratim']))
            events.append({
                'sort_dt': dt,
                'date': _fmt_date(dt),
                'source': 'gmach',
                'kind': 'tnuot',
                'kind_he': 'תנועה',
                'amount': amount,
                'currency': currency,
                'description': ' / '.join(desc_bits),
                'asmachta': asmachta,
                'ref': d.get('counter') or '',
                'link': '',
                'kabala': kabala_flag,
                'raw': d,
            })

        # If no Tormim link, we're done with the ZTorm side.
        ztorm_counts = {'trumot': 0, 'tashlumim': 0, 'kabalot': 0, 'tnuot_ztorm': 0}
        if num_torem_num is not None:
            # ---- 3. Trumot (donation pledges) ----
            trumot_rows = con.execute("""
                SELECT * FROM ztorm.Trumot WHERE num_torem = ?
            """, (num_torem_num,)).fetchall()
            ztorm_counts['trumot'] = len(trumot_rows)
            for r in trumot_rows:
                d = dict(r)
                dt = _parse_date(d.get('date_klita'))
                amt = d.get('shulam_s') or d.get('shulam_d') or d.get('tzafui_s') or d.get('tzafui_d') or 0
                currency = 'ILS' if d.get('shulam_s') or d.get('tzafui_s') else 'USD'
                events.append({
                    'sort_dt': dt,
                    'date': _fmt_date(dt),
                    'source': 'ztorm',
                    'kind': 'truma',
                    'kind_he': 'תרומה',
                    'amount': float(amt or 0),
                    'currency': currency,
                    'description': f"תרומה #{int(d.get('num_truma') or 0)} — {d.get('ofen') or ''} ({d.get('status') or ''})",
                    'asmachta': '',
                    'ref': int(d['num_truma']) if d.get('num_truma') else '',
                    'link': '',
                    'raw': d,
                })

            # ---- 4. Tashlumim (payments) — joined to Trumot for this num_torem ----
            tash_rows = con.execute("""
                SELECT t.* FROM ztorm.Tashlumim t
                  JOIN ztorm.Trumot tr ON t.num_truma = tr.num_truma
                 WHERE tr.num_torem = ?
            """, (num_torem_num,)).fetchall()
            ztorm_counts['tashlumim'] = len(tash_rows)
            for r in tash_rows:
                d = dict(r)
                dt = _parse_date(d.get('date'))
                schum = d.get('schum')
                matbea = (d.get('matbea') or '').lower()
                currency = 'USD' if matbea == 'usd' else ('ILS' if matbea in ('nis', 'ils', '') else matbea.upper())
                events.append({
                    'sort_dt': dt,
                    'date': _fmt_date(dt),
                    'source': 'ztorm',
                    'kind': 'tashlumim',
                    'kind_he': 'תשלום',
                    'amount': float(schum or 0),
                    'currency': currency,
                    'description': f"תשלום #{int(d.get('num_tashlum') or 0)} — {d.get('ofen') or ''} ({d.get('status') or ''})",
                    'asmachta': d.get('asmachta') or d.get('mispar') or '',
                    'ref': int(d['num_tashlum']) if d.get('num_tashlum') else '',
                    'link': '',
                    'kabala_no': int(d['num_kabala']) if d.get('num_kabala') else None,
                    'raw': d,
                })

            # ---- 5. Kabalot (issued tax receipts) ----
            kab_rows = con.execute("""
                SELECT * FROM ztorm.Kabalot WHERE num_torem = ?
            """, (num_torem_num,)).fetchall()
            ztorm_counts['kabalot'] = len(kab_rows)
            for r in kab_rows:
                d = dict(r)
                dt = _parse_date(d.get('date'))
                matbea = (d.get('matbea') or '').lower()
                currency = 'USD' if matbea == 'usd' else ('ILS' if matbea in ('nis', 'ils', '') else matbea.upper())
                canceled = (str(d.get('canceled') or '')).lower() == 'true'
                kind_he = 'קבלה (מבוטלת)' if canceled else 'קבלה'
                events.append({
                    'sort_dt': dt,
                    'date': _fmt_date(dt),
                    'source': 'ztorm',
                    'kind': 'kabala',
                    'kind_he': kind_he,
                    'amount': float(d.get('sum_total') or 0),
                    'currency': currency,
                    'description': (
                        f"קבלה #{int(d.get('mispar_kabala') or 0)} — {d.get('sug') or ''}"
                        + (f" — {d.get('pratim')}" if d.get('pratim') else '')
                    ),
                    'asmachta': '',
                    'ref': int(d['mispar_kabala']) if d.get('mispar_kabala') else '',
                    'link': '',
                    'canceled': canceled,
                    'ezcount_doc_num': d.get('ezcount_doc_num'),
                    'raw': d,
                })

            # ---- 6. Tnuot (ztorm general transactions, via num_heshbon = num_torem? ----
            # ZTorm Tnuot is a general-ledger table keyed by num_heshbon (account
            # number), not by num_torem directly. We don't have a clean per-donor
            # filter here without a Heshbonot-of-this-donor mapping (which the
            # mirror exposes via Heshbonot but is fund-account, not donor-account).
            # Skip for now — operator's primary need is receipts/donations/
            # payments, all already covered above.

        # Sort newest first.
        events.sort(key=lambda e: e['sort_dt'] or datetime.min, reverse=True)

        return {
            'header': header,
            'num_torem': int(num_torem_num) if num_torem_num else None,
            'counts': {
                'peulot': len(peulot_rows),
                'tnuot_gmach': len(tnuot_g_rows),
                **ztorm_counts,
            },
            'events': events,
        }
    finally:
        con.close()

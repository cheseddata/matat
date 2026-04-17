"""Refresh Matat donors from the operator's live C:\\ztorm\\ztormdata.mdb.

Uses the access_parser library (pip install access-parser) because the
ZTorm MDB is password-protected and Jet OLEDB can't open it.

Scope: keep this safe and scoped. We only update fields on existing
Donor rows matched by ztorm_donor_id; we do NOT create new donors or
cascade into donations/payments. The shipped snapshot has the base
data; this script just picks up edits since the snapshot was taken.

If the operator needs NEW donors synced too, we add that next.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
MATAT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(MATAT_DIR))
os.chdir(MATAT_DIR)

try:
    from access_parser import AccessParser
except ImportError:
    print('[!] access_parser not installed — skipping ZTorm sync.')
    print('    pip install access-parser to enable.')
    sys.exit(0)

from app import create_app
from app.extensions import db
from app.models import Donor


ZTORM_MDB = r'C:\ztorm\ztormdata.mdb'


def safe_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s != 'None' else None


def parse_table(parser, name):
    """Parse an access-parser table into list-of-dicts.

    access_parser sometimes returns columns with unequal row counts when
    the MDB has null/sparse rows; we guard each index lookup.
    """
    try:
        data = parser.parse_table(name)
    except Exception as e:
        print(f'  [!] cannot read {name}: {e}')
        return []
    if not data or not isinstance(data, dict):
        return []
    cols = list(data.keys())
    if not cols:
        return []
    n = min(len(data[c]) for c in cols)
    rows = []
    for i in range(n):
        row = {}
        for c in cols:
            try:
                row[c] = data[c][i]
            except (IndexError, KeyError):
                row[c] = None
        rows.append(row)
    return rows


def main():
    if not Path(ZTORM_MDB).exists():
        print(f'[!] {ZTORM_MDB} not found — skipping ZTorm sync.')
        return

    app = create_app('development')
    with app.app_context():
        print(f'Reading {ZTORM_MDB} via access_parser...')
        parser = AccessParser(ZTORM_MDB)
        tables = list(parser.catalog.keys())
        print(f'  Found {len(tables)} tables.')

        # Tormim is the donor table. Different builds spell it differently.
        tormim_tbl = next((t for t in ('Tormim', 'tormim', 'TORMIM') if t in tables),
                          None)
        if not tormim_tbl:
            print('  [!] No Tormim table found; nothing to sync.')
            return

        rows = parse_table(parser, tormim_tbl)
        print(f'  Tormim rows: {len(rows):,}')

        # Index existing Matat donors by ztorm_donor_id.
        by_ztorm = {d.ztorm_donor_id: d
                    for d in Donor.query.filter(Donor.ztorm_donor_id.isnot(None)).all()
                    if d.ztorm_donor_id is not None}
        print(f'  Matat donors linked to ZTorm: {len(by_ztorm):,}')

        updated = 0
        for row in rows:
            # Column name varies; try common spellings.
            num = row.get('num_torem') or row.get('Num_Torem') or row.get('id')
            try:
                num = int(num)
            except (TypeError, ValueError):
                continue
            donor = by_ztorm.get(num)
            if not donor:
                continue

            changed = False
            # Only update fields that look newer (non-empty) on the live
            # MDB side. Non-destructive.
            updates = {
                'first_name':  safe_str(row.get('shem_prati') or row.get('first_name')),
                'last_name':   safe_str(row.get('shem_mishpaha') or row.get('last_name')),
                'phone':       safe_str(row.get('tel') or row.get('phone')),
                'email':       safe_str(row.get('email')),
                'teudat_zehut': safe_str(row.get('t_z') or row.get('teudat_zehut')),
            }
            for k, v in updates.items():
                if v and getattr(donor, k, None) != v:
                    setattr(donor, k, v)
                    changed = True
            if changed:
                updated += 1

        db.session.commit()
        print(f'  Donor records updated: {updated:,}')


if __name__ == '__main__':
    main()

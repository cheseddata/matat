"""Enumerate tables, queries, and forms in every Access .mdb under C:\\Gmach.

Prints per-file object counts and a summary so we can tell which MDB is the
live data store (tables) vs the live front-end (forms/queries) vs archives.
"""
from __future__ import annotations

import glob
import os

import pyodbc

MDB_GLOB = r'C:\Gmach\*.mdb'
DRIVER = '{Microsoft Access Driver (*.mdb, *.accdb)}'

# MSysObjects.Type values we care about. These are the standard Access codes.
OBJ_TYPES = {
    1:  'table',      # local table
    4:  'linked',     # linked/ODBC table
    6:  'linked',     # linked Access table
    5:  'query',
    -32768: 'form',
    -32764: 'report',
    -32761: 'module',
    -32766: 'macro',
}


def audit(path: str):
    print(f'\n=== {os.path.basename(path)}  ({os.path.getsize(path):,} bytes) ===')
    conn_str = f'DRIVER={DRIVER};DBQ={path};'
    try:
        conn = pyodbc.connect(conn_str, autocommit=True, readonly=True)
    except pyodbc.Error as e:
        print(f'  [X] cannot open: {e}')
        return

    cur = conn.cursor()

    # Counts by object category. Hidden system objects start with ~ or MSys.
    try:
        cur.execute(
            "SELECT Type, COUNT(*) FROM MSysObjects "
            "WHERE Left(Name,1)<>'~' AND Left(Name,4)<>'MSys' "
            "GROUP BY Type ORDER BY Type"
        )
        rows = cur.fetchall()
    except pyodbc.Error as e:
        print(f'  [X] MSysObjects query failed (permissions?): {e}')
        # Fallback: list user tables via ODBC metadata only.
        tables = [r.table_name for r in cur.tables(tableType='TABLE')
                  if not r.table_name.startswith('MSys')]
        print(f'  tables (ODBC metadata): {len(tables)}')
        for t in tables[:10]:
            print(f'    - {t}')
        conn.close()
        return

    bucket = {}
    for typ, cnt in rows:
        label = OBJ_TYPES.get(typ, f'type={typ}')
        bucket[label] = bucket.get(label, 0) + cnt
    for label in ('table', 'linked', 'query', 'form', 'report', 'macro', 'module'):
        if label in bucket:
            print(f'  {label:<8} {bucket[label]}')
    for label, cnt in bucket.items():
        if label not in ('table', 'linked', 'query', 'form', 'report', 'macro', 'module'):
            print(f'  {label:<8} {cnt}')

    # Show form names if any — these are the screens the operator uses.
    if bucket.get('form'):
        cur.execute(
            "SELECT Name FROM MSysObjects WHERE Type=-32768 "
            "AND Left(Name,1)<>'~' ORDER BY Name"
        )
        forms = [r[0] for r in cur.fetchall()]
        print(f'  --- forms ({len(forms)}) ---')
        for f in forms:
            print(f'    {f}')

    # For data files: table list + rowcount hint.
    if bucket.get('table') and not bucket.get('form'):
        cur.execute(
            "SELECT Name FROM MSysObjects WHERE Type=1 "
            "AND Left(Name,1)<>'~' AND Left(Name,4)<>'MSys' ORDER BY Name"
        )
        tables = [r[0] for r in cur.fetchall()]
        print(f'  --- tables ({len(tables)}) ---')
        for t in tables[:40]:
            try:
                cur.execute(f'SELECT COUNT(*) FROM [{t}]')
                cnt = cur.fetchone()[0]
            except pyodbc.Error:
                cnt = '?'
            print(f'    {t:<40} rows={cnt}')
        if len(tables) > 40:
            print(f'    ...and {len(tables) - 40} more')

    conn.close()


def main():
    paths = sorted(glob.glob(MDB_GLOB))
    print(f'found {len(paths)} mdb files')
    print(f'pyodbc drivers available: {[d for d in pyodbc.drivers() if "Access" in d]}')
    for p in paths:
        audit(p)


if __name__ == '__main__':
    main()

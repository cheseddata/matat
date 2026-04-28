"""build_mirror_sqlite.py — load extracted Access TSVs into per-source SQLite
mirror files with VERBATIM Access table and column names.

Layout:
    <SqliteDir>/<source>.db
        contains tables named exactly as in the source Access MDB
        (Hork, Peulot, Haverim, Mosadot, etc., no prefixes)
        plus a `_meta_tables` index inside each file.

This per-source layout matches Access's per-MDB structure, avoids name
collisions across MDBs (e.g., `Bankim` exists in both MttData and ztorm),
and preserves the rule that mirror table names equal Access table names.

Wipe-and-reload: each table is dropped and re-created on every run.

Usage:
    python sync/build_mirror_sqlite.py <ExtractDir> <SqliteDir>
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path


INT_TYPES   = {2, 3, 11, 16, 17, 18, 19, 20, 21}
REAL_TYPES  = {4, 5, 6, 14, 131, 139}
DATE_TYPES  = {7, 133, 134, 135}
BLOB_TYPES  = {128, 204, 205}

def adtype_to_sqlite(t: int) -> str:
    if t in INT_TYPES:  return 'INTEGER'
    if t in REAL_TYPES: return 'REAL'
    if t in DATE_TYPES: return 'TEXT'
    if t in BLOB_TYPES: return 'BLOB'
    return 'TEXT'


def unescape(s: str):
    if s == r'\N': return None
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            c = s[i + 1]
            out.append({'\\': '\\', '|': '|', 'r': '\r', 'n': '\n', 't': '\t', 'N': '\\N'}.get(c, c))
            i += 2
        else:
            out.append(s[i]); i += 1
    return ''.join(out)


def parse_tsv_line(line: str) -> list:
    out, cur, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == '\\' and i + 1 < len(line):
            cur.append(c); cur.append(line[i + 1]); i += 2
        elif c == '|':
            out.append(''.join(cur)); cur = []; i += 1
        else:
            cur.append(c); i += 1
    out.append(''.join(cur))
    return out


def coerce(value, sqlite_type: str):
    if value is None or value == '\\N':
        return None
    if sqlite_type == 'INTEGER':
        try: return int(float(value))
        except (ValueError, TypeError): return None
    if sqlite_type == 'REAL':
        try: return float(value)
        except (ValueError, TypeError): return None
    return unescape(value)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def build_one(source_dir: Path, db_path: Path) -> tuple[int, int]:
    """Build one per-source SQLite mirror file. Returns (tables, rows)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE _meta_tables (
            orig_table TEXT PRIMARY KEY,
            row_count  INTEGER,
            built_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    tables, total_rows = 0, 0
    for sf in sorted(source_dir.glob('*.schema.tsv')):
        stem = sf.name[:-len('.schema.tsv')]
        tsv  = source_dir / f'{stem}.tsv'
        if not tsv.exists():
            print(f"  [!] missing data file for {stem}")
            continue

        cols = []
        orig_table = stem
        for line in sf.read_text(encoding='utf-8').splitlines()[1:]:
            if not line.strip(): continue
            parts = parse_tsv_line(line)
            if len(parts) < 4: continue
            cols.append((unescape(parts[0]),
                         int(parts[1]) if parts[1].lstrip('-').isdigit() else 202))
            orig_table = unescape(parts[3])
        if not cols:
            print(f"  [!] empty schema {stem}")
            continue

        qt = quote_ident(orig_table)
        cur.execute(f'DROP TABLE IF EXISTS {qt}')
        col_defs = ', '.join(f'{quote_ident(c)} {adtype_to_sqlite(t)}' for c, t in cols)
        cur.execute(f'CREATE TABLE {qt} ({col_defs})')

        sqlite_types = [adtype_to_sqlite(t) for _, t in cols]
        insert_sql = f'INSERT INTO {qt} VALUES ({", ".join("?" for _ in cols)})'

        row_count = 0
        batch = []
        BATCH_SZ = 5000
        with tsv.open('r', encoding='utf-8') as fh:
            fh.readline()  # skip header
            for line in fh:
                line = line.rstrip('\r\n')
                if not line: continue
                parts = parse_tsv_line(line)
                if len(parts) < len(cols): parts += [None] * (len(cols) - len(parts))
                elif len(parts) > len(cols): parts = parts[:len(cols)]
                row = tuple(coerce(parts[i], sqlite_types[i]) for i in range(len(cols)))
                batch.append(row)
                if len(batch) >= BATCH_SZ:
                    cur.executemany(insert_sql, batch); row_count += len(batch); batch.clear()
        if batch:
            cur.executemany(insert_sql, batch); row_count += len(batch)

        cur.execute('INSERT INTO _meta_tables (orig_table, row_count) VALUES (?, ?)',
                    (orig_table, row_count))
        tables += 1
        total_rows += row_count
        print(f"  {orig_table:40s} {row_count:>9,d} rows")

    conn.commit()
    cur.execute('VACUUM')
    conn.close()
    return tables, total_rows


def main():
    if len(sys.argv) < 3:
        print("Usage: build_mirror_sqlite.py <ExtractDir> <SqliteDir>")
        sys.exit(1)
    extract_dir = Path(sys.argv[1])
    sqlite_dir  = Path(sys.argv[2])

    grand_tables = grand_rows = 0
    for src in sorted(extract_dir.iterdir()):
        if not src.is_dir(): continue
        print(f"\n=== {src.name} -> {sqlite_dir / (src.name + '.db')} ===")
        t, r = build_one(src, sqlite_dir / f'{src.name}.db')
        grand_tables += t
        grand_rows += r

    print(f"\nDONE: {grand_tables} tables, {grand_rows:,} rows across {sum(1 for s in sqlite_dir.iterdir())} mirror files in {sqlite_dir}")


if __name__ == '__main__':
    main()

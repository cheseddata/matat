"""extract_ztorm_all.py — faithful full extract of every user table from a
ZTorm-style MDB (`ztormdata.mdb`, `zuser.mdb`, etc.) to TSV files.

Uses the `access_parser` Python library because ZTorm's MDBs are protected
by the `ztormw.mdw` workgroup file (Jet OLEDB needs credentials we don't
have, but access_parser reads the raw page format directly).

Output layout matches `extract_gmach_all.ps1`:
    <prefix><table>.tsv          pipe-delimited, header row, ALL columns
    <prefix><table>.schema.tsv   col_name | adType-equivalent | size | orig_table

Run from the matat venv:
    python sync/extract_ztorm_all.py <MdbPath> <OutDir> [<Prefix>]
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    from access_parser import AccessParser
except ImportError:
    print("[X] Missing dependency: pip install access_parser", file=sys.stderr)
    sys.exit(1)


# Map access_parser declared types to ADO/Jet adType numbers (so the
# downstream mirror builder uses the same type-table as the gmach side).
ADTYPE = {
    'Boolean': 11, 'Byte': 17, 'Integer': 2, 'Long Integer': 3,
    'Currency': 6, 'Single': 4, 'Double': 5,
    'Date/Time': 7, 'GUID': 72,
    'Text': 202, 'Memo': 203, 'OLE': 205, 'Hyperlink': 203,
}


def safe_name(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', s)


def escape_cell(v) -> str:
    if v is None:
        return '\\N'
    s = str(v)
    return (s.replace('\\', '\\\\')
             .replace('|', '\\|')
             .replace('\r', '\\r')
             .replace('\n', '\\n')
             .replace('\t', '\\t'))


def main():
    if len(sys.argv) < 3:
        print("Usage: extract_ztorm_all.py <MdbPath> <OutDir> [<Prefix>]")
        sys.exit(1)
    mdb_path = sys.argv[1]
    out_dir  = Path(sys.argv[2])
    prefix   = sys.argv[3] if len(sys.argv) >= 4 else ''

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Reading {mdb_path} via access_parser...")
    db = AccessParser(mdb_path)

    tables = [t for t in db.catalog if not t.startswith('MSys') and not t.startswith('~')]
    print(f"  Found {len(tables)} user tables")

    for tname in tables:
        safe = safe_name(tname)
        tsv_path    = out_dir / f"{prefix}{safe}.tsv"
        schema_path = out_dir / f"{prefix}{safe}.schema.tsv"

        try:
            tdef = db.catalog[tname]
            cols_meta = db.parse_table(tname).items() if False else None  # placeholder
            data = db.parse_table(tname)
        except Exception as e:
            print(f"  [!] skip {tname}: {e}")
            continue

        # data is dict {col_name: [val_row1, val_row2, ...]}
        col_names = list(data.keys())
        if not col_names:
            n = 0
        else:
            n = len(data[col_names[0]])

        # Schema
        with schema_path.open('w', encoding='utf-8', newline='\r\n') as f:
            f.write('name|adType|DefinedSize|orig_table\r\n')
            for c in col_names:
                # access_parser doesn't expose detailed type info per column easily;
                # we infer roughly from the parsed values
                sample = next((v for v in data[c] if v is not None), None)
                if isinstance(sample, bool):       at = 11
                elif isinstance(sample, int):      at = 3
                elif isinstance(sample, float):    at = 5
                elif hasattr(sample, 'year'):      at = 7   # datetime
                elif isinstance(sample, bytes):    at = 205
                else:                              at = 202   # text default
                size = max((len(str(v)) for v in data[c] if v is not None), default=0)
                f.write(f"{escape_cell(c)}|{at}|{size}|{escape_cell(tname)}\r\n")

        # Data
        with tsv_path.open('w', encoding='utf-8', newline='\r\n') as f:
            f.write('|'.join(escape_cell(c) for c in col_names) + '\r\n')
            for i in range(n):
                row = [escape_cell(data[c][i]) for c in col_names]
                f.write('|'.join(row) + '\r\n')

        print(f"  {tname}: {n:,} rows -> {tsv_path.name}")

    print("  Done.")


if __name__ == "__main__":
    main()

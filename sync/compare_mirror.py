"""compare_mirror.py — verify each per-source SQLite mirror file matches its
source MDB. Field-level fidelity, not just row counts.

Per the project's "Porting from Access" rule, every ported flow must verify
byte-for-byte (or row-for-row) parity with the legacy system. A naive
COUNT(*) equality passes even when every cell value is corrupted. This
script adds:

  1. Column-list comparison per table  (missing/extra columns)
  2. Numeric SUMs per table             (INTEGER / REAL columns only)
  3. Sample-row checksum                (TOP 5 rows in default cursor
                                         order, cell-by-cell diff)

Usage:
    python sync/compare_mirror.py <SqliteDir>           # full check
    python sync/compare_mirror.py <SqliteDir> --quick   # counts only
"""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

# Force UTF-8 stdout (sample diffs can contain Hebrew text and the default
# Hebrew Windows codepage cp1255 will crash on cells from other scripts).
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


DEFAULT_MDB_PATHS = {
    'MttData':           r'C:\Gmach\MttData.mdb',
    'Mikud':             r'C:\Gmach\Mikud.mdb',
    'trans':             r'C:\Gmach\trans.mdb',
    'ztormdata':         r'C:\ztorm\ztormdata.mdb',
    'zuser':             r'C:\ztorm\zuser.mdb',
    'ztorm_bankim':      r'C:\ztorm\bankim.mdb',
    'ztorm_mikud':       r'C:\ztorm\mikud.mdb',
    'ztorm_shearim':     r'C:\ztorm\shearim.mdb',
    'tash_ztormdata':    r'C:\ztorm\Tash\ztormdata.mdb',
    'tash_zuser':        r'C:\ztorm\Tash\zuser.mdb',
}


PS32 = r'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe'

SAMPLE_ROWS = 5


# ---------------------------------------------------------------------------
# PowerShell helpers — return text from a 32-bit PS process running ADO/DAO.
# ---------------------------------------------------------------------------

def _run_ps(script: str, timeout: int = 180) -> tuple[int, str, str]:
    """Run a PS script and return (rc, stdout_utf8, stderr_utf8).
    PowerShell's default stdout encoding is the OEM codepage (cp1255 on
    Hebrew Windows) which mangles non-ASCII Unicode. We force UTF-8 by
    prepending an output-encoding setup line, and we read the raw bytes
    and decode UTF-8 ourselves."""
    prelude = '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;'
    r = subprocess.run(
        [PS32, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', prelude + script],
        capture_output=True, timeout=timeout,
    )
    out = (r.stdout or b'').decode('utf-8', errors='replace')
    err = (r.stderr or b'').decode('utf-8', errors='replace')
    return r.returncode, out, err


def _ps_open_jet(mdb_path: str) -> str:
    """ADO connection string snippet for a Gmach (unsecured) MDB."""
    return (
        '$cn = New-Object -ComObject ADODB.Connection;'
        f'$cn.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source={mdb_path};");'
    )


def _ps_open_dao(mdb_path: str,
                 workgroup: str = r'C:\ztorm\ztormw.mdw',
                 user: str = 'user') -> str:
    """DAO + workgroup snippet for a ZTorm secured MDB."""
    return (
        '$engine = New-Object -ComObject DAO.DBEngine.36;'
        f'$engine.SystemDB = "{workgroup}";'
        f'$ws = $engine.CreateWorkspace("temp_cmp", "{user}", "", 2);'
        f'$db = $ws.OpenDatabase("{mdb_path}", $false, $true);'
    )


# ---------------------------------------------------------------------------
# Counts (preserved from the original script).
# ---------------------------------------------------------------------------

def gmach_count(mdb_path: str, table: str) -> int:
    safe_table = table.replace("'", "''")
    ps = _ps_open_jet(mdb_path) + (
        f'$rs = $cn.Execute("SELECT COUNT(*) AS c FROM [{safe_table}]");'
        'Write-Host $rs.Fields.Item("c").Value;'
        '$rs.Close(); $cn.Close()'
    )
    try:
        rc, out, _ = _run_ps(ps, timeout=120)
        if rc == 0 and out.strip():
            return int(out.strip().splitlines()[-1])
    except Exception as e:
        print(f"  [!] count failed for {table}: {e}")
    return -1


def ztorm_count(mdb_path: str, table: str,
                workgroup: str = r'C:\ztorm\ztormw.mdw',
                user: str = 'user') -> int:
    safe_table = table.replace("'", "''").replace('"', '""')
    ps = _ps_open_dao(mdb_path, workgroup, user) + (
        f'$rs = $db.OpenRecordset("SELECT COUNT(*) AS c FROM [{safe_table}]", 4);'
        'Write-Host $rs.Fields.Item("c").Value;'
        '$rs.Close(); $db.Close()'
    )
    try:
        rc, out, _ = _run_ps(ps, timeout=120)
        if rc == 0 and out.strip():
            return int(out.strip().splitlines()[-1])
    except Exception as e:
        print(f"  [!] ztorm count failed for {table}: {e}")
    return -1


# ---------------------------------------------------------------------------
# Column lists.
# ---------------------------------------------------------------------------

def gmach_columns(mdb_path: str, table: str) -> list[str] | None:
    """Return Access column names for a Gmach MDB table (Jet OLEDB)."""
    safe_table = table.replace("'", "''")
    ps = _ps_open_jet(mdb_path) + (
        '$rs = New-Object -ComObject ADODB.Recordset;'
        f'$rs.Open("SELECT * FROM [{safe_table}] WHERE 1=0", $cn, 3, 1);'
        'foreach ($f in $rs.Fields) { Write-Host $f.Name };'
        '$rs.Close(); $cn.Close()'
    )
    try:
        rc, out, err = _run_ps(ps, timeout=60)
        if rc != 0:
            return None
        return [ln.strip() for ln in out.splitlines() if ln.strip()]
    except Exception:
        return None


def ztorm_columns(mdb_path: str, table: str,
                  workgroup: str = r'C:\ztorm\ztormw.mdw',
                  user: str = 'user') -> list[str] | None:
    safe_table = table.replace("'", "''").replace('"', '""')
    ps = _ps_open_dao(mdb_path, workgroup, user) + (
        f'$rs = $db.OpenRecordset("SELECT * FROM [{safe_table}] WHERE 1=0", 4);'
        'foreach ($f in $rs.Fields) { Write-Host $f.Name };'
        '$rs.Close(); $db.Close()'
    )
    try:
        rc, out, err = _run_ps(ps, timeout=60)
        if rc != 0:
            return None
        return [ln.strip() for ln in out.splitlines() if ln.strip()]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Numeric SUMs.
# ---------------------------------------------------------------------------

def _ps_quote_dq(s: str) -> str:
    """Escape for a PowerShell double-quoted string."""
    return s.replace('`', '``').replace('"', '`"').replace('$', '`$')


def gmach_sum(mdb_path: str, table: str, column: str) -> float | None:
    safe_t = table.replace("'", "''")
    safe_c = column.replace("'", "''")
    sql = f'SELECT SUM([{safe_c}]) AS s FROM [{safe_t}]'
    ps = _ps_open_jet(mdb_path) + (
        f'$rs = $cn.Execute("{_ps_quote_dq(sql)}");'
        '$v = $rs.Fields.Item("s").Value;'
        'if ($null -eq $v -or [DBNull]::Value.Equals($v)) { Write-Host "NULL" }'
        'else { Write-Host ([string]$v) };'
        '$rs.Close(); $cn.Close()'
    )
    try:
        rc, out, _ = _run_ps(ps, timeout=120)
        if rc != 0: return None
        line = out.strip().splitlines()[-1] if out.strip() else ''
        if not line or line == 'NULL': return 0.0
        return float(line)
    except Exception:
        return None


def ztorm_sum(mdb_path: str, table: str, column: str,
              workgroup: str = r'C:\ztorm\ztormw.mdw',
              user: str = 'user') -> float | None:
    safe_t = table.replace("'", "''").replace('"', '""')
    safe_c = column.replace("'", "''").replace('"', '""')
    sql = f'SELECT SUM([{safe_c}]) AS s FROM [{safe_t}]'
    ps = _ps_open_dao(mdb_path, workgroup, user) + (
        f'$rs = $db.OpenRecordset("{_ps_quote_dq(sql)}", 4);'
        '$v = $rs.Fields.Item("s").Value;'
        'if ($null -eq $v -or [DBNull]::Value.Equals($v)) { Write-Host "NULL" }'
        'else { Write-Host ([string]$v) };'
        '$rs.Close(); $db.Close()'
    )
    try:
        rc, out, _ = _run_ps(ps, timeout=120)
        if rc != 0: return None
        line = out.strip().splitlines()[-1] if out.strip() else ''
        if not line or line == 'NULL': return 0.0
        return float(line)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sample rows.
# ---------------------------------------------------------------------------

def _parse_json_rows(out: str) -> list[dict]:
    """Parse PowerShell ConvertTo-Json output into a list of dicts."""
    out = out.strip()
    if not out: return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict): data = [data]
    return data or []


def gmach_fetch_top(mdb_path: str, table: str, n: int) -> list[dict]:
    """Fetch the first N rows from a Gmach Access table (default order)."""
    safe_t = table.replace("'", "''")
    sql = f"SELECT TOP {int(n)} * FROM [{safe_t}]"
    ps = _ps_open_jet(mdb_path) + (
        '$rs = New-Object -ComObject ADODB.Recordset;'
        '$rs.CursorLocation = 3;'
        f'$rs.Open("{_ps_quote_dq(sql)}", $cn, 3, 1);'
        '$rows = New-Object System.Collections.ArrayList;'
        'while (-not $rs.EOF) {'
        '  $h = [ordered]@{};'
        '  foreach ($f in $rs.Fields) {'
        '    $v = $f.Value;'
        '    if ($null -eq $v -or [DBNull]::Value.Equals($v)) { $h[$f.Name] = $null }'
        '    else { $h[$f.Name] = [string]$v }'
        '  };'
        '  [void] $rows.Add($h);'
        '  $rs.MoveNext()'
        '};'
        '$rs.Close(); $cn.Close();'
        '$rows | ConvertTo-Json -Depth 4 -Compress'
    )
    try:
        rc, out, err = _run_ps(ps, timeout=120)
        if rc != 0: return []
        return _parse_json_rows(out)
    except Exception as e:
        print(f"  [!] gmach_fetch_top failed for {table}: {e}")
        return []


def ztorm_fetch_top(mdb_path: str, table: str, n: int,
                    workgroup: str = r'C:\ztorm\ztormw.mdw',
                    user: str = 'user') -> list[dict]:
    safe_t = table.replace("'", "''").replace('"', '""')
    sql = f"SELECT TOP {int(n)} * FROM [{safe_t}]"
    ps = _ps_open_dao(mdb_path, workgroup, user) + (
        f'$rs = $db.OpenRecordset("{_ps_quote_dq(sql)}", 4);'
        '$rows = New-Object System.Collections.ArrayList;'
        'while (-not $rs.EOF) {'
        '  $h = [ordered]@{};'
        '  foreach ($f in $rs.Fields) {'
        '    $v = $f.Value;'
        '    if ($null -eq $v -or [DBNull]::Value.Equals($v)) { $h[$f.Name] = $null }'
        '    else { $h[$f.Name] = [string]$v }'
        '  };'
        '  [void] $rows.Add($h);'
        '  $rs.MoveNext()'
        '};'
        '$rs.Close(); $db.Close();'
        '$rows | ConvertTo-Json -Depth 4 -Compress'
    )
    try:
        rc, out, err = _run_ps(ps, timeout=120)
        if rc != 0: return []
        return _parse_json_rows(out)
    except Exception as e:
        print(f"  [!] ztorm_fetch_top failed for {table}: {e}")
        return []


# ---------------------------------------------------------------------------
# SQLite helpers.
# ---------------------------------------------------------------------------

def sqlite_columns(db: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    """Return [(col_name, col_type), ...] for a SQLite table."""
    return [(r[1], (r[2] or '').upper()) for r in db.execute(f'PRAGMA table_info("{table}")')]


def sqlite_top_rows(db: sqlite3.Connection, table: str, n: int) -> list[dict]:
    """Return the first n rows in natural (rowid) order as dicts.

    build_mirror_sqlite.py inserts rows in extract order (which itself
    iterates Access default cursor order), so SQLite's natural rowid order
    matches Access's TOP N order. This is a smoke check — if data was
    loaded faithfully, the first rows must match cell-for-cell.
    """
    cur = db.execute(f'SELECT * FROM "{table}" LIMIT ?', (n,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def sqlite_sum(db: sqlite3.Connection, table: str, col: str) -> float | None:
    try:
        r = db.execute(f'SELECT SUM("{col}") FROM "{table}"').fetchone()
        if r is None or r[0] is None: return 0.0
        return float(r[0])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-source comparison.
# ---------------------------------------------------------------------------

def _norm_cell(v) -> str:
    """Normalise a cell value for cross-side comparison.
    - None -> ''
    - numbers -> trimmed string ('1.0' == '1')
    - strings -> stripped
    """
    if v is None: return ''
    if isinstance(v, (int,)): return str(v)
    if isinstance(v, float):
        # 1.0 -> '1'; 1.50 -> '1.5'
        if v == int(v): return str(int(v))
        return repr(v).rstrip('0').rstrip('.')
    s = str(v)
    # Access-side numbers come back as string already; trim '.0' for parity.
    try:
        f = float(s)
        if f == int(f) and '.' in s:
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return s.strip()


def _short_repr(v, limit: int = 80) -> str:
    """Like repr() but truncates huge BLOBs / long strings."""
    r = repr(v)
    if len(r) > limit:
        return r[:limit] + f'...<{len(r)} chars>'
    return r


def _diff_row(sqlite_row: dict, access_row: dict, columns: list[str]) -> list[str]:
    diffs = []
    for c in columns:
        sv = _norm_cell(sqlite_row.get(c))
        av = _norm_cell(access_row.get(c))
        if sv != av:
            diffs.append(
                f"        {c!r}: sqlite={_short_repr(sqlite_row.get(c))}  "
                f"access={_short_repr(access_row.get(c))}"
            )
    return diffs


def compare_source(db_file: Path, mdb_path: str, quick: bool) -> tuple[int, int, int]:
    """Compare one source. Returns (pass, fail, skip)."""
    is_gmach = mdb_path.lower().startswith('c:\\gmach\\')
    col_fn   = gmach_columns   if is_gmach else ztorm_columns
    cnt_fn   = gmach_count     if is_gmach else ztorm_count
    sum_fn   = gmach_sum       if is_gmach else ztorm_sum
    fetch_fn = gmach_fetch_top if is_gmach else ztorm_fetch_top

    db = sqlite3.connect(db_file)
    rows = db.execute(
        'SELECT orig_table, row_count FROM _meta_tables ORDER BY orig_table'
    ).fetchall()
    p = f = s = 0
    for orig, mirror_count in rows:
        # ---- 1. count ----------------------------------------------------
        access_count = cnt_fn(mdb_path, orig)
        if access_count < 0:
            print(f"  {orig:35s} {mirror_count:>10,d}  {'?':>10}   ERROR(count)")
            f += 1
            continue
        diff = mirror_count - access_count
        count_ok = (diff == 0)
        status = 'OK' if count_ok else 'MISMATCH'
        print(f"  {orig:35s} {mirror_count:>10,d}  {access_count:>10,d}  {diff:>+8d}  {status}")
        if not count_ok:
            f += 1
        else:
            p += 1

        if quick or mirror_count == 0:
            continue

        # ---- 2. column list ---------------------------------------------
        sql_cols = sqlite_columns(db, orig)
        sql_names = [c[0] for c in sql_cols]
        access_names = col_fn(mdb_path, orig)
        if access_names is None:
            print(f"      [!] could not list Access columns for {orig}")
        else:
            missing = [c for c in access_names if c not in sql_names]
            extra   = [c for c in sql_names if c not in access_names]
            if missing or extra:
                if missing:
                    print(f"      COLS missing from sqlite ({len(missing)}): {missing}")
                if extra:
                    print(f"      COLS extra in sqlite    ({len(extra)}): {extra}")
                f += 1
            else:
                p += 1

        # ---- 3. numeric sums --------------------------------------------
        numeric_cols = [c for c, t in sql_cols if t in ('INTEGER', 'REAL')]
        if numeric_cols:
            mismatches = []
            for c in numeric_cols:
                s_sum = sqlite_sum(db, orig, c)
                a_sum = sum_fn(mdb_path, orig, c)
                if s_sum is None or a_sum is None:
                    mismatches.append((c, s_sum, a_sum, 'ERROR'))
                    continue
                # Compare with float tolerance.
                if abs(s_sum - a_sum) > 1e-6 * max(1.0, abs(a_sum)):
                    mismatches.append((c, s_sum, a_sum, 'DIFF'))
            if mismatches:
                print(f"      SUMS mismatch in {orig}:")
                for c, sv, av, tag in mismatches:
                    print(f"        {c}: sqlite={sv}  access={av}  [{tag}]")
                f += 1
            else:
                p += 1

        # ---- 4. sample rows (TOP N, default order, cell-by-cell) -------
        sql_samples = sqlite_top_rows(db, orig, SAMPLE_ROWS)
        access_samples = fetch_fn(mdb_path, orig, SAMPLE_ROWS)
        # access_samples is list[dict]; sql_samples is list[dict]; both
        # ordered by natural cursor order on each side.
        if not sql_samples and not access_samples:
            continue
        sample_fail = 0
        sample_diffs = []
        # Compare same index in each list. If counts differ, that itself
        # is a mismatch (already caught by the count check, but report).
        n = min(len(sql_samples), len(access_samples))
        if len(sql_samples) != len(access_samples):
            sample_diffs.append(
                f"      SAMPLE counts differ: sqlite={len(sql_samples)} "
                f"access={len(access_samples)}"
            )
            sample_fail += 1
        for i in range(n):
            srow = sql_samples[i]
            arow = access_samples[i]
            diffs = _diff_row(srow, arow, sql_names)
            if diffs:
                sample_fail += 1
                sample_diffs.append(f"      ROW #{i + 1}:")
                sample_diffs.extend(diffs)
        if sample_fail:
            print(f"      SAMPLE rows: {sample_fail}/{max(n, 1)} differ in {orig}")
            for line in sample_diffs[:40]:
                print(line)
            if len(sample_diffs) > 40:
                print(f"      ... ({len(sample_diffs) - 40} more)")
            f += 1
        else:
            p += 1

    db.close()
    return p, f, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sqlite_dir')
    ap.add_argument('--quick', action='store_true',
                    help='counts only (legacy behaviour, fast)')
    args = ap.parse_args()

    sqlite_dir = Path(args.sqlite_dir)
    if not sqlite_dir.exists():
        print(f"[X] not found: {sqlite_dir}"); sys.exit(1)

    mode = 'QUICK (counts only)' if args.quick else 'FULL (counts + columns + sums + sample rows)'
    print(f"compare_mirror.py — mode: {mode}")

    grand_p = grand_f = grand_s = 0
    for db_file in sorted(sqlite_dir.glob('*.db')):
        source = db_file.stem
        mdb    = DEFAULT_MDB_PATHS.get(source)
        print(f"\n=== {source} ({db_file.name}) ===")
        if not mdb or not Path(mdb).exists():
            print(f"  [!] no source MDB known for {source} — skipping")
            grand_s += 1
            continue
        print(f"  source: {mdb}")
        print(f"  {'TABLE':<35} {'MIRROR':>10}  {'ACCESS':>10}     STATUS")
        print('  ' + '-' * 80)
        p, f, s = compare_source(db_file, mdb, args.quick)
        grand_p += p; grand_f += f; grand_s += s

    print()
    print(f"==============  PASS={grand_p}  FAIL={grand_f}  SKIP={grand_s}  ==============")
    sys.exit(0 if grand_f == 0 else 1)


if __name__ == '__main__':
    main()

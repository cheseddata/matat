"""Push freshly-synced gemach tables from local SQLite up to matattest MySQL.

Called by sync_live_data.bat after the Access -> SQLite sync completes.
Connects via the SSH tunnel opened by start.bat (127.0.0.1:33306 -> server :3306).

Only touches gemach_* tables; donors/users/config on matattest are left alone.
Uses INSERT ... ON DUPLICATE KEY UPDATE (-i update) so existing rows are
refreshed and new rows are added. Rows deleted from Access will NOT be
deleted from matattest -- acceptable drift for the test phase.

Requires: pip install sqlite3-to-mysql (already in requirements).
"""
import os
import subprocess
import sys

GEMACH_TABLES = [
    'gemach_members',
    'gemach_loans',
    'gemach_transactions',
    'gemach_loan_transactions',
    'gemach_institutions',
    'gemach_cancelled_loans',
    'gemach_memorials',
    'gemach_cancellation_reasons',
    'gemach_transaction_types',
    'gemach_hash_accounts',
    'gemach_setup',
]

SQLITE_PATH    = r'C:\Matat\instance\matat.db'
MYSQL_HOST     = '127.0.0.1'
MYSQL_PORT     = '33306'
MYSQL_USER     = 'matat'
MYSQL_PASSWORD = '0584754666'
MYSQL_DB       = 'matattest'


def main() -> int:
    exe = os.path.join(os.path.dirname(sys.executable), 'sqlite3mysql.exe')
    if not os.path.isfile(exe):
        print(f'[X] sqlite3mysql.exe not found at {exe}')
        print('    Fix: .\\venv\\Scripts\\python.exe -m pip install sqlite3-to-mysql')
        return 1
    if not os.path.isfile(SQLITE_PATH):
        print(f'[X] Source SQLite not found at {SQLITE_PATH}')
        return 1

    cmd = [
        exe,
        '-f', SQLITE_PATH,
        '-d', MYSQL_DB,
        '-u', MYSQL_USER,
        '--mysql-password', MYSQL_PASSWORD,
        '-h', MYSQL_HOST,
        '-P', MYSQL_PORT,
        '--mysql-charset', 'utf8mb4',
        '--mysql-collation', 'utf8mb4_unicode_ci',
        '-i', 'update',              # upsert on PK
        '-K',                        # skip CREATE TABLE (tables already exist)
        '-t', *GEMACH_TABLES,
    ]

    print('>> Pushing gemach_* tables to matattest via SSH tunnel')
    print(f'   {SQLITE_PATH}  ->  {MYSQL_USER}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}')
    print(f'   Tables: {", ".join(GEMACH_TABLES)}')

    result = subprocess.run(cmd)
    if result.returncode == 0:
        print('>> Push complete.')
    else:
        print(f'[X] Push failed with exit code {result.returncode}')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())

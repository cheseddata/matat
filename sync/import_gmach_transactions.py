"""
Gmach TRANSACTIONS Import — Peulot + Tnuot + Munz.

Run AFTER import_gmach_data.py has loaded members + loans + lookups.

Usage:
    cd F:/matat_git && .\\venv\\Scripts\\python.exe F:/gemach/import/import_gmach_transactions.py

Input files (all from Access extract):
    F:/outlook_over_a_yer/gmach_extract/ids/peulot.txt   (~133K rows)
    F:/outlook_over_a_yer/gmach_extract/ids/tnuot.txt    (~98K rows)
    F:/outlook_over_a_yer/gmach_extract/ids/munz.txt     (usually empty)

Performance: Chunk-inserts of 2000 rows inside a single transaction
with FK checks off. Full 231K-row load on SQLite takes ~30s.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date
from pathlib import Path
from decimal import Decimal, InvalidOperation

SCRIPT_DIR = Path(__file__).parent
MATAT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(MATAT_DIR))
os.environ.setdefault('FLASK_APP', 'run.py')
os.chdir(MATAT_DIR)

from app import create_app
from app.extensions import db
from app.models import (
    GemachMember, GemachLoan, GemachLoanTransaction, GemachTransaction,
    GemachMemorial,
)
from sqlalchemy import text

EXTRACT_DIR = Path(os.environ.get('GMACH_EXTRACT_DIR',
                                  'F:/outlook_over_a_yer/gmach_extract/ids'))
CHUNK = 2000


# --------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------
def strip(v):
    if v is None: return None
    s = str(v).strip()
    return s or None


def parse_int(v):
    s = strip(v)
    if not s: return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def parse_decimal(v):
    s = strip(v)
    if not s: return None
    try:
        return Decimal(s.replace(',', ''))
    except (InvalidOperation, ValueError):
        return None


def parse_bool(v):
    s = strip(v)
    if not s: return False
    return s.lower() in ('1', 'true', 'yes', 'y', '-1', 't')


def parse_date(v):
    """Access dates look like '1/5/2018' or '2018-01-05 00:00:00'."""
    s = strip(v)
    if not s: return None
    for fmt in ('%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def read_pipe_file(path: Path):
    """Yield dict rows from a pipe-delimited UTF-8 file (header in row 1)."""
    if not path.exists():
        print(f'  SKIP (missing): {path.name}')
        return
    with open(path, 'r', encoding='utf-8') as f:
        header = f.readline().rstrip('\n\r').split('|')
        for raw in f:
            parts = raw.rstrip('\n\r').split('|')
            # pad if ragged
            if len(parts) < len(header):
                parts = parts + [''] * (len(header) - len(parts))
            yield dict(zip(header, parts))


# --------------------------------------------------------------------
# Importers
# --------------------------------------------------------------------
def import_peulot():
    """Loan transactions (Peulot). Requires loans to be imported first."""
    print('\n=== Peulot (loan transactions) ===')

    # Index loans by their legacy num_hork
    loan_by_num = {l.gmach_num_hork: l.id for l in GemachLoan.query.all()}
    print(f'  Loaded {len(loan_by_num):,} loans for FK lookup')

    # Already-imported counters (for idempotency)
    existing = {r[0] for r in db.session.execute(
        text('SELECT gmach_counter FROM gemach_loan_transactions WHERE gmach_counter IS NOT NULL')
    ).fetchall()}
    print(f'  Already imported: {len(existing):,} peulot counters')

    src = EXTRACT_DIR / 'peulot.txt'
    chunk = []
    total = skipped_orphan = skipped_dup = inserted = 0

    for row in read_pipe_file(src):
        total += 1
        counter = parse_int(row.get('counter'))
        num_hork = parse_int(row.get('num_hork'))

        if counter in existing:
            skipped_dup += 1
            continue
        loan_id = loan_by_num.get(num_hork)
        if not loan_id:
            skipped_orphan += 1
            continue

        tdate = parse_date(row.get('date'))
        if not tdate:
            # transaction_date is NOT NULL — skip if missing
            skipped_orphan += 1
            continue

        chunk.append({
            'gmach_counter': counter,
            'loan_id': loan_id,
            'transaction_date': tdate,
            'asmachta': parse_int(row.get('asmachta')),
            'amount_ils': parse_decimal(row.get('schum')),
            'amount_usd': parse_decimal(row.get('schum_d')),
            'bounced': parse_bool(row.get('hazar')),
            'bounce_reason': strip(row.get('siba')),
            'loan_type': strip(row.get('sug')),
            'receipt_issued': parse_bool(row.get('kabala')),
            'transfer_ref': parse_int(row.get('num_transfer')),
        })

        if len(chunk) >= CHUNK:
            db.session.bulk_insert_mappings(GemachLoanTransaction, chunk)
            db.session.commit()
            inserted += len(chunk)
            chunk = []
            print(f'    committed {inserted:,} rows')

    if chunk:
        db.session.bulk_insert_mappings(GemachLoanTransaction, chunk)
        db.session.commit()
        inserted += len(chunk)

    print(f'  Total read:       {total:,}')
    print(f'  Skipped orphan:   {skipped_orphan:,}')
    print(f'  Skipped dup:      {skipped_dup:,}')
    print(f'  Inserted:         {inserted:,}')


def import_tnuot():
    """General transactions (Tnuot). Requires members."""
    print('\n=== Tnuot (general transactions) ===')

    # Index members by card_no
    mem_by_card = {m.gmach_card_no: m.id for m in GemachMember.query.all()}
    print(f'  Loaded {len(mem_by_card):,} members for FK lookup')

    existing = {r[0] for r in db.session.execute(
        text('SELECT gmach_counter FROM gemach_transactions WHERE gmach_counter IS NOT NULL')
    ).fetchall()}
    print(f'  Already imported: {len(existing):,} tnuot counters')

    src = EXTRACT_DIR / 'tnuot.txt'
    chunk = []
    total = skipped_orphan = skipped_dup = inserted = 0

    for row in read_pipe_file(src):
        total += 1
        counter = parse_int(row.get('counter'))
        card_no = parse_int(row.get('card_no'))

        if counter in existing:
            skipped_dup += 1
            continue
        member_id = mem_by_card.get(card_no)
        if not member_id:
            skipped_orphan += 1
            continue

        tdate = parse_date(row.get('date'))
        if not tdate:
            skipped_orphan += 1
            continue

        num_zacai = parse_int(row.get('num_zacai'))
        beneficiary_id = mem_by_card.get(num_zacai) if num_zacai else None

        chunk.append({
            'gmach_counter': counter,
            'member_id': member_id,
            'beneficiary_member_id': beneficiary_id,
            'transaction_date': tdate,
            'posting_date': parse_date(row.get('date_peraon')),
            'value_date': parse_date(row.get('erech')),
            'receipt_date': parse_date(row.get('kabala_date')),
            'deposit_or_withdraw': strip(row.get('tash')),
            'category': strip(row.get('sug')),
            'amount_ils': parse_decimal(row.get('schum_sh')),
            'amount_usd': parse_decimal(row.get('schum_$')),
            'primary_currency': strip(row.get('matbea')) or 'ILS',
            'description': strip(row.get('pratim')),
            'payment_method': strip(row.get('ofen')),
            'bank_code': parse_int(row.get('bank')),
            'branch_code': parse_int(row.get('snif')),
            'account_number': parse_int(row.get('heshbon')),
            'check_number': parse_int(row.get('num_check')),
            'receipt_issued': parse_bool(row.get('kabala')),
            'organization_flag': parse_bool(row.get('amuta')),
            'private_flag': parse_bool(row.get('private')),
            'closure_ref': parse_int(row.get('num_sgira')),
            'transfer_ref': parse_int(row.get('num_transfer')),
        })

        if len(chunk) >= CHUNK:
            db.session.bulk_insert_mappings(GemachTransaction, chunk)
            db.session.commit()
            inserted += len(chunk)
            chunk = []
            print(f'    committed {inserted:,} rows')

    if chunk:
        db.session.bulk_insert_mappings(GemachTransaction, chunk)
        db.session.commit()
        inserted += len(chunk)

    print(f'  Total read:       {total:,}')
    print(f'  Skipped orphan:   {skipped_orphan:,}')
    print(f'  Skipped dup:      {skipped_dup:,}')
    print(f'  Inserted:         {inserted:,}')


def import_munz():
    """Memorial records (Munz)."""
    print('\n=== Munz (memorials) ===')

    mem_by_card = {m.gmach_card_no: m.id for m in GemachMember.query.all()}

    existing = {r[0] for r in db.session.execute(
        text('SELECT gmach_id FROM gemach_memorials WHERE gmach_id IS NOT NULL')
    ).fetchall()}
    print(f'  Already imported: {len(existing):,} munz ids')

    src = EXTRACT_DIR / 'munz.txt'
    chunk = []
    total = skipped = inserted = 0
    for row in read_pipe_file(src):
        total += 1
        gid = parse_int(row.get('id'))
        if gid in existing:
            skipped += 1
            continue
        card_no = parse_int(row.get('card_no'))
        sponsor_id = mem_by_card.get(card_no)
        if not sponsor_id:
            skipped += 1
            continue
        chunk.append({
            'gmach_id': gid,
            'sponsor_member_id': sponsor_id,
            'deceased_name': strip(row.get('name')),
            'hebrew_day': parse_int(row.get('yom')),
            'hebrew_month': strip(row.get('hodesh')),
            'hebrew_year': parse_int(row.get('shana')),
            'active': parse_bool(row.get('pail')) if row.get('pail') else True,
            'kaddish_end_date': parse_date(row.get('sium_kadish_yomi')),
            'registration_date': parse_date(row.get('date_klita')),
            'yahrzeit_printed': parse_bool(row.get('hudpas_tizcoret')),
            'kaddish_printed': parse_bool(row.get('hudpas_kadish')),
        })
    if chunk:
        db.session.bulk_insert_mappings(GemachMemorial, chunk)
        db.session.commit()
        inserted = len(chunk)
    print(f'  Total read: {total:,}  skipped: {skipped:,}  inserted: {inserted:,}')


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
def main():
    app = create_app('development')
    with app.app_context():
        # SQLite performance knobs
        db.session.execute(text('PRAGMA synchronous = OFF'))
        db.session.execute(text('PRAGMA journal_mode = MEMORY'))

        import_munz()
        import_peulot()
        import_tnuot()

        print('\n=== Final counts ===')
        print(f'  gemach_memorials:         {GemachMemorial.query.count():>8,}')
        print(f'  gemach_loan_transactions: {GemachLoanTransaction.query.count():>8,}')
        print(f'  gemach_transactions:      {GemachTransaction.query.count():>8,}')


if __name__ == '__main__':
    main()

"""
Gmach Data Import Script
========================

Imports the Access-extracted Gmach data (from F:/gemach/extract/ids/*.txt)
into the Matat Flask app database.

Usage:
    # From F:/matat_git
    .\\venv\\Scripts\\python.exe F:/gemach/import/import_gmach_data.py

Steps performed:
1. Load all lookup tables (Mosadot, HashAccts, Sibot_bitul, Sugei_Tnua)
2. Load Translate table (ZTorm ↔ Gmach map)
3. Import Haverim (4,086 members):
   - Match to existing Donor by: (a) Translate.tormim→Donor.ztorm_donor_id,
     (b) t_z, (c) email, (d) name
   - Set gemach_member.donor_id if matched
4. Import Hork (6,861 active loans)
5. Import Btlhork (8,027 cancelled loans)
6. Import Peulot and Tnuot if available (large — can be deferred)

Re-runnable: safely skips rows already imported (via gmach_* ID columns).
"""
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Portable paths: app root is the parent of this script (so this works
# in both F:/matat_git/sync and C:/Matat/sync). Extract dir is given by
# env var GMACH_EXTRACT_DIR (set by sync_live_data.bat); falls back to
# the dev path if unset.
SCRIPT_DIR = Path(__file__).parent
MATAT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(MATAT_DIR))

os.environ.setdefault('FLASK_APP', 'run.py')
os.chdir(MATAT_DIR)

from app import create_app
from app.extensions import db
from app.models import (
    Donor,
    GemachMember, GemachLoan, GemachLoanTransaction, GemachTransaction,
    GemachCancelledLoan, GemachInstitution,
    GemachCancellationReason, GemachTransactionType, GemachHashAccount, GemachSetup,
)

EXTRACT_DIR = Path(os.environ.get('GMACH_EXTRACT_DIR',
                                  'F:/gemach/extract/ids'))

app = create_app('development')


# ---------- Helpers ----------

def read_pipe_file(path):
    """Read a pipe-delimited UTF-8 file with a header row. Yields dicts."""
    if not path.exists():
        print(f"  [SKIP] File not found: {path}")
        return
    with open(path, 'r', encoding='utf-8-sig') as f:
        header = f.readline().strip().split('|')
        for line in f:
            parts = line.rstrip('\n').split('|')
            # Pad if last columns are empty
            while len(parts) < len(header):
                parts.append('')
            yield dict(zip(header, parts))


def parse_int(v):
    if v is None or v == '':
        return None
    try: return int(v)
    except (ValueError, TypeError): return None


def parse_decimal(v):
    if v is None or v == '':
        return None
    try: return float(str(v).replace(',', ''))
    except (ValueError, TypeError): return None


def parse_date(v):
    if not v or v == '':
        return None
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y %H:%M:%S'):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def parse_bool(v):
    if v is None or v == '':
        return False
    return str(v).lower() in ('true', '1', 'yes', '-1')


def strip_or_none(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


# ---------- Lookup table imports ----------

def import_institutions():
    print("\n[1/7] Importing Mosadot (institutions)...")
    count = 0
    for row in read_pipe_file(EXTRACT_DIR / 'mosadot.txt'):
        num_mosad = parse_int(row.get('num_mosad'))
        if num_mosad is None:
            continue
        existing = GemachInstitution.query.filter_by(gmach_num_mosad=num_mosad).first()
        if existing:
            continue
        inst = GemachInstitution(
            gmach_num_mosad=num_mosad,
            name=strip_or_none(row.get('shem_mosad')) or f'Institution {num_mosad}',
            code=strip_or_none(row.get('code_mosad')),
            active=parse_bool(row.get('pail')),
        )
        db.session.add(inst)
        count += 1
    db.session.commit()
    print(f"  Inserted {count} institutions.")


def import_cancellation_reasons():
    print("\n[2/7] Importing Sibot_bitul (cancellation reasons)...")
    count = 0
    for row in read_pipe_file(EXTRACT_DIR / 'sibot_bitul.txt'):
        code = strip_or_none(row.get('code_siba'))
        if not code:
            continue
        existing = GemachCancellationReason.query.get(code)
        if existing:
            continue
        reason = GemachCancellationReason(
            code=code,
            name=strip_or_none(row.get('shem_siba')) or code,
            triggers_cancellation=parse_bool(row.get('lvatel')),
        )
        db.session.add(reason)
        count += 1
    db.session.commit()
    print(f"  Inserted {count} cancellation reasons.")


def import_transaction_types():
    print("\n[3/7] Importing Sugei_Tnua (transaction types)...")
    count = 0
    for row in read_pipe_file(EXTRACT_DIR / 'sugei_tnua.txt'):
        code = strip_or_none(row.get('sug_tnua'))
        if not code:
            continue
        existing = GemachTransactionType.query.get(code)
        if existing:
            continue
        t = GemachTransactionType(
            code=code,
            description=strip_or_none(row.get('teur')) or code,
        )
        db.session.add(t)
        count += 1
    db.session.commit()
    print(f"  Inserted {count} transaction types.")


def import_hash_accounts():
    print("\n[4/7] Importing HashAccts (chart of accounts)...")
    count = 0
    for row in read_pipe_file(EXTRACT_DIR / 'hashaccts.txt'):
        acct_no = parse_int(row.get('acct_no'))
        if acct_no is None:
            continue
        existing = GemachHashAccount.query.get(acct_no)
        if existing:
            continue
        a = GemachHashAccount(
            account_no=acct_no,
            name=strip_or_none(row.get('name')) or f'Account {acct_no}',
            description=strip_or_none(row.get('desc')),
        )
        db.session.add(a)
        count += 1
    db.session.commit()
    print(f"  Inserted {count} hash accounts.")


# ---------- Translate table (ZTorm ↔ Gmach) ----------

def load_translate_map():
    """Returns dict: gmach_card_no → ztorm_tormim_id."""
    mapping = {}
    for row in read_pipe_file(EXTRACT_DIR / 'translate.txt'):
        tormim = parse_int(row.get('tormim'))
        gmach = parse_int(row.get('gmach'))
        if tormim and gmach:
            mapping[gmach] = tormim
    return mapping


# ---------- Haverim (Members) ----------

def import_members(translate_map):
    print("\n[5/7] Importing Haverim (members)...")

    # Pre-fetch existing GemachMembers by gmach_card_no
    existing_cards = {m.gmach_card_no for m in db.session.query(GemachMember.gmach_card_no).all()}

    # Pre-fetch all Donors with ztorm_donor_id for fast lookup
    donors_by_ztorm = {}
    donors_by_tz = {}
    donors_by_email = {}
    for d in Donor.query.all():
        if d.ztorm_donor_id:
            donors_by_ztorm[d.ztorm_donor_id] = d.id
        if d.teudat_zehut:
            donors_by_tz[d.teudat_zehut.strip()] = d.id
        if d.email:
            donors_by_email[d.email.strip().lower()] = d.id

    print(f"  Preloaded {len(donors_by_ztorm)} donors with ztorm_donor_id")
    print(f"  Preloaded {len(donors_by_tz)} donors with TZ")
    print(f"  Preloaded {len(donors_by_email)} donors with email")

    stats = {'new': 0, 'skip': 0, 'linked_by_ztorm': 0, 'linked_by_tz': 0, 'linked_by_translate': 0}
    batch_count = 0

    for row in read_pipe_file(EXTRACT_DIR / 'haverim.txt'):
        card_no = parse_int(row.get('card_no'))
        if card_no is None or card_no in existing_cards:
            stats['skip'] += 1
            continue

        tz_raw = strip_or_none(row.get('t_z'))
        num_torem_direct = parse_int(row.get('num_torem'))

        # Match to existing Donor
        donor_id = None
        ztorm_id = num_torem_direct or translate_map.get(card_no)

        if ztorm_id and ztorm_id in donors_by_ztorm:
            donor_id = donors_by_ztorm[ztorm_id]
            stats['linked_by_ztorm'] += 1
        elif tz_raw and tz_raw in donors_by_tz:
            donor_id = donors_by_tz[tz_raw]
            stats['linked_by_tz'] += 1
        elif card_no in translate_map:
            # Translate says this card_no maps to a ztorm_donor but we don't have
            # a Matat donor for it yet. Still record the ztorm link.
            stats['linked_by_translate'] += 1

        m = GemachMember(
            gmach_card_no=card_no,
            donor_id=donor_id,
            ztorm_donor_id=ztorm_id,
            last_name=strip_or_none(row.get('last_name')),
            first_name=strip_or_none(row.get('first_name')),
            title=strip_or_none(row.get('toar')),
            teudat_zehut=tz_raw,
            member_type=strip_or_none(row.get('sug')),
            phone=strip_or_none(row.get('tel')),
            phone_area=strip_or_none(row.get('tel_kidomet')),
            registration_date=parse_date(row.get('date_klita')),
        )
        db.session.add(m)
        stats['new'] += 1
        batch_count += 1

        if batch_count >= 500:
            db.session.commit()
            batch_count = 0

    db.session.commit()
    print(f"  Imported: {stats['new']} new members ({stats['skip']} already existed)")
    print(f"    - Linked via ztorm_donor_id: {stats['linked_by_ztorm']}")
    print(f"    - Linked via TZ match:        {stats['linked_by_tz']}")
    print(f"    - Translate map hit (no Matat donor yet): {stats['linked_by_translate']}")


# ---------- Hork (Loans) ----------

def import_loans():
    print("\n[6/7] Importing Hork (active loans)...")

    # Build lookup: gmach_card_no → member.id
    members_by_card = {m.gmach_card_no: m.id for m in
                       db.session.query(GemachMember.gmach_card_no, GemachMember.id).all()}
    institutions_by_num = {i.gmach_num_mosad: i.id for i in
                           db.session.query(GemachInstitution.gmach_num_mosad, GemachInstitution.id).all()}
    existing_horks = {l.gmach_num_hork for l in
                      db.session.query(GemachLoan.gmach_num_hork).all()}

    print(f"  {len(members_by_card)} members in DB, {len(institutions_by_num)} institutions")

    stats = {'new': 0, 'skip': 0, 'no_member': 0}
    batch_count = 0

    for row in read_pipe_file(EXTRACT_DIR / 'hork.txt'):
        num_hork = parse_int(row.get('num_hork'))
        if num_hork is None or num_hork in existing_horks:
            stats['skip'] += 1
            continue

        card_no = parse_int(row.get('card_no'))
        member_id = members_by_card.get(card_no)
        if not member_id:
            stats['no_member'] += 1
            continue

        zacai_no = parse_int(row.get('num_zacai'))
        beneficiary_id = members_by_card.get(zacai_no) if zacai_no else None

        mosad_no = parse_int(row.get('num_mosad'))
        institution_id = institutions_by_num.get(mosad_no) if mosad_no else None

        matbea = strip_or_none(row.get('matbea'))
        currency = 'USD' if matbea == '$' else 'ILS'

        l = GemachLoan(
            gmach_num_hork=num_hork,
            member_id=member_id,
            beneficiary_member_id=beneficiary_id,
            institution_id=institution_id,
            status=strip_or_none(row.get('status')) or 'p',
            currency=currency,
            amount=parse_decimal(row.get('schum')) or 0,
            start_date=parse_date(row.get('date_hathala')),
            charge_day=parse_int(row.get('yom')),
            period_months=parse_int(row.get('tkufa')) or 1,
            committed_payments=parse_int(row.get('hithayev')),
            payments_made=parse_int(row.get('buza')) or 0,
            bounces=parse_int(row.get('hazar')) or 0,
            loan_type=strip_or_none(row.get('sug')),
            bank_code=parse_int(row.get('bank')),
            branch_code=parse_int(row.get('snif')),
            account_number=strip_or_none(row.get('heshbon')),
        )
        db.session.add(l)
        stats['new'] += 1
        batch_count += 1

        if batch_count >= 500:
            db.session.commit()
            batch_count = 0

    db.session.commit()
    print(f"  Imported: {stats['new']} new loans ({stats['skip']} already existed, {stats['no_member']} skipped due to missing member)")


# ---------- Btlhork (Cancelled Loans Archive) ----------

def import_cancelled_loans():
    print("\n[7/7] Importing Btlhork (cancelled loans archive)...")

    stats = {'new': 0, 'skip': 0}
    batch_count = 0
    path = EXTRACT_DIR / 'btlhork.txt'
    if not path.exists():
        print("  [SKIP] No btlhork.txt file found.")
        return

    for row in read_pipe_file(path):
        num_hork = parse_int(row.get('num_hork'))
        if num_hork is None:
            stats['skip'] += 1
            continue

        matbea = strip_or_none(row.get('matbea'))
        currency = 'USD' if matbea == '$' else 'ILS'

        c = GemachCancelledLoan(
            gmach_num_hork=num_hork,
            start_date=parse_date(row.get('date_hathala')),
            currency=currency,
            amount=parse_decimal(row.get('schum')),
            committed_payments=parse_int(row.get('hithayev')),
            payments_made=parse_int(row.get('buza')),
            bounces=parse_int(row.get('hazar')),
            last_charge_date=parse_date(row.get('date_hiuv_aharon')),
            asmachta=parse_int(row.get('asmachta')),
            cancellation_reason_code=strip_or_none(row.get('siba')),
            details=strip_or_none(row.get('pratim')),
            loan_type=strip_or_none(row.get('sug')),
            period_months=parse_int(row.get('tkufa')),
        )
        db.session.add(c)
        stats['new'] += 1
        batch_count += 1

        if batch_count >= 500:
            db.session.commit()
            batch_count = 0

    db.session.commit()
    print(f"  Imported: {stats['new']} cancelled loans ({stats['skip']} skipped)")


# ---------- Main ----------

def main():
    print("=" * 60)
    print("GMACH DATA IMPORT")
    print(f"Source: {EXTRACT_DIR}")
    print("=" * 60)

    if not EXTRACT_DIR.exists():
        print(f"ERROR: Extract directory not found: {EXTRACT_DIR}")
        return 1

    with app.app_context():
        # Lookups first
        import_institutions()
        import_cancellation_reasons()
        import_transaction_types()
        import_hash_accounts()

        # Translate map (needed for member linking)
        translate_map = load_translate_map()
        print(f"\nTranslate map loaded: {len(translate_map)} entries")

        # Core data
        import_members(translate_map)
        import_loans()
        import_cancelled_loans()

        # Final summary
        print("\n" + "=" * 60)
        print("FINAL COUNTS")
        print("=" * 60)
        print(f"  Institutions:         {GemachInstitution.query.count()}")
        print(f"  Members:              {GemachMember.query.count()}")
        print(f"    - Linked to Donor:  {GemachMember.query.filter(GemachMember.donor_id.isnot(None)).count()}")
        print(f"    - With ZTorm ID:    {GemachMember.query.filter(GemachMember.ztorm_donor_id.isnot(None)).count()}")
        print(f"  Active loans:         {GemachLoan.query.filter_by(status='p').count()}")
        print(f"  All loans:            {GemachLoan.query.count()}")
        print(f"  Cancelled loans:      {GemachCancelledLoan.query.count()}")
        print(f"  Cancellation reasons: {GemachCancellationReason.query.count()}")
        print(f"  Transaction types:    {GemachTransactionType.query.count()}")
        print(f"  Hash accounts:        {GemachHashAccount.query.count()}")
        print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())

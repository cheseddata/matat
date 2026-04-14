"""
Import ZTorm donors into server MySQL with smart merge.
- Match by email, phone, TZ, or name
- If match: merge ZTorm fields into existing donor, set ztorm_donor_id
- If no match: create new donor with ztorm_donor_id
- Always preserve ztorm_donor_id as link back to Access
"""
import os
import sys
from datetime import datetime

# Add app to path
sys.path.insert(0, '/var/www/matat')
os.environ['FLASK_APP'] = 'run.py'

from app import create_app
from app.extensions import db
from app.models import Donor

app = create_app()

def load_tormim():
    """Load ZTorm donor data from ID mapping file."""
    donors = []
    with open('/var/www/matat/zt_tormim.txt', 'r', encoding='utf-8-sig') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 5 and parts[0].strip():
                donors.append({
                    'num_torem': int(parts[0].strip()),
                    'tz': parts[1].strip() or None,
                    'last_name': parts[2].strip() or 'Unknown',
                    'first_name': parts[3].strip() or '',
                    'email': parts[4].strip() or None,
                })
    return donors

def normalize_phone(phone):
    """Normalize phone for comparison."""
    if not phone:
        return None
    return phone.replace('-', '').replace(' ', '').replace('+972', '0').strip()[-7:]

def normalize_email(email):
    if not email:
        return None
    return email.strip().lower()

def find_matching_donor(zt_donor):
    """Find existing Matat donor matching this ZTorm donor."""
    # 1. Match by TZ (highest confidence)
    if zt_donor['tz'] and len(str(zt_donor['tz'])) >= 5:
        match = Donor.query.filter(
            Donor.teudat_zehut == str(zt_donor['tz']),
            Donor.deleted_at.is_(None)
        ).first()
        if match:
            return match, 'tz'

    # 2. Match by email
    if zt_donor['email']:
        email_norm = normalize_email(zt_donor['email'])
        match = Donor.query.filter(
            db.func.lower(Donor.email) == email_norm,
            Donor.deleted_at.is_(None)
        ).first()
        if match:
            return match, 'email'

    # 3. Match by exact name
    if zt_donor['last_name'] and zt_donor['first_name']:
        match = Donor.query.filter(
            Donor.last_name == zt_donor['last_name'],
            Donor.first_name == zt_donor['first_name'],
            Donor.deleted_at.is_(None)
        ).first()
        if match:
            return match, 'name'

    return None, None

def import_donors():
    print('=' * 60)
    print('ZTorm Donor Import with Merge')
    print('=' * 60)

    tormim = load_tormim()
    print(f'ZTorm donors to import: {len(tormim)}')

    existing_count = Donor.query.filter(Donor.deleted_at.is_(None)).count()
    print(f'Existing Matat donors: {existing_count}')

    # Check if already imported
    already_imported = Donor.query.filter(Donor.ztorm_donor_id.isnot(None)).count()
    if already_imported > 0:
        print(f'WARNING: {already_imported} donors already have ztorm_donor_id set')
        print('Skipping those to avoid duplicates')

    stats = {'merged': 0, 'created': 0, 'skipped': 0, 'errors': 0}
    merge_details = {'tz': 0, 'email': 0, 'name': 0}

    for i, zt in enumerate(tormim):
        try:
            # Skip if this ztorm_donor_id is already in the system
            existing_zt = Donor.query.filter_by(ztorm_donor_id=zt['num_torem']).first()
            if existing_zt:
                stats['skipped'] += 1
                continue

            # Try to find a matching existing donor
            match, match_type = find_matching_donor(zt)

            if match:
                # Merge: update existing donor with ZTorm data
                match.ztorm_donor_id = zt['num_torem']

                # Only fill in missing fields, don't overwrite existing data
                if not match.teudat_zehut and zt['tz']:
                    match.teudat_zehut = str(zt['tz'])
                if not match.first_name or match.first_name == 'Unknown':
                    match.first_name = zt['first_name']
                if not match.last_name or match.last_name == 'Unknown':
                    match.last_name = zt['last_name']
                if not match.email and zt['email']:
                    match.email = zt['email']

                stats['merged'] += 1
                merge_details[match_type] += 1
            else:
                # Create new donor
                donor = Donor(
                    ztorm_donor_id=zt['num_torem'],
                    first_name=zt['first_name'] or '',
                    last_name=zt['last_name'] or 'Unknown',
                    email=zt['email'] or f'ztorm_{zt["num_torem"]}@placeholder.local',
                    teudat_zehut=str(zt['tz']) if zt['tz'] else None,
                    country='IL',
                    language_pref='he',
                    send_mail=True,
                )
                db.session.add(donor)
                stats['created'] += 1

            if (i + 1) % 200 == 0:
                db.session.flush()
                print(f'  Processed {i + 1}/{len(tormim)}...')

        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] < 10:
                print(f'  Error on donor {zt['num_torem']}: {e}')

    db.session.commit()

    final_count = Donor.query.filter(Donor.deleted_at.is_(None)).count()
    ztorm_count = Donor.query.filter(Donor.ztorm_donor_id.isnot(None)).count()

    print()
    print('=' * 60)
    print('IMPORT RESULTS')
    print('=' * 60)
    print(f'  Merged with existing: {stats[merged]}')
    print(f'    - by TZ:    {merge_details[tz]}')
    print(f'    - by Email:  {merge_details[email]}')
    print(f'    - by Name:   {merge_details[name]}')
    print(f'  Created new:          {stats[created]}')
    print(f'  Skipped (already):    {stats[skipped]}')
    print(f'  Errors:               {stats[errors]}')
    print(f'  Total donors now:     {final_count}')
    print(f'  With ztorm_donor_id:  {ztorm_count}')
    print('=' * 60)

if __name__ == '__main__':
    with app.app_context():
        import_donors()

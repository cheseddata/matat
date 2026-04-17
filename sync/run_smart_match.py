"""Re-link Gemach members to Matat donors after a sync.

Matches in this priority order, first hit wins:
  1. ztorm_donor_id  (from the Translate cross-reference table)
  2. teudat_zehut    (Israeli ID number)
  3. normalized phone (last 9 digits, strips +972 country code)

Portable: uses sys.path relative to this script so it works from any
install root.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MATAT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(MATAT_DIR))
os.chdir(MATAT_DIR)

from app import create_app
from app.extensions import db
from app.models import GemachMember, Donor


def norm_phone(p):
    if not p:
        return None
    d = re.sub(r'\D', '', str(p))
    if len(d) < 7:
        return None
    if d.startswith('972'):
        d = '0' + d[3:]
    return d[-9:] if len(d) >= 9 else d


def main():
    app = create_app('development')
    with app.app_context():
        total = GemachMember.query.count()
        before = GemachMember.query.filter(GemachMember.donor_id.isnot(None)).count()
        print(f'Before: {before:,} / {total:,} linked')

        # 1. ztorm_donor_id
        n1 = 0
        for m in GemachMember.query.filter(
            GemachMember.ztorm_donor_id.isnot(None),
            GemachMember.donor_id.is_(None),
        ).all():
            d = Donor.query.filter(Donor.ztorm_donor_id == m.ztorm_donor_id).first()
            if d:
                m.donor_id = d.id
                n1 += 1
        db.session.commit()

        # 2. teudat_zehut
        n2 = 0
        for m in GemachMember.query.filter(
            GemachMember.teudat_zehut.isnot(None),
            GemachMember.teudat_zehut != '',
            GemachMember.donor_id.is_(None),
        ).all():
            d = Donor.query.filter(Donor.teudat_zehut == m.teudat_zehut).first()
            if d:
                m.donor_id = d.id
                n2 += 1
        db.session.commit()

        # 3. phone (normalized)
        by_phone = {}
        for d in Donor.query.filter(Donor.phone.isnot(None)).all():
            np = norm_phone(d.phone)
            if np and np not in by_phone:
                by_phone[np] = d.id
        n3 = 0
        for m in GemachMember.query.filter(
            GemachMember.donor_id.is_(None),
            GemachMember.phone.isnot(None),
        ).all():
            np = norm_phone(m.phone)
            if np and np in by_phone:
                m.donor_id = by_phone[np]
                n3 += 1
        db.session.commit()

        after = GemachMember.query.filter(GemachMember.donor_id.isnot(None)).count()
        print(f'Linked: +{n1} (ZTorm) +{n2} (TZ) +{n3} (phone)')
        print(f'After:  {after:,} / {total:,} = {100 * after / max(total, 1):.1f}%')


if __name__ == '__main__':
    main()

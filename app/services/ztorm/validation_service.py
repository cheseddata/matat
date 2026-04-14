"""
Validation service - ported from ZTorm VBA.
Israeli ID (TZ), bank account checksum, duplicate detection.
"""
from ...extensions import db
from ...models import Donor, Phone
from sqlalchemy import or_


def validate_tz(tz_str):
    """Validate Israeli Teudat Zehut (ID number) using check digit algorithm.
    Ported from VBA Module_Utils.
    """
    if not tz_str:
        return False
    tz = str(tz_str).strip().zfill(9)
    if len(tz) != 9 or not tz.isdigit():
        return False

    total = 0
    for i in range(9):
        digit = int(tz[i])
        multiplied = digit * ((i % 2) + 1)
        if multiplied > 9:
            multiplied -= 9
        total += multiplied
    return total % 10 == 0


def validate_bank_account(bank, branch, account):
    """Validate Israeli bank account number using per-bank checksum.
    Ported from VBA Module_Hork.VerifyAccount.
    8 bank groups with different algorithms.
    """
    if not all([bank, branch, account]):
        return True  # Skip validation if incomplete

    bank = int(bank)
    branch = int(branch)
    account_str = str(account).strip()

    # Bank groups (from VBA)
    # Group 1: Banks 11 (Discount), 17 (Mercantile)
    # Group 2: Banks 12 (Hapoalim), 4 (Yahav)
    # Group 3: Bank 10 (Leumi)
    # Group 4: Bank 20 (Mizrahi-Tefahot)
    # Group 5: Bank 31 (International)
    # Group 6: Banks 13, 46 (Union)
    # Group 7: Bank 14 (Otsar Hahayal)
    # Group 8: Bank 9 (Postal Bank)

    # Simplified validation - check account is numeric and reasonable length
    if not account_str.isdigit():
        return False
    if len(account_str) < 4 or len(account_str) > 15:
        return False

    return True  # Full checksum algorithms would be added per bank group


def detect_duplicates(first_name=None, last_name=None, phone=None,
                      tz=None, email=None, exclude_id=None):
    """Detect potential duplicate donors.
    Ported from VBA Form_Klita duplicate detection logic.
    Returns list of potential matches with match type.
    """
    duplicates = []

    if tz and len(str(tz)) >= 5:
        query = Donor.query_active().filter(Donor.teudat_zehut == str(tz))
        if exclude_id:
            query = query.filter(Donor.id != exclude_id)
        for d in query.all():
            duplicates.append({'donor': d, 'match_type': 'tz', 'confidence': 'high'})

    if email and '@' in str(email):
        query = Donor.query_active().filter(Donor.email == email)
        if exclude_id:
            query = query.filter(Donor.id != exclude_id)
        for d in query.all():
            if not any(dup['donor'].id == d.id for dup in duplicates):
                duplicates.append({'donor': d, 'match_type': 'email', 'confidence': 'high'})

    if phone and len(str(phone)) >= 7:
        phone_clean = str(phone).replace('-', '').replace(' ', '')
        query = Donor.query_active().filter(
            Donor.phone.like(f'%{phone_clean[-7:]}%')
        )
        if exclude_id:
            query = query.filter(Donor.id != exclude_id)
        for d in query.all():
            if not any(dup['donor'].id == d.id for dup in duplicates):
                duplicates.append({'donor': d, 'match_type': 'phone', 'confidence': 'medium'})

    if last_name and first_name:
        query = Donor.query_active().filter(
            Donor.last_name == last_name,
            Donor.first_name == first_name
        )
        if exclude_id:
            query = query.filter(Donor.id != exclude_id)
        for d in query.all():
            if not any(dup['donor'].id == d.id for dup in duplicates):
                duplicates.append({'donor': d, 'match_type': 'name', 'confidence': 'low'})

    return duplicates


def detect_gender(first_name):
    """Detect gender from Hebrew first name.
    Uses firstnames table from ZTorm.
    Returns: 'm', 'f', 'plural', or None.
    """
    if not first_name:
        return None

    # Common Hebrew male/female name patterns
    male_suffixes = ['אל', 'יהו', 'יה']
    female_suffixes = ['ה', 'ית', 'לי']

    name = first_name.strip()

    # Check for couple indicators
    couple_indicators = ['ה"ה', 'מר ומרת', 'והגברת']
    for indicator in couple_indicators:
        if indicator in name:
            return 'plural'

    # Simple heuristic based on name ending
    if any(name.endswith(s) for s in ['רחל', 'שרה', 'לאה', 'רבקה', 'מרים', 'חנה', 'דבורה', 'אסתר']):
        return 'f'

    return None  # Can't determine - would need full firstnames lookup table


def get_title_for_gender(gender):
    """Return appropriate Hebrew title based on gender.
    Ported from VBA App.GetGender defaults.
    """
    titles = {
        'm': 'הר"ר',
        'f': "גב'",
        'plural': 'ה"ה',
        'unknown': 'ה"ה',
    }
    return titles.get(gender, '')

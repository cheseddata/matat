"""Date formatting helpers — locale-aware Gregorian + Hebrew calendar.

Used by templates via the `format_date` and `hebrew_date` Jinja globals
injected by `app.utils.i18n.inject_i18n`.
"""
from datetime import date, datetime


# Map of stored preference values → strftime patterns. The keys are
# what gets persisted to User.date_format / what the salesperson form
# sends; the values are the actual format strings.
_DATE_PATTERNS = {
    'mm/dd/yyyy': '%m/%d/%Y',   # US
    'dd/mm/yyyy': '%d/%m/%Y',   # Israeli / European
    'yyyy-mm-dd': '%Y-%m-%d',   # ISO
    'mm-dd-yyyy': '%m-%d-%Y',
    'dd-mm-yyyy': '%d-%m-%Y',
}


def _resolve_pattern(user_format, lang):
    """Pick a strftime pattern: explicit user preference wins; 'auto' or
    unknown values fall back to the language-based default (US for
    English, Israeli for Hebrew)."""
    pat = _DATE_PATTERNS.get((user_format or '').lower())
    if pat:
        return pat
    return '%d/%m/%Y' if (lang or 'en').lower() == 'he' else '%m/%d/%Y'


def format_date_locale(d, lang='en', with_time=False, user_format='auto'):
    """Format a date/datetime per user preference, falling back to locale.

    Resolution order:
      1. Explicit user_format ('mm/dd/yyyy' / 'dd/mm/yyyy' / 'yyyy-mm-dd'…)
      2. lang ('he' → DD/MM/YYYY, else MM/DD/YYYY)

    Returns empty string for None/falsy inputs.
    """
    if not d:
        return ''
    pattern = _resolve_pattern(user_format, lang)
    if isinstance(d, datetime):
        return d.strftime(pattern + (' %H:%M' if with_time else ''))
    if isinstance(d, date):
        return d.strftime(pattern)
    return str(d)


# Public list for the salesperson form's dropdown — order matters
# (most-common first). Each entry: (stored_value, display_label_key).
DATE_FORMAT_CHOICES = [
    ('auto',        'date_format.auto'),
    ('mm/dd/yyyy',  'date_format.us'),
    ('dd/mm/yyyy',  'date_format.il'),
    ('yyyy-mm-dd',  'date_format.iso'),
]


_HEB_MONTH_TO_NUM = {
    # pyluach's Hebrew month numbering: Nissan=1, Iyar=2, ..., Elul=6,
    # Tishrei=7, ..., Adar=12, Adar II=13 (leap years only). Matches the
    # Torah ordering everyone in the office thinks in, so sorting on the
    # integer puts the months in calendar order for the typical "the
    # year goes Iyar → Sivan → ... → Elul" visual list.
    'ניסן':       1,
    'אייר':       2,
    'סיון':       3,
    'סיוון':      3,
    'תמוז':       4,
    'אב':         5,
    'מנחם אב':    5,
    'אלול':       6,
    'תשרי':       7,
    'מרחשון':     8,
    'חשון':       8,
    'חשוון':      8,
    'כסלו':       9,
    'כסליו':      9,
    'טבת':        10,
    'שבט':        11,
    'אדר':        12,
    'אדר א':      12,
    'אדר ב':      13,
    'אדר א\'':    12,
    'אדר ב\'':    13,
}

# Hebrew numerals (gematria) → integer for parsing wedding hebrew_date
# strings like 'כ"ד אייר' (24 Iyar), 'ט"ו תמוז' (15 Tammuz). Gershayim
# (") and gerasym (') are stripped before letter-sum, with the standard
# exceptions for 15 (ט"ו, not י-ה) and 16 (ט"ז, not י-ו).
_HEB_LETTER_VAL = {'א':1, 'ב':2, 'ג':3, 'ד':4, 'ה':5, 'ו':6, 'ז':7, 'ח':8, 'ט':9,
                   'י':10, 'כ':20, 'ל':30}


def parse_hebrew_md(heb_str):
    """Parse a free-text Hebrew date like 'כ"ד אייר' or 'ב\' תמוז' into
    (month_num, day_num) where month_num is in pyluach's 1-13 scheme
    (1=Tishrei, ..., 7=Adar II, 8=Nissan, ..., 13=Elul).

    Returns None for unparseable input. When only a month is given
    (e.g. 'אלול'), day defaults to 1 so month-only entries sort to the
    start of that month.
    """
    if not heb_str:
        return None
    # Normalize gershayim + gerasym + smart quotes; strip whitespace
    s = (heb_str.replace('"', '').replace("'", '')
                 .replace('״', '').replace('׳', '')
                 .strip())
    if not s:
        return None

    parts = s.split(None, 1)
    if len(parts) == 1:
        # Month-only, e.g. 'אלול' — default day to 1
        day_letters = ''
        month_name = parts[0].strip()
    else:
        day_letters, month_name = parts[0].strip(), parts[1].strip()

    # Day from gematria. Special cases for 15 and 16 to honour the
    # traditional ט"ו / ט"ז avoidance of י-ה / י-ו.
    if day_letters == '':
        day_num = 1
    elif day_letters == 'טו':
        day_num = 15
    elif day_letters == 'טז':
        day_num = 16
    else:
        day_num = sum(_HEB_LETTER_VAL.get(c, 0) for c in day_letters)
        if day_num == 0:
            return None

    # Trim trailing 'א'/'ב' qualifier off Adar — handled by the lookup
    # via 'אדר א'/'אדר ב' keys; otherwise lookup will find plain 'אדר'.
    month_num = _HEB_MONTH_TO_NUM.get(month_name)
    if not month_num:
        return None

    return (month_num, day_num)


def parse_hebrew_date_to_gregorian(heb_str, today=None):
    """Convert a free-text Hebrew date into a real Gregorian date.

    Uses the CURRENT Hebrew year (per pyluach's Rosh-Hashanah-rollover
    convention) so dates always sort within the same Jewish year cycle.
    A wedding entered as 'כ"ד אייר' on 26 Iyar 5786 resolves to
    2026-05-11 (this year's Iyar 24) — that's intentionally allowed
    to be slightly in the past so the sort puts the new entry at the
    correct position in the Hebrew calendar order instead of falling
    to the bottom of the list.

    Returns date or None on parse failure.
    """
    md = parse_hebrew_md(heb_str)
    if not md:
        return None
    month_num, day_num = md
    try:
        from pyluach.dates import GregorianDate, HebrewDate
        from datetime import date as _date
        today = today or _date.today()
        current_heb_year = GregorianDate(today.year, today.month, today.day).to_heb().year
        return HebrewDate(current_heb_year, month_num, day_num).to_pydate()
    except Exception:
        return None


def hebrew_date_str(d):
    """Return the Hebrew-calendar date string for a Gregorian date.

    e.g. date(2026, 4, 30) -> "י״ג אייר תשפ״ו"

    Returns empty string for None or on any conversion error (we don't
    want a date-rendering bug to crash the donations list).
    """
    if not d:
        return ''
    try:
        from pyluach.dates import GregorianDate
        if isinstance(d, datetime):
            d = d.date()
        return GregorianDate(d.year, d.month, d.day).to_heb().hebrew_date_string()
    except Exception:
        return ''

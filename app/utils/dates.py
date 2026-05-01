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

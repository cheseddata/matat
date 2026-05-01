"""Date formatting helpers — locale-aware Gregorian + Hebrew calendar.

Used by templates via the `format_date` and `hebrew_date` Jinja globals
injected by `app.utils.i18n.inject_i18n`.
"""
from datetime import date, datetime


def format_date_locale(d, lang='en', with_time=False):
    """Format a date/datetime per locale convention.

    - English (and anything non-Hebrew): MM/DD/YYYY (US convention)
    - Hebrew: DD/MM/YYYY (Israeli convention)

    Returns empty string for None/falsy inputs.
    """
    if not d:
        return ''
    if isinstance(d, datetime):
        if (lang or 'en').lower() == 'he':
            return d.strftime('%d/%m/%Y %H:%M') if with_time else d.strftime('%d/%m/%Y')
        return d.strftime('%m/%d/%Y %H:%M') if with_time else d.strftime('%m/%d/%Y')
    if isinstance(d, date):
        if (lang or 'en').lower() == 'he':
            return d.strftime('%d/%m/%Y')
        return d.strftime('%m/%d/%Y')
    return str(d)


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

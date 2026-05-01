import json
import os
from flask import g, request
from flask_login import current_user

_translations = {}
_translations_mtime = 0


def _i18n_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'i18n')


def _dir_mtime(path):
    """Max mtime of .json files in directory (cheap change-detector)."""
    max_mt = 0
    try:
        for fn in os.listdir(path):
            if fn.endswith('.json'):
                mt = os.path.getmtime(os.path.join(path, fn))
                if mt > max_mt:
                    max_mt = mt
    except OSError:
        pass
    return max_mt


def load_translations(force=False):
    """Load all translation files. Reloads when JSON files change on disk."""
    global _translations, _translations_mtime
    d = _i18n_dir()
    current_mt = _dir_mtime(d)
    if not force and _translations and current_mt <= _translations_mtime:
        return
    new_trans = {}
    for filename in os.listdir(d):
        if filename.endswith('.json'):
            lang = filename.replace('.json', '')
            filepath = os.path.join(d, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                new_trans[lang] = json.load(f)
    _translations = new_trans
    _translations_mtime = current_mt


def get_locale():
    """Get current user's locale."""
    # Check request args for language override (highest priority)
    try:
        lang = request.args.get('lang')
        if lang in ('en', 'he'):
            return lang
    except RuntimeError:
        pass

    # Check cookie for language preference
    try:
        lang = request.cookies.get('lang')
        if lang in ('en', 'he'):
            return lang
    except RuntimeError:
        pass

    # Check if user is logged in and has a language preference
    try:
        if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            if hasattr(current_user, 'language_pref') and current_user.language_pref:
                return current_user.language_pref
    except RuntimeError:
        # Outside of request context
        pass

    # Default to English
    return 'en'


def get_text(key, lang=None):
    """
    Get translated text by dot-notation key.

    Example:
        get_text('receipt.title', 'he') -> 'קבלה על תרומה'
    """
    # Always refresh on mtime change (cheap: 1 stat per request) so edits
    # to en.json/he.json take effect without restarting the Flask process.
    load_translations()

    # Use provided lang or detect from user
    if lang is None:
        lang = get_locale()

    # Fallback to English if language not found
    translations = _translations.get(lang, _translations.get('en', {}))

    # Navigate nested keys
    keys = key.split('.')
    value = translations
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, None)
            if value is None:
                # Try English fallback
                en_trans = _translations.get('en', {})
                for k2 in keys:
                    if isinstance(en_trans, dict):
                        en_trans = en_trans.get(k2, key)
                    else:
                        return key
                return en_trans if isinstance(en_trans, str) else key
        else:
            return key

    return value if isinstance(value, str) else key


def t(key, lang=None):
    """Shorthand for get_text."""
    return get_text(key, lang)


def is_rtl(lang=None):
    """Check if language is RTL."""
    if lang is None:
        lang = get_locale()
    return lang == 'he'


def init_i18n(app):
    """Initialize i18n for the Flask app."""
    # Prime the cache at startup so first request is fast.
    load_translations(force=True)

    @app.context_processor
    def inject_i18n():
        """Inject translation functions + global flags into templates."""
        lang = get_locale()
        try:
            from .sandbox import is_sandbox
            sbx = is_sandbox()
        except Exception:
            sbx = False

        # Processors the current user is allowed to see — used by the
        # always-visible processor tab strip rendered under the nav bar in
        # base.html. Empty for unauthenticated requests.
        nav_processors = []
        try:
            from flask_login import current_user
            if current_user.is_authenticated:
                from ..models.payment_processor import PaymentProcessor
                nav_processors = [
                    p for p in PaymentProcessor.get_enabled()
                    if current_user.can_view_processor(p.code)
                ]
        except Exception:
            nav_processors = []

        # Locale-aware date helpers + Hebrew-calendar conversion. Bound
        # late so the lang variable is captured per-request.
        from .dates import format_date_locale, hebrew_date_str
        def _fmt_date(d, with_time=False):
            return format_date_locale(d, lang=lang, with_time=with_time)
        def _fmt_datetime(d):
            return format_date_locale(d, lang=lang, with_time=True)

        return {
            't': t,
            'lang': lang,
            'is_rtl': is_rtl(lang),
            'text_dir': 'rtl' if is_rtl(lang) else 'ltr',
            'sandbox_mode': sbx,
            'nav_processors': nav_processors,
            'format_date': _fmt_date,
            'format_datetime': _fmt_datetime,
            'hebrew_date': hebrew_date_str,
        }

import json
import os
from flask import g, request
from flask_login import current_user

_translations = {}


def load_translations():
    """Load all translation files."""
    global _translations
    i18n_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'i18n')

    for filename in os.listdir(i18n_dir):
        if filename.endswith('.json'):
            lang = filename.replace('.json', '')
            filepath = os.path.join(i18n_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                _translations[lang] = json.load(f)


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
    if not _translations:
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

    @app.context_processor
    def inject_i18n():
        """Inject translation functions into templates."""
        lang = get_locale()
        return {
            't': t,
            'lang': lang,
            'is_rtl': is_rtl(lang),
            'text_dir': 'rtl' if is_rtl(lang) else 'ltr'
        }

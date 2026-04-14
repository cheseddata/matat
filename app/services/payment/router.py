"""
Payment processor router.
User selects which processor to use. System manages available processors.
"""
from .shva_processor import ShvaProcessor
from .creditguard_processor import CreditGuardProcessor
from .yaad_processor import YaadProcessor
from .pelecard_processor import PelecardProcessor


# Registry of all available processors
PROCESSOR_REGISTRY = {
    'shva': {
        'class': ShvaProcessor,
        'name': 'Shva/Ashrait',
        'name_he': 'שב"א / אשראית',
        'description': 'Israeli credit card processing via Shva network',
        'description_he': 'עיבוד כרטיסי אשראי דרך רשת שב"א',
        'country': 'IL',
        'type': 'credit_card',
        'icon': 'fa-credit-card',
        'color': '#2E5090',
    },
    'creditguard': {
        'class': CreditGuardProcessor,
        'name': 'CreditGuard (Hyp)',
        'name_he': 'קרדיטגארד (Hyp)',
        'description': 'Leading Israeli payment gateway, XML API',
        'description_he': 'שער תשלומים ישראלי מוביל, ממשק XML',
        'country': 'IL',
        'type': 'credit_card',
        'icon': 'fa-shield-halved',
        'color': '#1B5E20',
    },
    'yaad': {
        'class': YaadProcessor,
        'name': 'Yaad (iCard)',
        'name_he': 'יעד (iCard)',
        'description': 'Simple REST API, popular with Israeli nonprofits',
        'description_he': 'ממשק REST פשוט, פופולרי בעמותות',
        'country': 'IL',
        'type': 'credit_card',
        'icon': 'fa-credit-card',
        'color': '#FF6F00',
    },
    'pelecard': {
        'class': PelecardProcessor,
        'name': 'Pelecard',
        'name_he': 'פלאקארד',
        'description': 'Israeli processor with 35+ years, JSON REST API',
        'description_he': 'מעבד ישראלי ותיק, ממשק JSON REST',
        'country': 'IL',
        'type': 'credit_card',
        'icon': 'fa-building-columns',
        'color': '#4A148C',
    },
}


def get_processor(code, config=None):
    """Get a processor instance by code."""
    if code not in PROCESSOR_REGISTRY:
        raise ValueError(f"Unknown processor: {code}")

    proc_info = PROCESSOR_REGISTRY[code]
    return proc_info['class'](config=config)


def get_available_processors(enabled_only=True):
    """Get list of available processors."""
    processors = []
    for code, info in PROCESSOR_REGISTRY.items():
        processors.append({
            'code': code,
            'name': info['name'],
            'name_he': info['name_he'],
            'description': info['description'],
            'description_he': info['description_he'],
            'country': info['country'],
            'type': info['type'],
            'icon': info['icon'],
            'color': info['color'],
        })
    return processors


def get_default_processor():
    """Get the default processor code."""
    return 'shva'

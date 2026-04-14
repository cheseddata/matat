"""
Payment processor router.
User selects which processor to use. System manages available processors.
"""
from .shva_processor import ShvaProcessor


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
    # These will be added when we integrate from Matat server:
    # 'stripe': Stripe (international)
    # 'nedarim': Nedarim Plus (Israeli nonprofits)
    # 'cardcom': CardCom (auto Section 46 receipts)
    # 'grow': Grow/Meshulam (most popular Israel)
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

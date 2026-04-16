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
    """Get a processor instance by code.

    When SANDBOX_MODE is active, every processor is wrapped so that
    create_payment() returns a fake-success response without hitting the
    real gateway. All other methods still run as normal (validation,
    client_config, etc.) to preserve the operator's UX.
    """
    if code not in PROCESSOR_REGISTRY:
        raise ValueError(f"Unknown processor: {code}")

    proc_info = PROCESSOR_REGISTRY[code]
    instance = proc_info['class'](config=config)

    from ...utils.sandbox import is_sandbox, sandbox_charge_success
    if is_sandbox():
        # Monkey-patch just the money-moving method on this instance.
        real_name = instance.name

        def _sandbox_charge(amount, currency, card_data, donor_data=None, **kwargs):
            return sandbox_charge_success(
                amount=amount, currency=currency,
                processor=real_name, sandbox_note='SANDBOX_MODE active'
            )

        def _sandbox_refund(transaction_id, amount=None):
            return {'success': True, 'sandbox': True,
                    'refund_id': f'sbx_refund_{transaction_id}'}

        instance.create_payment = _sandbox_charge
        instance.refund = _sandbox_refund

    return instance


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

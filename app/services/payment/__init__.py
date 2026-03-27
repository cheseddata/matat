"""
Multi-processor payment system.

Supports multiple payment processors with table-driven routing rules.
Designed for multi-platform deployment where each client enables different processors.

Credit Card Processors:
- Stripe (international, credit cards)
- Nedarim Plus (Israeli nonprofits, iframe)
- CardCom (Israeli, auto Section 46 receipts)
- Grow/Meshulam (Israeli, most popular, Bit/Apple/Google Pay)
- Tranzila (Israeli, oldest gateway)
- PayMe (Israeli, hosted fields)
- iCount (Israeli, payment + invoicing combined)
- EasyCard (Israeli, PCI Level 1)

DAF / Charity Card Processors:
- The Donors Fund (Jewish DAF, username+PIN or card+CVV)
- Matbia (Jewish charity cards, NFC)
- Chariot/DAFpay (Universal DAF - 1,151+ providers including OJC, JCF, Fidelity, Schwab)
"""
from .base import BasePaymentProcessor
from .router import PaymentRouter, route_payment, get_processor, PROCESSOR_CLASSES
# Credit card processors
from .stripe_processor import StripeProcessor
from .nedarim_processor import NedarimProcessor
from .cardcom_processor import CardComProcessor
from .grow_processor import GrowProcessor
from .tranzila_processor import TranzilaProcessor
from .payme_processor import PayMeProcessor
from .icount_processor import ICountProcessor
from .easycard_processor import EasyCardProcessor
# DAF / charity card processors
from .donorsfund_processor import DonorsFundProcessor
from .matbia_processor import MatbiaProcessor
from .chariot_processor import ChariotProcessor

__all__ = [
    # Base and router
    'BasePaymentProcessor',
    'PaymentRouter',
    'route_payment',
    'get_processor',
    'PROCESSOR_CLASSES',
    # Credit card processors
    'StripeProcessor',
    'NedarimProcessor',
    'CardComProcessor',
    'GrowProcessor',
    'TranzilaProcessor',
    'PayMeProcessor',
    'ICountProcessor',
    'EasyCardProcessor',
    # DAF / charity card processors
    'DonorsFundProcessor',
    'MatbiaProcessor',
    'ChariotProcessor',
]

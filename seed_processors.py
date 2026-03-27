#!/usr/bin/env python3
"""Seed payment processors."""
from app import create_app
from app.extensions import db
from app.models import PaymentProcessor, PaymentRoutingRule

app = create_app('development')

with app.app_context():
    # Check if Stripe processor exists
    existing_stripe = PaymentProcessor.query.filter_by(code='stripe').first()
    if existing_stripe:
        print("Stripe processor already exists. Skipping...")
    else:
        # Create Stripe processor (default)
        stripe_proc = PaymentProcessor(
            code='stripe',
            name='Stripe',
            enabled=True,
            priority=10,  # High priority (lower number = higher priority)
            supported_currencies=['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'ILS'],
            supported_countries=['*'],  # All countries
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.9,
            fee_fixed_cents=30,
            fee_currency='USD',
            display_order=1,
            display_name='Credit Card',
        )
        db.session.add(stripe_proc)
        print("Created Stripe processor")

    # Check if Nedarim processor exists
    existing_nedarim = PaymentProcessor.query.filter_by(code='nedarim').first()
    if existing_nedarim:
        print("Nedarim processor already exists. Skipping...")
    else:
        # Create Nedarim Plus processor (disabled until credentials obtained)
        nedarim_proc = PaymentProcessor(
            code='nedarim',
            name='Nedarim Plus',
            enabled=False,  # Disabled until credentials obtained
            priority=5,  # Higher priority than Stripe when enabled
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL', 'US', '*'],  # Works internationally
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.0,  # Estimate
            fee_fixed_cents=50,  # Estimate in agorot
            fee_currency='ILS',
            display_order=2,
            display_name='Nedarim Plus (Israel)',
            organization_country='IL',
            config_json={
                'mosad_id': None,  # To be configured
                'api_password': None,  # To be configured
            }
        )
        db.session.add(nedarim_proc)
        print("Created Nedarim Plus processor (disabled)")

    # CardCom processor
    existing_cardcom = PaymentProcessor.query.filter_by(code='cardcom').first()
    if existing_cardcom:
        print("CardCom processor already exists. Skipping...")
    else:
        cardcom_proc = PaymentProcessor(
            code='cardcom',
            name='CardCom',
            enabled=False,
            priority=15,
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL'],
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.5,
            fee_fixed_cents=30,
            fee_currency='ILS',
            display_order=3,
            display_name='CardCom (Section 46 Receipts)',
            organization_country='IL',
            processor_type='credit_card',
        )
        db.session.add(cardcom_proc)
        print("Created CardCom processor (disabled)")

    # Grow/Meshulam processor
    existing_grow = PaymentProcessor.query.filter_by(code='grow').first()
    if existing_grow:
        print("Grow processor already exists. Skipping...")
    else:
        grow_proc = PaymentProcessor(
            code='grow',
            name='Grow (Meshulam)',
            enabled=False,
            priority=12,
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL'],
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.5,
            fee_fixed_cents=0,
            fee_currency='ILS',
            display_order=4,
            display_name='Grow (Bit, Apple Pay)',
            organization_country='IL',
            processor_type='credit_card',
        )
        db.session.add(grow_proc)
        print("Created Grow processor (disabled)")

    # Tranzila processor
    existing_tranzila = PaymentProcessor.query.filter_by(code='tranzila').first()
    if existing_tranzila:
        print("Tranzila processor already exists. Skipping...")
    else:
        tranzila_proc = PaymentProcessor(
            code='tranzila',
            name='Tranzila',
            enabled=False,
            priority=20,
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL'],
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.5,
            fee_fixed_cents=30,
            fee_currency='ILS',
            display_order=5,
            display_name='Tranzila',
            organization_country='IL',
            processor_type='credit_card',
        )
        db.session.add(tranzila_proc)
        print("Created Tranzila processor (disabled)")

    # PayMe processor
    existing_payme = PaymentProcessor.query.filter_by(code='payme').first()
    if existing_payme:
        print("PayMe processor already exists. Skipping...")
    else:
        payme_proc = PaymentProcessor(
            code='payme',
            name='PayMe',
            enabled=False,
            priority=18,
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL'],
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.5,
            fee_fixed_cents=30,
            fee_currency='ILS',
            display_order=6,
            display_name='PayMe',
            organization_country='IL',
            processor_type='credit_card',
        )
        db.session.add(payme_proc)
        print("Created PayMe processor (disabled)")

    # iCount processor
    existing_icount = PaymentProcessor.query.filter_by(code='icount').first()
    if existing_icount:
        print("iCount processor already exists. Skipping...")
    else:
        icount_proc = PaymentProcessor(
            code='icount',
            name='iCount',
            enabled=False,
            priority=25,
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL'],
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.5,
            fee_fixed_cents=30,
            fee_currency='ILS',
            display_order=7,
            display_name='iCount (Payment + Invoicing)',
            organization_country='IL',
            processor_type='credit_card',
        )
        db.session.add(icount_proc)
        print("Created iCount processor (disabled)")

    # EasyCard processor
    existing_easycard = PaymentProcessor.query.filter_by(code='easycard').first()
    if existing_easycard:
        print("EasyCard processor already exists. Skipping...")
    else:
        easycard_proc = PaymentProcessor(
            code='easycard',
            name='EasyCard',
            enabled=False,
            priority=22,
            supported_currencies=['ILS', 'USD'],
            supported_countries=['IL'],
            supports_recurring=True,
            supports_refunds=True,
            fee_percentage=2.5,
            fee_fixed_cents=30,
            fee_currency='ILS',
            display_order=8,
            display_name='EasyCard (PCI Level 1)',
            organization_country='IL',
            processor_type='credit_card',
        )
        db.session.add(easycard_proc)
        print("Created EasyCard processor (disabled)")

    # ============ DAF PROCESSORS ============

    # The Donors Fund (DAF)
    existing_donorsfund = PaymentProcessor.query.filter_by(code='donors_fund').first()
    if existing_donorsfund:
        print("Donors Fund processor already exists. Skipping...")
    else:
        donorsfund_proc = PaymentProcessor(
            code='donors_fund',
            name='The Donors Fund',
            enabled=False,
            priority=50,
            supported_currencies=['USD'],
            supported_countries=['US'],
            supports_recurring=True,
            supports_refunds=True,  # Via PUT /cancel
            fee_percentage=2.9,
            fee_fixed_cents=0,
            fee_currency='USD',
            display_order=10,
            display_name='The Donors Fund (DAF)',
            organization_country='US',
            processor_type='daf',
            config_json={
                'validation_token': None,  # To be configured
                'account_number': None,
                'tax_id': None,
                'sandbox': True,  # Start in sandbox
            }
        )
        db.session.add(donorsfund_proc)
        print("Created Donors Fund DAF processor (disabled)")

    # Matbia (Charity Card)
    existing_matbia = PaymentProcessor.query.filter_by(code='matbia').first()
    if existing_matbia:
        print("Matbia processor already exists. Skipping...")
    else:
        matbia_proc = PaymentProcessor(
            code='matbia',
            name='Matbia',
            enabled=False,
            priority=55,
            supported_currencies=['USD'],
            supported_countries=['US'],
            supports_recurring=True,
            supports_refunds=False,  # Manual refunds
            fee_percentage=2.9,
            fee_fixed_cents=30,
            fee_currency='USD',
            display_order=11,
            display_name='Matbia Charity Card',
            organization_country='US',
            processor_type='daf',
            config_json={
                'api_key': None,  # To be configured
                'org_handle': None,
                'sandbox': True,
            }
        )
        db.session.add(matbia_proc)
        print("Created Matbia processor (disabled)")

    # Chariot/DAFpay (Universal DAF)
    existing_chariot = PaymentProcessor.query.filter_by(code='chariot').first()
    if existing_chariot:
        print("Chariot processor already exists. Skipping...")
    else:
        chariot_proc = PaymentProcessor(
            code='chariot',
            name='DAFpay (Chariot)',
            enabled=False,
            priority=45,  # Higher priority than other DAFs (most versatile)
            supported_currencies=['USD', 'ILS'],
            supported_countries=['US', 'IL'],
            supports_recurring=False,  # DAF grants are one-time
            supports_refunds=False,  # Cannot refund DAF grants via API
            fee_percentage=2.9,
            fee_fixed_cents=0,
            fee_currency='USD',
            display_order=9,  # Show first in DAF section
            display_name='DAFpay (1,151+ DAF Providers)',
            organization_country='US',
            processor_type='daf_aggregator',
            config_json={
                'api_key': None,  # To be configured
                'connect_id': None,  # Generated via API
                'ein': None,  # Your nonprofit EIN
                'sandbox': True,
            }
        )
        db.session.add(chariot_proc)
        print("Created Chariot/DAFpay processor (disabled)")

    db.session.commit()

    # Check if routing rules exist
    existing_rules = PaymentRoutingRule.query.count()
    if existing_rules > 0:
        print(f"{existing_rules} routing rules already exist. Skipping...")
    else:
        # Get processor IDs
        stripe = PaymentProcessor.query.filter_by(code='stripe').first()
        nedarim = PaymentProcessor.query.filter_by(code='nedarim').first()

        # Create default routing rules
        rules = []

        # Rule 1: ILS currency -> Nedarim (when enabled)
        if nedarim:
            rules.append(PaymentRoutingRule(
                name='ILS -> Nedarim Plus',
                description='Route Israeli Shekel donations to Nedarim Plus',
                priority=10,
                enabled=True,
                currency='ILS',
                processor_id=nedarim.id,
            ))

        # Rule 2: Israel country -> Nedarim (when enabled)
        if nedarim:
            rules.append(PaymentRoutingRule(
                name='Israel -> Nedarim Plus',
                description='Route donations from Israel to Nedarim Plus',
                priority=20,
                enabled=True,
                country_code='IL',
                processor_id=nedarim.id,
            ))

        # Rule 3: USD -> Stripe (fallback)
        if stripe:
            rules.append(PaymentRoutingRule(
                name='USD -> Stripe',
                description='Route USD donations to Stripe',
                priority=100,
                enabled=True,
                currency='USD',
                processor_id=stripe.id,
            ))

        # Rule 4: Default -> Stripe
        if stripe:
            rules.append(PaymentRoutingRule(
                name='Default -> Stripe',
                description='Default fallback to Stripe for all other donations',
                priority=999,
                enabled=True,
                processor_id=stripe.id,
            ))

        for rule in rules:
            db.session.add(rule)

        db.session.commit()
        print(f"Created {len(rules)} routing rules")

    print("\nPayment processors setup complete!")
    print("\nCurrent processors:")
    for proc in PaymentProcessor.query.all():
        status = "ENABLED" if proc.enabled else "disabled"
        print(f"  - {proc.code}: {proc.name} [{status}]")

    print("\nCurrent routing rules:")
    for rule in PaymentRoutingRule.query.order_by(PaymentRoutingRule.priority).all():
        status = "enabled" if rule.enabled else "disabled"
        print(f"  - [{rule.priority}] {rule.name} -> {rule.processor.code} ({status})")

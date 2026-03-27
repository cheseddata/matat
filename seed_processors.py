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

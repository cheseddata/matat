#!/usr/bin/env python3
"""Seed script: create admin, config, initial data."""
from datetime import datetime
from app import create_app
from app.extensions import db, bcrypt
from app.models import User, ConfigSettings, ReceiptCounter

app = create_app('development')

with app.app_context():
    # Check if already seeded
    existing_config = ConfigSettings.query.first()
    if existing_config:
        print("Database already seeded. Skipping...")
    else:
        # Create config settings
        config = ConfigSettings(
            org_name='Matat Mordechai',
            org_prefix='MM',
            tax_id='XX-XXXXXXX',  # Placeholder - admin should update
            stripe_mode='test',
            default_commission_type='percentage',
            default_commission_rate=10.00,
            default_language='en'
        )
        db.session.add(config)
        
        # Create admin user
        admin = User(
            username='admin',
            password_hash=bcrypt.generate_password_hash('changeme123').decode('utf-8'),
            role='admin',
            first_name='Admin',
            last_name='User',
            email='admin@matatmordechai.org',
            is_temp_password=True,
            active=True
        )
        db.session.add(admin)
        
        # Create receipt counter for current year
        current_year = datetime.now().year
        receipt_counter = ReceiptCounter(
            org_prefix='MM',
            fiscal_year=current_year,
            last_sequence=0
        )
        db.session.add(receipt_counter)
        
        db.session.commit()
        print(f"Database seeded successfully!")
        print(f"  - Config created: {config.org_name}")
        print(f"  - Admin user created: {admin.username} (password: changeme123)")
        print(f"  - Receipt counter initialized: {receipt_counter.org_prefix}-{receipt_counter.fiscal_year}")

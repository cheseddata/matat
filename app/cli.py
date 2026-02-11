"""CLI commands for the application."""
import csv
import click
from flask import current_app
from flask.cli import with_appcontext
from .extensions import db
from .models.donor import Donor


@click.command('import-donors')
@click.argument('csv_file', type=click.Path(exists=True))
@with_appcontext
def import_donors_cmd(csv_file):
    """Import donors from Stripe CSV export (unified_payments.csv)."""
    imported = 0
    skipped = 0
    errors = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                email = row.get('Customer Email', '').strip()
                if not email:
                    skipped += 1
                    continue

                # Check if donor already exists
                existing = Donor.query.filter_by(email=email).first()
                if existing:
                    skipped += 1
                    continue

                # Parse name from Card Name field
                card_name = row.get('Card Name', '').strip()
                if card_name:
                    name_parts = card_name.split(' ', 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                else:
                    first_name = 'Unknown'
                    last_name = ''

                # Create donor with test=False (real customer)
                donor = Donor(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    address_line1=row.get('Card Address Line1', '').strip() or None,
                    address_line2=row.get('Card Address Line2', '').strip() or None,
                    city=row.get('Card Address City', '').strip() or None,
                    state=row.get('Card Address State', '').strip() or None,
                    zip=row.get('Card Address Zip', '').strip() or None,
                    country=row.get('Card Address Country', 'US').strip() or 'US',
                    stripe_customer_id=row.get('Customer ID', '').strip() or None,
                    test=False  # Real customers
                )

                db.session.add(donor)
                imported += 1

            except Exception as e:
                errors += 1
                click.echo(f"Error processing row: {e}")

        db.session.commit()

    click.echo(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")


def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(import_donors_cmd)

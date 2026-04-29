"""CLI commands for the application."""
import csv
import click
from datetime import datetime
from flask import current_app
from flask.cli import with_appcontext
from .extensions import db
from .models.donor import Donor
from .models.donation import Donation


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


@click.command('import-donations')
@click.argument('csv_file', type=click.Path(exists=True))
@with_appcontext
def import_donations_cmd(csv_file):
    """Import donations from Stripe CSV export (unified_payments.csv)."""
    imported = 0
    skipped = 0
    errors = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                email = row.get('Customer Email', '').strip()
                status = row.get('Status', '').strip().lower()
                payment_intent_id = row.get('PaymentIntent ID', '').strip()

                if not email or status != 'paid':
                    skipped += 1
                    continue

                # Skip if donation already exists (by payment intent ID)
                if payment_intent_id:
                    existing = Donation.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
                    if existing:
                        skipped += 1
                        continue

                # Find or create donor
                donor = Donor.query.filter_by(email=email).first()
                if not donor:
                    # Create donor if doesn't exist
                    card_name = row.get('Card Name', '').strip()
                    if card_name:
                        name_parts = card_name.split(' ', 1)
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                    else:
                        first_name = 'Unknown'
                        last_name = ''

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
                        test=False
                    )
                    db.session.add(donor)
                    db.session.flush()

                # Parse amount (in dollars, convert to cents)
                amount_str = row.get('Amount', '0').replace(',', '')
                amount_cents = int(float(amount_str) * 100)

                # Parse fee (in dollars, convert to cents)
                fee_str = row.get('Fee', '0').replace(',', '')
                fee_cents = int(float(fee_str) * 100)

                # Parse date
                date_str = row.get('Created date (UTC)', '')
                if date_str:
                    try:
                        created_at = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        created_at = datetime.utcnow()
                else:
                    created_at = datetime.utcnow()

                # Get payment method info
                card_brand = row.get('Card Brand', '').strip() or None
                card_last4 = row.get('Card Last4', '').strip() or None
                payment_source = row.get('Payment Source Type', '').strip().lower() or 'card'

                # Create donation
                donation = Donation(
                    donor_id=donor.id,
                    amount=amount_cents,
                    stripe_fee=fee_cents,
                    net_amount=amount_cents - fee_cents,
                    currency=row.get('Currency', 'usd').strip().lower(),
                    status='succeeded',
                    donation_type='one_time',
                    source='stripe_import',
                    stripe_payment_intent_id=payment_intent_id or None,
                    payment_method_type=payment_source,
                    payment_method_brand=card_brand,
                    payment_method_last4=card_last4,
                    created_at=created_at
                )

                db.session.add(donation)
                imported += 1

            except Exception as e:
                errors += 1
                click.echo(f"Error processing row: {e}")

        db.session.commit()

    click.echo(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")


@click.command('sync-nedarim')
@click.option('--with-receipts', is_flag=True, default=False, help='Generate receipts and send emails (off by default)')
@with_appcontext
def sync_nedarim_cmd(with_receipts):
    """Sync transactions from Nedarim Plus API.

    Polls GetHistoryJson to import any transactions we don't have yet.
    Run periodically via cron (e.g., every 10 minutes).

    By default, only imports donation records. Use --with-receipts to
    also generate PDF receipts and send emails (for ongoing syncs, not
    historical imports).
    """
    import logging
    from .models.payment_processor import PaymentProcessor
    from .services.payment.nedarim_processor import NedarimProcessor
    from .services.commission_service import calculate_commission, create_commission_record
    from .services.receipt_service import create_receipt_atomic
    from .services.email_service import send_receipt_email

    logger = logging.getLogger(__name__)

    # Get processor config
    proc = PaymentProcessor.get_by_code('nedarim')
    if not proc or not proc.enabled:
        click.echo('Nedarim Plus not enabled, skipping.')
        return

    config = proc.config_json or {}
    processor = NedarimProcessor(config=config)
    if not processor.initialize():
        click.echo('Nedarim Plus not configured (missing credentials).')
        return

    # Get last synced transaction ID from processor config
    last_id = int(config.get('last_sync_id', 0))

    click.echo(f'Syncing Nedarim transactions from ID {last_id}...')

    result = processor.sync_transactions(last_id=last_id)
    if not result.get('success'):
        click.echo(f'Sync failed: {result.get("error")}')
        return

    transactions = result.get('transactions', [])
    if not transactions:
        click.echo('No new transactions.')
        return

    click.echo(f'Found {len(transactions)} transactions to process.')

    imported = 0
    skipped = 0
    max_id = last_id

    for txn in transactions:
        try:
            txn_id = str(txn.get('Shovar') or txn.get('TransactionId', ''))
            if not txn_id or txn_id == '0':
                skipped += 1
                continue

            # Track highest ID for next sync
            try:
                numeric_id = int(txn_id)
                if numeric_id > max_id:
                    max_id = numeric_id
            except ValueError:
                pass

            # Check for duplicate
            existing = Donation.query.filter_by(
                nedarim_transaction_id=txn_id
            ).first()
            if not existing:
                existing = Donation.query.filter_by(
                    processor_transaction_id=txn_id,
                    payment_processor='nedarim'
                ).first()
            if existing:
                skipped += 1
                continue

            # Parse amount (Nedarim sends in shekels/dollars)
            amount_raw = float(txn.get('Amount', 0))
            amount_cents = int(amount_raw * 100)
            if amount_cents <= 0:
                skipped += 1
                continue

            # Parse currency
            currency_code = str(txn.get('Currency', '1'))
            currency = 'ILS' if currency_code == '1' else 'USD'

            # Find or create donor
            donor_email = (txn.get('Mail') or '').strip()
            donor_name = (txn.get('ClientName') or '').strip()
            donor_phone = (txn.get('Phone') or '').strip()

            donor = None
            if donor_email:
                donor = Donor.query.filter_by(email=donor_email).first()
            if not donor and donor_phone:
                donor = Donor.query.filter_by(phone=donor_phone).first()

            if not donor:
                name_parts = donor_name.split(' ', 1) if donor_name else ['Unknown', '']
                donor = Donor(
                    first_name=name_parts[0],
                    last_name=name_parts[1] if len(name_parts) > 1 else '',
                    email=donor_email or None,
                    phone=donor_phone,
                    country='IL',
                    test=False
                )
            else:
                # Update existing donor with any new info
                if donor_email and not donor.email:
                    donor.email = donor_email
                if donor_phone and not donor.phone:
                    donor.phone = donor_phone
                if donor_name and (not donor.first_name or donor.first_name == 'Unknown'):
                    name_parts = donor_name.split(' ', 1)
                    donor.first_name = name_parts[0]
                    donor.last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Capture Teudat Zehut
            zeout = (txn.get('Zeout') or '').strip()
            if zeout and zeout != '000000000' and not donor.teudat_zehut:
                donor.teudat_zehut = zeout
                db.session.add(donor)
                db.session.flush()

            # Determine if recurring (keva)
            is_keva = txn.get('KevaId') and str(txn.get('KevaId')) != '0'

            # Resolve salesperson from Param2
            salesperson_id = None
            param2 = txn.get('Param2')
            if param2:
                try:
                    salesperson_id = int(param2)
                except ValueError:
                    pass

            # Create donation
            donation = Donation(
                donor_id=donor.id,
                salesperson_id=salesperson_id,
                payment_processor='nedarim',
                processor_transaction_id=txn_id,
                nedarim_transaction_id=txn_id,
                nedarim_confirmation=txn.get('Confirmation'),
                amount=amount_cents,
                currency=currency,
                status='succeeded',
                donation_type='recurring' if is_keva else 'one_time',
                source='nedarim_sync',
                payment_method_last4=txn.get('LastNum'),
                donor_comment=txn.get('Comments') or None,
                processor_metadata=txn,
            )

            if is_keva:
                donation.nedarim_keva_id = str(txn['KevaId'])
                donation.processor_recurring_id = str(txn['KevaId'])

            db.session.add(donation)
            db.session.flush()

            # Commission
            commission_data = calculate_commission(donation)
            if commission_data:
                create_commission_record(donation, commission_data)

            # Receipt + email (only if --with-receipts)
            receipt = None
            if with_receipts:
                try:
                    receipt = create_receipt_atomic(donation, donor)
                except Exception as e:
                    logger.error(f'Receipt failed for nedarim txn {txn_id}: {e}')

            db.session.commit()

            if with_receipts and receipt and donor.email and not donor.email.endswith('@unknown.com'):
                try:
                    send_receipt_email(donor, donation, receipt)
                except Exception as e:
                    logger.error(f'Receipt email failed for nedarim txn {txn_id}: {e}')

            imported += 1
            click.echo(f'  Imported: {txn_id} - {amount_raw} {currency} - {donor_name}')

        except Exception as e:
            logger.error(f'Error processing nedarim txn: {e}')
            db.session.rollback()
            click.echo(f'  Error: {e}')

    # Save last sync ID in processor config
    if max_id > last_id:
        proc = PaymentProcessor.query.filter_by(code='nedarim').first()
        if proc:
            updated_config = dict(proc.config_json or {})
            updated_config['last_sync_id'] = str(max_id)
            proc.config_json = updated_config
            db.session.commit()

    click.echo(f'Sync complete: {imported} imported, {skipped} skipped. Last ID: {max_id}')


@click.command('backfill-donor-owner')
@click.option('--user-id', required=True, type=int,
              help='users.id to assign as owner_user_id on every unassigned donor.')
@click.option('--include-deleted/--no-include-deleted', default=False,
              help='Also assign owners to soft-deleted donors. Default: skip deleted.')
@click.option('--dry-run/--no-dry-run', default=False,
              help='Print row counts without writing.')
@with_appcontext
def backfill_donor_owner_cmd(user_id, include_deleted, dry_run):
    """Backfill donors.owner_user_id for the multi-office migration.

    Sets `owner_user_id = <user_id>` on every donor that currently has it as
    NULL. Use this once at rollout to assign all existing contacts to the
    starting office (e.g. user_id=4 for Gittle Goldblum).
    """
    from .models.user import User

    user = User.query.get(user_id)
    if not user:
        click.echo(f'[X] No user with id={user_id}')
        return

    q = Donor.query.filter(Donor.owner_user_id.is_(None))
    if not include_deleted:
        q = q.filter(Donor.deleted_at.is_(None))
    n = q.count()
    click.echo(
        f'Found {n} donors with NULL owner_user_id'
        f' (include_deleted={include_deleted}). Target: id={user.id} '
        f'({user.username} / {user.first_name} {user.last_name}).'
    )
    if dry_run:
        click.echo('[dry-run] No writes performed.')
        return

    updated = q.update({Donor.owner_user_id: user_id}, synchronize_session=False)
    db.session.commit()
    click.echo(f'[OK] {updated} donors now owned by user_id={user_id}.')


def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(import_donors_cmd)
    app.cli.add_command(import_donations_cmd)
    app.cli.add_command(sync_nedarim_cmd)
    app.cli.add_command(backfill_donor_owner_cmd)

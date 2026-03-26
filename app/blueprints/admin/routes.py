import logging
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from decimal import Decimal
import shortuuid
from . import admin_bp

logger = logging.getLogger(__name__)
from ...extensions import db, bcrypt
from ...utils.decorators import admin_required
from ...models.user import User
from ...models.donation import Donation
from ...models.donor import Donor
from ...models.commission import Commission
from ...models.donation_link import DonationLink
from ...models.campaign import Campaign
from ...models.receipt import Receipt
from ...models.config_settings import ConfigSettings


# =============================================================================
# DASHBOARD
# =============================================================================

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard - redirects to donations."""
    return redirect(url_for('admin.donations'))


@admin_bp.route('/dashboard-stats')
@admin_required
def dashboard_stats():
    """Admin dashboard with global stats."""
    # Total income (all succeeded donations)
    total_income = db.session.query(func.sum(Donation.amount)).filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).scalar() or 0

    # Donation count
    donation_count = Donation.query.filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).count()

    # Active salespersons
    active_salespersons = User.query.filter(
        User.role == 'salesperson',
        User.active == True,
        User.deleted_at.is_(None)
    ).count()

    # Total commissions
    total_commissions = db.session.query(func.sum(Commission.commission_amount)).scalar() or 0
    pending_commissions = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'pending'
    ).scalar() or 0

    # This month stats
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_income = db.session.query(func.sum(Donation.amount)).filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= month_start
    ).scalar() or 0

    this_month_count = Donation.query.filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= month_start
    ).count()

    # Today's stats
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_income = db.session.query(func.sum(Donation.amount)).filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= today_start
    ).scalar() or 0

    # Recent donations
    recent_donations = Donation.query.filter(
        Donation.deleted_at.is_(None)
    ).order_by(Donation.created_at.desc()).limit(10).all()

    # Top salespersons this month
    top_salespersons = db.session.query(
        User,
        func.sum(Donation.amount).label('total'),
        func.count(Donation.id).label('count')
    ).join(Donation, User.id == Donation.salesperson_id).filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= month_start
    ).group_by(User.id).order_by(func.sum(Donation.amount).desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_income=total_income / 100,
        donation_count=donation_count,
        active_salespersons=active_salespersons,
        total_commissions=total_commissions / 100,
        pending_commissions=pending_commissions / 100,
        this_month_income=this_month_income / 100,
        this_month_count=this_month_count,
        today_income=today_income / 100,
        recent_donations=recent_donations,
        top_salespersons=top_salespersons
    )


# =============================================================================
# SALESPERSON MANAGEMENT
# =============================================================================

@admin_bp.route('/salespersons')
@admin_required
def salespersons():
    """List all salespersons."""
    salespersons = User.query.filter(
        User.role == 'salesperson',
        User.deleted_at.is_(None)
    ).order_by(User.created_at.desc()).all()

    # Get stats for each salesperson
    salesperson_stats = {}
    for sp in salespersons:
        total = db.session.query(func.sum(Donation.amount)).filter(
            Donation.salesperson_id == sp.id,
            Donation.status == 'succeeded',
            Donation.deleted_at.is_(None)
        ).scalar() or 0
        count = Donation.query.filter(
            Donation.salesperson_id == sp.id,
            Donation.status == 'succeeded',
            Donation.deleted_at.is_(None)
        ).count()
        salesperson_stats[sp.id] = {'total': total / 100, 'count': count}

    return render_template(
        'admin/salespersons.html',
        salespersons=salespersons,
        stats=salesperson_stats
    )


@admin_bp.route('/salespersons/create', methods=['GET', 'POST'])
@admin_required
def create_salesperson():
    """Create new salesperson."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        commission_type = request.form.get('commission_type')
        commission_rate = request.form.get('commission_rate', '').strip()

        # Validation
        if not username or not email:
            flash('Username and email are required.', 'error')
            return redirect(url_for('admin.create_salesperson'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('admin.create_salesperson'))

        # Generate temp password and ref code
        temp_password = shortuuid.uuid()[:8]
        ref_code = f"SP-{shortuuid.uuid()[:6].upper()}"

        # Ensure ref_code is unique
        while User.query.filter_by(ref_code=ref_code).first():
            ref_code = f"SP-{shortuuid.uuid()[:6].upper()}"

        user = User(
            username=username,
            password_hash=bcrypt.generate_password_hash(temp_password).decode('utf-8'),
            role='salesperson',
            ref_code=ref_code,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            is_temp_password=True,
            commission_type=commission_type if commission_type else None,
            commission_rate=Decimal(commission_rate) if commission_rate else None,
            active=True
        )
        db.session.add(user)
        db.session.commit()

        flash(f'Salesperson created! Username: {username}, Temp Password: {temp_password}', 'success')
        return redirect(url_for('admin.salespersons'))

    return render_template('admin/salesperson_form.html', salesperson=None)


@admin_bp.route('/salespersons/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_salesperson(id):
    """Edit salesperson."""
    salesperson = User.query.get_or_404(id)

    if salesperson.role != 'salesperson':
        flash('Invalid salesperson.', 'error')
        return redirect(url_for('admin.salespersons'))

    if request.method == 'POST':
        salesperson.first_name = request.form.get('first_name', '').strip()
        salesperson.last_name = request.form.get('last_name', '').strip()
        salesperson.email = request.form.get('email', '').strip()
        salesperson.phone = request.form.get('phone', '').strip()
        salesperson.active = request.form.get('active') == 'on'

        commission_type = request.form.get('commission_type')
        commission_rate = request.form.get('commission_rate', '').strip()

        salesperson.commission_type = commission_type if commission_type else None
        salesperson.commission_rate = Decimal(commission_rate) if commission_rate else None

        db.session.commit()
        flash('Salesperson updated successfully.', 'success')
        return redirect(url_for('admin.salespersons'))

    return render_template('admin/salesperson_form.html', salesperson=salesperson)


@admin_bp.route('/salespersons/<int:id>/reset-password', methods=['POST'])
@admin_required
def reset_salesperson_password(id):
    """Reset salesperson password."""
    salesperson = User.query.get_or_404(id)

    if salesperson.role != 'salesperson':
        return jsonify({'error': 'Invalid salesperson'}), 400

    temp_password = shortuuid.uuid()[:8]
    salesperson.password_hash = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    salesperson.is_temp_password = True
    db.session.commit()

    return jsonify({'success': True, 'password': temp_password})


@admin_bp.route('/salespersons/<int:id>/delete', methods=['POST'])
@admin_required
def delete_salesperson(id):
    """Soft delete salesperson."""
    salesperson = User.query.get_or_404(id)

    if salesperson.role != 'salesperson':
        flash('Invalid salesperson.', 'error')
        return redirect(url_for('admin.salespersons'))

    salesperson.deleted_at = datetime.utcnow()
    salesperson.active = False
    db.session.commit()

    flash('Salesperson deleted.', 'success')
    return redirect(url_for('admin.salespersons'))


# =============================================================================
# COMMISSION MANAGEMENT
# =============================================================================

@admin_bp.route('/commissions')
@admin_required
def commissions():
    """List all commissions."""
    status_filter = request.args.get('status', 'all')

    query = Commission.query

    if status_filter != 'all':
        query = query.filter(Commission.status == status_filter)

    commissions = query.order_by(Commission.created_at.desc()).all()

    # Calculate totals
    total_pending = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'pending'
    ).scalar() or 0

    total_paid = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid'
    ).scalar() or 0

    return render_template(
        'admin/commissions.html',
        commissions=commissions,
        status_filter=status_filter,
        total_pending=total_pending / 100,
        total_paid=total_paid / 100
    )


@admin_bp.route('/commissions/<int:id>/pay', methods=['POST'])
@admin_required
def pay_commission(id):
    """Mark commission as paid."""
    commission = Commission.query.get_or_404(id)

    if commission.status != 'pending':
        return jsonify({'error': 'Commission is not pending'}), 400

    data = request.get_json() or {}

    commission.status = 'paid'
    commission.paid_date = datetime.utcnow()
    commission.paid_method = data.get('method', 'check')
    commission.paid_reference = data.get('reference', '')

    db.session.commit()

    return jsonify({'success': True})


@admin_bp.route('/commissions/pay-bulk', methods=['POST'])
@admin_required
def pay_commissions_bulk():
    """Mark multiple commissions as paid."""
    data = request.get_json() or {}
    commission_ids = data.get('ids', [])
    method = data.get('method', 'check')
    reference = data.get('reference', '')

    if not commission_ids:
        return jsonify({'error': 'No commissions selected'}), 400

    updated = 0
    for cid in commission_ids:
        commission = Commission.query.get(cid)
        if commission and commission.status == 'pending':
            commission.status = 'paid'
            commission.paid_date = datetime.utcnow()
            commission.paid_method = method
            commission.paid_reference = reference
            updated += 1

    db.session.commit()

    return jsonify({'success': True, 'updated': updated})


@admin_bp.route('/commissions/by-salesperson')
@admin_required
def commissions_by_salesperson():
    """View commissions grouped by salesperson."""
    salespersons = db.session.query(
        User,
        func.sum(Commission.commission_amount).filter(Commission.status == 'pending').label('pending'),
        func.sum(Commission.commission_amount).filter(Commission.status == 'paid').label('paid'),
        func.count(Commission.id).label('count')
    ).join(Commission, User.id == Commission.salesperson_id).filter(
        User.deleted_at.is_(None)
    ).group_by(User.id).order_by(func.sum(Commission.commission_amount).desc()).all()

    return render_template(
        'admin/commissions_by_salesperson.html',
        salespersons=salespersons
    )


# =============================================================================
# REPORTING
# =============================================================================

@admin_bp.route('/reports')
@admin_required
def reports():
    """Reports landing page."""
    now = datetime.utcnow()
    return render_template('admin/reports.html', now=now)


@admin_bp.route('/reports/daily')
@admin_required
def report_daily():
    """Daily donation report."""
    date_str = request.args.get('date')
    if date_str:
        report_date = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        report_date = datetime.utcnow()

    start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    donations = Donation.query.filter(
        Donation.created_at >= start,
        Donation.created_at < end,
        Donation.deleted_at.is_(None)
    ).order_by(Donation.created_at.desc()).all()

    # Stats
    total = sum(d.amount for d in donations if d.status == 'succeeded') / 100
    count = len([d for d in donations if d.status == 'succeeded'])
    fees = sum(d.stripe_fee or 0 for d in donations if d.status == 'succeeded') / 100

    # Calculate prev/next dates for navigation
    prev_date = (report_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (report_date + timedelta(days=1)).strftime('%Y-%m-%d')

    return render_template(
        'admin/report_daily.html',
        donations=donations,
        report_date=report_date,
        total=total,
        count=count,
        fees=fees,
        prev_date=prev_date,
        next_date=next_date
    )


@admin_bp.route('/reports/monthly')
@admin_required
def report_monthly():
    """Monthly donation report."""
    year = int(request.args.get('year', datetime.utcnow().year))
    month = int(request.args.get('month', datetime.utcnow().month))

    # Get daily totals for the month
    daily_totals = db.session.query(
        func.date(Donation.created_at).label('date'),
        func.sum(Donation.amount).label('total'),
        func.count(Donation.id).label('count')
    ).filter(
        extract('year', Donation.created_at) == year,
        extract('month', Donation.created_at) == month,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).group_by(func.date(Donation.created_at)).order_by(func.date(Donation.created_at)).all()

    # By salesperson
    by_salesperson = db.session.query(
        User,
        func.sum(Donation.amount).label('total'),
        func.count(Donation.id).label('count')
    ).outerjoin(Donation, User.id == Donation.salesperson_id).filter(
        User.role == 'salesperson',
        User.deleted_at.is_(None),
        Donation.status == 'succeeded',
        extract('year', Donation.created_at) == year,
        extract('month', Donation.created_at) == month
    ).group_by(User.id).order_by(func.sum(Donation.amount).desc()).all()

    # By source
    by_source = db.session.query(
        Donation.source,
        func.sum(Donation.amount).label('total'),
        func.count(Donation.id).label('count')
    ).filter(
        extract('year', Donation.created_at) == year,
        extract('month', Donation.created_at) == month,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).group_by(Donation.source).all()

    # Total
    total = sum(dt.total or 0 for dt in daily_totals) / 100
    count = sum(dt.count or 0 for dt in daily_totals)

    return render_template(
        'admin/report_monthly.html',
        year=year,
        month=month,
        daily_totals=daily_totals,
        by_salesperson=by_salesperson,
        by_source=by_source,
        total=total,
        count=count
    )


@admin_bp.route('/reports/yearly')
@admin_required
def report_yearly():
    """Yearly donation report."""
    year = int(request.args.get('year', datetime.utcnow().year))

    # Get monthly totals
    monthly_totals = db.session.query(
        extract('month', Donation.created_at).label('month'),
        func.sum(Donation.amount).label('total'),
        func.count(Donation.id).label('count')
    ).filter(
        extract('year', Donation.created_at) == year,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).group_by(extract('month', Donation.created_at)).order_by(extract('month', Donation.created_at)).all()

    # Format for display
    months_data = {int(m.month): {'total': m.total / 100, 'count': m.count} for m in monthly_totals}

    # Commission summary
    from sqlalchemy import case
    commission_summary = db.session.query(
        func.sum(case((Commission.status == 'pending', Commission.commission_amount), else_=0)).label('pending'),
        func.sum(case((Commission.status == 'paid', Commission.commission_amount), else_=0)).label('paid'),
        func.sum(Commission.commission_amount).label('total')
    ).filter(
        extract('year', Commission.created_at) == year
    ).first()

    # Total
    total = sum(m.total for m in monthly_totals) / 100
    count = sum(m.count for m in monthly_totals)

    return render_template(
        'admin/report_yearly.html',
        year=year,
        months_data=months_data,
        commission_summary=commission_summary,
        total=total,
        count=count
    )


# =============================================================================
# RECEIPT LOOKUP
# =============================================================================

@admin_bp.route('/receipts')
@admin_required
def receipts():
    """Receipt lookup and search."""
    search = request.args.get('q', '').strip()
    receipts_list = []

    if search:
        # Search by receipt number, donor email, or donor name
        receipts_list = Receipt.query.join(Donor).filter(
            db.or_(
                Receipt.receipt_number.ilike(f'%{search}%'),
                Donor.email.ilike(f'%{search}%'),
                Donor.first_name.ilike(f'%{search}%'),
                Donor.last_name.ilike(f'%{search}%')
            )
        ).order_by(Receipt.created_at.desc()).limit(50).all()
    else:
        # Show recent receipts
        receipts_list = Receipt.query.order_by(
            Receipt.created_at.desc()
        ).limit(50).all()

    return render_template(
        'admin/receipts.html',
        receipts=receipts_list,
        search=search
    )


@admin_bp.route('/receipts/<int:id>/resend', methods=['POST'])
@admin_required
def resend_receipt(id):
    """Resend receipt email."""
    from ...services.email_service import send_receipt_email
    from ...services.receipt_service import regenerate_receipt_pdf
    import traceback

    try:
        receipt = Receipt.query.get_or_404(id)
        donation = Donation.query.get(receipt.donation_id)
        donor = Donor.query.get(receipt.donor_id)

        if not donation or not donor:
            return jsonify({'error': 'Donation or donor not found'}), 400

        # Regenerate PDF if needed
        if not receipt.pdf_path:
            regenerate_receipt_pdf(receipt)

        # Send email
        success = send_receipt_email(donor, donation, receipt)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Email send failed - check email configuration'}), 500

    except Exception as e:
        print(f"Error in resend_receipt: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/receipts/<int:id>/download')
@admin_required
def download_receipt(id):
    """Download receipt PDF."""
    from flask import send_file
    import os

    receipt = Receipt.query.get_or_404(id)

    if receipt.pdf_path and os.path.exists(receipt.pdf_path):
        return send_file(
            receipt.pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{receipt.receipt_number}.pdf'
        )

    flash('Receipt PDF not found.', 'error')
    return redirect(url_for('admin.receipts'))


@admin_bp.route('/donations/<int:id>/send-receipt', methods=['POST'])
@admin_required
def send_donation_receipt(id):
    """Generate and send receipt for a donation."""
    from ...services.receipt_service import create_receipt
    from ...services.email_service import send_receipt_email
    import traceback

    try:
        donation = Donation.query.get_or_404(id)
        donor = Donor.query.get(donation.donor_id)

        if not donor:
            return jsonify({'error': 'Donor not found'}), 400

        if donation.status != 'succeeded':
            return jsonify({'error': 'Can only send receipts for successful donations'}), 400

        # Check if receipt already exists
        receipt = Receipt.query.filter_by(donation_id=donation.id).first()

        if not receipt:
            # Create new receipt
            receipt = create_receipt(donation, donor)
            if not receipt:
                return jsonify({'error': 'Failed to create receipt'}), 500

        # Send email
        success = send_receipt_email(donor, donation, receipt)

        if success:
            return jsonify({'success': True, 'message': f'Receipt sent to {donor.email}'})
        else:
            return jsonify({'error': 'Email send failed - check email configuration'}), 500

    except Exception as e:
        print(f"Error in send_donation_receipt: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# DONATIONS MANAGEMENT
# =============================================================================

@admin_bp.route('/donations')
@admin_required
def donations():
    """List all donations with filters."""
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    per_page = 50

    query = Donation.query.filter(Donation.deleted_at.is_(None))

    if status != 'all':
        query = query.filter(Donation.status == status)

    donations = query.order_by(Donation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Get salespersons for dropdown
    salespersons = User.query.filter(
        User.role == 'salesperson',
        User.deleted_at.is_(None)
    ).order_by(User.first_name).all()

    return render_template(
        'admin/donations.html',
        donations=donations,
        status_filter=status,
        salespersons=salespersons
    )


@admin_bp.route('/donations/<int:id>')
@admin_required
def donation_detail(id):
    """View donation details."""
    donation = Donation.query.get_or_404(id)
    return render_template('admin/donation_detail.html', donation=donation)


@admin_bp.route('/donations/<int:id>/update-salesperson', methods=['POST'])
@admin_required
def update_donation_salesperson(id):
    """Quick update salesperson for a donation."""
    donation = Donation.query.get_or_404(id)
    data = request.get_json() or {}

    salesperson_id = data.get('salesperson_id', '').strip() if data.get('salesperson_id') else None

    if salesperson_id:
        donation.salesperson_id = int(salesperson_id)
    else:
        donation.salesperson_id = None

    db.session.commit()

    return jsonify({'success': True})


@admin_bp.route('/donations/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_donation(id):
    """Edit donation details."""
    donation = Donation.query.get_or_404(id)

    # Get lists for dropdowns
    salespersons = User.query.filter(
        User.role == 'salesperson',
        User.deleted_at.is_(None)
    ).order_by(User.first_name).all()

    campaigns = Campaign.query.filter(
        Campaign.is_active == True
    ).order_by(Campaign.name).all()

    donors = Donor.query.filter(
        Donor.deleted_at.is_(None)
    ).order_by(Donor.last_name, Donor.first_name).all()

    if request.method == 'POST':
        # Update donation fields
        amount_dollars = request.form.get('amount', '').strip()
        if amount_dollars:
            donation.amount = int(float(amount_dollars) * 100)

        donation.status = request.form.get('status', donation.status)
        donation.donation_type = request.form.get('donation_type', donation.donation_type)
        donation.source = request.form.get('source', '').strip() or None

        # Update relationships
        salesperson_id = request.form.get('salesperson_id', '').strip()
        donation.salesperson_id = int(salesperson_id) if salesperson_id else None

        campaign_id = request.form.get('campaign_id', '').strip()
        donation.campaign_id = int(campaign_id) if campaign_id else None

        donor_id = request.form.get('donor_id', '').strip()
        if donor_id:
            donation.donor_id = int(donor_id)

        # Update donor info if provided
        if donation.donor:
            donor = donation.donor
            first_name = request.form.get('donor_first_name', '').strip()
            last_name = request.form.get('donor_last_name', '').strip()
            email = request.form.get('donor_email', '').strip()
            phone = request.form.get('donor_phone', '').strip()

            if first_name:
                donor.first_name = first_name
            if last_name:
                donor.last_name = last_name
            if email:
                donor.email = email
            donor.phone = phone or donor.phone

            # Update address fields
            donor.address_line1 = request.form.get('donor_address_line1', '').strip() or donor.address_line1
            donor.address_line2 = request.form.get('donor_address_line2', '').strip() or None
            donor.city = request.form.get('donor_city', '').strip() or donor.city
            donor.state = request.form.get('donor_state', '').strip() or donor.state
            donor.zip = request.form.get('donor_zip', '').strip() or donor.zip
            donor.country = request.form.get('donor_country', '').strip() or donor.country or 'US'

        db.session.commit()
        flash('Donation updated successfully.', 'success')
        return redirect(url_for('admin.donation_detail', id=donation.id))

    return render_template(
        'admin/donation_edit.html',
        donation=donation,
        salespersons=salespersons,
        campaigns=campaigns,
        donors=donors
    )


@admin_bp.route('/donations/<int:id>/receipt/print')
@admin_required
def print_receipt(id):
    """Print receipt for a donation."""
    from ...services.receipt_service import create_receipt_atomic

    donation = Donation.query.get_or_404(id)
    donor = Donor.query.get(donation.donor_id)

    if not donor or not donor.first_name or donor.first_name.strip().lower() == 'unknown':
        flash('Donor name is required to create a receipt. Please edit the donation and add the donor\'s real name first.', 'error')
        return redirect(url_for('admin.edit_donation', id=id))

    # Get or create receipt
    receipt = donation.receipt
    if not receipt:
        try:
            receipt = create_receipt_atomic(donation, donor)
            db.session.commit()
        except Exception as e:
            flash(f'Error creating receipt: {str(e)}', 'error')
            return redirect(url_for('admin.donation_detail', id=id))

    return render_template('admin/receipt_print.html', donation=donation, donor=donor, receipt=receipt)


@admin_bp.route('/donations/<int:id>/receipt/pdf')
@admin_required
def donation_receipt_pdf(id):
    """Download PDF receipt for a donation."""
    from flask import send_file
    from ...services.receipt_service import create_receipt_atomic, regenerate_receipt_pdf
    import os

    donation = Donation.query.get_or_404(id)
    donor = Donor.query.get(donation.donor_id)

    if not donor or not donor.first_name or donor.first_name.strip().lower() == 'unknown':
        flash('Donor name is required to create a receipt. Please edit the donation and add the donor\'s real name first.', 'error')
        return redirect(url_for('admin.edit_donation', id=id))

    # Get or create receipt
    receipt = donation.receipt
    if not receipt:
        try:
            receipt = create_receipt_atomic(donation, donor)
            db.session.commit()
        except Exception as e:
            flash(f'Error creating receipt: {str(e)}', 'error')
            return redirect(url_for('admin.donation_detail', id=id))

    # Regenerate PDF if missing
    if not receipt.pdf_path or not os.path.exists(receipt.pdf_path):
        try:
            regenerate_receipt_pdf(receipt)
        except Exception as e:
            flash(f'Error generating PDF: {str(e)}', 'error')
            return redirect(url_for('admin.donation_detail', id=id))

    return send_file(
        receipt.pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{receipt.receipt_number}.pdf'
    )


# =============================================================================
# CAMPAIGNS MANAGEMENT
# =============================================================================

@admin_bp.route('/campaigns')
@admin_required
def campaigns():
    """List all campaigns."""
    campaigns = Campaign.query.filter(
        Campaign.is_active == True
    ).order_by(Campaign.created_at.desc()).all()

    # Add donation stats for each campaign
    for campaign in campaigns:
        campaign.donation_count = Donation.query.filter(
            Donation.campaign_id == campaign.id,
            Donation.status == 'succeeded',
            Donation.deleted_at.is_(None)
        ).count()
        campaign.current_amount = db.session.query(func.sum(Donation.amount)).filter(
            Donation.campaign_id == campaign.id,
            Donation.status == 'succeeded',
            Donation.deleted_at.is_(None)
        ).scalar() or 0

    return render_template('admin/campaigns.html', campaigns=campaigns)


@admin_bp.route('/campaigns/create', methods=['GET', 'POST'])
@admin_required
def create_campaign():
    """Create new campaign."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        goal_amount = request.form.get('goal_amount', '').strip()
        commission_override_type = request.form.get('commission_override_type')
        commission_override_rate = request.form.get('commission_override_rate', '').strip()

        if not name:
            flash('Campaign name is required.', 'error')
            return redirect(url_for('admin.create_campaign'))

        # Generate aff code
        aff_code = f"C-{shortuuid.uuid()[:6].upper()}"
        while Campaign.query.filter_by(aff_code=aff_code).first():
            aff_code = f"C-{shortuuid.uuid()[:6].upper()}"

        campaign = Campaign(
            name=name,
            description=description,
            aff_code=aff_code,
            goal_amount=int(float(goal_amount) * 100) if goal_amount else None,
            commission_override_type=commission_override_type if commission_override_type else None,
            commission_override_rate=Decimal(commission_override_rate) if commission_override_rate else None,
            created_by=current_user.id,
            is_active=True
        )
        db.session.add(campaign)
        db.session.commit()

        flash('Campaign created successfully.', 'success')
        return redirect(url_for('admin.campaigns'))

    return render_template('admin/campaign_form.html', campaign=None)


@admin_bp.route('/campaigns/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_campaign(id):
    """Edit campaign."""
    campaign = Campaign.query.get_or_404(id)

    if request.method == 'POST':
        campaign.name = request.form.get('name', '').strip()
        campaign.description = request.form.get('description', '').strip()
        campaign.is_active = request.form.get('is_active') == 'on'

        goal_amount = request.form.get('goal_amount', '').strip()
        campaign.goal_amount = int(float(goal_amount) * 100) if goal_amount else None

        commission_override_type = request.form.get('commission_override_type')
        commission_override_rate = request.form.get('commission_override_rate', '').strip()

        campaign.commission_override_type = commission_override_type if commission_override_type else None
        campaign.commission_override_rate = Decimal(commission_override_rate) if commission_override_rate else None

        db.session.commit()
        flash('Campaign updated successfully.', 'success')
        return redirect(url_for('admin.campaigns'))

    return render_template('admin/campaign_form.html', campaign=campaign)


# =============================================================================
# SETTINGS
# =============================================================================

# =============================================================================
# DONORS MANAGEMENT
# =============================================================================

@admin_bp.route('/donors')
@admin_required
def donors():
    """List and search donors."""
    search = request.args.get('q', '').strip()
    filter_type = request.args.get('type', 'all')  # all, test, real
    page = int(request.args.get('page', 1))
    per_page = 50

    query = Donor.query.filter(Donor.deleted_at.is_(None))

    if search:
        query = query.filter(
            db.or_(
                Donor.email.ilike(f'%{search}%'),
                Donor.first_name.ilike(f'%{search}%'),
                Donor.last_name.ilike(f'%{search}%'),
                Donor.phone.ilike(f'%{search}%'),
                Donor.external_id.ilike(f'%{search}%')
            )
        )

    if filter_type == 'test':
        query = query.filter(Donor.test == True)
    elif filter_type == 'real':
        query = query.filter(Donor.test == False)

    donors_list = query.order_by(Donor.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Get counts
    total_donors = Donor.query.filter(Donor.deleted_at.is_(None)).count()
    test_donors = Donor.query.filter(Donor.deleted_at.is_(None), Donor.test == True).count()
    real_donors = Donor.query.filter(Donor.deleted_at.is_(None), Donor.test == False).count()

    return render_template(
        'admin/donors.html',
        donors=donors_list,
        search=search,
        filter_type=filter_type,
        total_donors=total_donors,
        test_donors=test_donors,
        real_donors=real_donors
    )


@admin_bp.route('/donors/<int:id>')
@admin_required
def donor_detail(id):
    """View donor details and donation history."""
    donor = Donor.query.get_or_404(id)

    # Get donation history
    donations_list = Donation.query.filter(
        Donation.donor_id == donor.id,
        Donation.deleted_at.is_(None)
    ).order_by(Donation.created_at.desc()).all()

    # Get receipts
    receipts_list = Receipt.query.filter(
        Receipt.donor_id == donor.id
    ).order_by(Receipt.created_at.desc()).all()

    # Calculate totals
    total_donated = sum(d.amount for d in donations_list if d.status == 'succeeded') / 100
    donation_count = len([d for d in donations_list if d.status == 'succeeded'])

    return render_template(
        'admin/donor_detail.html',
        donor=donor,
        donations=donations_list,
        receipts=receipts_list,
        total_donated=total_donated,
        donation_count=donation_count
    )


@admin_bp.route('/donors/<int:id>/toggle-test', methods=['POST'])
@admin_required
def toggle_donor_test(id):
    """Toggle donor test flag."""
    donor = Donor.query.get_or_404(id)
    donor.test = not donor.test
    db.session.commit()
    return jsonify({'success': True, 'test': donor.test})


@admin_bp.route('/donors/<int:id>/link', methods=['POST'])
@admin_required
def link_donor(id):
    """Link another donor record to this one."""
    primary_donor = Donor.query.get_or_404(id)
    search = request.form.get('search', '').strip()

    if not search:
        flash('Please enter a search term.', 'error')
        return redirect(url_for('admin.donor_detail', id=id))

    # Search for donors to link
    matches = Donor.query.filter(
        Donor.id != id,
        Donor.primary_donor_id.is_(None),  # Only show primary donors
        db.or_(
            Donor.email.ilike(f'%{search}%'),
            Donor.first_name.ilike(f'%{search}%'),
            Donor.last_name.ilike(f'%{search}%'),
            Donor.external_id.ilike(f'%{search}%')
        )
    ).limit(10).all()

    if not matches:
        flash(f'No donors found matching "{search}".', 'error')
        return redirect(url_for('admin.donor_detail', id=id))

    if len(matches) == 1:
        # Auto-link if only one match
        donor_to_link = matches[0]
        donor_to_link.primary_donor_id = primary_donor.effective_primary.id
        db.session.commit()
        logger.info(f'[link_donor] Linked donor {donor_to_link.id} to primary {primary_donor.effective_primary.id}')
        flash(f'Linked {donor_to_link.full_name} ({donor_to_link.email}) to this record.', 'success')
        return redirect(url_for('admin.donor_detail', id=id))

    # Multiple matches - show selection page
    return render_template(
        'admin/link_donor_select.html',
        primary_donor=primary_donor,
        matches=matches,
        search=search
    )


@admin_bp.route('/donors/<int:id>/link/<int:target_id>', methods=['POST'])
@admin_required
def link_donor_confirm(id, target_id):
    """Confirm linking a specific donor."""
    primary_donor = Donor.query.get_or_404(id)
    donor_to_link = Donor.query.get_or_404(target_id)

    # Determine the actual primary (in case primary_donor is already linked)
    actual_primary = primary_donor.effective_primary

    # Link the donor
    donor_to_link.primary_donor_id = actual_primary.id
    db.session.commit()

    logger.info(f'[link_donor] Linked donor {donor_to_link.id} to primary {actual_primary.id}')
    flash(f'Linked {donor_to_link.full_name} ({donor_to_link.email}) to this record.', 'success')
    return redirect(url_for('admin.donor_detail', id=id))


@admin_bp.route('/donors/<int:id>/unlink', methods=['POST'])
@admin_required
def unlink_donor(id):
    """Unlink a donor from its primary."""
    donor = Donor.query.get_or_404(id)

    if donor.primary_donor_id:
        primary_id = donor.primary_donor_id
        donor.primary_donor_id = None
        db.session.commit()
        logger.info(f'[unlink_donor] Unlinked donor {id} from primary {primary_id}')
        flash(f'Unlinked {donor.full_name} ({donor.email}).', 'success')
    else:
        flash('This donor is not linked to another record.', 'error')

    return redirect(url_for('admin.donor_detail', id=id))


@admin_bp.route('/donors/<int:id>/external-id', methods=['POST'])
@admin_required
def set_external_id(id):
    """Set or update external system ID."""
    donor = Donor.query.get_or_404(id)

    donor.external_id = request.form.get('external_id', '').strip() or None
    donor.external_source = request.form.get('external_source', '').strip() or None
    db.session.commit()

    logger.info(f'[set_external_id] Updated donor {id}: external_id={donor.external_id}, source={donor.external_source}')
    flash('External ID updated.', 'success')
    return redirect(url_for('admin.donor_detail', id=id))


# =============================================================================
# SETTINGS
# =============================================================================

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """System settings."""
    config = ConfigSettings.query.first()
    if not config:
        config = ConfigSettings()
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.org_name = request.form.get('org_name', '').strip()
        config.org_prefix = request.form.get('org_prefix', '').strip()
        config.tax_id = request.form.get('tax_id', '').strip()
        config.org_phone = request.form.get('org_phone', '').strip() or None
        config.logo_url = request.form.get('logo_url', '').strip() or None
        config.org_address = request.form.get('org_address', '').strip() or None
        config.org_city = request.form.get('org_city', '').strip() or None
        config.org_state = request.form.get('org_state', '').strip() or None
        config.org_zip = request.form.get('org_zip', '').strip() or None

        default_commission_type = request.form.get('default_commission_type')
        default_commission_rate = request.form.get('default_commission_rate', '').strip()

        config.default_commission_type = default_commission_type if default_commission_type else None
        config.default_commission_rate = Decimal(default_commission_rate) if default_commission_rate else None

        # Stripe settings
        config.stripe_mode = request.form.get('stripe_mode', 'test')
        config.stripe_test_secret_key = request.form.get('stripe_test_secret_key', '').strip() or None
        config.stripe_test_publishable_key = request.form.get('stripe_test_publishable_key', '').strip() or None
        config.stripe_live_secret_key = request.form.get('stripe_live_secret_key', '').strip() or None
        config.stripe_live_publishable_key = request.form.get('stripe_live_publishable_key', '').strip() or None
        config.stripe_webhook_secret = request.form.get('stripe_webhook_secret', '').strip() or None

        # Site URL
        config.site_url = request.form.get('site_url', '').strip() or 'https://matatmordechai.org'

        # Mailtrap settings
        config.mailtrap_token = request.form.get('mailtrap_token', '').strip() or None
        config.email_from_name = request.form.get('email_from_name', '').strip() or 'Matat Mordechai'
        config.email_from_address = request.form.get('email_from_address', '').strip() or None

        # Email/SMTP settings (fallback)
        config.smtp_host = request.form.get('smtp_host', '').strip() or None
        smtp_port = request.form.get('smtp_port', '').strip()
        config.smtp_port = int(smtp_port) if smtp_port else 587
        config.smtp_username = request.form.get('smtp_username', '').strip() or None
        config.smtp_password = request.form.get('smtp_password', '').strip() or None
        config.smtp_use_tls = request.form.get('smtp_use_tls') == 'on'

        db.session.commit()
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html', config=config)


@admin_bp.route('/settings/clear-test-data', methods=['POST'])
@admin_required
def clear_test_data():
    """Clear all test mode data from the system."""
    import traceback

    try:
        data = request.get_json() or {}
        delete_donors = data.get('delete_donors', False)

        # Find all test donors
        test_donors = Donor.query.filter(Donor.test == True).all()
        test_donor_ids = [d.id for d in test_donors]

        if not test_donor_ids:
            return jsonify({
                'success': True,
                'donations': 0,
                'receipts': 0,
                'commissions': 0,
                'donors': 0 if delete_donors else None
            })

        # Get all donations from test donors
        test_donations = Donation.query.filter(
            Donation.donor_id.in_(test_donor_ids)
        ).all()
        test_donation_ids = [d.id for d in test_donations]

        # Count items to delete
        donations_count = len(test_donations)
        receipts_count = 0
        commissions_count = 0

        # Delete commissions first (foreign key constraint)
        if test_donation_ids:
            commissions_count = Commission.query.filter(
                Commission.donation_id.in_(test_donation_ids)
            ).delete(synchronize_session=False)

        # Delete receipts
        receipts_count = Receipt.query.filter(
            Receipt.donor_id.in_(test_donor_ids)
        ).delete(synchronize_session=False)

        # Delete donations
        if test_donation_ids:
            Donation.query.filter(
                Donation.id.in_(test_donation_ids)
            ).delete(synchronize_session=False)

        # Optionally delete test donors
        donors_count = 0
        if delete_donors:
            donors_count = Donor.query.filter(
                Donor.id.in_(test_donor_ids)
            ).delete(synchronize_session=False)

        db.session.commit()

        return jsonify({
            'success': True,
            'donations': donations_count,
            'receipts': receipts_count,
            'commissions': commissions_count,
            'donors': donors_count if delete_donors else None
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error clearing test data: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# DONATION LINKS
# =============================================================================

@admin_bp.route('/links')
@admin_required
def links():
    """View all donation links with pending tab."""
    from ...models.message import MessageQueue

    # All links
    all_links = DonationLink.query.order_by(DonationLink.created_at.desc()).all()

    # Pending links - sent but not used (times_used == 0 or None)
    pending_links = DonationLink.query.filter(
        (DonationLink.times_used == 0) | (DonationLink.times_used.is_(None))
    ).order_by(DonationLink.created_at.desc()).all()

    # Get salespersons for reference
    salespersons = {u.id: u for u in User.query.filter(User.role == 'salesperson').all()}

    # Get email tracking data for pending links
    link_ids = [link.id for link in pending_links]
    email_status = {}
    if link_ids:
        messages = MessageQueue.query.filter(
            MessageQueue.related_link_id.in_(link_ids),
            MessageQueue.message_type == 'donation_link'
        ).all()
        for msg in messages:
            email_status[msg.related_link_id] = {
                'status': msg.status,
                'sent_at': msg.sent_at,
                'delivered_at': msg.delivered_at,
                'opened_at': msg.opened_at,
                'clicked_at': msg.clicked_at
            }

    return render_template(
        'admin/links.html',
        links=all_links,
        pending_links=pending_links,
        salespersons=salespersons,
        email_status=email_status,
        now=datetime.utcnow()
    )


@admin_bp.route('/links/<int:id>/delete', methods=['POST'])
@admin_required
def delete_link(id):
    """Delete a pending donation link."""
    from ...models.message import MessageQueue

    logger.info(f'[admin delete_link] Attempting to delete link {id} by admin {current_user.id}')

    link = DonationLink.query.get_or_404(id)

    logger.info(f'[admin delete_link] Found link: {link.short_code}, times_used={link.times_used}')

    # Only allow deleting unused links
    if link.times_used and link.times_used > 0:
        logger.warning(f'[admin delete_link] Cannot delete link {id} - has been used {link.times_used} times')
        flash('Cannot delete a link that has been used.', 'error')
        return redirect(url_for('admin.links'))

    try:
        # Clear related messages first (set link reference to NULL)
        related_messages = MessageQueue.query.filter_by(related_link_id=id).all()
        logger.info(f'[admin delete_link] Found {len(related_messages)} related messages')
        for msg in related_messages:
            msg.related_link_id = None

        db.session.delete(link)
        db.session.commit()
        logger.info(f'[admin delete_link] Link {id} deleted successfully')
        flash('Link deleted successfully.', 'success')
    except Exception as e:
        logger.error(f'[admin delete_link] Error deleting link {id}: {str(e)}')
        db.session.rollback()
        flash('Error deleting link. Please try again.', 'error')

    return redirect(url_for('admin.links'))


@admin_bp.route('/links/<int:id>/edit', methods=['POST'])
@admin_required
def edit_link(id):
    """Edit a pending donation link."""
    link = DonationLink.query.get_or_404(id)

    # Only allow editing unused links
    if link.times_used and link.times_used > 0:
        flash('Cannot edit a link that has been used.', 'error')
        return redirect(url_for('admin.links'))

    link.donor_name = request.form.get('donor_name', '').strip() or None
    link.donor_email = request.form.get('donor_email', '').strip() or None
    link.donor_address = request.form.get('donor_address', '').strip() or None

    db.session.commit()
    flash('Link updated successfully.', 'success')
    return redirect(url_for('admin.links'))


# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

@admin_bp.route('/email-templates')
@admin_required
def email_templates():
    """Manage email templates."""
    from ...models.email_template import EmailTemplate

    templates = EmailTemplate.query.filter(
        EmailTemplate.deleted_at.is_(None)
    ).order_by(EmailTemplate.name).all()

    return render_template(
        'admin/email_templates.html',
        templates=templates
    )


@admin_bp.route('/email-templates/create', methods=['GET', 'POST'])
@admin_required
def create_email_template():
    """Create a new email template."""
    from ...models.email_template import EmailTemplate

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        language = request.form.get('language', 'en')
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()
        is_global = request.form.get('is_global') == 'on'

        if not name or not subject or not body:
            flash('Name, subject, and body are required.', 'error')
            return redirect(url_for('admin.create_email_template'))

        template = EmailTemplate(
            name=name,
            language=language,
            subject=subject,
            body=body,
            is_global=is_global,
            created_by=current_user.id
        )
        db.session.add(template)
        db.session.commit()

        logger.info(f'[email_templates] Created template "{name}" by admin {current_user.id}')
        flash('Template created successfully.', 'success')
        return redirect(url_for('admin.email_templates'))

    return render_template('admin/email_template_form.html', template=None)


@admin_bp.route('/email-templates/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_email_template(id):
    """Edit an email template."""
    from ...models.email_template import EmailTemplate

    template = EmailTemplate.query.filter(
        EmailTemplate.id == id,
        EmailTemplate.deleted_at.is_(None)
    ).first_or_404()

    if request.method == 'POST':
        template.name = request.form.get('name', '').strip()
        template.language = request.form.get('language', 'en')
        template.subject = request.form.get('subject', '').strip()
        template.body = request.form.get('body', '').strip()
        template.is_global = request.form.get('is_global') == 'on'

        if not template.name or not template.subject or not template.body:
            flash('Name, subject, and body are required.', 'error')
            return redirect(url_for('admin.edit_email_template', id=id))

        db.session.commit()
        logger.info(f'[email_templates] Updated template {id} by admin {current_user.id}')
        flash('Template updated successfully.', 'success')
        return redirect(url_for('admin.email_templates'))

    return render_template('admin/email_template_form.html', template=template)


@admin_bp.route('/email-templates/<int:id>/delete', methods=['POST'])
@admin_required
def delete_email_template(id):
    """Delete an email template (soft delete)."""
    from ...models.email_template import EmailTemplate

    template = EmailTemplate.query.filter(
        EmailTemplate.id == id,
        EmailTemplate.deleted_at.is_(None)
    ).first_or_404()

    template.deleted_at = datetime.utcnow()
    db.session.commit()

    logger.info(f'[email_templates] Deleted template {id} by admin {current_user.id}')
    flash('Template deleted successfully.', 'success')
    return redirect(url_for('admin.email_templates'))


@admin_bp.route('/api/email-templates')
@admin_required
def api_email_templates():
    """API to get email templates for the send_link page."""
    from ...models.email_template import EmailTemplate

    templates = EmailTemplate.query.filter(
        EmailTemplate.deleted_at.is_(None),
        EmailTemplate.is_global == True
    ).order_by(EmailTemplate.name).all()

    result = []
    for t in templates:
        result.append({
            'id': t.id,
            'name': t.name,
            'language': t.language,
            'subject': t.subject,
            'body': t.body
        })

    return jsonify(result)

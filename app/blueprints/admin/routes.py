import logging
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
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
from ...models.donor_note import DonorNote
from ...models.message import MessageQueue


# =============================================================================
# DASHBOARD
# =============================================================================

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with stats."""
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

    # Yesterday's stats
    yesterday_start = today_start - timedelta(days=1)
    yesterday_income = db.session.query(func.sum(Donation.amount)).filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= yesterday_start,
        Donation.created_at < today_start
    ).scalar() or 0

    yesterday_count = Donation.query.filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= yesterday_start,
        Donation.created_at < today_start
    ).count()

    # Breakdown by processor and currency
    processor_breakdown = db.session.query(
        Donation.payment_processor,
        Donation.currency,
        func.count(Donation.id).label('count'),
        func.sum(Donation.amount).label('total')
    ).filter(
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).group_by(Donation.payment_processor, Donation.currency).all()

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
        yesterday_income=yesterday_income / 100,
        yesterday_count=yesterday_count,
        recent_donations=recent_donations,
        top_salespersons=top_salespersons,
        processor_breakdown=processor_breakdown
    )


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
            allowed_processors=request.form.getlist('allowed_processors') or None,
            language_pref=(request.form.get('language_pref') or 'en').strip().lower(),
            date_format=(request.form.get('date_format') or 'auto').strip().lower(),
            active=True
        )
        db.session.add(user)
        db.session.commit()

        flash(f'Salesperson created! Username: {username}, Temp Password: {temp_password}', 'success')
        return redirect(url_for('admin.salespersons'))

    from ...models.payment_processor import PaymentProcessor
    processors = PaymentProcessor.get_enabled()
    return render_template('admin/salesperson_form.html', salesperson=None, processors=processors)


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
        salesperson.allowed_processors = request.form.getlist('allowed_processors') or None
        if request.form.get('language_pref'):
            salesperson.language_pref = request.form.get('language_pref').strip().lower()
        if request.form.get('date_format'):
            salesperson.date_format = request.form.get('date_format').strip().lower()

        db.session.commit()
        flash('Salesperson updated successfully.', 'success')
        return redirect(url_for('admin.salespersons'))

    from ...models.payment_processor import PaymentProcessor
    processors = PaymentProcessor.get_enabled()
    return render_template('admin/salesperson_form.html', salesperson=salesperson, processors=processors)


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


@admin_bp.route('/donations/<int:id>/reissue-receipt', methods=['POST'])
@login_required
def reissue_donation_receipt(id):
    """Force-regenerate / re-issue a receipt.

    Query string ``via`` selects the channel:
      * ``via=yesh``   — issue an Israeli kabala via YeshInvoice
                         (`yeshinvoice_service.create_receipt`).
      * ``via=matat``  — regenerate our local PDF from the current template
                         and email it via Mailtrap. Bypasses the Israel-resident
                         country gate so an IL donor who never received their
                         Israeli kabala can still get a Matat-branded receipt.

    Default is ``matat`` (matches the original Reissue behaviour for
    non-IL donors).
    """
    from ...services.receipt_service import (
        create_receipt_atomic, regenerate_receipt_pdf,
    )
    from ...services.email_service import send_receipt_email
    import os, traceback

    via = (request.args.get('via') or 'matat').lower()
    if via not in ('matat', 'yesh'):
        via = 'matat'

    try:
        donation = Donation.query.get_or_404(id)
        donor = Donor.query.get(donation.donor_id)

        if not donor:
            return jsonify({'error': 'Donor not found'}), 400
        if donation.status != 'succeeded':
            return jsonify({'error': 'Can only reissue receipts for successful donations.'}), 400

        # ---- YeshInvoice path ----
        if via == 'yesh':
            # YeshInvoice issues *Israeli kabalas* (קבלות) — denominated in ILS
            # only. A USD donation cannot be reissued through YeshInvoice;
            # those use the Matat receipt path.
            currency = (donation.currency or '').upper()
            if currency != 'ILS':
                return jsonify({
                    'error': f'YeshInvoice is ILS-only. This donation is in {currency or "?"}; reissue via the Matat email path instead.'
                }), 400

            from ...services.yeshinvoice_service import (
                create_receipt as yesh_create_receipt,
                get_yeshinvoice_config,
            )
            cfg = get_yeshinvoice_config()
            if not cfg:
                return jsonify({'error': 'YeshInvoice is not enabled or credentials are missing. Set them in Admin → Settings.'}), 400
            result = yesh_create_receipt(donation, donor, config=cfg)
            if result.get('success'):
                return jsonify({
                    'success': True,
                    'message': (
                        f'YeshInvoice receipt {result.get("doc_number") or result.get("doc_id") or ""} '
                        f'created for {donor.full_name or donor.email}.'
                    ),
                    'doc_id': result.get('doc_id'),
                    'doc_number': result.get('doc_number'),
                    'pdf_url': result.get('pdf_url'),
                })
            return jsonify({
                'error': f'YeshInvoice rejected the request: {result.get("error", "unknown error")}'
            }), 502

        # ---- Matat email path ----
        if not donor.email or 'no-email-' in (donor.email or ''):
            return jsonify({'error': 'Donor has no email on file — cannot send Matat receipt.'}), 400

        # Receipt may not exist for older donations from the previous platform.
        receipt = donation.receipt
        if not receipt:
            receipt = create_receipt_atomic(donation, donor)
            db.session.commit()

        # Always regenerate so the donor gets the latest template.
        try:
            regenerate_receipt_pdf(receipt)
        except Exception as e:
            traceback.print_exc()
            return jsonify({'error': f'PDF regeneration failed: {e}'}), 500

        if not (receipt.pdf_path and os.path.exists(receipt.pdf_path)):
            return jsonify({'error': 'Regeneration produced no PDF.'}), 500

        success = send_receipt_email(donor, donation, receipt, override_country_gate=True)
        if not success:
            return jsonify({'error': 'Email send failed — check provider config.'}), 500

        return jsonify({
            'success': True,
            'message': f'Receipt {receipt.receipt_number} regenerated and emailed to {donor.email}.',
            'receipt_number': receipt.receipt_number,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/donations/<int:id>/yeshinvoice-pdf')
@admin_required
def yeshinvoice_pdf_proxy(id):
    """Proxy YeshInvoice's PDF so the browser opens it inline.

    YeshInvoice serves their PDFs with `Content-Disposition: attachment`,
    which forces every browser to download the file rather than open it
    in the built-in PDF viewer. Operators want to *see* the receipt
    immediately to verify formatting before forwarding the link to the
    donor — a forced download interrupts that flow.

    We fetch the PDF server-side and re-emit it with `inline`
    disposition. The original key stays on YeshInvoice's side; we never
    expose it to the browser.
    """
    import requests
    from flask import Response

    donation = Donation.query.get_or_404(id)
    if not donation.yeshinvoice_pdf_url:
        return jsonify({'error': 'No YeshInvoice receipt on this donation.'}), 404

    try:
        r = requests.get(donation.yeshinvoice_pdf_url, timeout=30)
        if r.status_code != 200 or not r.content:
            return jsonify({'error': f'YeshInvoice PDF fetch failed: {r.status_code}'}), 502

        filename = f'matat-receipt-{donation.yeshinvoice_doc_number or donation.id}.pdf'
        return Response(
            r.content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{filename}"',
                'Cache-Control': 'private, max-age=300',
            },
        )
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Network error fetching YeshInvoice PDF: {e}'}), 502


@admin_bp.route('/donations/<int:id>/yeshinvoice-void', methods=['POST'])
@admin_required
def yeshinvoice_void(id):
    """Void a YeshInvoice receipt by issuing a credit document.

    Per YeshInvoice support (2026-04-29): issued documents cannot be
    deleted under Israeli tax law. The supported "void" path is to
    issue a matching negative-amount document via createDocument with
    `DocumentType=4`. The original receipt and the credit doc both
    stay in the records; they net to zero.

    On success, `create_credit_note` clears the donation's
    yeshinvoice_doc_id / _doc_number / _pdf_url so the admin page no
    longer shows the link to the now-offset receipt and a fresh
    receipt can be issued.

    Admin-only — see @admin_required.
    """
    import traceback
    try:
        donation = Donation.query.get_or_404(id)
        if not donation.yeshinvoice_doc_id:
            return jsonify({'error': 'This donation has no active YeshInvoice receipt to void.'}), 400

        from ...services.yeshinvoice_service import (
            create_credit_note,
            get_yeshinvoice_config,
        )
        cfg = get_yeshinvoice_config()
        if not cfg:
            return jsonify({'error': 'YeshInvoice is not enabled or credentials are missing.'}), 400

        result = create_credit_note(donation, config=cfg)
        if not result.get('success'):
            return jsonify({'error': f'YeshInvoice rejected the void: {result.get("error", "unknown error")}'}), 502

        return jsonify({
            'success': True,
            'doc_id':     result.get('doc_id'),
            'doc_number': result.get('doc_number'),
            'pdf_url':    result.get('pdf_url'),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/donations/<int:id>/yeshinvoice-generate', methods=['POST'])
@login_required
def yeshinvoice_generate(id):
    """Generate a YeshInvoice kabala for this donation — DO NOT email donor.

    The YeshInvoice service already sends `SendEmail: false / SendSMS: false`
    in the createDocument payload, so YeshInvoice itself never reaches the
    donor. This endpoint exists so the operator can preview / download
    the kabala PDF, hand-check formatting (alignment is finicky), and
    forward it manually. Once we trust the format we can wire it into
    the auto-receipt path.

    Returns JSON `{success, doc_id, doc_number, pdf_url}` on success;
    `{error}` otherwise.
    """
    import traceback

    try:
        donation = Donation.query.get_or_404(id)
        donor = Donor.query.get(donation.donor_id)

        if not donor:
            return jsonify({'error': 'Donor not found'}), 400
        if donation.status != 'succeeded':
            return jsonify({'error': 'Can only issue YeshInvoice receipts for successful donations.'}), 400

        # YeshInvoice = ILS only.
        currency = (donation.currency or '').upper()
        if currency != 'ILS':
            return jsonify({
                'error': f'YeshInvoice is ILS-only. This donation is in {currency or "?"}.'
            }), 400

        # Block double-create — the API has no delete, so we don't want to
        # accidentally generate two for the same donation. Operator can
        # force a re-issue by clearing yeshinvoice_doc_id first if needed.
        if donation.yeshinvoice_doc_id:
            return jsonify({
                'success': True,
                'already_exists': True,
                'message': f'YeshInvoice doc {donation.yeshinvoice_doc_number} was already generated for this donation.',
                'doc_id':     donation.yeshinvoice_doc_id,
                'doc_number': donation.yeshinvoice_doc_number,
                'pdf_url':    donation.yeshinvoice_pdf_url or '',
            })

        from ...services.yeshinvoice_service import (
            create_receipt as yesh_create_receipt,
            get_yeshinvoice_config,
        )
        cfg = get_yeshinvoice_config()
        if not cfg:
            return jsonify({'error': 'YeshInvoice is not enabled or credentials are missing. Set them in Admin → Settings.'}), 400

        result = yesh_create_receipt(donation, donor, config=cfg)
        if not result.get('success'):
            return jsonify({'error': f'YeshInvoice rejected the request: {result.get("error", "unknown error")}'}), 502

        return jsonify({
            'success': True,
            'doc_id':     result.get('doc_id'),
            'doc_number': result.get('doc_number'),
            'pdf_url':    result.get('pdf_url'),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
# =============================================================================
# DONATIONS MANAGEMENT
# =============================================================================

@admin_bp.route('/api/donors/search')
@login_required
def api_search_donors():
    """Autocomplete lookup for existing donors by name / email / phone."""
    from sqlalchemy import or_, func
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify([])
    like = f'%{q}%'
    donors = Donor.query.filter(
        Donor.deleted_at.is_(None),
        or_(
            func.concat(Donor.first_name, ' ', Donor.last_name).ilike(like),
            func.concat(Donor.hebrew_first_name, ' ', Donor.hebrew_last_name).ilike(like),
            Donor.hebrew_first_name.ilike(like),
            Donor.hebrew_last_name.ilike(like),
            Donor.company_name.ilike(like),
            Donor.email.ilike(like),
            Donor.phone.ilike(like),
            Donor.teudat_zehut.ilike(like),
        )
    ).order_by(Donor.last_name, Donor.first_name).limit(15).all()
    return jsonify([{
        'id': d.id,
        'first_name': d.first_name or '',
        'last_name': d.last_name or '',
        'hebrew_first_name': d.hebrew_first_name or '',
        'hebrew_last_name': d.hebrew_last_name or '',
        'company_name': d.company_name or '',
        'email': d.email if d.email and 'no-email-' not in d.email else '',
        'phone': d.phone or '',
        'teudat_zehut': d.teudat_zehut or '',
        'address_line1': d.address_line1 or '',
        'address_line2': d.address_line2 or '',
        'city': d.city or '',
        'state': d.state or '',
        'zip': d.zip or '',
        'country': d.country or 'US',
        # Israeli address (used by Shva / YeshInvoice receipts)
        'il_address_line1': d.il_address_line1 or '',
        'il_address_line2': d.il_address_line2 or '',
        'il_city': d.il_city or '',
        'il_zip': d.il_zip or '',
        'has_il_address': bool(d.il_address_line1 or d.il_city or d.il_zip),
        'has_foreign_address': bool(d.address_line1 or d.city or d.zip),
        # Phones — Israeli vs foreign × home/cell/fax
        'il_phone_home': d.il_phone_home or '',
        'il_phone_cell': d.il_phone_cell or '',
        'il_phone_fax': d.il_phone_fax or '',
        'foreign_phone_home': d.foreign_phone_home or '',
        'foreign_phone_cell': d.foreign_phone_cell or '',
        'foreign_phone_fax': d.foreign_phone_fax or '',
    } for d in donors])


@admin_bp.route('/donations/new-check', methods=['GET', 'POST'])
@login_required
def new_check_donation():
    """Record a manual (check or Zelle) donation and optionally email the receipt."""
    from ...services.receipt_service import create_receipt_atomic
    from ...services.email_service import send_receipt_email
    from datetime import datetime as _dt
    from werkzeug.utils import secure_filename
    import os, uuid

    ALLOWED_IMAGE_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'heic'}

    if request.method == 'POST':
        donor_id_str = (request.form.get('donor_id') or '').strip()
        first_name = (request.form.get('first_name') or '').strip()
        last_name = (request.form.get('last_name') or '').strip()
        company_name = (request.form.get('company_name') or '').strip()
        email = (request.form.get('email') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        address_line1 = (request.form.get('address_line1') or '').strip()
        address_line2 = (request.form.get('address_line2') or '').strip()
        city = (request.form.get('city') or '').strip()
        state = (request.form.get('state') or '').strip()
        zip_code = (request.form.get('zip') or '').strip()
        country = (request.form.get('country') or 'US').strip() or 'US'
        amount_str = (request.form.get('amount') or '').strip()
        payment_method = (request.form.get('payment_method') or 'check').strip().lower()
        if payment_method not in ('check', 'zelle', 'credit_card', 'wire'):
            payment_method = 'check'
        reference = (request.form.get('reference') or '').strip()
        # Currency: USD by default, ILS for Israeli donors. The receipt-
        # routing logic in send_receipt_email reads donor.country (NOT
        # currency) — but the donation's currency still has to match the
        # actual charge so the receipt shows the right symbol.
        currency = (request.form.get('currency') or 'USD').strip().lower()
        if currency not in ('usd', 'ils'):
            currency = 'usd'
        payment_date_str = (request.form.get('payment_date') or '').strip()
        memo = (request.form.get('memo') or '').strip()
        # Credit-card-specific fields (manual entry, no live charge)
        card_brand = (request.form.get('card_brand') or '').strip().lower()
        card_last4 = (request.form.get('card_last4') or '').strip()
        # Keep only digits, max 4
        card_last4 = ''.join(ch for ch in card_last4 if ch.isdigit())[:4]
        receipt_override = (request.form.get('receipt_number') or '').strip()
        send_email = request.form.get('send_email') == 'on'

        bcc_raw = (request.form.get('bcc') or '').strip()
        bcc_list = []
        for item in bcc_raw.replace(';', ',').split(','):
            addr = item.strip()
            if addr and '@' in addr and '.' in addr.split('@')[-1] and addr not in bcc_list:
                bcc_list.append(addr)

        if not (first_name and last_name) and not company_name:
            flash('Enter a donor name (first + last) or a company name.', 'error')
            return redirect(url_for('admin.new_check_donation'))
        try:
            amount_dollars = float(amount_str)
        except ValueError:
            amount_dollars = 0
        if amount_dollars <= 0:
            flash('Amount must be greater than zero.', 'error')
            return redirect(url_for('admin.new_check_donation'))

        # Prefer explicit donor_id from the lookup picker; else match by email or name.
        donor = None
        if donor_id_str.isdigit():
            donor = Donor.query.filter(
                Donor.id == int(donor_id_str),
                Donor.deleted_at.is_(None),
            ).first()
        if not donor and email:
            donor = Donor.query.filter(
                Donor.email == email,
                Donor.deleted_at.is_(None),
            ).first()
        if not donor:
            donor = Donor.query.filter(
                Donor.first_name == first_name,
                Donor.last_name == last_name,
                Donor.deleted_at.is_(None),
            ).first()

        def _fill(attr, new_val, overwrite=False):
            """Set attr only if a non-empty value was supplied (and either it's empty or overwrite=True)."""
            if new_val and (overwrite or not getattr(donor, attr, None)):
                setattr(donor, attr, new_val)

        if donor:
            # Name and address: if the operator typed something different from what's on file, update it.
            _fill('first_name', first_name, overwrite=True)
            _fill('last_name', last_name, overwrite=True)
            _fill('company_name', company_name, overwrite=True)
            _fill('email', email)  # never overwrite an existing real email
            _fill('phone', phone)
            _fill('address_line1', address_line1, overwrite=True)
            _fill('address_line2', address_line2, overwrite=True)
            _fill('city', city, overwrite=True)
            _fill('state', state, overwrite=True)
            _fill('zip', zip_code, overwrite=True)
            _fill('country', country, overwrite=True)
        else:
            # Use empty strings (not NULL) for person-name columns when only a
            # company is supplied — schema is NOT NULL.
            email_slug = (first_name or last_name or company_name or 'unnamed').lower().replace(' ', '.')
            donor = Donor(
                first_name=first_name or '',
                last_name=last_name or '',
                company_name=company_name or None,
                email=email or f'no-email-{email_slug}@matatmordechai.org',
                phone=phone or None,
                address_line1=address_line1 or None,
                address_line2=address_line2 or None,
                city=city or None,
                state=state or None,
                zip=zip_code or None,
                country=country,
            )
            db.session.add(donor)
            db.session.flush()

        payment_date_iso = None
        if payment_date_str:
            try:
                payment_date_iso = _dt.strptime(payment_date_str, '%Y-%m-%d').date().isoformat()
            except ValueError:
                payment_date_iso = payment_date_str

        # Optional image upload (check photo / Zelle screenshot)
        saved_image_path = None
        image_file = request.files.get('check_image')
        if image_file and image_file.filename:
            ext = image_file.filename.rsplit('.', 1)[-1].lower() if '.' in image_file.filename else ''
            if ext not in ALLOWED_IMAGE_EXT:
                flash(f'Unsupported image type: .{ext}. Allowed: {", ".join(sorted(ALLOWED_IMAGE_EXT))}.', 'error')
                return redirect(url_for('admin.new_check_donation'))
            upload_dir = '/var/www/matat/uploads/check_images'
            os.makedirs(upload_dir, exist_ok=True)
            safe_base = secure_filename(f'{payment_method}_{donor.id}_{uuid.uuid4().hex[:8]}')
            saved_image_path = os.path.join(upload_dir, f'{safe_base}.{ext}')
            image_file.save(saved_image_path)

        # Optional additional email attachments (any number, any file type)
        email_attachment_paths = []
        attach_dir = '/var/www/matat/uploads/email_attachments'
        for f in request.files.getlist('email_attachments'):
            if not f or not f.filename:
                continue
            os.makedirs(attach_dir, exist_ok=True)
            safe_name = secure_filename(f.filename) or 'attachment'
            dest = os.path.join(attach_dir, f'{donor.id}_{uuid.uuid4().hex[:8]}_{safe_name}')
            f.save(dest)
            email_attachment_paths.append(dest)

        # If a salesperson is filling this in, credit them; admins enter
        # for nobody by default and can re-assign on the donations list.
        sp_id = current_user.id if getattr(current_user, 'role', None) == 'salesperson' else None
        amount_cents = int(round(amount_dollars * 100))

        # Map the form's "credit_card" choice to the manual_card processor;
        # check/zelle map directly. Card metadata flows into the existing
        # payment_method_* columns the receipt templates already render.
        processor_code = 'manual_card' if payment_method == 'credit_card' else payment_method
        donation_kwargs = dict(
            donor_id=donor.id,
            salesperson_id=sp_id,
            payment_processor=processor_code,
            processor_confirmation=reference or None,
            processor_metadata={
                'payment_method': payment_method,
                'reference': reference or None,
                'payment_date': payment_date_iso,
                'memo': memo or None,
                'image_path': saved_image_path,
                'email_attachments': email_attachment_paths or None,
                'entered_by_user_id': current_user.id,
            },
            amount=amount_cents,
            currency=currency,
            status='succeeded',
            donation_type='one_time',
            source=processor_code,
        )
        if payment_method == 'credit_card':
            donation_kwargs['payment_method_type'] = 'card'
            if card_brand:
                donation_kwargs['payment_method_brand'] = card_brand
            if card_last4:
                donation_kwargs['payment_method_last4'] = card_last4
        donation = Donation(**donation_kwargs)
        db.session.add(donation)
        db.session.flush()

        try:
            receipt = create_receipt_atomic(donation, donor, override_number=receipt_override or None)
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'error')
            return redirect(url_for('admin.new_check_donation'))
        db.session.commit()

        label = {'check': 'Check', 'zelle': 'Zelle', 'credit_card': 'Credit Card', 'wire': 'Wire Transfer'}.get(payment_method, payment_method.title())
        if send_email:
            if not donor.email or 'no-email-' in donor.email:
                flash(f'{label} donation saved (Receipt {receipt.receipt_number}), but donor has no email — skipped sending.', 'warning')
            else:
                ok = send_receipt_email(
                    donor, donation, receipt,
                    extra_attachments=email_attachment_paths or None,
                    extra_bcc=bcc_list or None,
                )
                if ok:
                    donation.receipt_sent = True
                    donation.receipt_sent_at = datetime.utcnow()
                    db.session.commit()
                    notes = []
                    if email_attachment_paths:
                        notes.append(f'{len(email_attachment_paths)} attachment(s)')
                    if bcc_list:
                        notes.append(f'BCC: {", ".join(bcc_list)}')
                    extra_note = f' ({"; ".join(notes)})' if notes else ''
                    flash(f'{label} donation saved and receipt {receipt.receipt_number} emailed to {donor.email}{extra_note}.', 'success')
                else:
                    flash(f'{label} donation saved (Receipt {receipt.receipt_number}), but email sending failed.', 'warning')
        else:
            flash(f'{label} donation saved. Receipt {receipt.receipt_number} generated.', 'success')

        if getattr(current_user, 'role', None) == 'admin':
            return redirect(url_for('admin.donations', processor=processor_code))
        return redirect(url_for('salesperson.my_donations'))

    return render_template('admin/new_check_donation.html')


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
    from ...models.payment_processor import PaymentProcessor

    status = request.args.get('status', 'all')
    processor = request.args.get('processor', 'all')
    charity = request.args.get('charity', 'all')
    page = int(request.args.get('page', 1))
    per_page = 50

    # Tab list: enabled processors the current user is allowed to view.
    all_enabled = PaymentProcessor.get_enabled()
    visible_processors = [p for p in all_enabled if current_user.can_view_processor(p.code)]
    visible_codes = [p.code for p in visible_processors]

    # If the requested processor is outside the user's allow-list, reset to 'all'.
    if processor != 'all' and processor not in visible_codes:
        processor = 'all'

    query = Donation.query.filter(Donation.deleted_at.is_(None))

    if status != 'all':
        query = query.filter(Donation.status == status)

    if processor != 'all':
        query = query.filter(Donation.payment_processor == processor)
    elif current_user.allowed_processors:
        # Restricted user viewing "All" — scope to their allowed processors.
        query = query.filter(Donation.payment_processor.in_(visible_codes))

    # Charity (Groupe / fund) filter — populated for Nedarim donations.
    # 'untagged' = NULL or empty; '<name>' = exact match.
    if charity == 'untagged':
        query = query.filter((Donation.charity.is_(None)) | (Donation.charity == ''))
    elif charity != 'all':
        query = query.filter(Donation.charity == charity)

    # Charity tabs — only the ones the current user explicitly opted into
    # via /admin/donation-permissions are surfaced as tabs. By default
    # users have visible_charities=NULL → no charity strip rendered (just
    # the underlying table column). Keeps the page clean for users who
    # don't track charities (e.g., Gittle is stripe-only and doesn't
    # work with Nedarim campaigns at all).
    user_visible = list(current_user.visible_charities or [])
    if user_visible:
        from sqlalchemy import func as _f
        rows = (db.session.query(Donation.charity, _f.count(Donation.id))
                .filter(Donation.deleted_at.is_(None),
                        Donation.charity.in_(user_visible))
                .group_by(Donation.charity).all())
        counts = {c: n for c, n in rows}
        # Preserve the operator's chosen ordering even when a tab has 0
        # rows so far.
        charity_rows = [(c, counts.get(c, 0)) for c in user_visible]
    else:
        charity_rows = []
    untagged_count = 0  # untagged tab removed with the auto-strip

    donations = query.order_by(Donation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Salesperson dropdown: include admins too — some donations are entered
    # or attributed to admin users (e.g. Sara), so the dropdown needs to
    # show every active human, not just role='salesperson'.
    salespersons = User.query.filter(
        User.role.in_(['salesperson', 'admin']),
        User.deleted_at.is_(None),
        User.active.is_(True),
    ).order_by(User.role.desc(), User.first_name).all()

    return render_template(
        'admin/donations.html',
        donations=donations,
        status_filter=status,
        processor_filter=processor,
        charity_filter=charity,
        charity_rows=charity_rows,
        untagged_count=untagged_count,
        visible_processors=visible_processors,
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

    # Get lists for dropdowns — include admins (e.g. Sara) since they can
    # also be the attributed user on a donation.
    salespersons = User.query.filter(
        User.role.in_(['salesperson', 'admin']),
        User.deleted_at.is_(None),
        User.active.is_(True),
    ).order_by(User.role.desc(), User.first_name).all()

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
    """List and search donors. Multi-office segregation: filter by owner.

    `office` query param values:
      - 'mine'   → only donors owned by the current user (default for non-admin
                   when set; admins see 'all' by default)
      - 'all'    → admins only; lift the office filter
      - <user_id>→ admins only; show donors owned by that user

    The office filter is applied AFTER the test/real and search filters.
    """
    from ...models import User

    search = request.args.get('q', '').strip()
    filter_type = request.args.get('type', 'all')  # all, test, real
    office = request.args.get('office', '').strip()
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

    # ---- Office (owner) filter ----
    is_admin = (getattr(current_user, 'role', None) == 'admin')
    selected_owner_id = None
    if not office:
        # Default: admins see 'all', non-admins are scoped to their own.
        office = 'all' if is_admin else 'mine'

    if office == 'mine':
        selected_owner_id = current_user.id
        query = query.filter(Donor.owner_user_id == current_user.id)
    elif office == 'all':
        if not is_admin:
            # Non-admins are not allowed to lift the filter.
            selected_owner_id = current_user.id
            query = query.filter(Donor.owner_user_id == current_user.id)
            office = 'mine'
        # else: admin sees everything
    else:
        # office is a user id string
        try:
            uid = int(office)
        except (TypeError, ValueError):
            uid = None
        if uid is not None and is_admin:
            selected_owner_id = uid
            query = query.filter(Donor.owner_user_id == uid)
        else:
            # Non-admin trying to view another office, or bad value -> scope to mine
            selected_owner_id = current_user.id
            query = query.filter(Donor.owner_user_id == current_user.id)
            office = 'mine'

    donors_list = query.order_by(Donor.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Office tab counts (admins only — non-admins don't switch offices).
    office_options = []
    if is_admin:
        rows = (
            db.session.query(Donor.owner_user_id, db.func.count(Donor.id))
            .filter(Donor.deleted_at.is_(None))
            .group_by(Donor.owner_user_id)
            .all()
        )
        counts_by_owner = {oid: c for oid, c in rows}
        active_users = User.query.filter(User.deleted_at.is_(None)).order_by(User.username).all()
        for u in active_users:
            office_options.append({
                'user_id':   u.id,
                'username':  u.username,
                'name':      f'{u.first_name or ""} {u.last_name or ""}'.strip() or u.username,
                'count':     counts_by_owner.get(u.id, 0),
            })
        # Also surface unassigned donors if any
        unassigned = counts_by_owner.get(None, 0)
        if unassigned:
            office_options.append({'user_id': None, 'username': '—', 'name': '(לא משויך)', 'count': unassigned})

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
        real_donors=real_donors,
        office=office,
        selected_owner_id=selected_owner_id,
        office_options=office_options,
        is_admin=is_admin,
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


@admin_bp.route('/donors/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def donor_edit(id):
    """Edit donor information."""
    donor = Donor.query.get_or_404(id)

    if request.method == 'POST':
        donor.first_name = request.form.get('first_name', donor.first_name).strip()
        donor.last_name = request.form.get('last_name', donor.last_name).strip()
        donor.email = request.form.get('email', donor.email).strip() or None
        donor.phone = request.form.get('phone', '').strip() or None
        donor.teudat_zehut = request.form.get('teudat_zehut', '').strip() or None
        donor.address_line1 = request.form.get('address_line1', '').strip() or None
        donor.address_line2 = request.form.get('address_line2', '').strip() or None
        donor.city = request.form.get('city', '').strip() or None
        donor.state = request.form.get('state', '').strip() or None
        donor.zip = request.form.get('zip', '').strip() or None
        donor.country = request.form.get('country', 'US').strip()
        donor.language_pref = request.form.get('language_pref', 'en')
        donor.title = request.form.get('title', '').strip() or None
        donor.suffix = request.form.get('suffix', '').strip() or None
        donor.spouse_name = request.form.get('spouse_name', '').strip() or None

        # Israeli address + phones
        donor.il_address_line1 = request.form.get('il_address_line1', '').strip() or None
        donor.il_address_line2 = request.form.get('il_address_line2', '').strip() or None
        donor.il_city = request.form.get('il_city', '').strip() or None
        donor.il_zip = request.form.get('il_zip', '').strip() or None
        donor.il_phone = request.form.get('il_phone', '').strip() or None
        donor.il_phone_cell = request.form.get('il_phone_cell', '').strip() or None
        donor.phone_cell = request.form.get('phone_cell', '').strip() or None

        db.session.commit()
        logger.info(f'[admin] Donor {donor.id} edited by admin {current_user.id}')
        flash(f'Donor {donor.full_name} updated.', 'success')

        action = request.form.get('action', 'save')
        if action == 'save_and_charge':
            return redirect(url_for('ztorm.charge_card', donor_id=donor.id))
        return redirect(url_for('admin.donor_detail', id=donor.id))

    return render_template('admin/donor_edit.html', donor=donor)


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


@admin_bp.route('/donors/fix-unknown')
@admin_required
def fix_unknown_donors():
    """Show list of donors with Unknown names for bulk editing."""
    donors_list = Donor.query.filter(
        Donor.deleted_at.is_(None),
        db.or_(
            Donor.first_name == 'Unknown',
            Donor.first_name == '',
            Donor.first_name.is_(None),
            Donor.last_name == '',
            Donor.last_name.is_(None)
        )
    ).order_by(Donor.created_at.desc()).all()

    return render_template('admin/fix_unknown_donors.html', donors=donors_list)


@admin_bp.route('/donors/<int:id>/update-name', methods=['POST'])
@admin_required
def update_donor_name(id):
    """Update a donor's name via AJAX."""
    donor = Donor.query.get_or_404(id)
    data = request.get_json()

    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()

    if not first_name:
        return jsonify({'success': False, 'error': 'First name is required'}), 400

    donor.first_name = first_name
    donor.last_name = last_name
    db.session.commit()

    logger.info(f'[update_donor_name] Updated donor {id} name to {first_name} {last_name}')
    return jsonify({'success': True, 'full_name': donor.full_name})


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

@admin_bp.route('/donation-permissions', methods=['GET', 'POST'])
@admin_required
def donation_permissions():
    """Per-user donation-visibility table.

    Lets an admin tick which non-admin users can see the full
    `/admin/donations` list (`can_view_all_donations`) and, when a row
    has any `allowed_processors` checked, scope what processor tabs
    they see. Admins are listed for transparency but their flag is
    forced True regardless of the database value.
    """
    from ...models.payment_processor import PaymentProcessor

    processors = PaymentProcessor.get_enabled()
    users = (User.query
             .filter(User.deleted_at.is_(None), User.active.is_(True))
             .order_by(User.role.desc(), User.username)
             .all())

    # Distinct charities currently in the donations table — used to
    # populate the per-user charity-tab checkbox group.
    from sqlalchemy import func as _f
    charity_options = [c for (c,) in (db.session.query(Donation.charity)
                                       .filter(Donation.deleted_at.is_(None),
                                               Donation.charity.isnot(None),
                                               Donation.charity != '')
                                       .group_by(Donation.charity)
                                       .order_by(_f.count(Donation.id).desc())
                                       .all())]

    if request.method == 'POST':
        view_all_ids = set(int(x) for x in request.form.getlist('view_all_user_id') if x.isdigit())
        for u in users:
            if u.role != 'admin':
                u.can_view_all_donations = (u.id in view_all_ids)
                allowed = request.form.getlist(f'processors_{u.id}')
                u.allowed_processors = allowed or None
            # Charity tabs apply to everyone (including admins) since
            # this is a personal display preference, not a permission.
            chars = request.form.getlist(f'charities_{u.id}')
            u.visible_charities = chars or None
        db.session.commit()
        flash('Donation permissions updated.', 'success')
        return redirect(url_for('admin.donation_permissions'))

    return render_template(
        'admin/donation_permissions.html',
        users=users,
        processors=processors,
        charity_options=charity_options,
    )



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

        # Email provider selection
        config.email_provider = request.form.get('email_provider', 'mailtrap').strip()

        # ActiveTrail settings
        config.activetrail_api_key = request.form.get('activetrail_api_key', '').strip() or None
        activetrail_profile_id = request.form.get('activetrail_profile_id', '').strip()
        config.activetrail_profile_id = int(activetrail_profile_id) if activetrail_profile_id else None
        config.activetrail_from_email = request.form.get('activetrail_from_email', '').strip() or None
        config.activetrail_from_name = request.form.get('activetrail_from_name', '').strip() or None

        # AI API keys (encrypted in DB)
        anthropic_key = request.form.get('anthropic_api_key', '').strip()
        if anthropic_key and anthropic_key != '••••••••':
            config.anthropic_api_key = anthropic_key

        openai_key = request.form.get('openai_api_key', '').strip()
        if openai_key and openai_key != '••••••••':
            config.openai_api_key = openai_key

        google_key = request.form.get('google_api_key', '').strip()
        if google_key and google_key != '••••••••':
            config.google_api_key = google_key

        # YeshInvoice settings
        config.yeshinvoice_enabled = request.form.get('yeshinvoice_enabled') == 'on'
        config.yeshinvoice_user_key = request.form.get('yeshinvoice_user_key', '').strip() or None
        config.yeshinvoice_secret_key = request.form.get('yeshinvoice_secret_key', '').strip() or None
        config.yeshinvoice_account_id = request.form.get('yeshinvoice_account_id', '').strip() or None
        config.yeshinvoice_default_doc_type = request.form.get('yeshinvoice_default_doc_type', 'receipt').strip()

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

    # Surface the configured Microsoft Graph mailbox (if any) so the
    # settings page can show a status panel for it. Credentials live on
    # the email_inbox_providers row, not in config_settings.
    from ...models.email_inbox_provider import EmailInboxProvider
    msgraph_provider = (EmailInboxProvider.query
                        .filter_by(code='msgraph', deleted_at=None)
                        .first())
    return render_template('admin/settings.html', config=config,
                           msgraph_provider=msgraph_provider)


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


@admin_bp.route('/settings/test-yeshinvoice', methods=['POST'])
@admin_required
def test_yeshinvoice():
    """Test YeshInvoice API connection."""
    from ...services.yeshinvoice_service import test_connection

    data = request.get_json() or {}
    config = {
        'user_key': data.get('user_key', ''),
        'secret_key': data.get('secret_key', ''),
        'account_id': data.get('account_id', ''),
        'default_doc_type': 'receipt',
    }

    if not config['user_key'] or not config['secret_key']:
        return jsonify({'success': False, 'error': 'User Key and Secret Key are required'})

    result = test_connection(config=config)
    return jsonify(result)


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
    from werkzeug.utils import secure_filename
    import os

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
            created_by=current_user.id,
            attachments=[],
        )

        # Multi-file upload: name="attachment" with multiple selected,
        # or name="attachments" — accept either. Each file ≤10 MB.
        files = request.files.getlist('attachment') + request.files.getlist('attachments')
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'uploads', 'email_attachments')
        os.makedirs(upload_dir, exist_ok=True)
        import time
        for file in files:
            if not file or not file.filename:
                continue
            file.seek(0, 2); size = file.tell(); file.seek(0)
            if size > 10 * 1024 * 1024:
                flash(f'Attachment "{file.filename}" too large (>10 MB) — skipped.', 'error')
                continue
            safe = secure_filename(file.filename)
            stamped = f'{int(time.time() * 1000)}_{safe}'
            file_path = os.path.join(upload_dir, stamped)
            file.save(file_path)
            template.attachments.append({'path': file_path, 'name': file.filename})

        db.session.add(template)
        db.session.commit()

        logger.info(f'[email_templates] Created template "{name}" by admin {current_user.id} '
                    f'with {len(template.attachments or [])} attachment(s)')
        flash('Template created successfully.', 'success')
        return redirect(url_for('admin.email_templates'))

    return render_template('admin/email_template_form.html', template=None)


@admin_bp.route('/email-templates/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_email_template(id):
    """Edit an email template."""
    from ...models.email_template import EmailTemplate
    from werkzeug.utils import secure_filename
    import os

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

        # Per-file removal: form submits remove_attachment=<path> for any
        # attachment the operator clicked the X on. Multiple values
        # supported — getlist handles them.
        if template.attachments is None:
            template.attachments = []
        # Migrate the legacy single-attachment into the list once, on
        # first edit, so removal/UI is uniform.
        if template.attachment_path and not any(
            (a or {}).get('path') == template.attachment_path for a in template.attachments
        ):
            template.attachments.append({
                'path': template.attachment_path,
                'name': template.attachment_name or os.path.basename(template.attachment_path),
            })
            template.attachment_path = None
            template.attachment_name = None

        to_remove = set(request.form.getlist('remove_attachment'))
        if to_remove:
            kept = []
            for a in template.attachments:
                if (a or {}).get('path') in to_remove:
                    if a.get('path') and os.path.exists(a['path']):
                        try: os.remove(a['path'])
                        except OSError: pass
                else:
                    kept.append(a)
            template.attachments = kept

        # Handle new uploads (multi-file).
        files = request.files.getlist('attachment') + request.files.getlist('attachments')
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'uploads', 'email_attachments')
        os.makedirs(upload_dir, exist_ok=True)
        import time
        for file in files:
            if not file or not file.filename:
                continue
            file.seek(0, 2); size = file.tell(); file.seek(0)
            if size > 10 * 1024 * 1024:
                flash(f'Attachment "{file.filename}" too large (>10 MB) — skipped.', 'error')
                continue
            safe = secure_filename(file.filename)
            stamped = f'{int(time.time() * 1000)}_{safe}'
            file_path = os.path.join(upload_dir, stamped)
            file.save(file_path)
            template.attachments.append({'path': file_path, 'name': file.filename})

        db.session.commit()
        logger.info(f'[email_templates] Updated template {id} by admin {current_user.id} — '
                    f'{len(template.attachments or [])} attachment(s)')
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
            'body': t.body,
            'has_attachment': bool(t.attachment_path),
            'attachment_name': t.attachment_name
        })

    return jsonify(result)


# =============================================================================
# PAYMENT PROCESSORS
# =============================================================================

@admin_bp.route('/payment-processors')
@admin_required
def payment_processors():
    """List and manage payment processors."""
    from ...models.payment_processor import PaymentProcessor
    from ...models.payment_routing_rule import PaymentRoutingRule

    processors = PaymentProcessor.query.filter(
        PaymentProcessor.deleted_at.is_(None)
    ).order_by(PaymentProcessor.priority).all()

    rules = PaymentRoutingRule.query.filter(
        PaymentRoutingRule.deleted_at.is_(None)
    ).order_by(PaymentRoutingRule.priority).all()

    return render_template(
        'admin/payment_processors.html',
        processors=processors,
        rules=rules
    )


@admin_bp.route('/payment-processors/<int:id>/toggle', methods=['POST'])
@admin_required
def toggle_processor(id):
    """Enable/disable a payment processor."""
    from ...models.payment_processor import PaymentProcessor

    processor = PaymentProcessor.query.get_or_404(id)
    processor.enabled = not processor.enabled
    db.session.commit()

    status = 'enabled' if processor.enabled else 'disabled'
    logger.info(f'[payment_processors] {processor.code} {status} by admin {current_user.id}')

    return jsonify({
        'success': True,
        'enabled': processor.enabled,
        'message': f'{processor.name} {status}'
    })


@admin_bp.route('/payment-processors/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_processor(id):
    """Edit payment processor credentials."""
    from ...models.payment_processor import PaymentProcessor
    import json

    processor = PaymentProcessor.query.get_or_404(id)

    if request.method == 'POST':
        # Update basic fields
        processor.name = request.form.get('name', processor.name).strip()
        processor.display_name = request.form.get('display_name', '').strip() or None
        processor.priority = int(request.form.get('priority', 100))
        processor.display_order = int(request.form.get('display_order', 100))

        # Update fees
        fee_pct = request.form.get('fee_percentage', '').strip()
        processor.fee_percentage = Decimal(fee_pct) if fee_pct else None

        fee_fixed = request.form.get('fee_fixed_cents', '').strip()
        processor.fee_fixed_cents = int(fee_fixed) if fee_fixed else None

        # Update credentials (config_json)
        config = processor.config_json or {}

        # Processor-specific credentials
        if processor.code == 'stripe':
            # Stripe keys are stored in ConfigSettings, not here
            pass
        elif processor.code == 'nedarim':
            config['mosad_id'] = request.form.get('mosad_id', '').strip() or None
            config['api_password'] = request.form.get('api_password', '').strip() or None
        elif processor.code == 'cardcom':
            config['terminal_number'] = request.form.get('terminal_number', '').strip() or None
            config['api_name'] = request.form.get('api_name', '').strip() or None
            config['api_password'] = request.form.get('api_password', '').strip() or None
        elif processor.code == 'grow':
            config['page_code'] = request.form.get('page_code', '').strip() or None
            config['user_id'] = request.form.get('user_id', '').strip() or None
            config['api_key'] = request.form.get('api_key', '').strip() or None
            config['sandbox'] = request.form.get('sandbox') == 'on'
        elif processor.code == 'tranzila':
            config['terminal_name'] = request.form.get('terminal_name', '').strip() or None
            config['terminal_password'] = request.form.get('terminal_password', '').strip() or None
            config['app_key'] = request.form.get('app_key', '').strip() or None
        elif processor.code == 'payme':
            config['seller_id'] = request.form.get('seller_id', '').strip() or None
            config['api_key'] = request.form.get('api_key', '').strip() or None
            config['sandbox'] = request.form.get('sandbox') == 'on'
        elif processor.code == 'icount':
            config['api_token'] = request.form.get('api_token', '').strip() or None
        elif processor.code == 'easycard':
            config['terminal_number'] = request.form.get('terminal_number', '').strip() or None
            config['api_key'] = request.form.get('api_key', '').strip() or None
        # DAF Processors
        elif processor.code == 'donors_fund':
            config['validation_token'] = request.form.get('validation_token', '').strip() or None
            config['account_number'] = request.form.get('account_number', '').strip() or None
            config['tax_id'] = request.form.get('tax_id', '').strip() or None
            config['sandbox'] = request.form.get('sandbox') == 'on'
        elif processor.code == 'matbia':
            config['api_key'] = request.form.get('api_key', '').strip() or None
            config['org_handle'] = request.form.get('org_handle', '').strip() or None
            config['org_tax_id'] = request.form.get('org_tax_id', '').strip() or None
            config['org_name'] = request.form.get('org_name', '').strip() or None
            config['org_email'] = request.form.get('org_email', '').strip() or None
            config['sandbox'] = request.form.get('sandbox') == 'on'
        elif processor.code == 'chariot':
            config['api_key'] = request.form.get('api_key', '').strip() or None
            config['connect_id'] = request.form.get('connect_id', '').strip() or None
            config['ein'] = request.form.get('ein', '').strip() or None
            config['sandbox'] = request.form.get('sandbox') == 'on'

        processor.config_json = config
        processor.updated_at = datetime.utcnow()
        db.session.commit()

        logger.info(f'[payment_processors] Updated {processor.code} by admin {current_user.id}')
        flash(f'{processor.name} settings updated.', 'success')
        return redirect(url_for('admin.payment_processors'))

    return render_template('admin/edit_processor.html', processor=processor)


@admin_bp.route('/routing-rules/<int:id>/toggle', methods=['POST'])
@admin_required
def toggle_routing_rule(id):
    """Enable/disable a routing rule."""
    from ...models.payment_routing_rule import PaymentRoutingRule

    rule = PaymentRoutingRule.query.get_or_404(id)
    rule.enabled = not rule.enabled
    db.session.commit()

    status = 'enabled' if rule.enabled else 'disabled'
    logger.info(f'[routing_rules] Rule {rule.id} ({rule.name}) {status} by admin {current_user.id}')

    return jsonify({
        'success': True,
        'enabled': rule.enabled,
        'message': f'Rule "{rule.name}" {status}'
    })


@admin_bp.route('/routing-rules/new', methods=['GET', 'POST'])
@admin_required
def new_routing_rule():
    """Create a new routing rule."""
    from ...models.payment_processor import PaymentProcessor
    from ...models.payment_routing_rule import PaymentRoutingRule

    processors = PaymentProcessor.query.filter(
        PaymentProcessor.deleted_at.is_(None)
    ).order_by(PaymentProcessor.name).all()

    if request.method == 'POST':
        rule = PaymentRoutingRule(
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip() or None,
            priority=int(request.form.get('priority', 100)),
            enabled=request.form.get('enabled') == 'on',
            currency=request.form.get('currency', '').strip().upper() or None,
            country_code=request.form.get('country_code', '').strip().upper() or None,
            donation_type=request.form.get('donation_type', '').strip() or None,
            processor_id=int(request.form.get('processor_id'))
        )

        min_amt = request.form.get('min_amount', '').strip()
        if min_amt:
            rule.min_amount_cents = int(float(min_amt) * 100)

        max_amt = request.form.get('max_amount', '').strip()
        if max_amt:
            rule.max_amount_cents = int(float(max_amt) * 100)

        db.session.add(rule)
        db.session.commit()

        logger.info(f'[routing_rules] Created rule {rule.id} by admin {current_user.id}')
        flash(f'Routing rule "{rule.name}" created.', 'success')
        return redirect(url_for('admin.payment_processors'))

    return render_template('admin/edit_routing_rule.html', rule=None, processors=processors)


@admin_bp.route('/routing-rules/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_routing_rule(id):
    """Edit a routing rule."""
    from ...models.payment_processor import PaymentProcessor
    from ...models.payment_routing_rule import PaymentRoutingRule

    rule = PaymentRoutingRule.query.get_or_404(id)
    processors = PaymentProcessor.query.filter(
        PaymentProcessor.deleted_at.is_(None)
    ).order_by(PaymentProcessor.name).all()

    if request.method == 'POST':
        rule.name = request.form.get('name', '').strip()
        rule.description = request.form.get('description', '').strip() or None
        rule.priority = int(request.form.get('priority', 100))
        rule.enabled = request.form.get('enabled') == 'on'
        rule.currency = request.form.get('currency', '').strip().upper() or None
        rule.country_code = request.form.get('country_code', '').strip().upper() or None
        rule.donation_type = request.form.get('donation_type', '').strip() or None
        rule.processor_id = int(request.form.get('processor_id'))

        min_amt = request.form.get('min_amount', '').strip()
        rule.min_amount_cents = int(float(min_amt) * 100) if min_amt else None

        max_amt = request.form.get('max_amount', '').strip()
        rule.max_amount_cents = int(float(max_amt) * 100) if max_amt else None

        rule.updated_at = datetime.utcnow()
        db.session.commit()

        logger.info(f'[routing_rules] Updated rule {rule.id} by admin {current_user.id}')
        flash(f'Routing rule "{rule.name}" updated.', 'success')
        return redirect(url_for('admin.payment_processors'))

    return render_template('admin/edit_routing_rule.html', rule=rule, processors=processors)


@admin_bp.route('/routing-rules/<int:id>/delete', methods=['POST'])
@admin_required
def delete_routing_rule(id):
    """Delete a routing rule (soft delete)."""
    from ...models.payment_routing_rule import PaymentRoutingRule

    rule = PaymentRoutingRule.query.get_or_404(id)
    rule.deleted_at = datetime.utcnow()
    db.session.commit()

    logger.info(f'[routing_rules] Deleted rule {rule.id} by admin {current_user.id}')
    flash(f'Routing rule "{rule.name}" deleted.', 'success')
    return redirect(url_for('admin.payment_processors'))


# =============================================================================
# DONOR NOTES
# =============================================================================

@admin_bp.route('/donors/<int:id>/notes', methods=['POST'])
@admin_required
def add_donor_note(id):
    """Add a note to a donor."""
    donor = Donor.query.get_or_404(id)

    content = request.form.get('content', '').strip()
    if not content:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Note content is required'}), 400
        flash('Note content is required.', 'error')
        return redirect(url_for('admin.donor_detail', id=id))

    note = DonorNote(
        donor_id=donor.id,
        user_id=current_user.id,
        content=content,
        is_pinned=request.form.get('is_pinned') == 'true'
    )
    db.session.add(note)
    db.session.commit()

    logger.info(f'[donor_notes] Added note {note.id} to donor {donor.id} by user {current_user.id}')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'note': {
                'id': note.id,
                'content': note.content,
                'is_pinned': note.is_pinned,
                'created_at': note.created_at.isoformat(),
                'author': current_user.full_name,
                'author_id': current_user.id
            }
        })

    flash('Note added successfully.', 'success')
    return redirect(url_for('admin.donor_detail', id=id))


@admin_bp.route('/donors/<int:donor_id>/notes/<int:note_id>', methods=['PUT'])
@admin_required
def update_donor_note(donor_id, note_id):
    """Update a donor note."""
    note = DonorNote.query.filter(
        DonorNote.id == note_id,
        DonorNote.donor_id == donor_id,
        DonorNote.deleted_at.is_(None)
    ).first_or_404()

    # Only author or admin can edit
    if note.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Not authorized to edit this note'}), 403

    data = request.get_json() or {}
    content = data.get('content', '').strip()

    if not content:
        return jsonify({'error': 'Note content is required'}), 400

    note.content = content
    note.updated_at = datetime.utcnow()
    db.session.commit()

    logger.info(f'[donor_notes] Updated note {note.id} by user {current_user.id}')

    return jsonify({
        'success': True,
        'note': {
            'id': note.id,
            'content': note.content,
            'is_pinned': note.is_pinned,
            'updated_at': note.updated_at.isoformat()
        }
    })


@admin_bp.route('/donors/<int:donor_id>/notes/<int:note_id>', methods=['DELETE'])
@admin_required
def delete_donor_note(donor_id, note_id):
    """Soft-delete a donor note."""
    note = DonorNote.query.filter(
        DonorNote.id == note_id,
        DonorNote.donor_id == donor_id,
        DonorNote.deleted_at.is_(None)
    ).first_or_404()

    # Only author or admin can delete
    if note.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Not authorized to delete this note'}), 403

    note.deleted_at = datetime.utcnow()
    db.session.commit()

    logger.info(f'[donor_notes] Deleted note {note.id} by user {current_user.id}')

    return jsonify({'success': True})


@admin_bp.route('/donors/<int:donor_id>/notes/<int:note_id>/pin', methods=['POST'])
@admin_required
def toggle_donor_note_pin(donor_id, note_id):
    """Toggle pin status of a donor note."""
    note = DonorNote.query.filter(
        DonorNote.id == note_id,
        DonorNote.donor_id == donor_id,
        DonorNote.deleted_at.is_(None)
    ).first_or_404()

    note.is_pinned = not note.is_pinned
    db.session.commit()

    logger.info(f'[donor_notes] Note {note.id} pinned={note.is_pinned} by user {current_user.id}')

    return jsonify({
        'success': True,
        'is_pinned': note.is_pinned
    })


@admin_bp.route('/donors/<int:id>/notes-list')
@admin_required
def donor_notes_list(id):
    """Get all notes for a donor (AJAX endpoint)."""
    donor = Donor.query.get_or_404(id)

    notes = DonorNote.query.filter(
        DonorNote.donor_id == donor.id,
        DonorNote.deleted_at.is_(None)
    ).order_by(DonorNote.is_pinned.desc(), DonorNote.created_at.desc()).all()

    notes_data = []
    for note in notes:
        notes_data.append({
            'id': note.id,
            'content': note.content,
            'is_pinned': note.is_pinned,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat() if note.updated_at else None,
            'author': note.user.full_name if note.user else 'Unknown',
            'author_id': note.user_id,
            'can_edit': note.user_id == current_user.id or current_user.role == 'admin'
        })

    return jsonify({'notes': notes_data})


@admin_bp.route('/donors/<int:id>/activity')
@admin_required
def donor_activity(id):
    """Get activity feed for a donor (AJAX endpoint)."""
    donor = Donor.query.get_or_404(id)

    # Get all linked donor IDs
    all_donors = donor.get_all_linked_donors()
    donor_ids = [d.id for d in all_donors]

    activities = []

    # 1. Donations
    donations = Donation.query.filter(
        Donation.donor_id.in_(donor_ids),
        Donation.deleted_at.is_(None)
    ).all()

    for d in donations:
        activities.append({
            'type': 'donation',
            'icon': 'money',
            'timestamp': d.created_at.isoformat(),
            'title': f'Donation {"₪" if (d.currency or "usd").upper() == "ILS" else "$"}{d.amount / 100:.2f}',
            'description': f'{d.donation_type.replace("_", " ").title()} - {d.status}',
            'link': url_for('admin.donation_detail', id=d.id),
            'status': d.status
        })

    # 2. Receipts
    receipts = Receipt.query.filter(
        Receipt.donor_id.in_(donor_ids)
    ).all()

    for r in receipts:
        activities.append({
            'type': 'receipt',
            'icon': 'receipt',
            'timestamp': r.created_at.isoformat(),
            'title': f'Receipt {r.receipt_number}',
            'description': f'{r.amount / 100:.2f}',
            'link': url_for('admin.download_receipt', id=r.id)
        })

    # 3. Emails sent
    # Get donation IDs for this donor
    donation_ids = [d.id for d in donations]

    emails = MessageQueue.query.filter(
        db.or_(
            MessageQueue.recipient_id.in_(donor_ids),
            MessageQueue.related_donation_id.in_(donation_ids) if donation_ids else False
        ),
        MessageQueue.channel == 'email'
    ).all()

    for e in emails:
        # Determine email status description
        if e.clicked_at:
            status_desc = f'Clicked at {e.clicked_at.strftime("%Y-%m-%d %H:%M")}'
            status = 'clicked'
        elif e.opened_at:
            status_desc = f'Opened at {e.opened_at.strftime("%Y-%m-%d %H:%M")}'
            status = 'opened'
        elif e.delivered_at:
            status_desc = f'Delivered at {e.delivered_at.strftime("%Y-%m-%d %H:%M")}'
            status = 'delivered'
        elif e.sent_at:
            status_desc = f'Sent at {e.sent_at.strftime("%Y-%m-%d %H:%M")}'
            status = 'sent'
        else:
            status_desc = e.status
            status = e.status

        activities.append({
            'type': 'email',
            'icon': 'email',
            'timestamp': e.created_at.isoformat(),
            'title': f'Email: {e.subject or e.message_type}',
            'description': status_desc,
            'status': status
        })

    # 4. Notes
    notes = DonorNote.query.filter(
        DonorNote.donor_id.in_(donor_ids),
        DonorNote.deleted_at.is_(None)
    ).all()

    for n in notes:
        activities.append({
            'type': 'note',
            'icon': 'note',
            'timestamp': n.created_at.isoformat(),
            'title': 'Note added',
            'description': f'By {n.user.full_name if n.user else "Unknown"}: {n.content[:100]}...' if len(n.content) > 100 else f'By {n.user.full_name if n.user else "Unknown"}: {n.content}',
            'author': n.user.full_name if n.user else 'Unknown'
        })

    # Sort by timestamp (newest first)
    activities.sort(key=lambda x: x['timestamp'], reverse=True)

    return jsonify({'activities': activities})


# =============================================================================
# ADMIN SCREENSHOTS
# =============================================================================

@admin_bp.route('/screenshots')
@admin_required
def screenshots():
    """View and upload screenshots for sharing with Claude."""
    from ...models.claude_session import ClaudeScreenshot
    shots = ClaudeScreenshot.query.order_by(ClaudeScreenshot.created_at.desc()).limit(50).all()
    return render_template('admin/screenshots.html', screenshots=shots)


@admin_bp.route('/screenshots/paste', methods=['POST'])
@admin_required
def paste_screenshot():
    """Upload a screenshot from clipboard paste (base64)."""
    from ...models.claude_session import ClaudeScreenshot
    import uuid, os, base64

    SCREENSHOT_FOLDER = '/var/www/matat/uploads/screenshots'
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

    data = request.get_json()
    image_data = data.get('image', '')
    description = data.get('description', '')

    if not image_data:
        return jsonify({'error': 'No image data'}), 400

    # Strip data URL prefix
    if ',' in image_data:
        image_data = image_data.split(',')[1]

    try:
        image_bytes = base64.b64decode(image_data)
    except Exception:
        return jsonify({'error': 'Invalid image data'}), 400

    filename = f'{uuid.uuid4().hex}.png'
    filepath = os.path.join(SCREENSHOT_FOLDER, filename)

    with open(filepath, 'wb') as f:
        f.write(image_bytes)

    screenshot = ClaudeScreenshot(
        user_id=current_user.id,
        filename=filename,
        original_filename='pasted_image.png',
        file_path=filepath,
        file_size=len(image_bytes),
        description=description
    )
    db.session.add(screenshot)
    db.session.commit()

    logger.info(f'[admin] Screenshot pasted by admin {current_user.id}')
    return jsonify({'success': True, 'id': screenshot.id})


@admin_bp.route('/screenshots/upload', methods=['POST'])
@admin_required
def upload_screenshot():
    """Upload a screenshot from admin."""
    from ...models.claude_session import ClaudeScreenshot
    import uuid
    import os
    from werkzeug.utils import secure_filename

    SCREENSHOT_FOLDER = '/var/www/matat/uploads/screenshots'
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('admin.screenshots'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('admin.screenshots'))

    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
        flash('Invalid image type.', 'danger')
        return redirect(url_for('admin.screenshots'))

    filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(SCREENSHOT_FOLDER, filename)
    file.save(filepath)

    screenshot = ClaudeScreenshot(
        user_id=current_user.id,
        filename=filename,
        original_filename=secure_filename(file.filename),
        file_path=filepath,
        file_size=os.path.getsize(filepath),
        description=request.form.get('description', '')
    )
    db.session.add(screenshot)
    db.session.commit()

    logger.info(f'[admin] Screenshot {filename} uploaded by admin {current_user.id}')
    flash('Screenshot uploaded.', 'success')
    return redirect(url_for('admin.screenshots'))


@admin_bp.route('/screenshots/<int:id>/delete', methods=['POST'])
@admin_required
def delete_screenshot(id):
    """Delete a screenshot."""
    from ...models.claude_session import ClaudeScreenshot
    import os

    shot = ClaudeScreenshot.query.get_or_404(id)
    if shot.file_path and os.path.exists(shot.file_path):
        os.remove(shot.file_path)
    db.session.delete(shot)
    db.session.commit()
    flash('Screenshot deleted.', 'success')
    return redirect(url_for('admin.screenshots'))


# =============================================================================
# EMAIL CAMPAIGN TRACKING
# =============================================================================

@admin_bp.route('/campaign-track/<campaign_name>')
@admin_required
def campaign_track(campaign_name):
    """Track donations from email campaigns."""
    from datetime import datetime

    # Define campaigns and their target emails
    campaigns = {
        'apology': {
            'title': 'Apology Email (Apr 14, 2026)',
            'sent_date': datetime(2026, 4, 14),
            'emails': [
                'ateretkallah@gmail.com', 'berlbat@gmail.com', 'bernardstern20@gmail.com',
                'bruchmarg@gmail.com', 'chanaschuss@gmail.com', 'cnmemail@gmail.com',
                'estys1211@gmail.com', 'familysalis@gmail.com', 'flphadas@gmail.com',
                'gittyfriedman33@gmail.com', 'glatt.benny@icloud.com', 'grosskopfchani@gmial.com',
                'hm.schapira@gmail.com', 'issacsilbersteinbr@gmail.com', 'kidstopm@gmail.com',
                'leeba@besimcha-israel.com', 'miriam92012@gmail.com', 'mlevy2483@gmail.com',
                'pinterchanie@gmail.com', 'rbsg46008@gmail.com', 'sarahrdayan1@gmail.com',
                'simonschifer@gmail.com', 'ss7987948@gmail.com', 'strenger.lugano@gmail.com',
                'tziporawells@gmail.com', 'uumiri18@gmail.com', 'yankisara@mosesnet.net',
                'yarbroughmolly@gmail.com', 'yehudamorsel89@gmail.com', 'zevibeer@gmail.com',
            ]
        }
    }

    campaign = campaigns.get(campaign_name)
    if not campaign:
        flash('Campaign not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    sent_date = campaign['sent_date']
    target_emails = campaign['emails']

    # Find donors by email
    from ...models.donor import Donor
    donors = Donor.query.filter(Donor.email.in_(target_emails)).all()
    donor_map = {d.email: d for d in donors}

    # Find new donations from these donors after the send date
    results = []
    total_donated = 0
    for email in target_emails:
        donor = donor_map.get(email)
        entry = {
            'email': email,
            'name': donor.full_name if donor else 'Unknown',
            'donations': [],
            'total': 0,
        }

        if donor:
            new_donations = Donation.query.filter(
                Donation.donor_id == donor.id,
                Donation.created_at >= sent_date,
                Donation.status == 'succeeded',
                Donation.deleted_at.is_(None)
            ).order_by(Donation.created_at.desc()).all()

            for d in new_donations:
                symbol = '₪' if (d.currency or 'usd').upper() == 'ILS' else '$'
                entry['donations'].append({
                    'id': d.id,
                    'amount': d.amount / 100,
                    'currency': d.currency,
                    'symbol': symbol,
                    'processor': d.payment_processor or 'stripe',
                    'date': d.created_at,
                    'comment': d.donor_comment,
                })
                entry['total'] += d.amount / 100
                total_donated += d.amount / 100

        results.append(entry)

    # Sort: donors who donated first, then by total
    results.sort(key=lambda x: (-x['total'], x['email']))

    donated_count = sum(1 for r in results if r['donations'])

    return render_template(
        'admin/campaign_track.html',
        campaign_name=campaign_name,
        campaign=campaign,
        results=results,
        total_donated=total_donated,
        donated_count=donated_count,
        total_sent=len(target_emails),
    )


# ============================================================
# UNIFIED CHARGE PAGE
# Lets an admin charge a credit card via any of the live processors
# (Stripe / Shva / Nedarim Plus) from a single page. Processor picker
# tabs are always visible at the top and switch which card-entry form
# is shown. Phase-2: rate-based routing — for now, manual selection only.
# ============================================================
LIVE_CHARGE_PROCESSORS = ('stripe', 'shva', 'nedarim')


@admin_bp.route('/charge', methods=['GET', 'POST'])
@admin_required
def charge_card():
    """Unified charge page across multiple live processors."""
    from ...models.payment_processor import PaymentProcessor
    from ...services.stripe_service import get_stripe_keys

    enabled = (PaymentProcessor.query
               .filter(PaymentProcessor.enabled.is_(True),
                       PaymentProcessor.code.in_(LIVE_CHARGE_PROCESSORS))
               .order_by(PaymentProcessor.priority).all())

    _, stripe_pub_key, stripe_mode, _ = get_stripe_keys()

    if request.method == 'POST':
        processor_code = (request.form.get('processor') or '').strip()
        if processor_code == 'shva':
            return _admin_charge_shva()
        flash(f'Unsupported processor for server-side charging: {processor_code}.', 'error')
        return redirect(url_for('admin.charge_card', processor=processor_code or None))

    # Initial tab — sticky across redirects: when ?processor=<code> is set
    # and is one of our supported codes, render that tab as active. Falls
    # back to the first enabled processor when the param is absent.
    initial_proc = (request.args.get('processor') or '').strip().lower()
    if initial_proc not in {p.code for p in enabled}:
        initial_proc = enabled[0].code if enabled else ''

    return render_template(
        'admin/charge.html',
        processors=enabled,
        initial_processor=initial_proc,
        stripe_publishable_key=stripe_pub_key or '',
        stripe_mode=stripe_mode or '',
    )


@admin_bp.route('/charge/stripe-intent', methods=['POST'])
@admin_required
def charge_stripe_intent():
    """Create a Stripe PaymentIntent for the unified admin charge page."""
    from ...services.stripe_service import create_payment_intent, get_or_create_customer, is_test_mode

    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        amount_cents = int(round(amount * 100))
        currency = (data.get('currency') or 'usd').lower()
        # Policy: shekel donations don't go through Stripe — route to Shva
        # or Nedarim instead. Hard-reject so a tampered client request
        # can't bypass the disabled <option> in the dropdown.
        if currency == 'ils':
            return jsonify({'error': 'Stripe is not used for ILS donations. Use Shva or Nedarim Plus.'}), 400

        email = (data.get('email') or '').strip()
        donor = None
        customer_id = None
        if email:
            donor = Donor.query.filter_by(email=email).first()
            if not donor:
                donor = Donor(
                    first_name=data.get('first_name') or 'Anonymous',
                    last_name=data.get('last_name') or 'Donor',
                    email=email,
                    phone=data.get('phone'),
                    address_line1=data.get('address_line1'),
                    city=data.get('city'),
                    state=data.get('state'),
                    zip=data.get('zip'),
                    country=data.get('country', 'US'),
                    test=is_test_mode(),
                )
                db.session.add(donor)
                db.session.flush()
            db.session.commit()
            customer_id = get_or_create_customer(donor)

        metadata = {
            'donation_type': 'one_time',
            'source': 'admin_charge',
            'admin_user_id': str(current_user.id),
        }
        if donor:
            metadata['donor_id'] = str(donor.id)
            metadata['donor_email'] = donor.email or ''
            metadata['donor_first_name'] = donor.first_name or ''
            metadata['donor_last_name'] = donor.last_name or ''

        intent = create_payment_intent(
            amount_cents=amount_cents,
            currency=currency,
            customer_id=customer_id,
            metadata=metadata,
        )
        return jsonify({'clientSecret': intent.client_secret, 'paymentIntentId': intent.id})
    except Exception as e:
        logger.error(f'admin charge stripe-intent error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 400


def _admin_charge_shva():
    """Server-side Shva charge from the unified admin charge page."""
    from ...services.payment.router import get_processor

    try:
        amount_str = (request.form.get('amount') or '').strip()
        if not amount_str:
            flash('Amount is required.', 'error')
            return redirect(url_for('admin.charge_card', processor='shva'))
        amount_cents = int(round(float(amount_str) * 100))
        currency = (request.form.get('currency') or 'ILS').upper()

        donor_id = request.form.get('donor_id', type=int)
        donor = Donor.query.get(donor_id) if donor_id else None

        first_name = (request.form.get('first_name') or '').strip()
        last_name = (request.form.get('last_name') or '').strip()
        hebrew_first_name = (request.form.get('hebrew_first_name') or '').strip()
        hebrew_last_name = (request.form.get('hebrew_last_name') or '').strip()
        email = (request.form.get('email') or '').strip()
        tz = (request.form.get('tz') or '').strip()

        # Six structured phones — Israeli vs foreign × home/cell/fax.
        il_phone_home = (request.form.get('il_phone_home') or '').strip()
        il_phone_cell = (request.form.get('il_phone_cell') or '').strip()
        il_phone_fax = (request.form.get('il_phone_fax') or '').strip()
        foreign_phone_home = (request.form.get('foreign_phone_home') or '').strip()
        foreign_phone_cell = (request.form.get('foreign_phone_cell') or '').strip()
        foreign_phone_fax = (request.form.get('foreign_phone_fax') or '').strip()
        # Legacy `phone` column kept in sync from whichever cell is most
        # relevant for the chosen address (IL cell when address_type=il,
        # else foreign cell). SMS / receipts read `donor.phone`.
        phone = (il_phone_cell if (request.form.get('address_type') == 'il')
                 else foreign_phone_cell) or il_phone_cell or foreign_phone_cell

        # Address fields — operator picks IL vs foreign via the address_type
        # toggle. Each set saves to its own column on Donor so a person who
        # has both an Israeli and US address keeps them separate.
        address_type = (request.form.get('address_type') or 'il').lower()
        il_address_line1 = (request.form.get('il_address_line1') or '').strip()
        il_city = (request.form.get('il_city') or '').strip()
        il_zip = (request.form.get('il_zip') or '').strip()
        foreign_address_line1 = (request.form.get('address_line1') or '').strip()
        foreign_city = (request.form.get('city') or '').strip()
        foreign_state = (request.form.get('state') or '').strip()
        foreign_zip = (request.form.get('zip') or '').strip()
        foreign_country = (request.form.get('country') or '').strip()

        if not donor:
            donor = Donor(
                first_name=first_name or 'Unknown',
                last_name=last_name or 'Unknown',
                hebrew_first_name=hebrew_first_name or None,
                hebrew_last_name=hebrew_last_name or None,
                email=email or None,
                phone=phone or None,
                teudat_zehut=tz or None,
                country=foreign_country or ('IL' if currency == 'ILS' else 'US'),
            )
            db.session.add(donor)
            db.session.flush()
        else:
            if first_name: donor.first_name = first_name
            if last_name: donor.last_name = last_name
            if hebrew_first_name: donor.hebrew_first_name = hebrew_first_name
            if hebrew_last_name: donor.hebrew_last_name = hebrew_last_name
            if email: donor.email = email
            if phone: donor.phone = phone
            if tz: donor.teudat_zehut = tz

        # Persist all six structured phones. Empty values DO overwrite
        # since the operator might have intentionally cleared a phone.
        donor.il_phone_home = il_phone_home or None
        donor.il_phone_cell = il_phone_cell or None
        donor.il_phone_fax = il_phone_fax or None
        donor.foreign_phone_home = foreign_phone_home or None
        donor.foreign_phone_cell = foreign_phone_cell or None
        donor.foreign_phone_fax = foreign_phone_fax or None

        # Save into the right address columns. Both sets persist — even
        # if the operator only filled one, the other column stays as it was.
        if il_address_line1: donor.il_address_line1 = il_address_line1
        if il_city: donor.il_city = il_city
        if il_zip: donor.il_zip = il_zip
        if foreign_address_line1: donor.address_line1 = foreign_address_line1
        if foreign_city: donor.city = foreign_city
        if foreign_state: donor.state = foreign_state
        if foreign_zip: donor.zip = foreign_zip
        if foreign_country: donor.country = foreign_country

        db.session.flush()

        proc = get_processor('shva')
        result = proc.create_payment(
            amount=amount_cents,
            currency=currency,
            card_data={
                'card_number': request.form.get('card_number', ''),
                'expiry': request.form.get('expiry', ''),
                'cvv': request.form.get('cvv', ''),
            },
            donor_data={'tz': tz},
            installments=int(request.form.get('installments') or 1),
        )

        if not result.get('success'):
            db.session.rollback()
            # Log the full raw response so we can diagnose what Shva sent.
            raw = result.get('raw_response') or {}
            logger.error(f'[admin/charge] Shva charge FAILED — '
                         f'ash_status={result.get("ash_status")} '
                         f'ash_status_desc={result.get("ash_status_desc")!r} '
                         f'raw_xmlStr={raw.get("xmlStr", "")[:500]!r}')
            ash_status = str(result.get('ash_status') or '')
            err_msg = result.get('error') or 'Unknown error'
            desc = result.get('ash_status_desc') or ''
            # Friendly explanations for common Shva codes.
            hints = {
                '416': 'Card brand not configured at this terminal — your Shva terminal is set up for Isracard only. To accept Visa/MasterCard etc., ask Shva to add the relevant sapakim (clearing providers).',
                '417': 'Invalid J parameter in the request.',
                '447': 'Invalid card number.',
                '33':  'Card declined by issuer.',
                '36':  'Card blocked / stolen.',
            }
            hint = hints.get(ash_status, '')
            if desc and desc not in err_msg:
                err_msg = f'{err_msg} ({desc})'
            if hint:
                err_msg = f'{err_msg} — {hint}'
            flash(f'Shva charge failed: {err_msg}', 'error')
            # Stay on the Shva tab so the operator can fix and retry
            return redirect(url_for('admin.charge_card', processor='shva'))

        # Capture the card-brand info Shva returned so future runs of
        # this query show what brand actually charged. The card_number
        # last-4 is derived from the form input — Shva doesn't echo the
        # PAN back (PCI). solek/rrn/ash_status_desc go into metadata.
        card_number_clean = (request.form.get('card_number', '') or '').replace(' ', '').replace('-', '')
        last4 = card_number_clean[-4:] if len(card_number_clean) >= 4 else None
        donation = Donation(
            donor_id=donor.id,
            amount=amount_cents,
            currency=currency,
            payment_method='credit',
            payment_processor='shva',
            processor_transaction_id=result.get('transaction_id', '') or '',
            processor_confirmation=result.get('confirmation', '') or '',
            status='succeeded',
            donation_type='one_time',
            payment_method_type='card',
            payment_method_last4=last4,
            payment_method_brand=(result.get('card_brand') or result.get('card_name') or '').strip() or None,
            processor_metadata={
                'card_name': result.get('card_name', ''),
                'card_brand': result.get('card_brand', ''),
                'solek': result.get('solek', ''),
                'rrn': result.get('rrn', ''),
                'ash_status': result.get('ash_status', ''),
                'ash_status_desc': result.get('ash_status_desc', ''),
                'authorization_code': result.get('authorization_code', ''),
            },
        )
        db.session.add(donation)
        db.session.commit()

        flash(f'Shva charge successful — donation #{donation.id} for {donor.full_name}.', 'success')
        return redirect(url_for('admin.donations', processor='shva'))

    except Exception as e:
        db.session.rollback()
        logger.error(f'admin shva charge error: {e}', exc_info=True)
        flash(f'Charge error: {e}', 'error')
        return redirect(url_for('admin.charge_card', processor='shva'))


# =============================================================================
# INBOX PORTAL — read-only view of mail pulled from any inbox provider
# =============================================================================

@admin_bp.route('/inbox')
@admin_required
def inbox():
    """Inbox portal — list view of ingested email messages.

    Supports filters: unread, attachments, assignment scope (mine /
    unassigned / user_id / all), folder name, and free-text search.
    """
    from ...models.email_message import EmailMessage
    from ...models.email_inbox_provider import EmailInboxProvider
    from ...models.user import User
    from flask_login import current_user

    page = int(request.args.get('page', 1))
    per_page = 50
    filter_unread = request.args.get('unread') == '1'
    filter_attachments = request.args.get('attachments') == '1'
    q = (request.args.get('q') or '').strip()
    # Assignment scope: 'mine' | 'unassigned' | 'all' | '<user_id>'
    assigned = (request.args.get('assigned') or 'all').strip()
    folder = (request.args.get('folder') or '').strip()

    query = EmailMessage.query.filter(EmailMessage.is_archived == False)
    if filter_unread:
        query = query.filter(EmailMessage.is_read == False)
    if filter_attachments:
        query = query.filter(EmailMessage.has_attachments == True)
    if folder:
        query = query.filter(EmailMessage.folder_name == folder)
    if assigned == 'mine':
        query = query.filter(EmailMessage.assigned_to_user_id == current_user.id)
    elif assigned == 'unassigned':
        query = query.filter(EmailMessage.assigned_to_user_id.is_(None))
    elif assigned and assigned != 'all':
        try:
            uid = int(assigned)
            query = query.filter(EmailMessage.assigned_to_user_id == uid)
        except ValueError:
            pass
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(
            EmailMessage.subject.ilike(like),
            EmailMessage.from_address.ilike(like),
            EmailMessage.from_name.ilike(like),
            EmailMessage.body_preview.ilike(like),
        ))

    pagination = query.order_by(EmailMessage.received_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    unread_count = EmailMessage.query.filter_by(is_read=False, is_archived=False).count()
    mine_count = EmailMessage.query.filter_by(
        is_archived=False, assigned_to_user_id=current_user.id
    ).count()
    unassigned_count = EmailMessage.query.filter(
        EmailMessage.is_archived == False,
        EmailMessage.assigned_to_user_id.is_(None),
    ).count()
    providers = EmailInboxProvider.query_active().all()
    users = User.query_active().filter_by(active=True).order_by(User.username).all()
    folders = [f[0] for f in db.session.query(EmailMessage.folder_name)
               .filter(EmailMessage.folder_name.isnot(None))
               .distinct().order_by(EmailMessage.folder_name).all()]

    return render_template(
        'admin/inbox_list.html',
        messages=pagination,
        unread_count=unread_count,
        mine_count=mine_count,
        unassigned_count=unassigned_count,
        filter_unread=filter_unread,
        filter_attachments=filter_attachments,
        assigned=assigned,
        folder=folder,
        q=q,
        providers=providers,
        users=users,
        folders=folders,
    )


def _rewrite_inline_cids(body_html, attachments):
    """Rewrite `cid:CONTENT_ID` references in email HTML to point at our
    own attachment route, so inline images render in the inbox view.

    Builds a content_id -> attachment.id map (case-insensitive, with
    angle brackets stripped — Outlook/Exchange sometimes wraps the id),
    then substitutes every cid:... occurrence whose value matches.
    Unknown cid values are left alone (broken images, but no worse
    than before).
    """
    if not body_html or not attachments:
        return body_html
    import re
    cid_to_id = {}
    for a in attachments:
        if not a.content_id:
            continue
        key = a.content_id.strip().strip('<>').lower()
        if key:
            cid_to_id[key] = a.id

    def repl(match):
        raw = match.group(1).strip().strip('<>').lower()
        att_id = cid_to_id.get(raw)
        if att_id is None:
            return match.group(0)
        return f'/admin/inbox/attachment/{att_id}'

    # Match cid:VALUE up to the next quote, whitespace, or angle bracket.
    return re.sub(r'cid:([^"\'\s>]+)', repl, body_html, flags=re.IGNORECASE)


@admin_bp.route('/inbox/<int:id>')
@admin_required
def inbox_message(id):
    """Single email view — full body + attachment list."""
    from ...models.email_message import EmailMessage

    msg = EmailMessage.query.get_or_404(id)

    # Mark as read on first open
    if not msg.is_read:
        msg.is_read = True
        db.session.commit()

    # Other messages in the same conversation, oldest first
    thread = []
    if msg.conversation_id:
        thread = EmailMessage.query.filter_by(
            conversation_id=msg.conversation_id
        ).order_by(EmailMessage.received_at.asc()).all()

    attachments = msg.attachments.all()
    body_html_rendered = _rewrite_inline_cids(msg.body_html, attachments)

    # User list for the assignment dropdown
    from ...models.user import User
    users = User.query_active().filter_by(active=True).order_by(User.username).all()

    return render_template(
        'admin/inbox_message.html',
        msg=msg,
        thread=thread,
        attachments=attachments,
        body_html_rendered=body_html_rendered,
        users=users,
    )


@admin_bp.route('/inbox/<int:id>/reply', methods=['GET', 'POST'])
@admin_required
def inbox_reply(id):
    """Reply to an inbox message — To prefilled with original sender."""
    return _inbox_compose(id, 'reply')


@admin_bp.route('/inbox/<int:id>/reply-all', methods=['GET', 'POST'])
@admin_required
def inbox_reply_all(id):
    """Reply All — To = original sender, Cc = original recipients minus our mailbox."""
    return _inbox_compose(id, 'reply_all')


@admin_bp.route('/inbox/<int:id>/forward', methods=['GET', 'POST'])
@admin_required
def inbox_forward(id):
    """Forward — To empty, body wraps original with full headers."""
    return _inbox_compose(id, 'forward')


def _inbox_compose(id, mode):
    """Shared compose handler for reply / reply-all / forward.

    Only the defaults differ across modes:
        reply     — To = original sender, Cc empty
        reply_all — To = original sender, Cc = original to+cc minus our mailbox
        forward   — To empty, Cc empty, subject Fwd:, body wraps the original
                    with full From/Sent/To/Cc/Subject header
    """
    import base64
    from ...models.email_message import EmailMessage

    msg = EmailMessage.query.get_or_404(id)

    if mode not in ('reply', 'reply_all', 'forward'):
        mode = 'reply'

    if request.method == 'GET':
        original_subject = msg.subject or ''
        subj_lower = original_subject.lower()
        if mode == 'forward':
            if subj_lower.startswith(('fwd:', 'fw:')):
                composed_subject = original_subject
            else:
                composed_subject = f'Fwd: {original_subject}'
        else:
            if subj_lower.startswith('re:'):
                composed_subject = original_subject
            else:
                composed_subject = f'Re: {original_subject}'

        when = msg.received_at.strftime('%a, %b %d, %Y at %H:%M UTC') if msg.received_at else ''
        sender_label = f'{msg.from_name or ""} <{msg.from_address or ""}>'.strip()
        original_body = msg.body_html or (
            '<p>' + (msg.body_text or '').replace('\n', '<br>') + '</p>'
        )

        if mode == 'forward':
            # Forwarded blocks traditionally show full headers, no
            # blockquote indent, divider above.
            to_line = ', '.join(msg.to_addresses or [])
            cc_line = ', '.join(msg.cc_addresses or [])
            cc_html = f'<div><b>Cc:</b> {cc_line}</div>' if cc_line else ''
            quoted = (
                f'<br><br>'
                f'<div style="border-top:1px solid #ccc; padding-top:10px; color:#444;">'
                f'<p style="margin:0 0 8px 0;"><b>---------- Forwarded message ----------</b></p>'
                f'<div><b>From:</b> {sender_label}</div>'
                f'<div><b>Sent:</b> {when}</div>'
                f'<div><b>To:</b> {to_line}</div>'
                f'{cc_html}'
                f'<div><b>Subject:</b> {original_subject}</div>'
                f'<br>'
                f'{original_body}'
                f'</div>'
            )
            default_to = ''
            default_cc = ''
        else:
            quoted = (
                f'<br><br><div style="border-left:3px solid #ccc; padding-left:10px; color:#555;">'
                f'<p>On {when}, {sender_label} wrote:</p>'
                f'{original_body}'
                f'</div>'
            )
            default_to = msg.from_address or ''
            default_cc = ''
            if mode == 'reply_all':
                # Cc = (original To + original Cc) minus our own mailbox + the
                # original sender (already in To). De-dup case-insensitively.
                our_mailbox = (msg.provider.mailbox_address or '').lower()
                from_addr = (msg.from_address or '').lower()
                cc_pool = []
                seen = {our_mailbox, from_addr, ''}
                for addr in (msg.to_addresses or []) + (msg.cc_addresses or []):
                    a = (addr or '').strip()
                    al = a.lower()
                    if al in seen:
                        continue
                    seen.add(al)
                    cc_pool.append(a)
                default_cc = ', '.join(cc_pool)

        action_label = {
            'reply':     'Reply',
            'reply_all': 'Reply All',
            'forward':   'Forward',
        }[mode]

        return render_template(
            'admin/inbox_reply.html',
            msg=msg,
            mode=mode,
            action_label=action_label,
            default_to=default_to,
            default_cc=default_cc,
            default_subject=composed_subject,
            default_body_html=quoted,
        )

    # --- POST: send the message ---
    def _split_addrs(raw):
        if not raw:
            return []
        return [a.strip() for a in raw.replace(';', ',').split(',') if a.strip()]

    to_addresses  = _split_addrs(request.form.get('to'))
    cc_addresses  = _split_addrs(request.form.get('cc'))
    bcc_addresses = _split_addrs(request.form.get('bcc'))
    subject       = (request.form.get('subject') or '').strip()
    body_html     = request.form.get('body') or ''

    endpoint = {
        'reply':     'admin.inbox_reply',
        'reply_all': 'admin.inbox_reply_all',
        'forward':   'admin.inbox_forward',
    }.get(mode, 'admin.inbox_reply')

    if not to_addresses:
        flash('At least one To recipient is required.', 'error')
        return redirect(url_for(endpoint, id=id))

    # Read uploaded files into base64 attachments
    attachments = []
    for fileobj in request.files.getlist('attachments'):
        if not fileobj or not fileobj.filename:
            continue
        data = fileobj.read()
        if not data:
            continue
        attachments.append({
            'filename':     fileobj.filename,
            'content_type': fileobj.content_type or 'application/octet-stream',
            'content_b64':  base64.b64encode(data).decode('ascii'),
        })

    handler = msg.provider.get_handler()
    if not handler.supports_send():
        flash(f'{handler.name} does not support sending.', 'error')
        return redirect(url_for('admin.inbox_message', id=id))

    # Forward shouldn't thread with the original — different conversation.
    in_reply_to = None if mode == 'forward' else msg.remote_id

    result = handler.send_message(
        to_addresses=to_addresses,
        subject=subject,
        body_html=body_html,
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        attachments=attachments,
        in_reply_to_remote_id=in_reply_to,
    )

    sent_label = {'reply': 'Reply', 'reply_all': 'Reply', 'forward': 'Forward'}.get(mode, 'Message')

    if result.get('success'):
        flash(f'{sent_label} sent.', 'success')
        return redirect(url_for('admin.inbox_message', id=id))

    flash(f'Send failed: {result.get("error", "unknown error")}', 'error')
    return redirect(url_for(endpoint, id=id))


@admin_bp.route('/inbox/compose', methods=['GET', 'POST'])
@admin_required
def inbox_compose_new():
    """Compose a brand-new email (not a reply or forward).

    Sends from the first enabled inbox provider's mailbox — for now
    that's support@matatmordechai.org. If multiple providers are
    enabled in the future we'd add a From dropdown.
    """
    import base64
    from ...models.email_inbox_provider import EmailInboxProvider

    providers = EmailInboxProvider.get_enabled()
    if not providers:
        flash('No enabled inbox providers configured — can\'t send.', 'error')
        return redirect(url_for('admin.inbox'))
    provider = providers[0]

    if request.method == 'GET':
        return render_template(
            'admin/inbox_reply.html',
            msg=None,
            mode='new',
            action_label='New Message',
            default_to='',
            default_cc='',
            default_subject='',
            default_body_html='',
            sending_mailbox=provider.mailbox_address,
        )

    def _split_addrs(raw):
        if not raw:
            return []
        return [a.strip() for a in raw.replace(';', ',').split(',') if a.strip()]

    to_addresses  = _split_addrs(request.form.get('to'))
    cc_addresses  = _split_addrs(request.form.get('cc'))
    bcc_addresses = _split_addrs(request.form.get('bcc'))
    subject       = (request.form.get('subject') or '').strip()
    body_html     = request.form.get('body') or ''

    if not to_addresses:
        flash('At least one To recipient is required.', 'error')
        return redirect(url_for('admin.inbox_compose_new'))

    attachments = []
    for fileobj in request.files.getlist('attachments'):
        if not fileobj or not fileobj.filename:
            continue
        data = fileobj.read()
        if not data:
            continue
        attachments.append({
            'filename':     fileobj.filename,
            'content_type': fileobj.content_type or 'application/octet-stream',
            'content_b64':  base64.b64encode(data).decode('ascii'),
        })

    handler = provider.get_handler()
    if not handler.supports_send():
        flash(f'{handler.name} does not support sending.', 'error')
        return redirect(url_for('admin.inbox'))

    result = handler.send_message(
        to_addresses=to_addresses,
        subject=subject,
        body_html=body_html,
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        attachments=attachments,
    )

    if result.get('success'):
        flash('Message sent.', 'success')
        return redirect(url_for('admin.inbox'))

    flash(f'Send failed: {result.get("error", "unknown error")}', 'error')
    return redirect(url_for('admin.inbox_compose_new'))


@admin_bp.route('/inbox/<int:id>/delete', methods=['POST'])
@admin_required
def inbox_delete(id):
    """Move a message to the upstream Deleted Items folder via Graph,
    then archive locally so it disappears from the portal view."""
    from ...models.email_message import EmailMessage
    msg = EmailMessage.query.get_or_404(id)
    handler = msg.provider.get_handler()
    result = handler.move_to_folder(msg.remote_id, 'deleteditems')
    if not result.get('success'):
        flash(f'Delete failed: {result.get("error", "unknown error")}', 'error')
        return redirect(url_for('admin.inbox_message', id=id))
    # Update remote_id if Graph reassigned it on move
    new_id = result.get('new_id')
    if new_id:
        msg.remote_id = new_id
    msg.is_archived = True
    db.session.commit()
    flash('Message deleted (moved to Deleted Items).', 'success')
    return redirect(url_for('admin.inbox'))


@admin_bp.route('/inbox/<int:id>/assign', methods=['POST'])
@admin_required
def inbox_assign(id):
    """Assign / unassign / reassign an email to an operator."""
    from ...models.email_message import EmailMessage
    from ...models.user import User
    msg = EmailMessage.query.get_or_404(id)
    raw = (request.form.get('user_id') or '').strip()
    if not raw or raw == '0':
        msg.assigned_to_user_id = None
    else:
        try:
            uid = int(raw)
        except ValueError:
            flash('Invalid user id.', 'error')
            return redirect(url_for('admin.inbox_message', id=id))
        user = User.query_active().filter_by(id=uid, active=True).first()
        if not user:
            flash('User not found or inactive.', 'error')
            return redirect(url_for('admin.inbox_message', id=id))
        msg.assigned_to_user_id = user.id
    db.session.commit()
    return redirect(url_for('admin.inbox_message', id=id))


@admin_bp.route('/inbox/<int:id>/archive', methods=['POST'])
@admin_required
def inbox_archive(id):
    """Mark a message archived in our portal (does not touch the upstream mailbox)."""
    from ...models.email_message import EmailMessage
    msg = EmailMessage.query.get_or_404(id)
    msg.is_archived = True
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/inbox/<int:id>/mark-unread', methods=['POST'])
@admin_required
def inbox_mark_unread(id):
    """Force-mark a message as unread again (handy after accidental open)."""
    from ...models.email_message import EmailMessage
    msg = EmailMessage.query.get_or_404(id)
    msg.is_read = False
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/inbox/attachment/<int:id>')
@admin_required
def inbox_attachment(id):
    """Download an attachment.

    Lazy-fetches the binary from the upstream provider on first click,
    then caches it on the row so subsequent downloads are instant.
    """
    import base64
    from datetime import datetime
    from flask import Response
    from ...models.email_attachment import EmailAttachment
    from ...models.email_message import EmailMessage

    att = EmailAttachment.query.get_or_404(id)
    msg = EmailMessage.query.get(att.email_id)
    if not msg:
        return jsonify({'error': 'Parent message not found'}), 404

    if not att.content_b64:
        # First click — fetch from provider
        try:
            handler = msg.provider.get_handler()
            resp = handler.download_attachment(msg.remote_id, att.remote_id)
        except Exception as e:
            return jsonify({'error': f'Provider fetch failed: {e}'}), 502
        if not resp.get('success'):
            return jsonify({'error': resp.get('error', 'unknown')}), 502
        att.content_b64 = resp.get('content_b64')
        att.fetched_at = datetime.utcnow()
        # If the provider gave us a more accurate filename / size, capture
        if resp.get('filename') and not att.filename:
            att.filename = resp['filename']
        if resp.get('content_type') and not att.content_type:
            att.content_type = resp['content_type']
        db.session.commit()

    if not att.content_b64:
        return jsonify({'error': 'No content available'}), 502

    try:
        binary = base64.b64decode(att.content_b64)
    except Exception:
        return jsonify({'error': 'Stored attachment is not valid base64'}), 500

    safe_name = (att.filename or f'attachment-{att.id}').replace('"', '')
    return Response(
        binary,
        mimetype=att.content_type or 'application/octet-stream',
        headers={
            'Content-Disposition': f'inline; filename="{safe_name}"',
            'Content-Length': str(len(binary)),
        },
    )


@admin_bp.route('/inbox/sync-now', methods=['POST'])
@admin_required
def inbox_sync_now():
    """Trigger an inbox sync on demand (in addition to the cron timer)."""
    from ...services.email.sync import sync_all
    try:
        results = sync_all(limit=200)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from decimal import Decimal
import shortuuid
from . import admin_bp
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
        return jsonify({'error': 'Failed to send email'}), 500


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

    return render_template(
        'admin/donations.html',
        donations=donations,
        status_filter=status
    )


@admin_bp.route('/donations/<int:id>')
@admin_required
def donation_detail(id):
    """View donation details."""
    donation = Donation.query.get_or_404(id)
    return render_template('admin/donation_detail.html', donation=donation)


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
                Donor.phone.ilike(f'%{search}%')
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

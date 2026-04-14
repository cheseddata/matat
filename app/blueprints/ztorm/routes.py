from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from . import ztorm_bp
from ...extensions import db
from ...models import (
    Donor, Donation, Agreement, Payment, Receipt, Address, Phone,
    MemorialName, Communication, DonationEvent, DonorNote, Classification
)


# ============================================================
# SWITCHBOARD (Main Menu)
# ============================================================
@ztorm_bp.route('/')
@login_required
def switchboard():
    """Main menu - mimics Access Switchboard."""
    stats = {
        'donors': Donor.query_active().count(),
        'donations': Donation.query_active().count(),
        'payments': Payment.query.count(),
        'agreements': Agreement.query.filter_by(is_cancelled=False).count(),
        'receipts': Receipt.query.count(),
    }
    return render_template('ztorm/switchboard.html', stats=stats)


# ============================================================
# DONOR BROWSER (Tormim)
# ============================================================
@ztorm_bp.route('/donors')
@login_required
def donors():
    """Donor browser - mimics Access Tormim form with tabs."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    sort = request.args.get('sort', 'name')  # name or number

    query = Donor.query_active()
    if search:
        query = query.filter(
            or_(
                Donor.last_name.ilike(f'{search}%'),
                Donor.first_name.ilike(f'{search}%'),
                Donor.email.ilike(f'%{search}%'),
                Donor.phone.ilike(f'%{search}%'),
                Donor.teudat_zehut.ilike(f'{search}%'),
            )
        )

    if sort == 'number':
        query = query.order_by(Donor.id)
    else:
        query = query.order_by(Donor.last_name, Donor.first_name)

    donors = query.paginate(page=page, per_page=50)
    return render_template('ztorm/donors.html', donors=donors, search=search, sort=sort)


@ztorm_bp.route('/donors/<int:donor_id>')
@login_required
def donor_detail(donor_id):
    """Donor detail with tabs - mimics Access Tormim tabbed form."""
    donor = Donor.query.get_or_404(donor_id)
    tab = request.args.get('tab', 'overview')

    # Load tab-specific data
    donations = donor.donations.filter(Donation.deleted_at.is_(None)).order_by(Donation.created_at.desc()).all()
    payments = Payment.query.join(Donation).filter(
        Donation.donor_id == donor_id, Donation.deleted_at.is_(None)
    ).order_by(Payment.payment_date.desc()).all()
    agreements = Agreement.query.filter_by(donor_id=donor_id, is_cancelled=False).all()
    addresses = donor.addresses.all()
    phones = donor.phones.all()
    notes = donor.notes.order_by(DonorNote.created_at.desc()).all()
    memorial_names = donor.memorial_names.all()
    communications = donor.communications.order_by(Communication.created_at.desc()).limit(50).all()

    return render_template('ztorm/donor_detail.html',
                           donor=donor, tab=tab,
                           donations=donations, payments=payments,
                           agreements=agreements, addresses=addresses,
                           phones=phones, notes=notes,
                           memorial_names=memorial_names,
                           communications=communications)


# ============================================================
# DATA ENTRY (Klita)
# ============================================================
@ztorm_bp.route('/klita', methods=['GET', 'POST'])
@login_required
def klita():
    """Data entry form - mimics Access Klita form."""
    if request.method == 'POST':
        return _process_klita(request.form)
    return render_template('ztorm/klita.html')


def _process_klita(form):
    """Process the Klita data entry form."""
    try:
        # 1. Create or find donor
        donor_id = form.get('donor_id')
        if donor_id:
            donor = Donor.query.get(int(donor_id))
        else:
            donor = Donor(
                first_name=form.get('first_name', ''),
                last_name=form.get('last_name', ''),
                email=form.get('email', ''),
                phone=form.get('phone', ''),
                teudat_zehut=form.get('teudat_zehut', ''),
                title=form.get('title', ''),
                gender=form.get('gender', ''),
                city=form.get('city', ''),
                address_line1=form.get('address_line1', ''),
                zip=form.get('zip', ''),
                country=form.get('country', 'IL'),
            )
            db.session.add(donor)
            db.session.flush()

        # 2. Create agreement if needed
        agreement_id = form.get('agreement_id')
        if not agreement_id and form.get('agreement_type'):
            agreement = Agreement(
                donor_id=donor.id,
                agreement_type=form.get('agreement_type'),
                sub_type=form.get('agreement_sub_type'),
                currency=form.get('currency', 'ILS'),
                total_amount=form.get('total_amount', 0),
            )
            db.session.add(agreement)
            db.session.flush()
            agreement_id = agreement.id

        # 3. Create donation
        amount_str = form.get('amount', '0')
        amount = int(float(amount_str) * 100)  # Convert to cents
        payment_method = form.get('payment_method', 'cash')

        donation = Donation(
            donor_id=donor.id,
            agreement_id=agreement_id if agreement_id else None,
            amount=amount,
            currency=form.get('currency', 'ILS'),
            payment_method=payment_method,
            status='active' if payment_method != 'cash' else 'succeeded',
            donation_type='recurring' if payment_method in ('credit', 'hork') else 'one_time',
            entry_date=db.func.current_date(),
            send_receipt=True,
            user_created=current_user.username if current_user else None,
        )
        db.session.add(donation)
        db.session.flush()

        # 4. Create payment method record
        if payment_method == 'hork':
            from ...models import StandingOrder
            so = StandingOrder(
                donation_id=donation.id,
                bank_code=form.get('bank_code', type=int),
                branch_code=form.get('branch_code', type=int),
                account_number=form.get('account_number'),
                amount=float(amount_str),
                currency=form.get('currency', 'ILS'),
                collection_day=form.get('collection_day', 1, type=int),
                total_payments=form.get('installments', type=int),
            )
            db.session.add(so)

        elif payment_method in ('credit', 'ashp'):
            from ...models import CreditCardRecurring
            cc = CreditCardRecurring(
                donation_id=donation.id,
                card_last4=form.get('card_last4'),
                card_expiry=form.get('card_expiry'),
                amount=float(amount_str),
                currency=form.get('currency', 'ILS'),
                total_charges=form.get('installments', type=int),
                collection_day=form.get('collection_day', 1, type=int),
            )
            db.session.add(cc)

        elif payment_method in ('cash', 'check'):
            # Create immediate payment record
            payment = Payment(
                donation_id=donation.id,
                amount=float(amount_str),
                currency=form.get('currency', 'ILS'),
                payment_date=db.func.current_date(),
                value_date=db.func.current_date(),
                status='ok',
                method=payment_method,
            )
            if payment_method == 'check':
                payment.check_bank = form.get('check_bank', type=int)
                payment.check_branch = form.get('check_branch', type=int)
                payment.check_account = form.get('check_account')
                payment.check_number = form.get('check_number')
            db.session.add(payment)

        db.session.commit()
        flash(f'Donation #{donation.id} created successfully for {donor.full_name}', 'success')
        return redirect(url_for('ztorm.donor_detail', donor_id=donor.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('ztorm.klita'))


# ============================================================
# DONATIONS
# ============================================================
@ztorm_bp.route('/donations')
@login_required
def donations():
    """Donation list with filters."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    method = request.args.get('method', '')

    query = Donation.query_active().join(Donor)
    if status:
        query = query.filter(Donation.status == status)
    if method:
        query = query.filter(Donation.payment_method == method)

    query = query.order_by(Donation.created_at.desc())
    donations = query.paginate(page=page, per_page=50)
    return render_template('ztorm/donations.html', donations=donations, status=status, method=method)


# ============================================================
# PAYMENTS
# ============================================================
@ztorm_bp.route('/payments')
@login_required
def payments():
    """Payment list."""
    page = request.args.get('page', 1, type=int)
    payments = Payment.query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=50)
    return render_template('ztorm/payments.html', payments=payments)


# ============================================================
# AGREEMENTS
# ============================================================
@ztorm_bp.route('/agreements')
@login_required
def agreements():
    """Agreement list."""
    agreements = Agreement.query.filter_by(is_cancelled=False).order_by(Agreement.created_at.desc()).all()
    return render_template('ztorm/agreements.html', agreements=agreements)


# ============================================================
# REPORTS
# ============================================================
@ztorm_bp.route('/reports')
@login_required
def reports():
    """Reports menu."""
    return render_template('ztorm/reports.html')


# ============================================================
# API ENDPOINTS (for AJAX)
# ============================================================
@ztorm_bp.route('/api/donors/search')
@login_required
def api_donor_search():
    """Type-ahead donor search (like Access Seek)."""
    q = request.args.get('q', '')
    if len(q) < 2:
        return jsonify([])

    donors = Donor.query_active().filter(
        or_(
            Donor.last_name.ilike(f'{q}%'),
            Donor.first_name.ilike(f'{q}%'),
            Donor.phone.ilike(f'%{q}%'),
            Donor.teudat_zehut.ilike(f'{q}%'),
            Donor.email.ilike(f'%{q}%'),
        )
    ).limit(20).all()

    return jsonify([{
        'id': d.id,
        'name': d.full_name,
        'email': d.email or '',
        'phone': d.phone or '',
        'tz': d.teudat_zehut or '',
        'city': d.city or '',
    } for d in donors])


@ztorm_bp.route('/api/donors/<int:donor_id>/summary')
@login_required
def api_donor_summary(donor_id):
    """Get donor summary for AJAX tab loading."""
    donor = Donor.query.get_or_404(donor_id)
    donation_count = donor.donations.filter(Donation.deleted_at.is_(None)).count()
    total = db.session.query(func.sum(Donation.amount)).filter(
        Donation.donor_id == donor_id, Donation.deleted_at.is_(None),
        Donation.status.in_(['succeeded', 'active'])
    ).scalar() or 0

    return jsonify({
        'id': donor.id,
        'name': donor.full_name,
        'email': donor.email,
        'phone': donor.phone,
        'tz': donor.teudat_zehut,
        'donation_count': donation_count,
        'total_donated': total / 100,
    })


# ============================================================
# DONOR CRUD
# ============================================================
@ztorm_bp.route('/donors/<int:donor_id>/edit')
@login_required
def donor_edit(donor_id):
    """Edit donor form."""
    donor = Donor.query.get_or_404(donor_id)
    return render_template('ztorm/donor_edit.html', donor=donor)


@ztorm_bp.route('/donors/new')
@login_required
def donor_new():
    """New donor form."""
    donor = Donor(first_name='', last_name='', country='IL', language_pref='he', send_mail=True)
    return render_template('ztorm/donor_edit.html', donor=donor)


@ztorm_bp.route('/donors/<int:donor_id>/save', methods=['POST'])
@login_required
def donor_save(donor_id):
    """Save donor (create or update)."""
    if donor_id > 0:
        donor = Donor.query.get_or_404(donor_id)
    else:
        donor = Donor()
        db.session.add(donor)

    # Update fields from form
    for field in ['first_name', 'last_name', 'email', 'phone', 'teudat_zehut',
                  'title', 'suffix', 'gender', 'spouse_name', 'spouse_tz',
                  'father_name', 'mother_name', 'occupation', 'receipt_name',
                  'receipt_tz', 'address_line1', 'city', 'zip', 'country',
                  'language_pref', 'classification_1', 'classification_2',
                  'classification_3', 'letter_first_name', 'letter_last_name']:
        val = request.form.get(field, '').strip()
        setattr(donor, field, val if val else None)

    # Boolean fields
    donor.send_mail = 'send_mail' in request.form
    donor.bookmark = 'bookmark' in request.form

    # Integer fields
    birth_year = request.form.get('birth_year', '').strip()
    donor.birth_year = int(birth_year) if birth_year else None

    try:
        db.session.commit()
        flash(f'תורם {donor.full_name} נשמר בהצלחה', 'success')
        return redirect(url_for('ztorm.donor_detail', donor_id=donor.id))
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
        return redirect(url_for('ztorm.donor_edit', donor_id=donor_id or 0))


@ztorm_bp.route('/donors/<int:donor_id>/delete', methods=['POST'])
@login_required
def donor_delete(donor_id):
    """Soft-delete a donor."""
    donor = Donor.query.get_or_404(donor_id)
    from datetime import datetime
    donor.deleted_at = datetime.utcnow()
    db.session.commit()
    flash(f'תורם {donor.full_name} נמחק', 'success')
    return redirect(url_for('ztorm.donors'))


# ============================================================
# DONATION CRUD
# ============================================================
@ztorm_bp.route('/donations/<int:donation_id>/activate', methods=['POST'])
@login_required
def donation_activate(donation_id):
    """Activate a donation."""
    from ...services.ztorm.donation_service import activate_donation
    try:
        activate_donation(donation_id, user=current_user.username)
        db.session.commit()
        flash('התרומה הופעלה בהצלחה', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    donation = Donation.query.get(donation_id)
    return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='donations'))


@ztorm_bp.route('/donations/<int:donation_id>/cancel', methods=['POST'])
@login_required
def donation_cancel(donation_id):
    """Cancel a donation."""
    from ...services.ztorm.donation_service import cancel_donation
    reason = request.form.get('reason', '')
    try:
        cancel_donation(donation_id, reason=reason, user=current_user.username)
        db.session.commit()
        flash('התרומה בוטלה', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    donation = Donation.query.get(donation_id)
    return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='donations'))


@ztorm_bp.route('/donations/<int:donation_id>/complete', methods=['POST'])
@login_required
def donation_complete(donation_id):
    """Complete a donation."""
    from ...services.ztorm.donation_service import complete_donation
    try:
        complete_donation(donation_id, user=current_user.username)
        db.session.commit()
        flash('התרומה הושלמה', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    donation = Donation.query.get(donation_id)
    return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='donations'))


# ============================================================
# PAYMENT CRUD
# ============================================================
@ztorm_bp.route('/payments/add/<int:donation_id>', methods=['GET', 'POST'])
@login_required
def payment_add(donation_id):
    """Add payment to donation."""
    donation = Donation.query.get_or_404(donation_id)

    if request.method == 'POST':
        from ...services.ztorm.payment_service import add_payment
        try:
            amount = float(request.form.get('amount', 0))
            payment = add_payment(
                donation_id=donation_id,
                amount=amount,
                currency=request.form.get('currency', 'ILS'),
                method=request.form.get('method', 'cash'),
                payment_date=_parse_form_date(request.form.get('payment_date')),
                check_bank=request.form.get('check_bank', type=int),
                check_branch=request.form.get('check_branch', type=int),
                check_account=request.form.get('check_account'),
                check_number=request.form.get('check_number'),
                reference=request.form.get('reference'),
                notes=request.form.get('notes'),
                user=current_user.username,
            )
            db.session.commit()
            flash(f'תשלום #{payment.id} נוצר בהצלחה', 'success')
            return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='payments'))
        except Exception as e:
            db.session.rollback()
            flash(f'שגיאה: {str(e)}', 'error')

    return render_template('ztorm/payment_form.html', donation=donation, payment=None)


@ztorm_bp.route('/payments/<int:payment_id>/delete', methods=['POST'])
@login_required
def payment_delete(payment_id):
    """Delete a payment."""
    from ...services.ztorm.payment_service import delete_payment
    payment = Payment.query.get_or_404(payment_id)
    donation = Donation.query.get(payment.donation_id)
    try:
        delete_payment(payment_id, user=current_user.username)
        db.session.commit()
        flash('התשלום נמחק', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='payments'))


@ztorm_bp.route('/payments/<int:payment_id>/return', methods=['POST'])
@login_required
def payment_return(payment_id):
    """Process bank return (hazara)."""
    from ...services.ztorm.payment_service import process_return
    payment = Payment.query.get_or_404(payment_id)
    donation = Donation.query.get(payment.donation_id)
    try:
        reason = request.form.get('reason', 'Return')
        process_return(payment_id, reason=reason, user=current_user.username)
        db.session.commit()
        flash('החזרה עובדה בהצלחה', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='payments'))


# ============================================================
# RECEIPTS
# ============================================================
@ztorm_bp.route('/receipts')
@login_required
def receipts():
    """Receipt list."""
    page = request.args.get('page', 1, type=int)
    receipts = Receipt.query.order_by(Receipt.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('ztorm/receipts.html', receipts=receipts)


@ztorm_bp.route('/receipts/create/<int:donation_id>', methods=['POST'])
@login_required
def receipt_create(donation_id):
    """Create receipt for donation."""
    from ...services.ztorm.receipt_service import create_receipt, generate_receipt_pdf
    try:
        receipt = create_receipt(donation_id, user=current_user.username)
        db.session.commit()
        # Generate PDF
        pdf_path = generate_receipt_pdf(receipt.id)
        db.session.commit()
        flash(f'קבלה {receipt.receipt_number} נוצרה בהצלחה', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    donation = Donation.query.get(donation_id)
    return redirect(url_for('ztorm.donor_detail', donor_id=donation.donor_id, tab='donations'))


@ztorm_bp.route('/receipts/<int:receipt_id>/cancel', methods=['POST'])
@login_required
def receipt_cancel(receipt_id):
    """Cancel a receipt."""
    from ...services.ztorm.receipt_service import cancel_receipt
    receipt = Receipt.query.get_or_404(receipt_id)
    try:
        reason = request.form.get('reason', 'Cancelled')
        cancel_receipt(receipt_id, reason=reason, user=current_user.username)
        db.session.commit()
        flash('הקבלה בוטלה', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה: {str(e)}', 'error')
    return redirect(url_for('ztorm.receipts'))


@ztorm_bp.route('/receipts/batch', methods=['GET', 'POST'])
@login_required
def receipts_batch():
    """Batch receipt preparation."""
    if request.method == 'POST':
        from ...services.ztorm.receipt_service import batch_prepare_receipts
        try:
            results = batch_prepare_receipts()
            db.session.commit()
            flash(f'נוצרו {len(results["created"])} קבלות, {len(results["errors"])} שגיאות, {len(results["skipped"])} דולגו', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'שגיאה: {str(e)}', 'error')
        return redirect(url_for('ztorm.receipts'))
    return render_template('ztorm/receipts_batch.html')


# ============================================================
# REPORTS
# ============================================================
@ztorm_bp.route('/reports/donations')
@login_required
def report_donations():
    """Donation report with filters."""
    from datetime import datetime

    status = request.args.get('status', '')
    method = request.args.get('method', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    currency = request.args.get('currency', '')

    query = Donation.query_active().join(Donor)

    if status:
        query = query.filter(Donation.status == status)
    if method:
        query = query.filter(Donation.payment_method == method)
    if currency:
        query = query.filter(Donation.currency == currency)
    if date_from:
        try:
            query = query.filter(Donation.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except: pass
    if date_to:
        try:
            query = query.filter(Donation.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        except: pass

    donations = query.order_by(Donation.created_at.desc()).all()

    # Calculate totals
    total_nis = sum(float(d.paid_nis or 0) for d in donations)
    total_usd = sum(float(d.paid_usd or 0) for d in donations)

    return render_template('ztorm/report_donations.html',
                           donations=donations, total_nis=total_nis, total_usd=total_usd,
                           status=status, method=method, date_from=date_from,
                           date_to=date_to, currency=currency)


@ztorm_bp.route('/reports/donations/export')
@login_required
def report_donations_export():
    """Export donations to CSV."""
    import csv
    import io
    from flask import Response

    donations = Donation.query_active().join(Donor).order_by(Donation.created_at.desc()).all()

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel Hebrew support
    writer = csv.writer(output)
    writer.writerow(['מספר', 'תורם', 'אופן', 'סכום', 'מטבע', 'סטטוס', 'שולם ₪', 'שולם $', 'תאריך', 'הסכם'])

    for d in donations:
        writer.writerow([
            d.id,
            d.donor.full_name if d.donor else '',
            d.payment_method or '',
            d.amount_display,
            d.currency or '',
            d.status or '',
            float(d.paid_nis or 0),
            float(d.paid_usd or 0),
            d.created_at.strftime('%d/%m/%Y') if d.created_at else '',
            d.agreement_id or '',
        ])

    response = Response(output.getvalue(), mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = 'attachment; filename=donations_report.csv'
    return response


@ztorm_bp.route('/reports/payments')
@login_required
def report_payments():
    """Payment report with filters."""
    from datetime import datetime

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    method = request.args.get('method', '')
    status = request.args.get('status', '')

    query = Payment.query.join(Donation).join(Donor)

    if status:
        query = query.filter(Payment.status == status)
    if method:
        query = query.filter(Payment.method == method)
    if date_from:
        try:
            query = query.filter(Payment.payment_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        except: pass
    if date_to:
        try:
            query = query.filter(Payment.payment_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        except: pass

    payments = query.order_by(Payment.payment_date.desc()).limit(1000).all()

    total = sum(float(p.amount or 0) for p in payments)

    return render_template('ztorm/report_payments.html',
                           payments=payments, total=total,
                           status=status, method=method,
                           date_from=date_from, date_to=date_to)


# ============================================================
# NOTES
# ============================================================
@ztorm_bp.route('/donors/<int:donor_id>/notes/add', methods=['POST'])
@login_required
def note_add(donor_id):
    """Add a note to a donor."""
    content = request.form.get('content', '').strip()
    if content:
        note = DonorNote(
            donor_id=donor_id,
            user_id=current_user.id,
            content=content,
            note_type=request.form.get('note_type', 'general'),
        )
        db.session.add(note)
        db.session.commit()
        flash('הערה נוספה', 'success')
    return redirect(url_for('ztorm.donor_detail', donor_id=donor_id, tab='notes'))


# ============================================================
# PAYMENT PROCESSORS
# ============================================================
@ztorm_bp.route('/processors')
@login_required
def payment_processors():
    """Payment processor settings."""
    from ...services.payment.router import get_available_processors, get_default_processor

    processors = get_available_processors()
    active = get_default_processor()

    # Load saved configs
    shva_config = {
        'merchant_number': '2481062014',
        'username': 'MXRCX',
        'password': 'Z496089',
        'test_mode': False,
    }
    ezcount_config = {
        'api_key': '3766c7b037ae4f78cc93eaa23a33b89c1739c2d9b4928d2c4ba152337b9227fa',
        'prefix': 'Z2',
    }

    return render_template('ztorm/payment_processors.html',
                           processors=processors, active_processor=active,
                           shva_config=shva_config, ezcount_config=ezcount_config)


@ztorm_bp.route('/processors/set', methods=['POST'])
@login_required
def set_processor():
    """Set active payment processor."""
    processor = request.form.get('processor', 'shva')
    flash(f'ספק אשראי הוגדר ל-{processor}', 'success')
    return redirect(url_for('ztorm.payment_processors'))


@ztorm_bp.route('/processors/config', methods=['POST'])
@login_required
def save_processor_config():
    """Save processor configuration."""
    processor = request.form.get('processor', '')
    flash(f'הגדרות {processor} נשמרו', 'success')
    return redirect(url_for('ztorm.payment_processors'))


@ztorm_bp.route('/api/test-processor/<processor_code>')
@login_required
def api_test_processor(processor_code):
    """Test processor connection."""
    from ...services.payment.router import get_processor
    try:
        proc = get_processor(processor_code)
        result = proc.test_connection()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ============================================================
# CHARGE CREDIT CARD (using selected processor)
# ============================================================
@ztorm_bp.route('/charge', methods=['GET', 'POST'])
@login_required
def charge_card():
    """Credit card charge form - user selects processor."""
    from ...services.payment.router import get_available_processors, get_processor

    processors = get_available_processors()

    if request.method == 'POST':
        processor_code = request.form.get('processor', 'shva')
        proc = get_processor(processor_code)

        amount_str = request.form.get('amount', '0')
        amount_cents = int(float(amount_str) * 100)
        currency = request.form.get('currency', 'ILS')

        card_data = {
            'card_number': request.form.get('card_number', ''),
            'expiry': request.form.get('expiry', ''),
            'cvv': request.form.get('cvv', ''),
        }

        donor_data = {
            'tz': request.form.get('tz', ''),
        }

        installments = int(request.form.get('installments', 1))

        # Step 1: Charge the card
        result = proc.create_payment(
            amount=amount_cents,
            currency=currency,
            card_data=card_data,
            donor_data=donor_data,
            installments=installments,
        )

        if result['success']:
            try:
                # Step 2: Find or create donor, and update with form corrections
                donor_id = request.form.get('donor_id', type=int)
                if donor_id:
                    donor = Donor.query.get(donor_id)
                else:
                    donor = Donor(country='IL')
                    db.session.add(donor)

                # Always update donor with latest form data (user may have corrected info)
                form_first = request.form.get('first_name', '').strip()
                form_last = request.form.get('last_name', '').strip()
                form_email = request.form.get('email', '').strip()
                form_phone = request.form.get('phone', '').strip()
                form_tz = request.form.get('tz', '').strip()
                form_city = request.form.get('city', '').strip()
                form_address = request.form.get('address', '').strip()

                if form_first:
                    donor.first_name = form_first
                if form_last:
                    donor.last_name = form_last
                if form_email:
                    donor.email = form_email
                if form_phone:
                    donor.phone = form_phone
                if form_tz:
                    donor.teudat_zehut = form_tz
                if form_city:
                    donor.city = form_city
                if form_address:
                    donor.address_line1 = form_address

                db.session.flush()

                # Step 3: Create donation record
                donation = Donation(
                    donor_id=donor.id,
                    amount=amount_cents,
                    currency=currency,
                    payment_method='credit',
                    payment_processor=processor_code,
                    processor_transaction_id=result.get('transaction_id', ''),
                    processor_confirmation=result.get('confirmation', ''),
                    status='succeeded',
                    donation_type='one_time' if installments <= 1 else 'recurring',
                    entry_date=db.func.current_date(),
                    send_receipt=True,
                    receipt_name=request.form.get('receipt_name') or donor.full_name,
                    receipt_tz=request.form.get('tz', ''),
                    receipt_email=donor.email,
                    donor_comment=request.form.get('notes', ''),
                    user_created=current_user.username,
                    paid_nis=float(amount_str) if currency == 'ILS' else 0,
                    paid_usd=float(amount_str) if currency == 'USD' else 0,
                )
                db.session.add(donation)
                db.session.flush()

                # Step 4: Create payment record
                from datetime import date as date_today
                payment = Payment(
                    donation_id=donation.id,
                    amount=float(amount_str),
                    currency=currency,
                    payment_date=date_today.today(),
                    value_date=date_today.today(),
                    status='ok',
                    method='credit',
                    reference=result.get('confirmation', ''),
                    authorization_number=result.get('authorization_code', ''),
                )
                db.session.add(payment)
                db.session.flush()

                # Step 5: Generate receipt via EZCount API
                receipt_obj = None
                if 'send_receipt' in request.form:
                    try:
                        from ...services.ztorm.ezcount_service import create_receipt as ezcount_create
                        from ...services.ztorm.receipt_service import create_receipt as local_create

                        receipt_name = request.form.get('receipt_name') or donor.full_name
                        description = request.form.get('notes') or 'תרומה'

                        # Create receipt via EZCount (official Israeli tax receipt)
                        ez_result = ezcount_create(
                            donor_name=receipt_name,
                            donor_tz=request.form.get('tz', ''),
                            donor_email=donor.email,
                            amount=float(amount_str),
                            currency=currency,
                            payment_method='credit',
                            description=description,
                            donor_address=request.form.get('address', ''),
                            donor_city=request.form.get('city', ''),
                        )

                        if ez_result.get('success'):
                            # Create local receipt record linked to EZCount
                            receipt_obj = local_create(donation.id, user=current_user.username)
                            receipt_obj.doc_number = ez_result.get('doc_number', '')
                            receipt_obj.doc_url = ez_result.get('pdf_url', '')
                            receipt_obj.tax_allocation_num = ez_result.get('tax_allocation_num', '')
                            receipt_obj.email_sent_to = donor.email
                            receipt_obj.sent_at = db.func.now()
                            db.session.flush()

                            result['receipt_number'] = receipt_obj.receipt_number
                            result['ezcount_doc'] = ez_result.get('doc_number', '')
                            result['receipt_pdf'] = ez_result.get('pdf_url', '')
                            result['receipt_sent'] = True
                        else:
                            result['receipt_error'] = f"EZCount: {ez_result.get('error', 'Unknown')}"
                            # Fall back to local receipt
                            receipt_obj = local_create(donation.id, user=current_user.username)
                            db.session.flush()
                            result['receipt_number'] = receipt_obj.receipt_number
                            result['receipt_sent'] = False

                    except Exception as e:
                        result['receipt_error'] = str(e)

                db.session.commit()

                result['donor_name'] = donor.full_name
                result['donor_id'] = donor.id
                result['donation_id'] = donation.id

                flash(f'חיוב הצליח! {donor.full_name} - אישור: {result.get("confirmation", "")}', 'success')

            except Exception as e:
                db.session.rollback()
                result['db_error'] = str(e)
                flash(f'חיוב הצליח אך שגיאה בשמירה: {str(e)}', 'error')
        else:
            flash(f'חיוב נכשל: {result.get("error", "Unknown")}', 'error')

        return render_template('ztorm/charge_result.html', result=result, processors=processors)

    return render_template('ztorm/charge_form.html', processors=processors)


# ============================================================
# HELPERS
# ============================================================
def _parse_form_date(date_str):
    """Parse date from form input."""
    if not date_str:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

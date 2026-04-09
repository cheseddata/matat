# Matbia Payment Integration - Implementation Guide

## Overview
Matbia (matbia.org) is a Jewish charity card platform with a FULL REST Payment API. Donors carry a physical NFC charity card (like a credit card for tzedakah) and tap to give. Matbia acts as a payment gateway specifically for Jewish charities. Hundreds of nonprofits on the platform.

## Authentication
- API credentials from Matbia developer portal
- Developer Docs: https://developers.matbia.org

### Environments
- Production: https://api.matbia.org
- Sandbox: https://sandbox.api.matbia.org (test data provided)

---

## PHASE 1: Database and Config

### ConfigSettings model
- matbia_api_key = db.Column(db.String(255), nullable=True)
- matbia_org_handle = db.Column(db.String(255), nullable=True)
- matbia_org_tax_id = db.Column(db.String(50), nullable=True)
- matbia_enabled = db.Column(db.Boolean, default=False)

### Donation model
- matbia_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
- matbia_schedule_id = db.Column(db.String(255), nullable=True)
- is_matbia_donation = db.Column(db.Boolean, default=False)

---

## PHASE 2: API Endpoints

### Charge (Process Transaction)
POST v1/Matbia/Charge

Process a one-time donation through Matbia card.

### Schedule (Recurring Payments)
POST v1/Matbia/Schedule

Set up recurring donations (weekly, monthly, etc.)

### Preauthorization (Card Verification)
POST v1/Matbia/Preauthorization

Verify a Matbia card is valid before charging.

---

## PHASE 3: Nonprofit Identification

Your nonprofit is identified in API calls by either:
- orgUserHandle (your Matbia handle)
OR
- Combination of: orgTaxId + orgName + orgEmail

---

## PHASE 4: Integration Flow

1. Donor has a Matbia charity card (physical NFC card)
2. On your donation page, add "Pay with Matbia" option
3. Donor enters Matbia card number (or taps NFC at physical location)
4. Your server calls POST v1/Matbia/Charge with card details and amount
5. Matbia processes the transaction
6. Create Donation record with payment_provider=matbia
7. Generate receipt, calculate commission

For recurring:
1. Call POST v1/Matbia/Schedule with frequency and amount
2. Matbia handles recurring charges automatically
3. Track via matbia_schedule_id

---

## Important Notes

1. JEWISH SPECIFIC: Matbia is built specifically for the frum/Orthodox Jewish charity ecosystem.

2. NFC CARDS: Physical charity cards are a key differentiator. Consider supporting NFC tap at events/locations.

3. SANDBOX AVAILABLE: Full test environment at sandbox.api.matbia.org.

4. REGISTER FIRST: Your nonprofit must be registered on Matbia platform before API access.

5. CONTACT: Through developers.matbia.org for API credentials.

---

## File Changes Summary
- app/models/config_settings.py - Add matbia fields
- app/models/donation.py - Add matbia fields
- app/services/matbia_service.py - NEW
- app/blueprints/webhook/routes.py - Add matbia callback
- app/blueprints/donate/routes.py - Add matbia flow
- app/blueprints/admin/routes.py - Add matbia settings
- app/templates/donate/donation_page.html - Add "Pay with Matbia"
- migrations/ - New migration

## Testing Checklist
- [ ] Matbia credentials configured
- [ ] Preauthorization works in sandbox
- [ ] Charge processes successfully
- [ ] Schedule creates recurring donation
- [ ] Donation record created with payment_provider=matbia
- [ ] Receipt generated
- [ ] Commission calculated

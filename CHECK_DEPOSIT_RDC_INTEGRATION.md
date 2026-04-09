# Check Image Deposit (RDC) Integration - Master Overview

## Overview
Remote Deposit Capture (RDC) allows donors to snap a picture of a check and deposit it
digitally. This document covers all available APIs for programmatic check image deposit.

## KEY DECISION: Deposit to Existing Chase Account vs New Account

### Option A: Keep Your Chase Account (Route Deposits to Chase)
These platforms route deposits through a payment gateway to YOUR bank:

1. Payology / Check21.com (RECOMMENDED)
2. iWallet
3. SpeedChex
4. FTNI ETran
5. CheckAlt

### Option B: Open New Account (BaaS Platforms)
These require opening a new bank account through their platform:

1. Column (most developer-friendly)
2. Unit (well-documented)
3. Synctera (clear 2-step API)
4. Treasury Prime

---

## TIER 1: BEST OPTIONS FOR MATAT MORDECHAI

### 1. Payology / Check21.com -- RECOMMENDED (Works with Chase)

Cloud-based API, no software installation required.

- Docs: https://check21.readme.io/docs/introduction-to-payology-mobile-check-capture-api
- Website: https://www.check21.com

How it works:
- Cloud API accepts raw images from mobile devices or scanners
- Crops, rotates, converts to federally accepted standards
- Returns parsed MICR (routing, account, check number), payee name/address, amounts
- Routes through Check21.com Payment Gateway to YOUR bank (Chase)
- Salesforce integration available

Features:
- Multi-check capture
- Image quality validation
- MICR extraction
- Amount recognition (CAR/LAR)
- Federal Reserve compliant output

### 2. iWallet -- GOOD OPTION (Works with Any Bank)

- Docs: https://iwallet.com/api
- REST API

How it works:
- Mobile capture processes front image
- Extracts payee name, address, amount
- Routes through payment gateway to YOUR financial institution
- Built-in fraud protection (scans bad check writer database, real-time alerts)
- Multi-check capture
- Webhooks for bank confirmation and rejections
- Can issue refunds

### 3. Column -- BEST DEVELOPER EXPERIENCE (Requires New Account)

Column IS a bank (Column N.A.), directly connected to Federal Reserve.

- Docs: https://column.com/docs/checks/deposits

Two-step process:
1. Send raw front/back photos to Check Imaging API (beta) -- crops, formats, extracts MICR
2. Submit formatted images + MICR to Check Deposit API

Most complete public documentation of any option.

### 4. Unit -- WELL DOCUMENTED (Requires New Account)

- Docs: https://docs.unit.co/check-deposits/

How it works:
- Upload front-side JPEG image (max 1.5 MB)
- Create check deposit resource
- Client-side component runs image quality validation
- Dynamic clearing period (configurable days to clear)

### 5. Synctera -- CLEAR 2-STEP API (Requires New Account)

- Docs: https://docs.synctera.com/docs/create-mobile-deposit-guide

Two-step API:
1. POST /v0/documents -- upload front/back check images
2. POST /v0/rdc/deposits -- create deposit with image IDs, amount, account
3. GET /v0/rdc/deposits/{id} -- check status

Returns OCR-extracted data. Sandbox: https://apitest.synctera.com

---

## TIER 2: OTHER OPTIONS WITH APIs

### 6. SpeedChex (SOAP/XML API, Works with Any Bank)
- Docs: https://www.speedchex.com/.../SpeedChex_WebServiceAPI_RemoteDepositCommands_M_v1.0.pdf
- Scanned at 200+ DPI with MICR capture
- Converted to ACH or Check 21 (IRD)
- Processed to Federal Reserve, deposited to YOUR bank
- Endpoints: Create Batch, Add Check to Batch, Process Batch

### 7. FTNI ETran (Enterprise, Works with Any Bank)
- Website: https://www.ftni.com/etran-advanced-remote-deposit-capture
- 50%+ of customers use their APIs
- Scanner or mobile capture
- Works with virtually any bank
- Enterprise pricing, contact sales

### 8. CheckAlt / FinCapture (Works with Any Bank)
- Docs: https://www.checkalt.com/check21api
- Mobile capture front/back
- Fraud detection (duplicate detection, endorsement verification, real-time risk scoring)
- Customizable deposit limits
- Also partnered with Treasury Prime

### 9. Paygears (REST API)
- Docs: https://docs.paygears.com/
- Send physical or digital checks, instant remote deposits
- Webhooks at every stage

### 10. All My Papers / AMP (Enterprise, Image Processing Focus)
- Docs: https://www.allmypapers.com/apidev/

Three APIs:
- AMP Check API: Item/Verify (MICR + amount recognition), Item/Conform-Images
- AMP Deposit API: Item/Deposit, Item/Data, Item/Update (full lifecycle)
- AMP Mobile API: Check/Deposit, Check/Result, Check/Confirm, Check/Void, Check/Flag

Plus X9 RPC for ICL/X9.37 file generation. Enterprise pricing.
Contact: sales@allmypapers.com, +1 (408) 366-6400

---

## TIER 3: CAPTURE-ONLY SDKs (Need Separate Deposit Processor)

### 11. Mitek MiSnap (Industry Standard Capture SDK)
- GitHub: https://github.com/Mitek-Systems/MiSnap-Android
- Docs: https://docs.us.mitekcloud.com/
- Mobile SDK with auto-capture, image quality validation, edge detection
- Used by most major banks (Chase, BofA, etc.) for their mobile deposit
- IMAGE CAPTURE ONLY -- does not deposit. Pair with a deposit API above.

### 12. Ingo Money / Ingo Payments (Risk + Capture)
- Docs: https://developer.ingo.money/
- Mobile SDK (iOS/Android, based on Mitek MiSnap)
- Check Protect API for risk decisioning with OCR validation
- Webhooks for responses
- Enterprise pricing

---

## PLATFORMS THAT DO NOT OFFER CHECK DEPOSIT

- Plaid: No RDC API
- Stripe: Mentions "remote check acceptance" in Treasury but no public API
- Square: No check deposit
- PayPal: Discontinued RDC in 2014

---

## RECOMMENDED IMPLEMENTATION FOR MATAT MORDECHAI

### Phase 1: Choose a Processor
IF keeping Chase account: Payology/Check21.com or iWallet
IF willing to open new account: Column or Synctera

### Phase 2: Database Changes
Add to Donation model:
- check_image_front = db.Column(db.String(500)) -- S3/storage path
- check_image_back = db.Column(db.String(500))
- check_routing_number = db.Column(db.String(20))
- check_account_number = db.Column(db.String(20))
- check_number = db.Column(db.String(20))
- check_amount_ocr = db.Column(db.Numeric(10,2))
- check_deposit_status = db.Column(db.String(50)) -- pending, submitted, cleared, returned
- check_deposit_reference = db.Column(db.String(255))
- is_check_donation = db.Column(db.Boolean, default=False)

### Phase 3: Donor Flow
1. Donor selects "Pay by Check" on donation page
2. Donor uses phone camera to capture front and back of check
3. Images uploaded to your server (store in S3 or similar)
4. Server submits to RDC processor API
5. Processor validates image quality, reads MICR, extracts amount
6. If valid: deposit initiated, donation record created as pending
7. Webhook/poll for deposit confirmation
8. On confirmation: mark donation as completed, generate receipt

### Phase 4: Admin Features
- View pending check deposits
- Manual approval/rejection for flagged checks
- Deposit status tracking
- Return handling (bounced checks)

---

## Contact Info Summary

| Platform | Contact | Best For |
|----------|---------|----------|
| Payology/Check21 | check21.com | Existing Chase account |
| iWallet | iwallet.com/api | Existing bank, fraud protection |
| Column | column.com | Best dev experience |
| Unit | unit.co | Well-documented BaaS |
| Synctera | synctera.com | Clear 2-step API |
| SpeedChex | speedchex.com | SOAP/XML, any bank |
| FTNI | ftni.com | Enterprise, any bank |
| CheckAlt | checkalt.com | Fraud detection |
| AMP | allmypapers.com | Image processing |
| Mitek | miteksystems.com | Capture SDK only |

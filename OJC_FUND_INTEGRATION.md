# OJC Fund (Orthodox Jewish Chamber) DAF Integration - Implementation Guide

## Overview
OJC Fund (ojcfund.org) is a Jewish donor-advised fund serving 8,000+ organizations. Provides API keys for platform integration. Integrated with all major Jewish charity platforms including The Chesed Fund, Charidy, and AB Charity.

## Authentication
- API Key provided by OJC for platform integration
- Integrated into partner platform dashboards (e.g., Chesed Fund dashboard)
- No public developer portal -- integration via API key in supported platforms

### How Grants Work
1. Donor loads OJC Fund account
2. Donor uses OJC card (physical or digital) or platform integrations to direct grants
3. If nonprofit has OJC account: funds received directly
4. If nonprofit does NOT have OJC account: funds held until they register

## Integration Paths for Matat Mordechai

### Path A: Via Chariot/DAFpay (Recommended)
OJC Fund is a supported DAF provider in Chariot/DAFpay.
Add DAFpay button and OJC donors can give automatically.
See CHARIOT_DAFPAY_INTEGRATION.md.

### Path B: Direct API Key Integration
1. Contact OJC Fund: https://ojcfund.org/contact/
2. Request API key for your platform
3. Integrate API key into your donation flow
4. Accept OJC card payments directly

### Path C: Via Partner Platforms
If campaigns run on Charidy, CauseMatch, The Chesed Fund, or AB Charity,
OJC integration is already built in.

## Platform Partners
- The Chesed Fund (dashboard API key integration)
- Charidy
- AB Charity
- CauseMatch (via DAFpay)

## Implementation Steps
1. Register your nonprofit with OJC Fund
2. Add DAFpay button (covers OJC automatically)
3. Optionally contact OJC for direct API key
4. Add "Pay with OJC Fund" as payment option
5. Track donations with daf_provider="OJC Fund"

## Contact
- Website: https://ojcfund.org
- Contact: https://ojcfund.org/contact/

# Jewish DAF & Donation Platforms - Master Overview

## Summary for Matat Mordechai

This document maps out the entire Jewish DAF (Donor-Advised Fund) and donation platform ecosystem,
identifying which platforms have APIs and how to integrate them.

---

## PLATFORMS WITH FULL APIs (Build Direct Integrations)

### 1. Chariot / DAFpay -- HIGHEST PRIORITY
- Universal DAF button covering 1,151+ providers
- Covers: Donors Fund, OJC, JCF, CJP, Fidelity, Schwab, all Jewish Federation DAFs
- Full REST API with sandbox
- ONE integration = ALL DAF providers
- See: CHARIOT_DAFPAY_INTEGRATION.md

### 2. Matbia -- HIGH PRIORITY (Jewish Specific)
- Jewish charity card with NFC
- Full REST Payment API with sandbox
- Endpoints: Charge, Schedule (recurring), Preauthorization
- Popular in Orthodox/frum communities
- See: MATBIA_INTEGRATION.md

### 3. Charidy -- MEDIUM PRIORITY
- Jewish crowdfunding platform
- Public API for campaign data
- Useful if running campaigns, less relevant for direct donations
- See: CHARIDY_INTEGRATION.md

### 4. IsraelGives / GivingTech -- MEDIUM PRIORITY
- Search API (3M+ international charities)
- Payment API, Pooled Grant API, Reporting API
- Docs: israelgives.org/instruction/israeltoremet_api.pdf
- Good for expanding to international giving

---

## PLATFORMS WITH PARTIAL INTEGRATION (API Keys / Partnerships)

### 5. The Donors Fund
- Has API infrastructure (not publicly documented)
- Integrates via Chariot/DAFpay or partner platforms
- Contact support@thedonorsfund.org for direct API access
- See: THE_DONORS_FUND_INTEGRATION.md

### 6. OJC Fund
- API key integration through partner platforms
- 8,000+ organizations
- Supported via Chariot/DAFpay
- See: OJC_FUND_INTEGRATION.md

### 7. JGive
- Webhooks, Zapier integration, pixel tracking
- Embeddable fundraising pages
- No full REST API

### 8. AB Charity
- Browser Payment API support
- Accepts OJC, Donors Fund, Pledger, Matbia cards
- Google Pay, Apple Pay, PayPal

---

## DAF PROVIDERS WITH NO API (Accessible via Chariot/DAFpay)

### 9. Jewish Communal Fund (JCF)
- No public API, donor portal only
- Supported through Chariot/DAFpay
- $4B in assets, 5,400 funds

### 10. Combined Jewish Philanthropies (CJP)
- No public API, uses DonorFirst platform
- Supported through Chariot/DAFpay
- $2B+ in DAF assets

### 11. Jewish Federation DAFs (Various Cities)
- Bay Area, St. Louis, Omaha, San Diego, MetroWest NJ, etc.
- No public APIs, online donor portals
- Many supported through Chariot/DAFpay

---

## PLATFORMS WITH NO API

### 12. Jewish National Fund (JNF) -- No API
### 13. Keren Hashviis -- No API
### 14. Colel Chabad -- No API (accepts BTC, PayPal, Venmo)
### 15. Bnai Tzedek / Jewish Teen Foundation -- No API
### 16. Kehilla Fund -- No API
### 17. The Jewish Fund -- No API

---

## CROWDFUNDING/CAMPAIGN PLATFORMS (Not Payment Gateways)

### 18. The Chesed Fund -- No public API, accepts OJC/Donors Fund
### 19. CauseMatch -- No public API, has DAFpay integration
### 20. Jewcer -- No public API

---

## RECOMMENDED INTEGRATION PRIORITY FOR MATAT MORDECHAI

### Phase 1: Core Payment Processors (Israel)
Already have MD files for: Nedarim Plus, Tranzila, CardCom, Grow, PayMe, iCount, EasyCard

### Phase 2: DAFpay Button (Covers ALL DAFs)
Implement Chariot/DAFpay -- single integration covers:
- The Donors Fund
- OJC Fund
- Jewish Communal Fund
- Combined Jewish Philanthropies
- All Jewish Federation DAFs
- 1,141+ more secular DAF providers

### Phase 3: Matbia (Jewish Charity Card)
Direct Matbia API integration for frum community donors who use charity cards.

### Phase 4: Direct DAF Partnerships
Contact The Donors Fund and OJC Fund for direct API access (beyond DAFpay).

### Phase 5: Campaign Platform Sync
If running campaigns on Charidy/CauseMatch/Chesed Fund, sync data via their APIs.

---

## TOTAL COVERAGE

With just 3 integrations (Israeli processor + DAFpay + Matbia), Matat Mordechai covers:
- All Israeli credit cards (Visa, Mastercard, Isracard, AMEX, Diners)
- Bit (Israeli mobile payment)
- Apple Pay, Google Pay
- 1,151+ DAF providers worldwide
- Matbia charity cards
- Installments (tashlumim)
- Recurring donations
- Section 46 donation receipts (via CardCom)

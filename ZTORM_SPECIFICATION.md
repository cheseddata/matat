# ZTorm - Donation & Fundraising Management System
# Complete Specification for Python Rewrite

---

## 1. EXECUTIVE SUMMARY

ZTorm is a comprehensive donation/fundraising management system built in Microsoft Access 2003 with VBA. It manages the full lifecycle of charitable donations for Israeli non-profit organizations (Amutot), including:

- **Donor Management** - Contact details, addresses, phones, classifications
- **Donation Tracking** - Multiple payment methods (credit card, standing orders, cash/checks)
- **Agreement Management** - Grouping donations under fundraising agreements
- **Payment Processing** - Automated credit card billing, bank direct debits
- **Receipt Generation** - Tax-deductible receipts via EZCount API
- **Accounting** - Double-entry credit/debit allocation to accounts
- **Communications** - Letters, emails, mail merge, yahrzeit reminders
- **Reporting** - Extensive financial and operational reports

### Current Architecture
- **Frontend:** Microsoft Access 2003 (.mdb/.mde) with VBA
- **Backend:** Jet (Access MDB) or SQL Server (configurable)
- **External APIs:** EZCount (receipts), Ashrait (credit cards), Bank of Israel (exchange rates)
- **Code Size:** ~35,000 lines of VBA across 250+ modules
- **Data:** 65+ tables, 149 queries, 25 reports, 1 main form with sub-forms

### Key Terminology (Hebrew -> English)
| Hebrew | English | Description |
|--------|---------|-------------|
| Torem/Tormim | Donor/Donors | Contact/person who donates |
| Truma/Trumot | Donation/Donations | A donation commitment |
| Tashlum/Tashlumim | Payment/Payments | Individual payment instance |
| Hescem/Hescemim | Agreement/Agreements | Fundraising agreement/campaign |
| Kabala/Kabalot | Receipt/Receipts | Tax receipt |
| Hork | Standing Order | Bank direct debit |
| Ashrai/Ashp | Credit Card | Credit card payment |
| Gvia | Collection | Batch collection run |
| Mahlaka | Department | Organizational department |
| Zicui/Zicuim | Credit/Credits | Accounting credit entries |
| Heshbon | Account | Ledger account |
| Matbea | Currency | NIS/USD/EUR |
| Schum | Amount | Monetary amount |
| Erech | Value Date | Date for financial processing |
| Mikud | Zip Code | Israeli postal code |
| Ctovet/Ctovot | Address/Addresses | Mailing address |
| Tikshoret | Communication | Correspondence record |
| Michtav | Letter | Letter template |
| Masof | Terminal | Credit card terminal |

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Database Architecture (Split Database)

```
[zuser.mdb] - Front-end (Forms, Reports, VBA Code, Queries)
     |
     v (linked tables)
[ztormdata.mdb] - Main Data (65+ tables)
     |
[bankim.mdb] - Bank/Branch reference data (18 banks, 1,524 branches)
[mikud.mdb]  - Israeli postal codes (617K+ zip codes, 32K streets, 1,482 cities)
[shearim.mdb]- Exchange rates (14K+ daily rates)
```

### 2.2 External Integrations

| Integration | Purpose | Protocol |
|------------|---------|----------|
| **EZCount API** | Electronic receipt generation & tax allocation | REST API via COM DLL |
| **Ashrait/Credit Card Processor** | Credit card authorization & billing | COM DLL (ZCNetLib) |
| **Bank of Israel** | USD exchange rate updates | HTTP API |
| **SMTP (Gmail)** | Email sending for receipts and letters | CDO/SMTP |
| **Microsoft Word** | Mail merge for letters and receipts | COM Automation |
| **SumatraPDF** | PDF printing | Command-line |
| **SignPdf.dll** | Digital PDF signing | .NET COM |

### 2.3 Security Model
- Workgroup security file (ztormw.mdw) with user authentication
- RC4 encrypted passwords for local security mode
- Permission-based access to forms and operations
- Application-level locks for concurrent access control (receipt printing, billing)
- Credit card number encryption (last 4 digits stored, full number encrypted)

---

## 3. DATA MODEL

### 3.1 Core Entity Hierarchy

```
Tormim (Donors) 1--* Trumot (Donations) 1--* Tashlumim (Payments)
     |                    |                        |
     |                    |--- Hork (Standing Orders, 1:1)
     |                    |--- CreditP (Recurring CC, 1:1)
     |                    |--- CreditCards (CC Charges, 1:*)
     |                    |--- TrumotEruim (Events/Audit, 1:*)
     |                    |--- Zacaim (Account Allocations, 1:*)
     |                    |
     |                    *--1 Hescemim (Agreements)
     |                         |
     |--- Ctovot (Addresses, 1:*)    
     |--- Tel (Phones, 1:*)
     |--- Children (1:*)
     |--- Hearot (Notes, 1:*)
     |--- Sivug (Classifications, 1:*)
     |--- ShemotAzcara (Memorial Names, 1:*)
     |--- ShemotTfila (Prayer Names, 1:*)
     |--- Yamim (Special Dates, 1:*)
     |--- Tikshoret (Communications, 1:*)
     |--- Kabalot (Receipts, 1:*)
```

### 3.2 Table Definitions

#### Core Master Tables

**Tormim (Donors)** - 1,842 records
| Field | Type | Description |
|-------|------|-------------|
| num_torem | AutoNumber (PK) | Unique donor number |
| last_name | Text | Last/family name |
| first_name | Text | First name |
| toar | Text | Title (Mr., Rabbi, etc.) |
| t_z | Number | Israeli ID (Teudat Zehut) |
| email | Text | Email address |
| min | Text | Gender (m/f/plural/unknown) |
| birth_date | Date | Date of birth |
| ben_zug | Text | Spouse name |
| t_z_ben_zug | Number | Spouse ID |
| send_doar | Boolean | Send mail flag |
| send_kabalot_once | Boolean | Annual receipt only |
| simun | Boolean | Bookmark/flag |
| date_klita | Date | Registration date |
| date_idcun | Date | Last update |
| safa | Text | Language preference |
| name_kabala | Text | Name for receipts |
| tz_kabala | Number | ID for receipts |
| shimur_freq | Number | Follow-up frequency |
| clali_1..5 | Text | Classification fields |

**Trumot (Donations)** - 3,652 records
| Field | Type | Description |
|-------|------|-------------|
| num_truma | AutoNumber (PK) | Unique donation number |
| num_torem | Number (FK) | Donor reference |
| num_hescem | Number (FK) | Agreement reference |
| ofen | Text | Method: credit/hork/cash/hafkada |
| status | Text | pail/butal/siem/new |
| shulam_d | Currency | Paid amount (USD) |
| shulam_s | Currency | Paid amount (NIS) |
| tzafui_d | Currency | Expected (USD) |
| tzafui_s | Currency | Expected (NIS) |
| date_klita | Date | Entry date |
| first_tashlum | Date | First payment date |
| last_tashlum | Date | Last payment date |
| date_bitul | Date | Cancellation date |
| num_mahlaka | Number (FK) | Department |
| matbea | Text | Currency (nis/usd) |
| send_kabala | Boolean | Send receipt flag |
| user | Text | Entered by user |

**Tashlumim (Payments)** - 18,698 records
| Field | Type | Description |
|-------|------|-------------|
| num_tashlum | AutoNumber (PK) | Payment number |
| num_truma | Number (FK) | Donation reference |
| erech | Date | Value date |
| date | Date | Payment date |
| ofen | Text | Method |
| status | Text | ok/hazar/ready/shulam |
| schum | Currency | Amount (original currency) |
| matbea | Text | Currency |
| schum_nis | Currency | Amount in NIS |
| shovi | Currency | USD equivalent |
| num_kabala | Number (FK) | Receipt number |
| num_gvia | Number (FK) | Collection batch |
| bank/snif/heshbon | Number | Check bank details |
| asmachta | Text | Reference number |
| num_msvdetail | Number (FK) | Standing order detail |

**Hescemim (Agreements)** - 1,891 records
| Field | Type | Description |
|-------|------|-------------|
| num_hescem | AutoNumber (PK) | Agreement number |
| num_torem | Number (FK) | Contact donor |
| sug | Text | Type (clali/matbeot/nziv) |
| tat_sug | Text | Sub-type |
| sach_ltashlum | Currency | Total to pay |
| SumOfShulam | Currency | Sum paid |
| SumOfTzafui | Currency | Sum expected |
| matbea | Text | Currency |
| num_mahlaka | Number (FK) | Department |
| mvutal | Boolean | Cancelled |

**Kabalot (Receipts)** - Tax receipts
| Field | Type | Description |
|-------|------|-------------|
| num_kabala | AutoNumber (PK) | Internal receipt ID |
| mispar_kabala | Number | Sequential receipt number |
| sug | Text | Type (credit/hork/cash) |
| date | Date | Receipt date |
| sum_total | Currency | Total amount |
| name | Text | Recipient name |
| tz | Number | Recipient ID |
| num_torem | Number (FK) | Donor |
| num_truma | Number (FK) | Donation |
| num_mahlaka | Number (FK) | Department |
| canceled | Boolean | Cancelled flag |
| num_cancel | Number (FK) | Cancellation reference |
| doc_num | Text | EZCount document number |
| tax_allocation_num | Text | Tax authority number |
| api | Text | API used (ezc) |
| url | Text | Receipt URL |

#### Credit Card Tables

**Hork (Standing Orders)**
| Field | Type | Description |
|-------|------|-------------|
| num_truma | Number (FK/PK) | Donation (1:1) |
| bank/snif/heshbon | Number | Bank account details |
| schum | Currency | Monthly amount |
| peimot | Number | Number of payments (null=unlimited) |
| buza | Number | Current payment count |
| yom | Number | Day of month to collect |
| tkufa | Number | Collection period (months) |
| num_mosad | Number (FK) | Collection institution |
| asmachta | Text | Bank reference |

**CreditP (Recurring Credit Card)**
| Field | Type | Description |
|-------|------|-------------|
| num_truma | Number (FK/PK) | Donation (1:1) |
| mispar_cartis | Text | Card number (last 4 digits) |
| tokef | Number | Expiry (YYMM) |
| schum | Currency | Amount per charge |
| peimot | Number | Number of charges |
| buza | Number | Current charge count |
| yom | Number | Day of month |
| code_hevra | Number | Card company code |
| solek | Number | Clearing house |

**CreditCards (One-Time & Installment CC Charges)**
**Note:** This table stores one-time and installment credit card charges (NOT just "individual charges"). These are processed alongside CreditP (recurring) during the billing run.
| Field | Type | Description |
|-------|------|-------------|
| num_truma | Number (FK) | Donation |
| date_bitzua | Date | Execution date |
| schum | Currency | Amount |
| mispar_cartis | Text | Card number |
| tokef | Number | Expiry |
| sug_iska | Text | Transaction type |
| code_hevra | Number | Company code |
| num_gvia | Number (FK) | Collection batch |
| num_ishur | Number | Authorization number |
| ofen_gvia | Text | Collection method (online/offline) |

#### Supporting Tables

**Gvia (Collection Batches)** - 2,330 records
| Field | Type | Description |
|-------|------|-------------|
| num_gvia | AutoNumber (PK) | Batch number |
| time | DateTime | Timestamp |
| sug | Text | Type (ash=credit, hork=standing order) |
| date_hiuv | Date | Charge date |
| shaar | Currency | Exchange rate |
| hazarot_done | Boolean | Returns processed |

**Zacaim (Account Allocations)** - 3,652 records
Maps donations to accounting accounts with percentage splits.

**Heshbonot (Accounts)** - 184 records
Ledger accounts for double-entry accounting.

**Tnuot (Transactions)** - 7,361 records
Accounting journal entries.

**Settings** - 38 key/value configuration pairs
Including: email settings, default values, API keys, paths.

### 3.3 Lookup/Reference Tables

| Table | Records | Description |
|-------|---------|-------------|
| Bankim | 18 | Israeli banks |
| Snifim | 1,524 | Bank branches |
| MK_Cities | 1,482 | Israeli cities |
| MK_Streets | 32,330 | Streets per city |
| MK_Zip_Code | 617,932 | Postal codes |
| Shearim | 14,106 | Daily exchange rates |
| Areas | 81 | Geographic areas |
| AreaStreets | 375 | Streets per area |
| Kidomot | 324 | Phone area codes |
| AshMasofim | 1 | CC terminal definitions |
| Mosadot | 2 | Collection institutions |
| Mahlakot | 1 | Departments |
| KabalotDef | 5 | Receipt number ranges |
| UserCodes | 38 | Classification codes |
| Firstnames | 425 | Gender lookup by first name |

---

## 4. FUNCTIONAL MODULES

### 4.1 Main Menu (Switchboard)

The application uses a data-driven switchboard menu system with:
- Up to 8 configurable buttons per menu page
- Permission-based button visibility
- Sub-menu navigation
- Commands: Open Form (Add/Browse), Open Report, Run Macro, Run Code, Exit

**Screenshot reference:** `screenshots/02_switchboard.png`

### 4.2 Data Entry (Klita) - 1,404 lines of code

The main data entry form combines donor creation/selection with donation setup in a single workflow.

**Workflow:**
1. Search for existing donor (by name, phone, ID, card number, bank account)
2. If new: enter donor details (name, title, gender, ID, address, phone, email)
3. Select donation method: Credit Card, Standing Order (Hork), Credit Installments (Ashp), Cash, None
4. Enter financial details based on method:
   - **Credit:** Card number, expiry, amount, currency, installments
   - **Hork:** Bank, branch, account, amount, collection day
   - **Cash:** Amount, currency
5. Select/create agreement (hescem) with type and sub-type
6. Set start date, payment limit, collection frequency
7. Save atomically (all-or-nothing transaction)

**Key Validations:**
- Israeli ID (TZ) check digit validation
- Credit card number validation via Ashrait
- Bank account checksum validation (per-bank algorithm)
- Postal code lookup from city/street
- Duplicate donor detection (name, phone, ID, card, bank account)
- Gender detection from Hebrew first name
- Max installments limit (configurable, default 72)

**Screenshot reference:** N/A (form requires initialization context)

### 4.3 Donor Management (Tormim) - 531 lines

Tabbed interface for viewing and managing a single donor's complete record.

**Tabs:**
1. **Grid** - Donor list with incremental search by name/number
2. **Donations (Trumot)** - All donations with type-specific detail sub-forms
3. **Payments (Tashlumim)** - All payments with filtering by donation
4. **Agreements (Hescemim)** - Linked agreements
5. **Communications (Tikshoret)** - Correspondence history
6. **Details (Pratim)** - Extended donor information

**Features:**
- Type-ahead incremental search (using table Seek for Jet, TOP 1 for SQL Server)
- Hebrew character handling (sofiot/final letters)
- Browsing history tracking per user
- Bookmark (simun) toggle
- Resizable sub-forms

**Screenshot reference:** `screenshots/tormim.png`, `screenshots/tormim_search.png`, `screenshots/tormim_grid.png`

### 4.4 Donation Management (Trumot)

**Create New Donation:**
- **Credit Card:** Online (auto-charge) or Manual (yadani), installments, currency
- **Standing Order (Hork):** Bank details, institution, amount, collection day, payment limit
- **Cash/Check:** Amount, date, check details

**Edit Donation:**
- Status transitions: new -> pail (active) -> siem (completed) -> butal (cancelled)
- Modify payment count, amount, currency, collection day
- Cancel with reason (triggers cancellation receipt for credit)
- Undo cancellation (recreates payment schedule)

**Key Business Rules:**
- Credit card validation via Ashrait before saving
- Activation generates future payment schedule (12 months ahead)
- Completion deletes unexecuted future payments
- Cancellation creates negative receipt and logs event
- Encrypted credit card storage (only last 4 visible)

### 4.5 Payment Management (Tashlumim) - 424 lines

**Operations:**
- Add cash/check payments
- Edit payment details (date, amount, currency, status)
- Delete payments (with recalculation)
- Move payment between donations
- Generate receipt for payment
- Multi-select for batch operations

**Payment Statuses:** ok, hazar (returned), ready (future), shulam (paid)

**Screenshot reference:** `screenshots/tashlumim.png`

### 4.6 Credit Card Billing (AshGvia) - 275 lines

Multi-step automated credit card billing process. **Processes TWO types of charges:**
- **CreditP** records: recurring monthly charges (הוראת קבע)
- **CreditCards** records: one-time and installment charges (עסקאות חד-פעמיות ותשלומים)

1. **Prepare** - Identify eligible charges from BOTH CreditP and CreditCards tables, apply exchange rate
2. **Get Authorizations** - Submit all charges to credit card processor via Ashrait/Shva
3. **Transmit** - Send approved charges to clearing house
4. **Update** - Create payment records, update donation summaries
5. **Cleanup** - Finalize batch

**Features:**
- Multiple merchant terminals (masofim) support
- USD/NIS conversion at current exchange rate
- Exclusive form lock prevents concurrent billing
- Retry for failed/unauthorized transactions

### 4.7 Standing Order Processing (Hork) - 498 lines

**Collection (Gvia) Cycle:**
1. Generate bank file from eligible Hork records
2. Send to bank/institution
3. Process response file (MsvDetail records)
4. Handle returns (hazarot) with configurable auto-cancellation

**Bank Account Validation:**
- Per-bank checksum algorithm (8 bank groups)
- Branch lookup with full Israeli branch database

**Returns Handling:**
- Configurable return reason codes with auto-cancel rules
- Consecutive returns trigger automatic donation cancellation
- Return reversal (undo hazara) supported

### 4.8 Receipt Generation (Kabalot) - 312 + 746 lines

**Two Systems:**
1. **Modern (EZCount API):** Electronic receipts via cloud service
2. **Legacy (Word merge):** Paper receipts via mail merge

**EZCount Receipt Flow:**
1. Identify payments needing receipts (by collection batch)
2. Validate donor TZ (required for tax receipts)
3. Create receipt records with sequential numbering per department
4. Send to EZCount API for document generation
5. Retrieve tax allocation numbers from tax authority
6. Download/email/print receipt PDFs

**Receipt Types:** Credit card, Standing order, Cash, Check, Deposit

**Operations:**
- Issue receipt
- Cancel receipt (creates negative mirror receipt)
- Fix/correct receipt (new receipt linked to original)
- Email receipt to donor
- Print via SumatraPDF

**Screenshot reference:** `screenshots/reportkabalot.png`

### 4.9 Accounting Module (Zicuim)

**Double-entry accounting:**
- Payments allocated to accounts via Zacaim rules (percentage-based)
- Commission calculation per contract type (Hozim/Hozim2)
- Journal entries (Tnuot) with period closings (TnuotSgira)
- Tax credit reports for Israeli tax authority (Section 46)

### 4.10 Communications & Letters

**Letter System:**
- Word mail merge templates
- Category-based templates (hescem, truma, kabala, yahrzeit)
- Batch preparation with address validation
- Print/email/label generation

**Yahrzeit (Memorial) Letters:**
- Hebrew calendar date handling
- Auto-scheduled based on anniversary dates
- Batch processing with tracking

**Email System:**
- SMTP via Gmail
- Receipt PDF attachment
- Communication logging to Tikshoret table

### 4.11 Reporting

**Report Categories:**
- Donation reports (by type, status, date range, beneficiary)
- Payment reports (per donor, per period)
- Receipt reports (printed/unprinted, by department)
- Standing order reports
- Credit card reports (billing summaries, returns)
- Accounting reports (account statements, tax credits)
- Donor reports (labels, envelopes, address lists)

**Report Features:**
- Dynamic query construction with multiple filters
- Excel export
- Custom saved queries
- Two-pass filtering (donation criteria + donor criteria)

**Screenshot reference:** `screenshots/reporttashlumim.png`

### 4.12 System Administration

**Setup:**
- Database backend selection (Jet/SQL Server)
- Table relinking
- Data compaction
- Version checking

**Configuration (Settings table):**
| Key | Sample Value | Purpose |
|-----|-------------|---------|
| KlitaDefault.OfenTashlum | credit | Default payment method |
| KlitaDefault.matbea | nis | Default currency |
| KlitaDefault.peimot | 12 | Default installments |
| Klita.MaxPeimot | 72 | Max installments |
| KabalotMinAmtToSend | 50 | Min receipt amount |
| hiuvdays | 1;10;20 | Collection days of month |
| mail.SmtpServerAddress | smtp.gmail.com | Email server |
| EZCountAPIKey | (key) | EZCount API key |
| KabalotApi | ezc | Receipt API selection |

---

## 5. DATA FLOWS

### 5.1 Donation Entry Flow
```
User enters data in Klita form
    -> Validate donor (TZ, duplicates)
    -> Create/select Tormim record
    -> Create Ctovot (address), Tel (phone) records
    -> Create Hescemim (agreement) if new
    -> Create Trumot (donation) record
    -> Create TrumaHescem junction
    -> Create payment method record (Hork/CreditP/CreditCards)
    -> Create Zacaim (account allocation) rules
    -> If active: generate Tashlumim (payment schedule)
```

### 5.2 Credit Card Collection Flow
**Important:** The system has TWO credit card donation modes:
1. **CreditP table** = Recurring/permanent monthly charges (הוראת קבע באשראי)
2. **CreditCards table** = One-time charges AND installment charges (עסקאות חד-פעמיות ותשלומים)

Both tables are processed during the billing run (PrepGvia).
```
AshGvia form initiated
    -> Create Gvia (batch) record
    -> Find eligible CreditP records (recurring charges due this month)
    -> Find eligible CreditCards records (one-time/installment charges pending)
    -> Create AshTempOut staging records from BOTH tables
    -> Submit all to credit card processor (Ashrait/Shva)
    -> Receive authorizations
    -> Create AshDetail records for approved transactions
    -> Transmit to clearing house
    -> Create Tashlumim (payment) records
    -> Generate Zicuim (accounting credits)
    -> Update Ash batch summary
```

### 5.3 Standing Order Collection Flow
```
MsvPrep initiated
    -> Create Gvia (batch) record
    -> Generate bank file from Hork records
    -> Send to bank
    -> Import response (MsvDetail records)
    -> Create Tashlumim for successful debits
    -> Process returns (Hazarot)
    -> Generate Zicuim (accounting credits)
```

### 5.4 Receipt Generation Flow
```
KabalotPrepare form
    -> Query eligible payments (by collection batch)
    -> Validate donor TZ
    -> Group payments by donor/year/department
    -> Create Kabalot records with sequential numbering
    -> Send to EZCount API
    -> Get tax allocation numbers
    -> Email/print receipt PDFs
    -> Update Tashlumim with receipt references
    -> Create Tikshoret communication records
```

---

## 6. SCREENSHOTS

The following screenshots were captured from the running Access application:

| File | Description |
|------|-------------|
| `screenshots/02_switchboard.png` | Main menu/switchboard with navigation buttons |
| `screenshots/tormim.png` | Donor management form (tabbed interface) |
| `screenshots/tormim_search.png` | Donor search with results grid |
| `screenshots/tormim_grid.png` | Donor grid view with data columns |
| `screenshots/tormim_select_filter.png` | Advanced donor filter dialog |
| `screenshots/trumot.png` | Donations view (with VBA editor visible) |
| `screenshots/hescemim.png` | Agreements form |
| `screenshots/tashlumim.png` | Payments form with tabs |
| `screenshots/hazarot.png` | Bank returns processing form |
| `screenshots/setup.png` | Database configuration/settings |
| `screenshots/shemotazcara.png` | Memorial names entry |
| `screenshots/lettersedit.png` | Letter template editor |
| `screenshots/reportkabalot.png` | Receipt reports filter |
| `screenshots/reporttashlumim.png` | Payment reports filter |

---

## 7. PYTHON REWRITE RECOMMENDATIONS

### 7.1 Technology Stack Suggestions

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Backend** | Python + FastAPI/Django | Modern web framework |
| **Database** | PostgreSQL | Robust, supports Hebrew, JSON fields |
| **ORM** | SQLAlchemy / Django ORM | Type-safe database access |
| **Frontend** | React / Vue.js | Rich interactive UI |
| **PDF Generation** | ReportLab / WeasyPrint | Receipt generation |
| **Email** | Python smtplib | SMTP integration |
| **Credit Card** | Payment gateway API | Replace Ashrait COM |
| **Exchange Rates** | Bank of Israel API | Already used |
| **Hebrew Calendar** | pyluach / hdate | Hebrew date calculations |

### 7.2 Architecture Recommendations

1. **REST API Backend** - Replace Access forms with API endpoints
2. **Single-Page Application** - Replace Access forms with web UI
3. **Database Migration** - Map Access tables to PostgreSQL with proper types
4. **Authentication** - Replace workgroup security with JWT/session auth
5. **Hebrew Support** - Ensure UTF-8 throughout, RTL UI support
6. **Multi-currency** - Use Python Decimal type, store rates
7. **Audit Trail** - Database triggers or middleware for change tracking
8. **Background Jobs** - Celery for batch processing (billing, receipts)
9. **PDF/Receipt** - Direct API integration with EZCount
10. **Postal Codes** - Israeli government API instead of local DB

### 7.3 Migration Strategy

**Phase 1: Foundation**
- Set up PostgreSQL database with migrated schema
- Create data migration scripts from Access MDB
- Implement user authentication and authorization
- Build core API endpoints

**Phase 2: Core Donor Management**
- Donor CRUD with search
- Address, phone, classification management
- Israeli postal code integration

**Phase 3: Donations & Payments**
- Donation lifecycle (create, activate, cancel, complete)
- Payment recording and management
- Agreement management

**Phase 4: Financial Processing**
- Credit card integration
- Standing order file generation/processing
- Exchange rate handling

**Phase 5: Receipts & Reporting**
- EZCount API integration for receipts
- Report generation (PDF export)
- Dashboard and analytics

**Phase 6: Communications**
- Email integration
- Letter/template management
- Yahrzeit tracking

---

## 8. EXPORTED SOURCE FILES

All VBA source code, queries, table definitions, and analysis files have been exported to:

```
F:\outlook_over_a_yer\vba_export\
  _AllQueries.sql          - All 149 SQL queries
  _Tables.txt              - Complete table definitions with field types
  _Relationships.txt       - Database relationships
  _analysis_modules.txt    - Detailed analysis of 30 VBA modules
  _analysis_forms.txt      - Detailed analysis of 30 form modules
  _analysis_data.txt       - Complete data model analysis
  Module_*.bas             - All VBA module source code (250+ files)
  Form_*.txt               - Exported Access form definitions
  Report_*.txt             - Exported Access report definitions
  Macro_*.txt              - Exported macro definitions

F:\outlook_over_a_yer\screenshots\
  *.png                    - Application screenshots
```

---

## APPENDIX A: COMPLETE TABLE LIST (ztormdata.mdb)

| # | Table | Records | Purpose |
|---|-------|---------|---------|
| 1 | Tormim | 1,842 | Donors |
| 2 | Trumot | 3,652 | Donations |
| 3 | Tashlumim | 18,698 | Payments |
| 4 | Hescemim | 1,891 | Agreements |
| 5 | Heshbonot | 184 | Accounts |
| 6 | Kabalot | - | Receipts |
| 7 | KabalotChecks | 1,465 | Receipt check details |
| 8 | KabalotDef | 5 | Receipt number ranges |
| 9 | KabalotLog | 354 | Receipt processing log |
| 10 | CreditCards | 2,141 | CC charges |
| 11 | CreditP | 1,011 | Recurring CC setup |
| 12 | Hork | 0 | Standing orders |
| 13 | Ash | 2,311 | CC batch summaries |
| 14 | AshDetail | - | CC transaction details |
| 15 | AshTran | 4,063 | CC transmissions |
| 16 | AshTempOut | 0 | CC staging |
| 17 | AshMasofim | 1 | CC terminals |
| 18 | AshLog | 0 | CC audit log |
| 19 | AmalotAshrai | 4 | CC fee rates |
| 20 | Gvia | 2,330 | Collection batches |
| 21 | MsvDetail | 0 | SO collection details |
| 22 | MsvMasofim | 1 | SO terminals |
| 23 | Mosadot | 2 | Collection institutions |
| 24 | Ctovot | 1,291 | Addresses |
| 25 | Tel | 1,214 | Phones |
| 26 | Children | 0 | Donor children |
| 27 | Hearot | 5 | Notes |
| 28 | Sivug | 2 | Classifications |
| 29 | History | 485 | View history |
| 30 | Tikshoret | 3,326 | Communications |
| 31 | Michtavim | 1 | Letter templates |
| 32 | Michtavim_Base | 1 | Base letter templates |
| 33 | PrintHist | 30 | Print history |
| 34 | ShemotAzcara | 0 | Memorial names |
| 35 | ShemotAzcaraLink | 0 | Memorial links |
| 36 | ShemotTfila | 86 | Prayer names |
| 37 | Yamim | 0 | Special dates |
| 38 | Zacaim | 3,652 | Account allocations |
| 39 | Zicuim | - | Accounting credits |
| 40 | Tnuot | 7,361 | Journal transactions |
| 41 | TnuotSgira | 211 | Period closings |
| 42 | Hozim | 1 | Contract types |
| 43 | Hozim2 | 0 | Contract details |
| 44 | TrumotEruim | 23,794 | Donation events |
| 45 | ToremEruim | 2 | Donor events |
| 46 | TrumaHescem | - | Donation-Agreement links |
| 47 | Mahlakot | 1 | Departments |
| 48 | Kupot | 0 | Collection funds |
| 49 | Areas | 81 | Geographic areas |
| 50 | AreaStreets | 375 | Area streets |
| 51 | Kidomot | 324 | Phone prefixes |
| 52 | Tearim | 0 | Titles |
| 53 | Counter | 1,000 | Sequence counter |
| 54 | DataTables | 32 | Table registry |
| 55 | ErrorLog | 578 | Error log |
| 56 | FixSumsLog | 0 | Sum correction log |
| 57 | GmachTransfers | 879 | Gmach transfers |
| 58 | HescemimParnas | 0 | Agreement sponsors |
| 59 | PostponeHorkPmts | 0 | Postponed payments |
| 60 | SCLHiuvim | 0 | School charges |
| 61 | SCLTaarifim | 0 | School tariffs |
| 62 | Settings | 38 | System settings |
| 63 | Temp | 0 | Temporary data |
| 64 | UserCodes | 38 | User-defined codes |
| 65 | TashlumimRicuz | 0 | Payment summaries |
| 66 | firstnames | 425 | Gender lookup |

## APPENDIX B: QUERY COUNT BY CATEGORY

| Category | Count | Description |
|----------|-------|-------------|
| Donation views (QTrumot*) | 15 | Donation queries for forms/reports |
| Receipt queries (Q_Kabala*) | 12 | Receipt generation and display |
| Payment queries (QTashlumim*) | 8 | Payment views and reports |
| Credit card (QAsh*) | 10 | CC processing queries |
| Standing order (frm/VMsv*) | 5 | SO processing queries |
| Donor views (QTorm*) | 6 | Donor information queries |
| Report queries (rpt*) | 8 | Report-specific queries |
| Form support (frm*) | 20 | Form datasource queries |
| Accounting (Zicuim*) | 8 | Accounting queries |
| Mail merge (QMizug*) | 6 | Letter merge queries |
| Tax credits (s_Zicuim*) | 8 | Tax credit reports |
| Data maintenance | 10 | Utility/maintenance queries |
| Address (Ctovot*) | 6 | Address-related queries |
| Gmach (loan fund) | 5 | Charitable loan queries |
| Miscellaneous | 22 | Other support queries |
| **Total** | **149** | |

---

*Generated on 2026-04-13 from ZTorm Access application analysis*
*Source: C:\ztorm\ (zuser.mdb, ztormdata.mdb, supporting databases)*
*Code: ~35,000 lines of VBA across 250+ modules*

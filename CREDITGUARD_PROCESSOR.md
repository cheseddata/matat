# CreditGuard (Hyp) Payment Processor Integration

## Overview
CreditGuard (now part of Hyp) is a leading Israeli payment gateway.
Processes the majority of online credit card transactions in Israel.
Website: https://www.creditguard.co.il/en/
Parent: https://hyp.co.il/

## API Details
- **Base URL:** `https://meshulam.creditguard.co.il/xpo/Relay`
- **Test URL:** `https://meshulam-test.creditguard.co.il/xpo/Relay`
- **Protocol:** XML over HTTPS (POST)
- **Auth:** Terminal number + username + password in XML request
- **API Guide PDF:** https://www.creditguard.co.il/wp-content/uploads/2022/11/20221024-3_2_45-EMV-XML-API.pdf

## Integration Type
XML API. Supports both redirect (iframe) and server-to-server.

## Request Format
POST to relay URL with `user` and `int_in` parameters:
```
POST /xpo/Relay
Content-Type: application/x-www-form-urlencoded

user=terminal_user&int_in=<ashrait>...</ashrait>
```

## XML Request Structure (doDeal)
```xml
<ashrait>
  <request>
    <version>2000</version>
    <language>HE</language>
    <command>doDeal</command>
    <doDeal>
      <terminalNumber>TERMINAL</terminalNumber>
      <cardNo>4580000000000000</cardNo>
      <cardExpiration>1227</cardExpiration>
      <cvv>123</cvv>
      <total>1800</total>
      <transactionType>Debit</transactionType>
      <creditType>RegularCredit</creditType>
      <currency>ILS</currency>
      <transactionCode>Phone</transactionCode>
      <validation>TxnSetup</validation>
      <numberOfPayments>1</numberOfPayments>
      <firstPayment>1800</firstPayment>
      <periodicalPayment>0</periodicalPayment>
      <user>username</user>
      <mid>TERMINAL</mid>
      <uniqueid></uniqueid>
      <id>DONOR_TZ</id>
    </doDeal>
  </request>
</ashrait>
```

## Transaction Types
- `Debit` = Regular charge (חיוב)
- `Credit` = Refund/credit (זיכוי)
- `Authorize` = Authorization only

## Credit Types
- `RegularCredit` = Regular (רגיל)
- `Payments` = Installments (תשלומים)
- `IsraCredit` = Israeli credit (30+)
- `AdditionalCredit` = Additional credit
- `ImmediateCharge` = Immediate debit

## XML Response Structure
```xml
<ashrait>
  <response>
    <command>doDeal</command>
    <doDeal>
      <cgGatewayResponseXml>
        <ashrait>
          <response>
            <result>000</result>
            <message>Approved</message>
            <userMessage>Transaction Approved</userMessage>
            <tranId>12345678</tranId>
            <authNumber>0963058</authNumber>
            <cardToken>TOKEN_FOR_RECURRING</cardToken>
            <cardMask>****0000</cardMask>
            <cardBrand>VISA</cardBrand>
            <cardExpiration>1227</cardExpiration>
            <slaveTerminalNumber>TERMINAL</slaveTerminalNumber>
            <slaveTerminalSequence>001</slaveTerminalSequence>
          </response>
        </ashrait>
      </cgGatewayResponseXml>
    </doDeal>
  </response>
</ashrait>
```

## Result Codes
- `000` = Approved
- `001` = Card blocked
- `002` = Stolen card
- `003` = Contact company
- `004` = Declined
- `006` = CVV wrong
- `012` = Invalid transaction
- `036` = Card expired

## Token / Recurring
- Response includes `cardToken` on successful charge
- Use `cardToken` in subsequent charges instead of full card number
- In XML: `<cardToken>TOKEN</cardToken>` replaces `<cardNo>`
- Token is permanent and PCI compliant
- No need to store card numbers!

## Refund
Same XML format with `transactionType` = `Credit`:
```xml
<doDeal>
  <terminalNumber>TERMINAL</terminalNumber>
  <transactionType>Credit</transactionType>
  <total>1800</total>
  <authNumber>ORIGINAL_AUTH</authNumber>
</doDeal>
```

## Configuration Needed
- Terminal Number (מספר מסוף)
- Username
- Password
- MID (Merchant ID)
- Test/Production mode toggle

## File Location
Create as: `app/services/payment/creditguard_processor.py`
Must extend `BasePaymentProcessor` from `app/services/payment/base.py`
Register in `app/services/payment/router.py`

## Supported Features
- ✅ One-time charges
- ✅ Installments (up to 36)
- ✅ Tokenization (cardToken for recurring)
- ✅ Refunds
- ✅ ILS, USD, EUR, GBP
- ✅ Authorization only (pre-auth)
- ✅ Card validation
- ✅ 3D Secure support

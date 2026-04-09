# Charidy Integration - Implementation Guide

## Overview
Charidy (charidy.com) is the leading Jewish crowdfunding platform. Has a public API for accessing campaign data and building custom integrations. Integrates with DAF payment methods (OJC, Donors Fund, Matbia, Pledger).

## API Access
- Public API documented at: https://articles.charidy.com/hc/en-us/articles/4561905476116-Access-Charidy-s-Public-API
- Dashboard (dev): https://dashboard.develop.charidy.com/
- API features: Access campaign data, build custom integrations

## Third-Party Integrations
- Salesforce
- Tagboard
- Mailchimp

## DAF Payment Methods on Charidy Campaigns
- OJC Fund
- The Donors Fund
- Matbia
- Pledger

## Integration Path for Matat Mordechai

### If running campaigns on Charidy:
- Charidy handles the donation page, payment processing, and DAF integrations
- Use Charidy API to pull campaign/donation data into your system
- Sync with Matat Mordechai database for commission tracking

### If building your own donation page:
- Charidy is less relevant (it is a campaign platform, not a payment gateway)
- Use the individual payment processors (Nedarim Plus, CardCom, etc.) directly
- Use Chariot/DAFpay for DAF integration

## Contact
- Support: support@charidy.com
- Or your Charidy Campaign Manager

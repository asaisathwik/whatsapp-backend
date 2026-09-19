# Automated Testing Guide

## Test Suite Overview

All tests are located under `/tests` and run via Pytest with isolated in-memory testing sessions and mock provider engines.

## Executing Automated Tests

```bash
cd backend
venv\Scripts\pytest ..\tests -v
```

## Verified Test Suites

1. `test_health_and_ready.py`:
   - Validates `/health` liveness probe.
   - Validates `/ready` dependency probe (Database + Redis connectivity).

2. `test_multi_tenancy.py`:
   - Organization A cannot read Organization B contacts.
   - Organization A cannot access Organization B WhatsApp instances.
   - Organization A cannot cancel or modify Organization B campaigns.
   - Organization A cannot read Organization B conversation messages.

3. `test_auth.py`:
   - Registration, automatic Organization creation with OWNER role.
   - Password hashing with standard bcrypt.
   - JWT generation & verification on `/auth/me`.
   - Rejection of invalid/expired tokens and unauthorized requests.

4. `test_phone_normalizer.py`:
   - Verification of `+91 9XXXXXXXXX`, `0919XXXXXXXXX`, `919XXXXXXXXX`, and 10-digit formats with configurable default country code.

5. `test_contact_import.py`:
   - CSV & Excel file parsing, validation, duplicate detection, and import reporting.

6. `test_templates.py`:
   - Dynamic variable extraction (`{{name}}`, `{{plan}}`, `{{city}}`) and runtime rendering.

7. `test_campaign_queue.py`:
   - Campaign creation, rate limiting, background worker batch execution, message status updates (`QUEUED` -> `SENT`), and idempotency keys.

8. `test_webhooks_idempotency.py`:
   - Inbound message persistence from Evolution API webhooks and duplicate webhook rejection.

9. `test_ai_and_human_takeover.py`:
   - AI automatic responses and tool calling.
   - Escalation trigger and Human Takeover (`HUMAN_ACTIVE`).
   - Hard lock: verification that AI NEVER auto-responds during `HUMAN_ACTIVE`.
   - Human agent reply dispatch.
   - Release to AI (`AI_RESUMED`) resuming autonomous responses.

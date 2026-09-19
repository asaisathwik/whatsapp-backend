# API Reference Documentation

Base URL: `/api/v1`

## Authentication & Multi-Tenancy
- `POST /api/v1/auth/register` - Create user and new organization.
- `POST /api/v1/auth/login` - Obtain JWT access token.
- `GET /api/v1/auth/me` - Retrieve authenticated user profile and organization details.

## Organizations & Team
- `GET /api/v1/organizations/current` - View organization settings.
- `PUT /api/v1/organizations/current` - Update default country and configuration.
- `GET /api/v1/organizations/members` - List organization members and roles.

## WhatsApp Instances
- `GET /api/v1/whatsapp/instances` - List connected numbers.
- `POST /api/v1/whatsapp/instances` - Create and register instance.
- `GET /api/v1/whatsapp/instances/{id}/qr` - Get real-time base64 QR code or pairing code.
- `POST /api/v1/whatsapp/instances/{id}/connect` - Trigger session connection.
- `POST /api/v1/whatsapp/instances/{id}/disconnect` - Logout and disconnect number.

## Contacts & Tags
- `GET /api/v1/contacts` - Search, filter, and paginate contacts.
- `POST /api/v1/contacts` - Create contact with international phone normalization.
- `DELETE /api/v1/contacts/{id}` - Delete contact.
- `GET /api/v1/contacts/tags` - List tags.
- `POST /api/v1/contacts/tags` - Create tag.
- `POST /api/v1/contacts/import/preview` - Upload CSV/Excel and preview rows with duplicate analysis.
- `POST /api/v1/contacts/import/confirm` - Execute batch import with error report.

## Templates
- `GET /api/v1/templates` - List templates.
- `POST /api/v1/templates` - Create template with auto variable extraction (`{{name}}`, `{{phone}}`, `{{city}}`).
- `DELETE /api/v1/templates/{id}` - Delete template.

## Campaigns & Dispatch
- `GET /api/v1/campaigns` - List campaigns and delivery metrics.
- `POST /api/v1/campaigns` - Create broadcast campaign.
- `POST /api/v1/campaigns/preview` - Preview audience size, duration, and sample rendered messages.
- `POST /api/v1/campaigns/{id}/send-now` - Dispatch campaign to background worker queue.
- `POST /api/v1/campaigns/{id}/pause` - Pause sending.
- `POST /api/v1/campaigns/{id}/resume` - Resume sending.
- `POST /api/v1/campaigns/{id}/cancel` - Cancel sending.

## Live Conversations & Inbox
- `GET /api/v1/conversations` - List conversations filtered by AI mode.
- `GET /api/v1/conversations/{id}/messages` - Message history.
- `POST /api/v1/conversations/{id}/messages` - Send human agent reply.
- `POST /api/v1/conversations/{id}/takeover` - Human takeover (`HUMAN_ACTIVE`).
- `POST /api/v1/conversations/{id}/release-to-ai` - Resume AI chatbot (`AI_RESUMED`).
- `POST /api/v1/conversations/{id}/close` - Close conversation.
- `WS /api/v1/conversations/ws/{org_id}` - Real-time WebSocket connection.

## AI Agents & Knowledge
- `GET /api/v1/ai-agents/default` - Get active agent configuration.
- `PUT /api/v1/ai-agents/{id}` - Update system prompt, model, allowed tools, and handoff rules.
- `GET /api/v1/knowledge` - List RAG knowledge documents.
- `POST /api/v1/knowledge` - Upload FAQ / domain documentation.
- `DELETE /api/v1/knowledge/{id}` - Delete document.

## Analytics & Probes
- `GET /api/v1/analytics/dashboard` - Global metrics (sent, delivered, read, failed, inbound, AI resolution).
- `GET /health` - Liveness health check.
- `GET /ready` - Readiness health check (database + Redis).

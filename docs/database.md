# Database Schema & Entity Relationship

PostgreSQL with SQLAlchemy 2.0 and Alembic.

## Schema Tables (23 Entities)

1. **`organizations`**: Multi-tenant business container (`id`, `name`, `slug`, `default_country_code`, `settings`).
2. **`users`**: System users and agents (`id`, `email`, `full_name`, `hashed_password`, `is_active`).
3. **`organization_members`**: Organization memberships with roles (`id`, `organization_id`, `user_id`, `role`: `OWNER`, `ADMIN`, `AGENT`, `VIEWER`).
4. **`roles`**: System roles.
5. **`permissions`**: Granular capability permissions.
6. **`whatsapp_instances`**: Connected WhatsApp business numbers and Evolution API sessions (`id`, `organization_id`, `instance_name`, `status`, `qr_code`).
7. **`contacts`**: WhatsApp customer profiles (`id`, `organization_id`, `name`, `phone`, `email`, `status`, `custom_fields`).
8. **`tags`**: Customer classification tags (`id`, `organization_id`, `name`, `color`).
9. **`contact_tags`**: Many-to-many contact-to-tag mapping.
10. **`templates`**: Reusable campaign templates (`id`, `organization_id`, `name`, `content`, `variables`).
11. **`media`**: S3/local media attachments (`id`, `organization_id`, `filename`, `file_path`, `mime_type`, `file_size`).
12. **`campaigns`**: Mass broadcast jobs (`id`, `organization_id`, `name`, `template_id`, `status`, `rate_limit_per_second`).
13. **`campaign_contacts`**: Individual recipient dispatch records (`id`, `campaign_id`, `contact_id`, `status`, `idempotency_key`).
14. **`conversations`**: WhatsApp chat threads (`id`, `organization_id`, `contact_id`, `status`, `ai_mode`: `AI_ACTIVE`, `HUMAN_REQUESTED`, `HUMAN_ACTIVE`, `AI_RESUMED`).
15. **`messages`**: Inbound and outbound WhatsApp messages (`id`, `conversation_id`, `direction`, `content`, `provider_message_id`, `status`).
16. **`conversation_participants`**: Assigned human agents.
17. **`ai_agents`**: Chatbot brain configurations (`id`, `organization_id`, `name`, `system_prompt`, `model`, `allowed_tools`, `working_hours`, `handoff_rules`).
18. **`knowledge_documents`**: RAG knowledge library (`id`, `organization_id`, `title`, `category`, `content`).
19. **`ai_runs`**: Execution log of LLM inferences (`id`, `conversation_id`, `tokens_used`, `latency_ms`).
20. **`ai_tool_calls`**: Executed AI function calls (`id`, `ai_run_id`, `tool_name`, `input_arguments`, `output_result`).
21. **`escalations`**: Human intervention requests (`id`, `conversation_id`, `reason`, `status`).
22. **`webhook_events`**: Raw incoming webhook event log for idempotency verification (`id`, `idempotency_key`, `event_type`, `raw_payload`).
23. **`audit_logs`**: Security & compliance activity audit trails.

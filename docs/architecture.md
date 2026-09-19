# System Architecture: Multi-Tenant WhatsApp AI SaaS

## 1. High-Level Architectural Flow

```
                                  +-----------------------+
                                  |   Next.js Frontend    |
                                  |  (React/TS/Tailwind)  |
                                  +-----------+-----------+
                                              |
                                  REST APIs / WebSockets
                                              |
                                              v
                                  +-----------------------+
                                  |    FastAPI Backend    |
                                  | (Multi-tenant Tenant  |
                                  |  Isolation & Auth)    |
                                  +-----+-----+-----+-----+
                                        |     |     |
                 +----------------------+     |     +----------------------+
                 |                            |                            |
                 v                            v                            v
      +--------------------+       +--------------------+       +--------------------+
      |  PostgreSQL / DB   |       |    Redis Queue     |       |   Evolution API    |
      | (Alembic Schema)   |       |   (Job Broker)     |       | (WhatsApp Engine)  |
      +--------------------+       +----------+---------+       +--------------------+
                                              |
                                              v
                                   +---------------------+
                                   |  Background Worker  |
                                   | (Campaigns, AI,     |
                                   |  Webhook processor, |
                                   |  Schedulers, Import)|
                                   +----------+----------+
                                              |
                         +--------------------+--------------------+
                         |                                         |
                         v                                         v
              +----------------------+                  +----------------------+
              |     AI Provider      |                  |  S3/Object Storage   |
              | (LLM, RAG, Tools)    |                  |  & Google Sheets API |
              +----------------------+                  +----------------------+
```

## 2. Core Abstractions & Decoupling Principle

To guarantee provider independence, four core interfaces govern all third-party interactions:

1. **`WhatsAppProvider`**:
   - Manages instance creation, QR pairing, connection state, webhook configuration, and dispatching text, image, video, audio, document, and location messages.
   - Default implementations: `EvolutionApiProvider` (HTTP REST integration) and `EvolutionApiMockProvider` (high-fidelity offline testing & mock mode).

2. **`AIProvider`**:
   - Orchestrates LLM inference with system prompt injection, message history trimming, RAG context attachment, and tool execution.
   - Default implementations: `MockAIProvider` (deterministic local intelligence) and `OpenAIProvider` (`gpt-4o`).

3. **`StorageProvider`**:
   - Manages media file storage, MIME type validation, file size limits, and pre-signed access URLs.
   - Default implementations: `LocalStorageProvider` and `S3StorageProvider`.

4. **`KnowledgeProvider`**:
   - Pluggable document retriever supporting PostgreSQL, pgvector, Qdrant, Pinecone, or Weaviate.

## 3. Webhook Ingress & Idempotency Pipeline

```
Evolution API Webhook Ingress -> FastAPI Route (/api/v1/webhooks/evolution)
                                           |
                                 Compute Deterministic
                                    Idempotency Key
                                           |
                              +------------+------------+
                              |                         |
                       Existing Hash?              New Event?
                              |                         |
                       (DUPLICATE_IGNORED)       Persist WebhookEvent
                       Return Fast 200 OK               |
                                                 Check Inbound / Status Update
                                                        |
                                                 Inbound Message -> Find / Create Contact
                                                        |
                                                 Create Conversation (if new)
                                                        |
                                                 Check AI Mode (HUMAN_ACTIVE lock)
                                                        |
                                                 If AI_ACTIVE -> Trigger AIService
                                                        |
                                                 Generate Reply -> Send via WhatsAppProvider
                                                        |
                                                 Broadcast via WebSockets
```

## 4. Multi-Tenant Isolation Model

- Every database entity (contacts, templates, campaigns, messages, conversations, ai_agents, knowledge_documents, media) contains a mandatory `organization_id` column.
- Authentication tokens encode `user_id` and `organization_id`.
- The `TenantRepository` pattern and dependency injection (`TenantContext`) strictly scope all queries by `organization_id`.
- Tests prove that Organization A cannot view, query, or mutate resources belonging to Organization B.

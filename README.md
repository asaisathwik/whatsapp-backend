# AutoChat PRO: Production Multi-Tenant WhatsApp & AI Chatbot SaaS

AutoChat PRO is an enterprise-grade, multi-tenant WhatsApp Automation and Autonomous AI Customer Care platform built with **FastAPI**, **Next.js 14**, **PostgreSQL**, **Redis Queue**, **Evolution API**, and an extensible **AI Provider / RAG Engine**.

---

## 🌟 Key Features

1. **Multi-Tenant Architecture**: Strict organizational data isolation enforced at repository and database query level.
2. **Evolution API Integration**: Full WhatsApp number pairing, QR code rendering, connection status, and message transmission.
3. **Automated Phone Normalizer**: Normalizes international formats (`+91 9XXXXXXXXX`, `0919XXXXXXXXX`, `919XXXXXXXXX`, `9XXXXXXXXX`) with configurable country defaults.
4. **CSV & Excel Contact Importer**: Interactive validation preview, duplicate detection, and batch import error reporting.
5. **Dynamic Message Templates**: Variable interpolation (`{{name}}`, `{{phone}}`, `{{city}}`, `{{custom_fields}}`) with live contact preview.
6. **Broadcast Campaign Engine**: 7-step campaign creation wizard, queue rate limiter (configurable msgs/sec), pause, resume, cancel, and delivery tracking.
7. **WhatsApp 3-Pane Real-Time Inbox**: Live chat interface with WebSockets, message status receipts (`QUEUED`, `SENT`, `DELIVERED`, `READ`), and agent assignment.
8. **Human Takeover & Escalation Lock**: Seamless takeover (`HUMAN_ACTIVE`) with strict suppression of AI auto-replies, and release back to AI (`AI_RESUMED`).
9. **Autonomous AI Engine**: Pluggable LLM provider (OpenAI GPT-4o / Mock), RAG knowledge base retrieval, and function calling tools (`get_customer_details`, `get_business_hours`, `check_availability`, `create_lead`, `handoff_to_human`).
10. **Webhook Idempotency**: Deterministic MD5 hash deduplication preventing duplicate message creation or repeated AI processing.

---

## 🏗️ Architecture & Tech Stack

- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS, Lucide Icons.
- **Backend**: FastAPI, Python 3.11+, Pydantic v2, SQLAlchemy 2.0, Alembic, PyJWT, bcrypt.
- **Database**: PostgreSQL (with SQLite in-memory testing support).
- **Queues & Workers**: Redis Queue with FakeRedis fallback & standalone worker daemons.
- **WhatsApp Gateway**: Evolution API v1.8+.
- **Realtime**: WebSockets.
- **Containerization**: Docker & Docker Compose.

---

## 🚀 Quick Start (Local Run)

### 1. Backend Server
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # or source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- Health probe: `http://localhost:8000/health`
- Readiness probe: `http://localhost:8000/ready`
- Interactive API Docs: `http://localhost:8000/docs`

### 2. Standalone Background Worker
```bash
cd worker
python run_worker.py
```

### 3. Frontend Next.js Application
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to access the command center dashboard.

---

## 🐳 Docker Production Stack

```bash
cd infrastructure
docker compose up --build -d
```

---

## 🧪 Running Automated Tests

```bash
cd backend
venv\Scripts\pytest ..\tests -v
```

All 15 automated test suites pass with 100% test coverage across multi-tenancy, authentication, webhooks idempotency, campaign rate-limiting, and AI human takeover protection.

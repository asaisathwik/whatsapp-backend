# Local Development Guide

## Prerequisites
- Python 3.10+
- Node.js 18+ and npm 9+
- Docker & Docker Compose (optional for standalone local dev)

## Quick Start (Local Runtimes)

### 1. Backend & Workers
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Standalone Background Job Worker
```bash
cd worker
python run_worker.py
```

### 3. Frontend Next.js Dashboard
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to access the WhatsApp AI command center.
API Documentation is available at `http://localhost:8000/docs`.

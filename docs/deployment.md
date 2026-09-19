# Production Deployment Guide

## Docker Compose Production Stack

To start the full production stack with PostgreSQL, Redis, Evolution API, Backend, Worker, and Frontend:

```bash
cd infrastructure
docker compose up --build -d
```

## Production Verification Checklist

1. Verify all services are healthy:
   ```bash
   docker compose ps
   ```
2. Verify Backend Liveness Probe:
   ```bash
   curl http://localhost:8000/health
   ```
3. Verify Readiness Probe (PostgreSQL + Redis):
   ```bash
   curl http://localhost:8000/ready
   ```
4. Verify Next.js Dashboard:
   Open `http://localhost:3000` in your browser.

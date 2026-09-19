import logging
import time
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.redis_client import get_redis_client

import os
from fastapi.staticfiles import StaticFiles

# Import API routers
from app.api.v1.auth import router as auth_router
from app.api.v1.organizations import router as orgs_router
from app.api.v1.whatsapp import router as whatsapp_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.templates import router as templates_router
from app.api.v1.media import router as media_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.ai_agents import router as ai_agents_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.analytics import router as analytics_router
from app.webhooks.evolution import router as webhooks_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

# Ensure uploads dir
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Auto-create tables for local/dev
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-Ready Multi-Tenant WhatsApp Messaging + AI Chatbot SaaS Platform API"
)

# Mount Static Files for Media
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health & Ready Probes
@app.get("/health", tags=["Health Probes"])
def health_check():
    """Liveness probe: verifies the FastAPI application process is alive."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@app.get("/ready", tags=["Health Probes"])
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe: verifies database and redis connectivity."""
    db_status = "unhealthy"
    redis_status = "unhealthy"
    
    # Check Database
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        db_status = f"error: {str(e)}"

    # Check Redis
    try:
        client = get_redis_client()
        client.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error(f"Redis readiness check failed: {e}")
        redis_status = f"error: {str(e)}"

    is_ready = (db_status == "healthy" and redis_status == "healthy")
    return {
        "status": "ready" if is_ready else "degraded",
        "database": db_status,
        "redis": redis_status,
        "environment": settings.ENVIRONMENT
    }

# Mount API v1 Routers
api_v1_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(orgs_router, prefix=api_v1_prefix)
app.include_router(whatsapp_router, prefix=api_v1_prefix)
app.include_router(contacts_router, prefix=api_v1_prefix)
app.include_router(templates_router, prefix=api_v1_prefix)
app.include_router(media_router, prefix=api_v1_prefix)
app.include_router(campaigns_router, prefix=api_v1_prefix)
app.include_router(conversations_router, prefix=api_v1_prefix)
app.include_router(ai_agents_router, prefix=api_v1_prefix)
app.include_router(knowledge_router, prefix=api_v1_prefix)
app.include_router(analytics_router, prefix=api_v1_prefix)
app.include_router(webhooks_router, prefix=api_v1_prefix)

@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready"
    }

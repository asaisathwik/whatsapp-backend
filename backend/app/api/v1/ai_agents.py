from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext, require_roles
from app.models.models import AIAgent, MemberRole
from app.schemas.schemas import AIAgentCreate, AIAgentResponse

router = APIRouter(prefix="/ai-agents", tags=["AI Agents"])

@router.get("", response_model=List[AIAgentResponse])
def list_ai_agents(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    return db.query(AIAgent).filter(AIAgent.organization_id == context.organization_id).all()

@router.get("/default", response_model=AIAgentResponse)
def get_default_agent(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    agent = db.query(AIAgent).filter(
        AIAgent.organization_id == context.organization_id,
        AIAgent.is_default == True
    ).first()
    if not agent:
        # Create default
        agent = AIAgent(
            organization_id=context.organization_id,
            name="Assistant",
            system_prompt="You are a helpful WhatsApp customer support agent for our company.",
            is_default=True
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
    return agent

@router.put("/{agent_id}", response_model=AIAgentResponse)
def update_ai_agent(
    agent_id: str,
    payload: AIAgentCreate,
    context: TenantContext = Depends(require_roles([MemberRole.OWNER, MemberRole.ADMIN])),
    db: Session = Depends(get_db)
):
    agent = db.query(AIAgent).filter(
        AIAgent.id == agent_id,
        AIAgent.organization_id == context.organization_id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="AI Agent not found")

    agent.name = payload.name
    agent.system_prompt = payload.system_prompt
    agent.personality = payload.personality
    agent.model = payload.model
    agent.business_description = payload.business_description
    agent.faq_data = payload.faq_data
    agent.products_services = payload.products_services
    agent.working_hours = payload.working_hours
    agent.allowed_tools = payload.allowed_tools
    agent.handoff_rules = payload.handoff_rules

    db.commit()
    db.refresh(agent)
    return agent

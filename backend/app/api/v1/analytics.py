from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import Message, Conversation, Campaign, Contact, MessageDirection, MessageStatus, AIMode
from app.schemas.schemas import DashboardMetrics

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])

@router.get("/dashboard", response_model=DashboardMetrics)
def get_dashboard_metrics(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    org_id = context.organization_id

    total_sent = db.query(Message).filter(Message.organization_id == org_id, Message.direction == MessageDirection.OUTBOUND.value).count()
    total_delivered = db.query(Message).filter(Message.organization_id == org_id, Message.status == MessageStatus.DELIVERED.value).count()
    total_read = db.query(Message).filter(Message.organization_id == org_id, Message.status == MessageStatus.READ.value).count()
    total_failed = db.query(Message).filter(Message.organization_id == org_id, Message.status == MessageStatus.FAILED.value).count()
    total_inbound = db.query(Message).filter(Message.organization_id == org_id, Message.direction == MessageDirection.INBOUND.value).count()

    active_convs = db.query(Conversation).filter(Conversation.organization_id == org_id, Conversation.status == "OPEN").count()
    ai_convs = db.query(Conversation).filter(Conversation.organization_id == org_id, Conversation.ai_mode.in_([AIMode.AI_ACTIVE.value, AIMode.AI_RESUMED.value])).count()
    human_convs = db.query(Conversation).filter(Conversation.organization_id == org_id, Conversation.ai_mode.in_([AIMode.HUMAN_ACTIVE.value, AIMode.HUMAN_REQUESTED.value])).count()

    total_campaigns = db.query(Campaign).filter(Campaign.organization_id == org_id).count()
    total_contacts = db.query(Contact).filter(Contact.organization_id == org_id).count()

    return DashboardMetrics(
        messages_sent=total_sent,
        messages_delivered=total_delivered,
        messages_read=total_read,
        messages_failed=total_failed,
        messages_inbound=total_inbound,
        messages_outbound=total_sent,
        active_conversations=active_convs,
        ai_conversations=ai_convs,
        human_conversations=human_convs,
        total_campaigns=total_campaigns,
        total_contacts=total_contacts
    )

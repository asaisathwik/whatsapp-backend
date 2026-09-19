import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import Conversation, Message, Contact, WhatsAppInstance, Escalation, EscalationStatus, AIMode, MessageDirection, MessageType, MessageStatus
from app.schemas.schemas import ConversationResponse, MessageResponse, MessageSendRequest, HumanTakeoverRequest
from app.integrations.evolution import get_whatsapp_provider

logger = logging.getLogger("conversations")
router = APIRouter(prefix="/conversations", tags=["Conversations & Inbox"])

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, org_id: str, websocket: WebSocket):
        await websocket.accept()
        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        self.active_connections[org_id].append(websocket)

    def disconnect(self, org_id: str, websocket: WebSocket):
        if org_id in self.active_connections:
            self.active_connections[org_id].remove(websocket)

    async def broadcast_to_org(self, org_id: str, data: dict):
        if org_id in self.active_connections:
            for connection in self.active_connections[org_id]:
                try:
                    await connection.send_json(data)
                except Exception:
                    pass

ws_manager = ConnectionManager()

@router.websocket("/ws/{org_id}")
async def websocket_endpoint(websocket: WebSocket, org_id: str):
    await ws_manager.connect(org_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo heartbeat or client typing event
            await websocket.send_json({"type": "PONG", "payload": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(org_id, websocket)

@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    ai_mode: Optional[str] = None,
    status: Optional[str] = None,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(Conversation).filter(Conversation.organization_id == context.organization_id)
    if ai_mode:
        query = query.filter(Conversation.ai_mode == ai_mode)
    if status:
        query = query.filter(Conversation.status == status)

    convs = query.order_by(Conversation.last_message_at.desc()).all()
    results = []
    for c in convs:
        last_msg = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at.desc()).first()
        results.append(ConversationResponse(
            id=c.id,
            organization_id=c.organization_id,
            contact_id=c.contact_id,
            contact_name=c.contact.name if c.contact else "Unknown",
            contact_phone=c.contact.phone if c.contact else "",
            whatsapp_instance_id=c.whatsapp_instance_id,
            status=c.status,
            ai_mode=c.ai_mode,
            assigned_user_id=c.assigned_user_id,
            unread_count=c.unread_count or 0,
            last_message_at=c.last_message_at,
            last_message=MessageResponse.model_validate(last_msg) if last_msg else None,
            created_at=c.created_at,
            updated_at=c.updated_at
        ))
    return results

@router.post("/contact/{contact_id}", response_model=ConversationResponse)
def get_or_create_conversation_for_contact(
    contact_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.organization_id == context.organization_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    conv = db.query(Conversation).filter(
        Conversation.contact_id == contact_id,
        Conversation.organization_id == context.organization_id
    ).first()

    if not conv:
        inst = db.query(WhatsAppInstance).filter(
            WhatsAppInstance.organization_id == context.organization_id
        ).first()
        conv = Conversation(
            organization_id=context.organization_id,
            contact_id=contact_id,
            whatsapp_instance_id=inst.id if inst else None,
            status="OPEN",
            ai_mode=AIMode.HUMAN_ACTIVE.value
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    last_msg = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).first()
    return ConversationResponse(
        id=conv.id,
        organization_id=conv.organization_id,
        contact_id=conv.contact_id,
        contact_name=contact.name,
        contact_phone=contact.phone,
        whatsapp_instance_id=conv.whatsapp_instance_id,
        status=conv.status,
        ai_mode=conv.ai_mode,
        assigned_user_id=conv.assigned_user_id,
        unread_count=conv.unread_count or 0,
        last_message_at=conv.last_message_at,
        last_message=MessageResponse.model_validate(last_msg) if last_msg else None,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == context.organization_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Reset unread count
    conv.unread_count = 0
    db.commit()

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.organization_id == context.organization_id
    ).order_by(Message.created_at.asc()).all()
    return messages

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_agent_message(
    conversation_id: str,
    payload: MessageSendRequest,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == context.organization_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    whatsapp_provider = get_whatsapp_provider()
    instance = conv.whatsapp_instance
    instance_name = instance.instance_name if instance else "default"
    to_phone = conv.contact.phone if conv.contact else "unknown"

    msg = Message(
        organization_id=context.organization_id,
        conversation_id=conv.id,
        contact_id=conv.contact_id,
        whatsapp_instance_id=conv.whatsapp_instance_id,
        direction=MessageDirection.OUTBOUND.value,
        message_type=payload.message_type or MessageType.TEXT.value,
        content=payload.content,
        media_url=payload.media_url,
        status=MessageStatus.SENT.value,
        sent_at=datetime.now(timezone.utc)
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    # Dispatch to WhatsApp provider
    try:
        if payload.message_type == MessageType.IMAGE.value and payload.media_url:
            await whatsapp_provider.send_image(instance_name, to_phone, payload.media_url, caption=payload.content)
        elif payload.message_type == MessageType.DOCUMENT.value and payload.media_url:
            await whatsapp_provider.send_document(instance_name, to_phone, payload.media_url, filename=payload.content or "document.pdf", caption=payload.content)
        else:
            await whatsapp_provider.send_text(instance_name, to_phone, payload.content)
    except Exception as e:
        logger.error(f"Failed to dispatch agent WhatsApp message: {e}")
        msg.status = MessageStatus.FAILED.value
        msg.error_message = str(e)
        db.commit()

    # Broadcast via WebSocket
    await ws_manager.broadcast_to_org(context.organization_id, {
        "event": "NEW_MESSAGE",
        "conversation_id": conv.id,
        "message": {
            "id": msg.id,
            "direction": msg.direction,
            "content": msg.content,
            "status": msg.status,
            "created_at": msg.created_at.isoformat()
        }
    })

    return msg

# Human Takeover & AI Resume Actions
@router.post("/{conversation_id}/takeover")
async def takeover_conversation(
    conversation_id: str,
    payload: HumanTakeoverRequest,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == context.organization_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.ai_mode = AIMode.HUMAN_ACTIVE.value
    conv.assigned_user_id = context.user_id

    # Resolve pending escalations
    pending_esc = db.query(Escalation).filter(
        Escalation.conversation_id == conversation_id,
        Escalation.status == EscalationStatus.PENDING.value
    ).all()
    for esc in pending_esc:
        esc.status = EscalationStatus.RESOLVED.value
        esc.resolved_at = datetime.now(timezone.utc)
        esc.assigned_user_id = context.user_id

    db.commit()
    return {"status": "SUCCESS", "ai_mode": conv.ai_mode, "assigned_to": context.user.full_name}

@router.post("/{conversation_id}/release-to-ai")
async def release_to_ai(
    conversation_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == context.organization_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.ai_mode = AIMode.AI_RESUMED.value
    db.commit()
    return {"status": "SUCCESS", "ai_mode": conv.ai_mode}

@router.post("/{conversation_id}/close")
def close_conversation(
    conversation_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == context.organization_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.status = "CLOSED"
    db.commit()
    return {"status": "SUCCESS", "conversation_status": "CLOSED"}

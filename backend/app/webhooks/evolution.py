import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.redis_client import RedisQueue
from app.models.models import WebhookEvent, WhatsAppInstance, Conversation, Message, Contact, ContactStatus, MessageDirection, MessageType, MessageStatus, AIMode
from app.services.phone_normalizer import normalize_phone_number
from app.services.ai_service import AIService

logger = logging.getLogger("evolution_webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

def generate_payload_idempotency_key(payload: Dict[str, Any]) -> str:
    """Computes a deterministic MD5 hash of event payload for deduplication."""
    # If provider provides explicit message ID, prioritize it
    data = payload.get("data", {})
    key = data.get("key", {})
    msg_id = key.get("id")
    if msg_id:
        return f"evo_msg_{msg_id}"
    
    dumped = json.dumps(payload, sort_keys=True)
    return f"evo_hash_{hashlib.md5(dumped.encode('utf-8')).hexdigest()}"

@router.post("/evolution")
async def handle_evolution_webhook(
    request: Request,
    db: Session = Depends(get_db),
    apikey: Optional[str] = Header(None, alias="apikey")
):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    event_type = payload.get("event") or payload.get("type", "UNKNOWN")
    instance_name = payload.get("instance")
    
    # 1. Deduplication / Idempotency Key check
    idempotency_key = generate_payload_idempotency_key(payload)
    
    existing_event = db.query(WebhookEvent).filter(
        WebhookEvent.idempotency_key == idempotency_key
    ).first()

    if existing_event:
        logger.info("Duplicate webhook event received: %s. Skipping duplicate processing.", idempotency_key)
        return {"status": "DUPLICATE_IGNORED", "idempotency_key": idempotency_key}

    # Find associated WhatsApp Instance
    instance = None
    org_id = None
    if instance_name:
        instance = db.query(WhatsAppInstance).filter(WhatsAppInstance.instance_name == instance_name).first()
        if instance:
            org_id = instance.organization_id

    # 2. Persist raw WebhookEvent
    webhook_event = WebhookEvent(
        organization_id=org_id,
        provider="EVOLUTION",
        event_type=event_type,
        provider_event_id=idempotency_key,
        idempotency_key=idempotency_key,
        raw_payload=payload,
        status="PROCESSED",
        processed_at=datetime.now(timezone.utc)
    )
    db.add(webhook_event)
    db.commit()

    # 3. Process Inbound Messages (messages.upsert)
    if event_type in ["messages.upsert", "MESSAGES_UPSERT"]:
        await _process_inbound_message_event(db, payload, instance, org_id)

    # 4. Process Status Updates (messages.update)
    elif event_type in ["messages.update", "MESSAGES_UPDATE"]:
        await _process_message_status_update(db, payload, org_id)

    # Fast 200 OK return
    return {"status": "SUCCESS", "event": event_type, "idempotency_key": idempotency_key}

async def _process_inbound_message_event(db: Session, payload: Dict[str, Any], instance: Optional[WhatsAppInstance], org_id: Optional[str]):
    data = payload.get("data", {})
    key = data.get("key", {})
    from_me = key.get("fromMe", False)
    
    # Ignore messages sent by self
    if from_me:
        return

    remote_jid = key.get("remoteJid", "")
    raw_phone = remote_jid.split("@")[0]
    provider_msg_id = key.get("id")

    # Extract text content
    msg_obj = data.get("message", {})
    content = (
        msg_obj.get("conversation") or 
        msg_obj.get("extendedTextMessage", {}).get("text") or 
        msg_obj.get("imageMessage", {}).get("caption") or 
        msg_obj.get("videoMessage", {}).get("caption") or 
        ""
    )

    if not raw_phone or not org_id:
        return

    # Normalize phone
    is_valid, normalized_phone, _ = normalize_phone_number(raw_phone)
    phone_to_use = normalized_phone if is_valid else raw_phone

    # Find or create Contact
    contact = db.query(Contact).filter(
        Contact.organization_id == org_id,
        Contact.phone == phone_to_use
    ).first()

    push_name = data.get("pushName") or f"WhatsApp {phone_to_use[-4:]}"
    if not contact:
        contact = Contact(
            organization_id=org_id,
            name=push_name,
            phone=phone_to_use,
            status=ContactStatus.ACTIVE.value,
            source="INBOUND"
        )
        db.add(contact)
        db.flush()

    # Find or create Conversation
    conversation = db.query(Conversation).filter(
        Conversation.organization_id == org_id,
        Conversation.contact_id == contact.id,
        Conversation.whatsapp_instance_id == (instance.id if instance else None)
    ).first()

    if not conversation:
        conversation = Conversation(
            organization_id=org_id,
            contact_id=contact.id,
            whatsapp_instance_id=instance.id if instance else None,
            status="OPEN",
            ai_mode=AIMode.AI_ACTIVE.value,
            unread_count=1
        )
        db.add(conversation)
        db.flush()
    else:
        conversation.unread_count = (conversation.unread_count or 0) + 1
        conversation.last_message_at = datetime.now(timezone.utc)

    # Persist Inbound Message
    inbound_message = Message(
        organization_id=org_id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        whatsapp_instance_id=instance.id if instance else None,
        direction=MessageDirection.INBOUND.value,
        message_type=MessageType.TEXT.value,
        content=content,
        provider_message_id=provider_msg_id,
        status=MessageStatus.DELIVERED.value
    )
    db.add(inbound_message)
    db.commit()
    db.refresh(inbound_message)

    # Trigger AI processing if AI is active
    if conversation.ai_mode == AIMode.AI_ACTIVE.value:
        await AIService.process_inbound_message(
            db=db,
            organization_id=org_id,
            conversation_id=conversation.id,
            inbound_message_id=inbound_message.id
        )

async def _process_message_status_update(db: Session, payload: Dict[str, Any], org_id: Optional[str]):
    data = payload.get("data", [])
    if isinstance(data, dict):
        data = [data]

    for item in data:
        key = item.get("key", {})
        msg_id = key.get("id")
        raw_status = item.get("status")

        if not msg_id or not raw_status:
            continue

        status_map = {
            "PENDING": MessageStatus.QUEUED.value,
            "SERVER_ACK": MessageStatus.SENT.value,
            "DELIVERY_ACK": MessageStatus.DELIVERED.value,
            "READ": MessageStatus.READ.value,
            "PLAYED": MessageStatus.READ.value,
            "ERROR": MessageStatus.FAILED.value
        }
        target_status = status_map.get(raw_status)
        if not target_status:
            continue

        msg = db.query(Message).filter(Message.provider_message_id == msg_id).first()
        if msg:
            msg.status = target_status
            if target_status == MessageStatus.DELIVERED.value:
                msg.delivered_at = datetime.now(timezone.utc)
            elif target_status == MessageStatus.READ.value:
                msg.read_at = datetime.now(timezone.utc)
            db.commit()

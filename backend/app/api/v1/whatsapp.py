from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext, require_roles
from app.models.models import (
    WhatsAppInstance, WhatsAppInstanceStatus, MemberRole,
    Contact, Conversation, Message, MessageDirection, MessageType, MessageStatus
)
from app.schemas.schemas import WhatsAppInstanceCreate, WhatsAppInstanceResponse
from app.integrations.evolution import get_whatsapp_provider

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Instances"])


@router.get("/instances", response_model=list[WhatsAppInstanceResponse])
async def list_instances(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    instances = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.organization_id == context.organization_id
    ).all()
    
    provider = get_whatsapp_provider()
    for inst in instances:
        try:
            status_res = await provider.get_instance_status(inst.instance_name)
            inst_data = status_res.get("instance", {})
            state = inst_data.get("state") or status_res.get("status")
            phone = inst_data.get("phone")
            if phone and not inst.phone_number:
                inst.phone_number = str(phone)
            if state == "CONNECTED":
                inst.status = WhatsAppInstanceStatus.CONNECTED.value
            elif state in ["DISCONNECTED", "ERROR"]:
                inst.status = WhatsAppInstanceStatus.DISCONNECTED.value
            elif state in ["INITIALIZING", "LOADING", "QR_READY"]:
                inst.status = WhatsAppInstanceStatus.CONNECTING.value
            db.commit()
        except Exception:
            pass
            
    return instances


@router.post("/instances", response_model=WhatsAppInstanceResponse)
async def create_instance(
    payload: WhatsAppInstanceCreate,
    context: TenantContext = Depends(require_roles([MemberRole.OWNER, MemberRole.ADMIN])),
    db: Session = Depends(get_db)
):
    # Unique instance name in org
    existing = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.organization_id == context.organization_id,
        WhatsAppInstance.instance_name == payload.instance_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An instance with this name already exists.")

    provider = get_whatsapp_provider()
    try:
        prov_res = await provider.create_instance(payload.instance_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WhatsApp instance creation failed: {str(e)}")

    # QR may not be ready immediately (real bridge takes 5-10s)
    qr_b64 = prov_res.get("qrcode", {}).get("base64") if isinstance(prov_res, dict) else None

    instance = WhatsAppInstance(
        organization_id=context.organization_id,
        instance_name=payload.instance_name,
        phone_number=payload.phone_number,
        status=WhatsAppInstanceStatus.CONNECTING.value,
        qr_code=qr_b64,
        is_default=payload.is_default or False
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


@router.get("/instances/{instance_id}/qr")
async def get_instance_qr(
    instance_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Fetch the latest QR code for an instance.
    For real bridge: may return status=QR_INITIALIZING if not ready yet — frontend should retry.
    """
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    try:
        try:
            res = await provider.get_qr_code(instance.instance_name)
        except Exception:
            # If bridge session not running, start it
            await provider.create_instance(instance.instance_name)
            res = await provider.get_qr_code(instance.instance_name)

        qr_code = res.get("base64") or res.get("code")
        bridge_status = res.get("status", "UNKNOWN")
        bridge_message = res.get("message")

        # If we got a real QR, persist it
        if qr_code and qr_code.startswith("data:image"):
            instance.qr_code = qr_code
            instance.status = WhatsAppInstanceStatus.CONNECTING.value
            db.commit()
        elif bridge_status == "CONNECTED":
            instance.status = WhatsAppInstanceStatus.CONNECTED.value
            instance.qr_code = None
            db.commit()

        return {
            "instance_id": instance.id,
            "qr_code": qr_code,
            "pairing_code": res.get("pairingCode"),
            "status": bridge_status,
            "message": bridge_message,
        }
    except Exception as e:
        return {
            "instance_id": instance.id,
            "qr_code": None,
            "status": "INITIALIZING",
            "message": str(e),
        }


@router.post("/instances/{instance_id}/connect")
async def connect_instance(
    instance_id: str,
    context: TenantContext = Depends(require_roles([MemberRole.OWNER, MemberRole.ADMIN])),
    db: Session = Depends(get_db)
):
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    try:
        res = await provider.connect_instance(instance.instance_name)
        bridge_status = res.get("status") if isinstance(res, dict) else None
        if bridge_status == "CONNECTED":
            instance.status = WhatsAppInstanceStatus.CONNECTED.value
        else:
            instance.status = WhatsAppInstanceStatus.CONNECTING.value
        db.commit()
        return {"status": "SUCCESS", "details": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect instance: {str(e)}")


@router.post("/instances/{instance_id}/disconnect")
async def disconnect_instance(
    instance_id: str,
    context: TenantContext = Depends(require_roles([MemberRole.OWNER, MemberRole.ADMIN])),
    db: Session = Depends(get_db)
):
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    try:
        res = await provider.disconnect_instance(instance.instance_name)
        instance.status = WhatsAppInstanceStatus.DISCONNECTED.value
        instance.qr_code = None
        db.commit()
        return {"status": "SUCCESS", "details": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect instance: {str(e)}")


@router.post("/instances/{instance_id}/restart")
async def restart_instance(
    instance_id: str,
    context: TenantContext = Depends(require_roles([MemberRole.OWNER, MemberRole.ADMIN])),
    db: Session = Depends(get_db)
):
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    try:
        res = await provider.reconnect_instance(instance.instance_name)
        instance.status = WhatsAppInstanceStatus.CONNECTING.value
        instance.qr_code = None
        db.commit()
        return {"status": "SUCCESS", "details": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart instance: {str(e)}")



@router.post("/instances/{instance_id}/sync")
async def sync_instance_chats(
    instance_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Sync all real chats and contacts from the connected WhatsApp session into the database.
    """
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    try:
        chats = await provider.get_chats(instance.instance_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch chats from WhatsApp: {str(e)}")

    synced_contacts = 0
    synced_conversations = 0

    for chat in chats:
        phone = chat.get("phone") or ""
        name = chat.get("name") or phone or "Unknown"
        chat_id_val = chat.get("id") or ""
        if not phone and not chat_id_val:
            continue

        target_phone = phone if phone else chat_id_val.replace("@c.us", "").replace("@g.us", "")

        # Check existing contact
        contact = db.query(Contact).filter(
            Contact.organization_id == context.organization_id,
            (Contact.phone == target_phone) | (Contact.name == name)
        ).first()

        if not contact:
            contact = Contact(
                organization_id=context.organization_id,
                name=name,
                phone=target_phone,
                source="WHATSAPP_SYNC",
                status="ACTIVE"
            )
            db.add(contact)
            db.flush()
            synced_contacts += 1

        # Check conversation
        conv = db.query(Conversation).filter(
            Conversation.organization_id == context.organization_id,
            Conversation.contact_id == contact.id
        ).first()

        if not conv:
            conv = Conversation(
                organization_id=context.organization_id,
                contact_id=contact.id,
                whatsapp_instance_id=instance.id,
                status="OPEN"
            )
            db.add(conv)
            db.flush()
            synced_conversations += 1

        # If lastMessage exists, sync it
        last_msg = chat.get("lastMessage")
        if last_msg and last_msg.get("body"):
            body = last_msg.get("body")
            from_me = last_msg.get("fromMe", False)
            existing_msg = db.query(Message).filter(
                Message.conversation_id == conv.id,
                Message.content == body
            ).first()
            if not existing_msg:
                msg = Message(
                    organization_id=context.organization_id,
                    conversation_id=conv.id,
                    contact_id=contact.id,
                    whatsapp_instance_id=instance.id,
                    direction=MessageDirection.OUTBOUND.value if from_me else MessageDirection.INBOUND.value,
                    message_type=MessageType.TEXT.value,
                    content=body,
                    status=MessageStatus.DELIVERED.value
                )
                db.add(msg)

    db.commit()
    return {
        "status": "SUCCESS",
        "total_chats_from_whatsapp": len(chats),
        "synced_contacts": synced_contacts,
        "synced_conversations": synced_conversations,
        "chats": chats
    }


@router.get("/instances/{instance_id}/chats")
async def get_instance_chats(
    instance_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    return await provider.get_chats(instance.instance_name)


@router.get("/instances/{instance_id}/chats/{chat_id}/messages")
async def get_instance_chat_messages(
    instance_id: str,
    chat_id: str,
    limit: int = 50,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    instance = db.query(WhatsAppInstance).filter(
        WhatsAppInstance.id == instance_id,
        WhatsAppInstance.organization_id == context.organization_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="WhatsApp instance not found.")

    provider = get_whatsapp_provider()
    return await provider.get_chat_messages(instance.instance_name, chat_id, limit=limit)

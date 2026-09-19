import uuid
import json
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import Campaign, CampaignContact, Contact, Template, WhatsAppInstance, CampaignStatus, MessageStatus
from app.schemas.schemas import CampaignCreate, CampaignResponse, CampaignPreview
from app.services.template_service import TemplateService
from app.core.redis_client import RedisQueue
from app.workers.campaign_worker import CampaignWorker

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.get("", response_model=List[CampaignResponse])
def list_campaigns(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    return db.query(Campaign).filter(
        Campaign.organization_id == context.organization_id
    ).order_by(Campaign.created_at.desc()).all()

@router.post("/preview", response_model=CampaignPreview)
def preview_campaign(
    payload: CampaignCreate,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    template_content = payload.custom_content or ""
    variables_needed = []
    
    if payload.template_id:
        template = db.query(Template).filter(
            Template.id == payload.template_id,
            Template.organization_id == context.organization_id
        ).first()
        if template:
            template_content = template.content
            variables_needed = template.variables or []
    else:
        variables_needed = TemplateService.extract_variables(template_content)

    # Fetch targeted audience
    if payload.contact_ids:
        contacts = db.query(Contact).filter(
            Contact.organization_id == context.organization_id,
            Contact.id.in_(payload.contact_ids)
        ).all()
        total_count = len(contacts)
    else:
        contacts_query = db.query(Contact).filter(
            Contact.organization_id == context.organization_id,
            Contact.status == "ACTIVE"
        )
        tag_id = payload.audience_filter.get("tag_id") if payload.audience_filter else None
        if tag_id:
            from app.models.models import ContactTag
            contacts_query = contacts_query.join(ContactTag).filter(ContactTag.tag_id == tag_id)

        contacts = contacts_query.limit(100).all()
        total_count = contacts_query.count()

    sample_messages = []
    for c in contacts[:3]:
        contact_dict = {"name": c.name, "phone": c.phone, "email": c.email, "custom_fields": c.custom_fields}
        rendered = TemplateService.render_template(template_content, contact_dict, payload.variables_mapping)
        sample_messages.append({"recipient": c.name, "phone": c.phone, "preview": rendered})

    est_duration = total_count / max(1, payload.rate_limit_per_second or 5)

    return CampaignPreview(
        campaign_name=payload.name,
        total_recipients=total_count,
        sample_messages=sample_messages,
        variables_needed=variables_needed,
        invalid_recipients_count=0,
        estimated_duration_seconds=int(est_duration)
    )

@router.post("", response_model=CampaignResponse)
def create_campaign(
    payload: CampaignCreate,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    template_id = payload.template_id
    v_mapping = payload.variables_mapping or {}
    
    # Check if custom content should be saved as a Store Template
    custom_msg = payload.custom_content or payload.message_content
    if not template_id and custom_msg:
        if payload.save_to_store:
            extracted_vars = TemplateService.extract_variables(custom_msg)
            tmpl_name = payload.store_asset_name or f"Saved Template ({payload.name[:30]})"
            tmpl = Template(
                organization_id=context.organization_id,
                name=tmpl_name,
                category="MARKETING",
                content=custom_msg,
                variables=extracted_vars,
                is_active=True
            )
            db.add(tmpl)
            db.flush()
            template_id = tmpl.id
        else:
            # Store custom text directly in variables_mapping without creating a dummy template
            v_mapping["custom_text"] = custom_msg

    if payload.media_url:
        v_mapping["media_url"] = payload.media_url

    # Fetch audience
    if payload.contact_ids:
        target_contacts = db.query(Contact).filter(
            Contact.organization_id == context.organization_id,
            Contact.id.in_(payload.contact_ids)
        ).all()
    elif payload.recipient_phones:
        target_contacts = []
        for ph in payload.recipient_phones:
            clean_ph = ph.strip().replace("+", "").replace(" ", "").replace("-", "")
            if not clean_ph:
                continue
            c = db.query(Contact).filter(
                Contact.organization_id == context.organization_id,
                Contact.phone == clean_ph
            ).first()
            if not c:
                c = Contact(
                    organization_id=context.organization_id,
                    name=clean_ph,
                    phone=clean_ph,
                    source="MANUAL_BROADCAST",
                    status="ACTIVE"
                )
                db.add(c)
                db.flush()
            target_contacts.append(c)
    else:
        contacts_query = db.query(Contact).filter(
            Contact.organization_id == context.organization_id,
            Contact.status == "ACTIVE"
        )
        tag_id = payload.audience_filter.get("tag_id") if payload.audience_filter else None
        if tag_id:
            from app.models.models import ContactTag
            contacts_query = contacts_query.join(ContactTag).filter(ContactTag.tag_id == tag_id)
        target_contacts = contacts_query.all()

    # If no instance provided, pick default instance
    wa_instance_id = payload.whatsapp_instance_id
    if not wa_instance_id:
        def_inst = db.query(WhatsAppInstance).filter(
            WhatsAppInstance.organization_id == context.organization_id
        ).first()
        if def_inst:
            wa_instance_id = def_inst.id

    campaign = Campaign(
        organization_id=context.organization_id,
        name=payload.name,
        whatsapp_instance_id=wa_instance_id,
        template_id=template_id,
        status=CampaignStatus.SCHEDULED.value if payload.scheduled_at else CampaignStatus.DRAFT.value,
        scheduled_at=payload.scheduled_at,
        total_recipients=len(target_contacts),
        rate_limit_per_second=payload.rate_limit_per_second or 5,
        variables_mapping=v_mapping,
        audience_filter=payload.audience_filter or {}
    )
    db.add(campaign)
    db.flush()

    # Create CampaignContact records with deterministic idempotency keys
    for c in target_contacts:
        idem_key = f"camp_{campaign.id}_{c.id}_{uuid.uuid4().hex[:6]}"
        db.add(CampaignContact(
            organization_id=context.organization_id,
            campaign_id=campaign.id,
            contact_id=c.id,
            status=MessageStatus.QUEUED.value,
            idempotency_key=idem_key
        ))

    db.commit()
    db.refresh(campaign)
    return campaign

@router.post("/{campaign_id}/send-now")
async def send_campaign_now(
    campaign_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == context.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.QUEUED.value
    db.commit()

    # Enqueue to Redis
    queue = RedisQueue("queue:campaigns")
    queue.enqueue(json.dumps({"campaign_id": campaign.id, "organization_id": context.organization_id}))

    # Also directly process in background task if running in lightweight single-process mode
    import asyncio
    asyncio.create_task(CampaignWorker.process_campaign_batch(campaign.id))

    return {"status": "QUEUED", "message": "Campaign dispatched to sending queue", "campaign_id": campaign.id}

@router.post("/{campaign_id}/pause")
def pause_campaign(
    campaign_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == context.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = CampaignStatus.PAUSED.value
    db.commit()
    return {"status": "PAUSED"}

@router.post("/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == context.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = CampaignStatus.RUNNING.value
    db.commit()
    
    import asyncio
    asyncio.create_task(CampaignWorker.process_campaign_batch(campaign.id))
    return {"status": "RESUMED"}

@router.post("/{campaign_id}/cancel")
def cancel_campaign(
    campaign_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == context.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.status = CampaignStatus.CANCELLED.value
    db.commit()
    return {"status": "CANCELLED"}


@router.get("/{campaign_id}")
def get_campaign_detail(
    campaign_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == context.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    contacts = db.query(CampaignContact).filter(
        CampaignContact.campaign_id == campaign_id
    ).all()

    recipient_details = []
    for cc in contacts:
        c = cc.contact
        recipient_details.append({
            "id": cc.id,
            "contact_id": cc.contact_id,
            "name": c.name if c else "Unknown",
            "phone": c.phone if c else "—",
            "status": cc.status,
            "error_message": cc.error_message,
            "sent_at": cc.sent_at.isoformat() if cc.sent_at else None,
        })

    # Resolve message content
    message_content = ""
    template_name = None
    if campaign.template_id:
        tmpl = db.query(Template).filter(Template.id == campaign.template_id).first()
        if tmpl:
            message_content = tmpl.content
            template_name = tmpl.name
    elif campaign.variables_mapping and isinstance(campaign.variables_mapping, dict):
        message_content = campaign.variables_mapping.get("custom_text", "")

    media_url = None
    if campaign.variables_mapping and isinstance(campaign.variables_mapping, dict):
        media_url = campaign.variables_mapping.get("media_url")

    # Determine message type
    msg_type = "TEXT"
    if media_url:
        is_img = any(media_url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"])
        msg_type = "IMAGE" if is_img else "DOCUMENT"

    return {
        "id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "message_type": msg_type,
        "message_content": message_content,
        "media_url": media_url,
        "template_name": template_name,
        "total_recipients": campaign.total_recipients,
        "sent_count": campaign.sent_count,
        "failed_count": campaign.failed_count,
        "rate_limit_per_second": campaign.rate_limit_per_second,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "variables_mapping": campaign.variables_mapping,
        "recipients": recipient_details,
    }


@router.post("/{campaign_id}/retry-failed")
async def retry_failed_campaign(
    campaign_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == context.organization_id
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    failed_contacts = db.query(CampaignContact).filter(
        CampaignContact.campaign_id == campaign_id,
        CampaignContact.status == MessageStatus.FAILED.value
    ).all()

    if not failed_contacts:
        return {"status": "NO_FAILED", "message": "No failed recipients found for this campaign."}

    # Reset failed contacts to QUEUED
    for fc in failed_contacts:
        fc.status = MessageStatus.QUEUED.value
        fc.error_message = None
        fc.sent_at = None

    campaign.status = CampaignStatus.QUEUED.value
    db.commit()

    import asyncio
    asyncio.create_task(CampaignWorker.process_campaign_batch(campaign.id))

    return {
        "status": "QUEUED",
        "message": f"Retrying {len(failed_contacts)} failed recipients in background.",
        "retried_count": len(failed_contacts)
    }



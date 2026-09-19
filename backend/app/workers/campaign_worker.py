import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Campaign, CampaignContact, Contact, Template, WhatsAppInstance, Message, MessageDirection, MessageType, MessageStatus, CampaignStatus
from app.services.template_service import TemplateService
from app.integrations.evolution import get_whatsapp_provider

logger = logging.getLogger("campaign_worker")

class CampaignWorker:
    @staticmethod
    async def process_campaign_batch(campaign_id: str, db: Optional[Session] = None):
        """Processes recipients for a campaign with rate limiting and idempotency."""
        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True

        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign or campaign.status in [CampaignStatus.CANCELLED.value, CampaignStatus.PAUSED.value]:
                logger.info("Campaign %s not eligible for processing (Status: %s)", campaign_id, campaign.status if campaign else 'None')
                return

            campaign.status = CampaignStatus.RUNNING.value
            db.commit()

            template = db.query(Template).filter(Template.id == campaign.template_id).first()
            instance = db.query(WhatsAppInstance).filter(WhatsAppInstance.id == campaign.whatsapp_instance_id).first()
            instance_name = instance.instance_name if instance else "default"
            whatsapp_provider = get_whatsapp_provider()

            # Query queued campaign contacts
            contacts_to_send = db.query(CampaignContact).filter(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.status == MessageStatus.QUEUED.value
            ).limit(500).all()

            rate_delay = 1.0 / max(1, campaign.rate_limit_per_second or 5)

            for cc in contacts_to_send:
                # Refresh status check
                db.refresh(campaign)
                if campaign.status in [CampaignStatus.PAUSED.value, CampaignStatus.CANCELLED.value]:
                    logger.info("Campaign %s was %s during batch execution.", campaign_id, campaign.status)
                    break

                contact = cc.contact
                if not contact:
                    cc.status = MessageStatus.FAILED.value
                    cc.error_message = "Contact record missing"
                    campaign.failed_count += 1
                    db.commit()
                    continue

                # Variable replacement
                contact_data = {
                    "name": contact.name or "Friend",
                    "phone": contact.phone,
                    "email": contact.email or "",
                    "custom_fields": contact.custom_fields or {}
                }

                raw_content = ""
                if template:
                    raw_content = template.content
                elif campaign.variables_mapping and isinstance(campaign.variables_mapping, dict) and "custom_text" in campaign.variables_mapping:
                    raw_content = campaign.variables_mapping.get("custom_text", "")

                rendered_text = TemplateService.render_template(
                    raw_content,
                    contact_data,
                    campaign.variables_mapping
                ) if raw_content else ""

                # Check if this campaign has media attached
                media_url = None
                if campaign.variables_mapping and isinstance(campaign.variables_mapping, dict):
                    media_url = campaign.variables_mapping.get("media_url")
                
                if not media_url and template and template.media_id:
                    from app.models.models import Media
                    med_obj = db.query(Media).filter(Media.id == template.media_id).first()
                    if med_obj:
                        media_url = med_obj.public_url

                try:
                    # WhatsApp API dispatch: Text, Image, or Document
                    if media_url:
                        full_url = media_url if media_url.startswith("http") else f"http://127.0.0.1:8000{media_url}"
                        is_img = any(full_url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"])
                        
                        if is_img:
                            resp = await whatsapp_provider.send_image(
                                instance_name=instance_name,
                                to_number=contact.phone,
                                image_url=full_url,
                                caption=rendered_text if rendered_text else None
                            )
                        else:
                            filename = media_url.split("/")[-1] if "/" in media_url else "document"
                            resp = await whatsapp_provider.send_document(
                                instance_name=instance_name,
                                to_number=contact.phone,
                                document_url=full_url,
                                filename=filename,
                                caption=rendered_text if rendered_text else None
                            )
                    else:
                        resp = await whatsapp_provider.send_text(
                            instance_name=instance_name,
                            to_number=contact.phone,
                            message=rendered_text or "Hello"
                        )
                    
                    provider_msg_id = resp.get("key", {}).get("id") if isinstance(resp, dict) else None

                    cc.status = MessageStatus.SENT.value
                    cc.sent_at = datetime.now(timezone.utc)
                    campaign.sent_count += 1

                    # Persist message record with accurate type
                    final_msg_type = MessageType.TEXT.value
                    if media_url:
                        final_msg_type = MessageType.IMAGE.value if is_img else MessageType.DOCUMENT.value

                    msg = Message(
                        organization_id=campaign.organization_id,
                        conversation_id=None,
                        contact_id=contact.id,
                        campaign_id=campaign.id,
                        whatsapp_instance_id=campaign.whatsapp_instance_id,
                        direction=MessageDirection.OUTBOUND.value,
                        message_type=final_msg_type,
                        content=rendered_text if rendered_text else (media_url.split("/")[-1] if media_url and "/" in media_url else "Attachment"),
                        media_url=media_url,
                        provider_message_id=provider_msg_id,
                        idempotency_key=cc.idempotency_key,
                        status=MessageStatus.SENT.value,
                        sent_at=datetime.now(timezone.utc)
                    )
                    db.add(msg)

                except Exception as e:
                    logger.error(f"Error sending message to {contact.phone}: {e}")
                    err_msg = str(e)
                    # If bridge encountered transient detached frame or connection error, retry once
                    if any(phrase in err_msg for phrase in ["detached Frame", "Target closed", "500", "Session closed", "Execution context"]):
                        logger.info(f"Triggering bridge recovery and retry for {contact.phone}...")
                        try:
                            await whatsapp_provider.reconnect_instance(instance_name)
                            await asyncio.sleep(4.0)
                            if media_url:
                                if is_img:
                                    resp = await whatsapp_provider.send_image(
                                        instance_name=instance_name,
                                        to_number=contact.phone,
                                        image_url=full_url,
                                        caption=rendered_text if rendered_text else None
                                    )
                                else:
                                    resp = await whatsapp_provider.send_document(
                                        instance_name=instance_name,
                                        to_number=contact.phone,
                                        document_url=full_url,
                                        filename=filename,
                                        caption=rendered_text if rendered_text else None
                                    )
                            else:
                                resp = await whatsapp_provider.send_text(
                                    instance_name=instance_name,
                                    to_number=contact.phone,
                                    message=rendered_text or "Hello"
                                )
                            provider_msg_id = resp.get("key", {}).get("id") if isinstance(resp, dict) else None
                            cc.status = MessageStatus.SENT.value
                            cc.sent_at = datetime.now(timezone.utc)
                            campaign.sent_count += 1
                            db.commit()
                            continue
                        except Exception as retry_err:
                            logger.error(f"Retry attempt failed for {contact.phone}: {retry_err}")
                            err_msg = str(retry_err)

                    cc.status = MessageStatus.FAILED.value
                    cc.error_message = err_msg
                    campaign.failed_count += 1

                db.commit()
                # Humanized safe delay (3 to 6s) to prevent WhatsApp bans
                import random
                await asyncio.sleep(random.uniform(3.0, 6.0))

            # Check if all completed
            remaining = db.query(CampaignContact).filter(
                CampaignContact.campaign_id == campaign_id,
                CampaignContact.status.in_([MessageStatus.QUEUED.value, MessageStatus.SENDING.value])
            ).count()

            if remaining == 0:
                campaign.status = CampaignStatus.COMPLETED.value
                db.commit()

        except Exception as e:
            logger.error(f"Error in CampaignWorker for campaign {campaign_id}: {e}")
        finally:
            if close_session:
                db.close()

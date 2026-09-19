import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import (
    Conversation, Message, AIAgent, KnowledgeDocument, 
    AIRun, AIToolCall, Escalation, EscalationStatus,
    AIMode, MessageDirection, MessageType, MessageStatus
)
from app.integrations.ai import get_ai_provider
from app.integrations.ai.tools import ToolExecutor, AVAILABLE_TOOLS_METADATA
from app.integrations.evolution import get_whatsapp_provider
from app.core.redis_client import get_redis_client

logger = logging.getLogger("ai_service")

class AIService:
    @staticmethod
    async def process_inbound_message(
        db: Session,
        organization_id: str,
        conversation_id: str,
        inbound_message_id: str
    ) -> Optional[Message]:
        """
        Orchestrates AI reply pipeline for incoming messages.
        Enforces strict HUMAN_ACTIVE check, tool execution, and message dispatch.
        """
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id
        ).first()

        if not conversation:
            logger.warning("Conversation %s not found in org %s", conversation_id, organization_id)
            return None

        # CRITICAL RULE: If HUMAN_ACTIVE, AI MUST NOT SEND AUTOMATIC RESPONSES!
        if conversation.ai_mode == AIMode.HUMAN_ACTIVE.value:
            logger.info("Conversation %s is HUMAN_ACTIVE. AI response suppressed.", conversation_id)
            return None

        # Fetch active AI agent for organization
        agent = db.query(AIAgent).filter(
            AIAgent.organization_id == organization_id,
            AIAgent.status == "ACTIVE"
        ).first()

        if not agent:
            # Fallback default agent configuration
            system_prompt = "You are a helpful WhatsApp assistant for our business."
            allowed_tools = ["get_customer_details", "get_business_hours", "check_availability", "create_lead", "handoff_to_human"]
        else:
            system_prompt = agent.system_prompt
            if agent.business_description:
                system_prompt += f"\nBusiness Overview: {agent.business_description}"
            allowed_tools = agent.allowed_tools or []

        # Load recent conversation history (last 10 messages)
        recent_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.organization_id == organization_id
        ).order_by(Message.created_at.asc()).limit(10).all()

        formatted_history = []
        for m in recent_messages:
            role = "assistant" if m.direction == MessageDirection.OUTBOUND.value else "user"
            formatted_history.append({"role": role, "content": m.content or ""})

        # Load knowledge base context
        knowledge_docs = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.organization_id == organization_id
        ).limit(5).all()
        knowledge_context = "\n".join([f"[{d.title}]: {d.content}" for d in knowledge_docs]) if knowledge_docs else ""

        # Filter available tools by allowed_tools
        active_tools = [t for t in AVAILABLE_TOOLS_METADATA if t["name"] in allowed_tools]

        # Call AI provider
        ai_provider = get_ai_provider()
        ai_result = await ai_provider.generate_response(
            system_prompt=system_prompt,
            messages=formatted_history,
            tools=active_tools,
            context_knowledge=knowledge_context
        )

        # Log AI Run
        ai_run = AIRun(
            organization_id=organization_id,
            conversation_id=conversation_id,
            inbound_message_id=inbound_message_id,
            prompt_tokens=20,
            completion_tokens=ai_result.tokens_used,
            total_tokens=ai_result.tokens_used + 20,
            latency_ms=ai_result.latency_ms,
            status="SUCCESS"
        )
        db.add(ai_run)
        db.flush()

        # Execute Tool Calls if any
        tool_executor = ToolExecutor(db, organization_id, conversation_id, conversation.contact_id)
        for tc in ai_result.tool_calls:
            tool_output = tool_executor.execute_tool(tc.name, tc.arguments, allowed_tools)
            db.add(AIToolCall(
                organization_id=organization_id,
                ai_run_id=ai_run.id,
                tool_name=tc.name,
                input_arguments=tc.arguments,
                output_result=tool_output,
                is_success="error" not in tool_output
            ))

        # Check escalation
        if ai_result.should_escalate or conversation.ai_mode == AIMode.HUMAN_REQUESTED.value:
            conversation.ai_mode = AIMode.HUMAN_REQUESTED.value
            existing_esc = db.query(Escalation).filter(
                Escalation.conversation_id == conversation_id,
                Escalation.status == EscalationStatus.PENDING.value
            ).first()
            if not existing_esc:
                db.add(Escalation(
                    organization_id=organization_id,
                    conversation_id=conversation_id,
                    reason=ai_result.escalation_reason or "Customer requested human support",
                    status=EscalationStatus.PENDING.value
                ))

        db.commit()

        # If a response message was generated, send it via WhatsAppProvider
        if ai_result.content:
            whatsapp_provider = get_whatsapp_provider()
            instance = conversation.whatsapp_instance
            instance_name = instance.instance_name if instance else "default"
            contact_phone = conversation.contact.phone if conversation.contact else "unknown"

            # Create outbound message in database
            outbound_msg = Message(
                organization_id=organization_id,
                conversation_id=conversation_id,
                contact_id=conversation.contact_id,
                whatsapp_instance_id=instance.id if instance else None,
                direction=MessageDirection.OUTBOUND.value,
                message_type=MessageType.TEXT.value,
                content=ai_result.content,
                status=MessageStatus.SENT.value
            )
            db.add(outbound_msg)
            conversation.last_message_at = outbound_msg.created_at
            db.commit()
            db.refresh(outbound_msg)

            # Send via WhatsApp provider
            try:
                await whatsapp_provider.send_text(instance_name, contact_phone, ai_result.content)
            except Exception as e:
                logger.error(f"Failed to dispatch WhatsApp message: {e}")
                outbound_msg.status = MessageStatus.FAILED.value
                outbound_msg.error_message = str(e)
                db.commit()

            return outbound_msg

        return None

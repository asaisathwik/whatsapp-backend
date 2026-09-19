from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.models import Contact, AIAgent, Escalation, EscalationStatus, Conversation, AIMode

AVAILABLE_TOOLS_METADATA = [
    {
        "name": "get_customer_details",
        "description": "Retrieves the current customer profile, name, phone, email, and custom fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Customer phone number (optional if in context)"}
            },
            "required": []
        }
    },
    {
        "name": "get_business_hours",
        "description": "Returns company working hours and availability status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "check_availability",
        "description": "Checks availability for booking or appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "service": {"type": "string", "description": "Service name"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "create_lead",
        "description": "Records customer interest and creates/updates lead information.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Lead full name"},
                "requirement": {"type": "string", "description": "Customer requirements"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "handoff_to_human",
        "description": "Escalates the conversation to a human support agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for human escalation"}
            },
            "required": ["reason"]
        }
    }
]

class ToolExecutor:
    def __init__(self, db: Session, organization_id: str, conversation_id: str, contact_id: str):
        self.db = db
        self.organization_id = organization_id
        self.conversation_id = conversation_id
        self.contact_id = contact_id

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], allowed_tools: List[str]) -> Dict[str, Any]:
        if tool_name not in allowed_tools:
            return {"error": f"Tool '{tool_name}' is not authorized for this AI agent."}

        handler = getattr(self, f"_tool_{tool_name}", None)
        if not handler:
            return {"error": f"Tool '{tool_name}' implementation not found."}

        try:
            return handler(arguments)
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def _tool_get_customer_details(self, args: Dict[str, Any]) -> Dict[str, Any]:
        contact = self.db.query(Contact).filter(
            Contact.id == self.contact_id,
            Contact.organization_id == self.organization_id
        ).first()
        if not contact:
            return {"found": False, "message": "Contact not found"}
        return {
            "found": True,
            "name": contact.name,
            "phone": contact.phone,
            "email": contact.email,
            "custom_fields": contact.custom_fields,
            "status": contact.status
        }

    def _tool_get_business_hours(self, args: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.db.query(AIAgent).filter(
            AIAgent.organization_id == self.organization_id,
            AIAgent.is_default == True
        ).first()
        hours = agent.working_hours if agent and agent.working_hours else {
            "monday_friday": "09:00 AM - 06:00 PM",
            "saturday": "10:00 AM - 02:00 PM",
            "sunday": "Closed",
            "timezone": "Asia/Kolkata"
        }
        return {"business_hours": hours}

    def _tool_check_availability(self, args: Dict[str, Any]) -> Dict[str, Any]:
        date = args.get("date", "Today")
        service = args.get("service", "General Consultation")
        return {
            "date": date,
            "service": service,
            "available_slots": ["10:00 AM", "02:00 PM", "04:30 PM"],
            "status": "AVAILABLE"
        }

    def _tool_create_lead(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        req = args.get("requirement", "Interested in services")
        contact = self.db.query(Contact).filter(
            Contact.id == self.contact_id,
            Contact.organization_id == self.organization_id
        ).first()
        if contact:
            contact.custom_fields = {**(contact.custom_fields or {}), "lead_requirement": req}
            self.db.commit()
        return {"success": True, "lead_status": "RECORDED", "name": name, "requirement": req}

    def _tool_handoff_to_human(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reason = args.get("reason", "Requested by user")
        conversation = self.db.query(Conversation).filter(
            Conversation.id == self.conversation_id,
            Conversation.organization_id == self.organization_id
        ).first()
        if conversation:
            conversation.ai_mode = AIMode.HUMAN_REQUESTED.value
            escalation = Escalation(
                organization_id=self.organization_id,
                conversation_id=self.conversation_id,
                reason=reason,
                status=EscalationStatus.PENDING.value
            )
            self.db.add(escalation)
            self.db.commit()
        return {"success": True, "escalated": True, "reason": reason}

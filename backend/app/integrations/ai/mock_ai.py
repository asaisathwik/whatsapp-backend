import time
from typing import List, Dict, Any, Optional
from app.integrations.ai.provider import AIProvider, AICompletionResult, ToolCallDefinition

class MockAIProvider(AIProvider):
    async def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        context_knowledge: Optional[str] = None,
        temperature: float = 0.7
    ) -> AICompletionResult:
        start_time = time.time()
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "").lower()
                break

        tool_calls = []
        should_escalate = False
        escalation_reason = None
        response_text = ""

        # Escalation trigger keywords
        escalate_keywords = ["human", "agent", "person", "representative", "support", "talk to human", "complaint"]
        if any(kw in last_user_msg for kw in escalate_keywords):
            should_escalate = True
            escalation_reason = "Customer explicitly requested a human agent"
            tool_calls.append(ToolCallDefinition(name="handoff_to_human", arguments={"reason": escalation_reason}))
            response_text = "I am transferring you to a human agent right now. An agent will be with you shortly."

        # Hours query trigger
        elif "hour" in last_user_msg or "timing" in last_user_msg or "open" in last_user_msg:
            tool_calls.append(ToolCallDefinition(name="get_business_hours", arguments={}))
            response_text = "Our standard working hours are Monday to Friday from 9:00 AM to 6:00 PM, and Saturday 10:00 AM to 2:00 PM."

        # Booking / availability query trigger
        elif "book" in last_user_msg or "slot" in last_user_msg or "appointment" in last_user_msg or "available" in last_user_msg:
            tool_calls.append(ToolCallDefinition(name="check_availability", arguments={"date": "Tomorrow", "service": "Consultation"}))
            response_text = "We have slots available tomorrow at 10:00 AM, 02:00 PM, and 04:30 PM. Would you like me to book one for you?"

        # Pricing or service inquiry
        elif "price" in last_user_msg or "cost" in last_user_msg or "plan" in last_user_msg:
            response_text = "We offer Starter, Professional, and Enterprise plans tailored to your WhatsApp automation needs. Would you like a personalized quote?"

        # Greeting
        elif any(g in last_user_msg for g in ["hi", "hello", "hey", "good morning", "good evening"]):
            response_text = "Hello! 👋 Welcome! How can I assist you with your business queries today?"

        else:
            if context_knowledge:
                response_text = f"Based on our catalog: {context_knowledge[:100]}... How can I assist you further?"
            else:
                response_text = f"Thank you for reaching out. We have received your message: '{last_user_msg}'. How can I help you today?"

        latency = int((time.time() - start_time) * 1000)
        return AICompletionResult(
            content=response_text,
            tool_calls=tool_calls,
            tokens_used=len(response_text.split()) + 30,
            latency_ms=latency,
            should_escalate=should_escalate,
            escalation_reason=escalation_reason
        )

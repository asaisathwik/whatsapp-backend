from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ToolCallDefinition(BaseModel):
    name: str
    arguments: Dict[str, Any]

class AICompletionResult(BaseModel):
    content: Optional[str] = None
    tool_calls: List[ToolCallDefinition] = []
    tokens_used: int = 0
    latency_ms: int = 0
    should_escalate: bool = False
    escalation_reason: Optional[str] = None

class AIProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        context_knowledge: Optional[str] = None,
        temperature: float = 0.7
    ) -> AICompletionResult:
        """Generate response or tool calls given message history and context."""
        pass

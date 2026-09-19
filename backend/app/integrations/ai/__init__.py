from app.core.config import settings
from app.integrations.ai.provider import AIProvider
from app.integrations.ai.mock_ai import MockAIProvider

_ai_instance = None

def get_ai_provider() -> AIProvider:
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = MockAIProvider()
    return _ai_instance

import httpx
from app.core.config import settings
from app.integrations.evolution.provider import WhatsAppProvider
from app.integrations.evolution.evolution_api import EvolutionApiProvider
from app.integrations.evolution.mock_provider import EvolutionApiMockProvider

BRIDGE_URL = "http://127.0.0.1:8001"

# Singletons
_evolution_instance = None
_bridge_instance = None
_mock_instance = None


def _is_bridge_running() -> bool:
    """Quick check (≤2s) whether the local whatsapp-bridge is alive."""
    try:
        with httpx.Client(timeout=1.5) as client:
            r = client.get(f"{BRIDGE_URL}/health")
            return r.status_code == 200
    except Exception:
        return False


def get_whatsapp_provider() -> WhatsAppProvider:
    global _evolution_instance, _bridge_instance, _mock_instance

    if not settings.EVOLUTION_USE_MOCK:
        if _evolution_instance is None:
            _evolution_instance = EvolutionApiProvider()
        return _evolution_instance

    # Always check bridge freshly (fast local HTTP call)
    if _is_bridge_running():
        if _bridge_instance is None:
            from app.integrations.evolution.bridge_provider import WhatsAppBridgeProvider
            _bridge_instance = WhatsAppBridgeProvider()
        # Reset mock cache so next switch back works cleanly
        _mock_instance = None
        return _bridge_instance

    # Bridge not running — use mock
    # Reset bridge cache so when bridge starts we get a fresh instance
    _bridge_instance = None
    if _mock_instance is None:
        _mock_instance = EvolutionApiMockProvider()
    return _mock_instance

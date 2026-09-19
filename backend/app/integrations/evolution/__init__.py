import httpx
from app.core.config import settings
from app.integrations.evolution.provider import WhatsAppProvider
from app.integrations.evolution.mock_provider import EvolutionApiMockProvider

# Singletons
_bridge_instance = None
_mock_instance = None


def get_bridge_base_url() -> str:
    url = settings.EVOLUTION_API_URL or "http://127.0.0.1:8001"
    return url.rstrip("/")


def _is_bridge_running() -> bool:
    """Quick check (<=3s) whether the whatsapp-bridge is alive."""
    try:
        bridge_url = get_bridge_base_url()
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{bridge_url}/health")
            return r.status_code == 200
    except Exception:
        return False


def get_whatsapp_provider() -> WhatsAppProvider:
    global _bridge_instance, _mock_instance

    # If mock is explicitly requested AND bridge is not reachable
    if settings.EVOLUTION_USE_MOCK and not _is_bridge_running():
        if _mock_instance is None:
            _mock_instance = EvolutionApiMockProvider()
        return _mock_instance

    # Default to WhatsAppBridgeProvider with dynamic URL
    from app.integrations.evolution.bridge_provider import WhatsAppBridgeProvider
    base_url = get_bridge_base_url()
    if _bridge_instance is None or getattr(_bridge_instance, "base_url", None) != base_url:
        _bridge_instance = WhatsAppBridgeProvider(base_url=base_url)
    return _bridge_instance

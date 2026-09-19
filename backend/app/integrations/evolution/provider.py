from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class WhatsAppProvider(ABC):
    @abstractmethod
    async def create_instance(self, instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Create a new WhatsApp instance on the provider."""
        pass

    @abstractmethod
    async def connect_instance(self, instance_name: str) -> Dict[str, Any]:
        """Initiate connection or QR generation for an instance."""
        pass

    @abstractmethod
    async def get_instance_status(self, instance_name: str) -> Dict[str, Any]:
        """Fetch real-time state: CONNECTED, CONNECTING, DISCONNECTED, QR_READY."""
        pass

    @abstractmethod
    async def get_qr_code(self, instance_name: str) -> Dict[str, Any]:
        """Get base64 QR code representation or pairing code."""
        pass

    @abstractmethod
    async def disconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        """Disconnect WhatsApp instance."""
        pass

    @abstractmethod
    async def reconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        """Reconnect WhatsApp instance."""
        pass

    @abstractmethod
    async def send_text(self, instance_name: str, to_number: str, message: str) -> Dict[str, Any]:
        """Send a plain text message."""
        pass

    @abstractmethod
    async def send_image(self, instance_name: str, to_number: str, image_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """Send an image message."""
        pass

    @abstractmethod
    async def send_video(self, instance_name: str, to_number: str, video_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """Send a video message."""
        pass

    @abstractmethod
    async def send_document(self, instance_name: str, to_number: str, document_url: str, filename: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """Send a document (PDF, Excel, doc)."""
        pass

    @abstractmethod
    async def send_audio(self, instance_name: str, to_number: str, audio_url: str) -> Dict[str, Any]:
        """Send an audio message."""
        pass

    @abstractmethod
    async def send_location(self, instance_name: str, to_number: str, latitude: float, longitude: float, name: str, address: str) -> Dict[str, Any]:
        """Send a location pin."""
        pass

    @abstractmethod
    async def register_webhook(self, instance_name: str, webhook_url: str) -> Dict[str, Any]:
        """Configure webhook callback URL on the provider."""
        pass

    @abstractmethod
    async def get_message_status(self, instance_name: str, message_id: str) -> Dict[str, Any]:
        """Fetch delivery/read status of a specific message."""
        pass

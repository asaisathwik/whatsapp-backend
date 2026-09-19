import httpx
from typing import Dict, Any, Optional
from app.integrations.evolution.provider import WhatsAppProvider
from app.core.config import settings

class EvolutionApiProvider(WhatsAppProvider):
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or settings.EVOLUTION_API_URL).rstrip("/")
        self.api_key = api_key or settings.EVOLUTION_API_KEY
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, headers=self.headers, json=json)
            response.raise_for_status()
            return response.json()

    async def create_instance(self, instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "instanceName": instance_name,
            "token": "",
            "qrcode": True,
            "webhook": webhook_url
        }
        return await self._request("POST", "/instance/create", payload)

    async def connect_instance(self, instance_name: str) -> Dict[str, Any]:
        return await self._request("GET", f"/instance/connect/{instance_name}")

    async def get_instance_status(self, instance_name: str) -> Dict[str, Any]:
        return await self._request("GET", f"/instance/connectionState/{instance_name}")

    async def get_qr_code(self, instance_name: str) -> Dict[str, Any]:
        return await self._request("GET", f"/instance/connect/{instance_name}")

    async def disconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"/instance/logout/{instance_name}")

    async def reconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        return await self._request("POST", f"/instance/restart/{instance_name}")

    async def send_text(self, instance_name: str, to_number: str, message: str) -> Dict[str, Any]:
        payload = {
            "number": to_number,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "textMessage": {
                "text": message
            }
        }
        return await self._request("POST", f"/message/sendText/{instance_name}", payload)

    async def send_image(self, instance_name: str, to_number: str, image_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "number": to_number,
            "mediaMessage": {
                "mediatype": "image",
                "caption": caption or "",
                "media": image_url
            }
        }
        return await self._request("POST", f"/message/sendMedia/{instance_name}", payload)

    async def send_video(self, instance_name: str, to_number: str, video_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "number": to_number,
            "mediaMessage": {
                "mediatype": "video",
                "caption": caption or "",
                "media": video_url
            }
        }
        return await self._request("POST", f"/message/sendMedia/{instance_name}", payload)

    async def send_document(self, instance_name: str, to_number: str, document_url: str, filename: str, caption: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "number": to_number,
            "mediaMessage": {
                "mediatype": "document",
                "fileName": filename,
                "caption": caption or "",
                "media": document_url
            }
        }
        return await self._request("POST", f"/message/sendMedia/{instance_name}", payload)

    async def send_audio(self, instance_name: str, to_number: str, audio_url: str) -> Dict[str, Any]:
        payload = {
            "number": to_number,
            "audioMessage": {
                "audio": audio_url
            }
        }
        return await self._request("POST", f"/message/sendWhatsAppAudio/{instance_name}", payload)

    async def send_location(self, instance_name: str, to_number: str, latitude: float, longitude: float, name: str, address: str) -> Dict[str, Any]:
        payload = {
            "number": to_number,
            "locationMessage": {
                "latitude": latitude,
                "longitude": longitude,
                "name": name,
                "address": address
            }
        }
        return await self._request("POST", f"/message/sendLocation/{instance_name}", payload)

    async def register_webhook(self, instance_name: str, webhook_url: str) -> Dict[str, Any]:
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "events": [
                    "QRCODE_UPDATED",
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE",
                    "SEND_MESSAGE",
                    "CONNECTION_UPDATE"
                ]
            }
        }
        return await self._request("POST", f"/webhook/set/{instance_name}", payload)

    async def get_message_status(self, instance_name: str, message_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/chat/findMessages/{instance_name}?id={message_id}")

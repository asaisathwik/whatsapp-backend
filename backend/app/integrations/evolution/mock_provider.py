import uuid
import io
import base64
from typing import Dict, Any, Optional
from app.integrations.evolution.provider import WhatsAppProvider

def _generate_qr_base64(data: str) -> str:
    """Generate a real scannable QR code and return as base64 data URI."""
    try:
        import qrcode
        from PIL import Image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        # Fallback: return a minimal valid QR placeholder
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIAAAACAAQMAAAD58POIAAAABlBMVEX///8AAABVwtN+AAAA"


class EvolutionApiMockProvider(WhatsAppProvider):
    def __init__(self):
        self.instances: Dict[str, Dict[str, Any]] = {}
        self.sent_messages: list = []

    async def create_instance(self, instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        # Generate a realistic WhatsApp-style QR payload
        qr_payload = f"whatsapp://qr?instance={instance_name}&id={uuid.uuid4().hex}&ts={uuid.uuid4().hex[:8]}"
        qr_b64 = _generate_qr_base64(qr_payload)
        instance_data = {
            "instance": {
                "instanceName": instance_name,
                "status": "created",
                "webhook": webhook_url
            },
            "hash": {
                "apikey": f"mock_key_{instance_name}"
            },
            "qrcode": {
                "code": qr_payload,
                "base64": qr_b64
            }
        }
        self.instances[instance_name] = instance_data
        return instance_data

    async def connect_instance(self, instance_name: str) -> Dict[str, Any]:
        return {
            "instance": instance_name,
            "status": "open",
            "state": "CONNECTED"
        }

    async def get_instance_status(self, instance_name: str) -> Dict[str, Any]:
        return {
            "instance": {
                "instanceName": instance_name,
                "state": "open",
                "statusReason": 200
            }
        }

    async def get_qr_code(self, instance_name: str) -> Dict[str, Any]:
        qr_payload = f"whatsapp://qr?instance={instance_name}&refresh={uuid.uuid4().hex[:12]}"
        qr_b64 = _generate_qr_base64(qr_payload)
        return {
            "pairingCode": f"{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}",
            "code": qr_payload,
            "base64": qr_b64
        }

    async def disconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        if instance_name in self.instances:
            self.instances[instance_name]["status"] = "close"
        return {"status": "SUCCESS", "message": "Instance disconnected"}

    async def reconnect_instance(self, instance_name: str) -> Dict[str, Any]:
        return {"status": "SUCCESS", "message": "Instance restarted"}

    async def send_text(self, instance_name: str, to_number: str, message: str) -> Dict[str, Any]:
        msg_id = f"MOCK_MSG_{uuid.uuid4().hex[:12]}"
        record = {
            "key": {
                "remoteJid": f"{to_number}@s.whatsapp.net",
                "fromMe": True,
                "id": msg_id
            },
            "message": {"conversation": message},
            "messageTimestamp": 1726000000,
            "status": "PENDING"
        }
        self.sent_messages.append(record)
        return record

    async def send_image(self, instance_name: str, to_number: str, image_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        msg_id = f"MOCK_IMG_{uuid.uuid4().hex[:12]}"
        return {
            "key": {"remoteJid": f"{to_number}@s.whatsapp.net", "fromMe": True, "id": msg_id},
            "message": {"imageMessage": {"url": image_url, "caption": caption}},
            "status": "PENDING"
        }

    async def send_video(self, instance_name: str, to_number: str, video_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        msg_id = f"MOCK_VID_{uuid.uuid4().hex[:12]}"
        return {
            "key": {"remoteJid": f"{to_number}@s.whatsapp.net", "fromMe": True, "id": msg_id},
            "message": {"videoMessage": {"url": video_url, "caption": caption}},
            "status": "PENDING"
        }

    async def send_document(self, instance_name: str, to_number: str, document_url: str, filename: str, caption: Optional[str] = None) -> Dict[str, Any]:
        msg_id = f"MOCK_DOC_{uuid.uuid4().hex[:12]}"
        return {
            "key": {"remoteJid": f"{to_number}@s.whatsapp.net", "fromMe": True, "id": msg_id},
            "message": {"documentMessage": {"url": document_url, "fileName": filename, "caption": caption}},
            "status": "PENDING"
        }

    async def send_audio(self, instance_name: str, to_number: str, audio_url: str) -> Dict[str, Any]:
        msg_id = f"MOCK_AUD_{uuid.uuid4().hex[:12]}"
        return {
            "key": {"remoteJid": f"{to_number}@s.whatsapp.net", "fromMe": True, "id": msg_id},
            "message": {"audioMessage": {"url": audio_url}},
            "status": "PENDING"
        }

    async def send_location(self, instance_name: str, to_number: str, latitude: float, longitude: float, name: str, address: str) -> Dict[str, Any]:
        msg_id = f"MOCK_LOC_{uuid.uuid4().hex[:12]}"
        return {
            "key": {"remoteJid": f"{to_number}@s.whatsapp.net", "fromMe": True, "id": msg_id},
            "message": {"locationMessage": {"degreesLatitude": latitude, "degreesLongitude": longitude, "name": name, "address": address}},
            "status": "PENDING"
        }

    async def register_webhook(self, instance_name: str, webhook_url: str) -> Dict[str, Any]:
        return {"webhook": {"enabled": True, "url": webhook_url}}

    async def get_message_status(self, instance_name: str, message_id: str) -> Dict[str, Any]:
        return {"id": message_id, "status": "DELIVERED"}

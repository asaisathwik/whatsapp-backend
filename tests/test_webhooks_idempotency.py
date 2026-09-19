from app.models.models import WebhookEvent, Message, Conversation

def test_webhook_inbound_and_idempotency(client, org_a_setup, db_session):
    instance_name = org_a_setup["instance"].instance_name
    webhook_payload = {
        "event": "messages.upsert",
        "instance": instance_name,
        "data": {
            "key": {
                "remoteJid": "919876543299@s.whatsapp.net",
                "fromMe": False,
                "id": "EVO_MSG_ID_UNIQUE_999"
            },
            "pushName": "John Doe",
            "message": {
                "conversation": "Hello, what are your business hours?"
            },
            "messageTimestamp": 1726000000
        }
    }

    # 1. First webhook delivery
    resp1 = client.post("/api/v1/webhooks/evolution", json=webhook_payload)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "SUCCESS"

    # Verify conversation & message created
    conv = db_session.query(Conversation).filter(
        Conversation.organization_id == org_a_setup["org"].id
    ).first()
    assert conv is not None

    inbound_msg = db_session.query(Message).filter(
        Message.provider_message_id == "EVO_MSG_ID_UNIQUE_999"
    ).first()
    assert inbound_msg is not None
    assert inbound_msg.content == "Hello, what are your business hours?"

    # 2. Duplicate webhook delivery with the exact same payload
    resp2 = client.post("/api/v1/webhooks/evolution", json=webhook_payload)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "DUPLICATE_IGNORED"

    # Verify NO duplicate message was created in database
    msg_count = db_session.query(Message).filter(
        Message.provider_message_id == "EVO_MSG_ID_UNIQUE_999"
    ).count()
    assert msg_count == 1  # Strictly 1, duplicate prevented!

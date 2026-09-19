import pytest
from app.models.models import Contact, Conversation, Message, AIMode, MessageDirection, MessageStatus
from app.services.ai_service import AIService

@pytest.mark.asyncio
async def test_ai_response_and_human_takeover_lock(client, org_a_setup, db_session):
    org_id = org_a_setup["org"].id

    # 1. Create Contact & Conversation in AI_ACTIVE mode
    contact = Contact(
        organization_id=org_id,
        name="Charlie Customer",
        phone="919876543233"
    )
    db_session.add(contact)
    db_session.flush()

    conv = Conversation(
        organization_id=org_id,
        contact_id=contact.id,
        whatsapp_instance_id=org_a_setup["instance"].id,
        ai_mode=AIMode.AI_ACTIVE.value
    )
    db_session.add(conv)
    db_session.flush()

    inbound_1 = Message(
        organization_id=org_id,
        conversation_id=conv.id,
        contact_id=contact.id,
        direction=MessageDirection.INBOUND.value,
        content="What are your business hours?",
        status=MessageStatus.DELIVERED.value
    )
    db_session.add(inbound_1)
    db_session.commit()

    # Process via AI Service when AI_ACTIVE
    ai_msg_1 = await AIService.process_inbound_message(
        db=db_session,
        organization_id=org_id,
        conversation_id=conv.id,
        inbound_message_id=inbound_1.id
    )
    assert ai_msg_1 is not None
    assert "working hours" in ai_msg_1.content.lower()

    # 2. Human Takeover via API
    takeover_resp = client.post(
        f"/api/v1/conversations/{conv.id}/takeover",
        json={"reason": "Agent intervening for VIP customer"},
        headers=org_a_setup["headers"]
    )
    assert takeover_resp.status_code == 200
    assert takeover_resp.json()["ai_mode"] == AIMode.HUMAN_ACTIVE.value

    # Refresh conversation state
    db_session.refresh(conv)
    assert conv.ai_mode == AIMode.HUMAN_ACTIVE.value

    # 3. New inbound message arrives while HUMAN_ACTIVE
    inbound_2 = Message(
        organization_id=org_id,
        conversation_id=conv.id,
        contact_id=contact.id,
        direction=MessageDirection.INBOUND.value,
        content="Are you still there?",
        status=MessageStatus.DELIVERED.value
    )
    db_session.add(inbound_2)
    db_session.commit()

    # CRITICAL VERIFICATION: AI MUST NOT RESPOND DURING HUMAN_ACTIVE!
    ai_msg_suppressed = await AIService.process_inbound_message(
        db=db_session,
        organization_id=org_id,
        conversation_id=conv.id,
        inbound_message_id=inbound_2.id
    )
    assert ai_msg_suppressed is None  # Proves AI is strictly blocked from auto-responding during HUMAN_ACTIVE!

    # 4. Human Agent manually sends message
    send_resp = client.post(
        f"/api/v1/conversations/{conv.id}/messages",
        json={"content": "Hi Charlie, I am your dedicated human specialist. How can I help?"},
        headers=org_a_setup["headers"]
    )
    assert send_resp.status_code == 200
    agent_msg = send_resp.json()
    assert agent_msg["direction"] == MessageDirection.OUTBOUND.value

    # 5. Release conversation back to AI
    release_resp = client.post(
        f"/api/v1/conversations/{conv.id}/release-to-ai",
        headers=org_a_setup["headers"]
    )
    assert release_resp.status_code == 200
    assert release_resp.json()["ai_mode"] == AIMode.AI_RESUMED.value

    db_session.refresh(conv)
    assert conv.ai_mode == AIMode.AI_RESUMED.value

    # 6. Customer sends new message after release -> AI responds again
    inbound_3 = Message(
        organization_id=org_id,
        conversation_id=conv.id,
        contact_id=contact.id,
        direction=MessageDirection.INBOUND.value,
        content="Thanks! Can I check pricing plans?",
        status=MessageStatus.DELIVERED.value
    )
    db_session.add(inbound_3)
    db_session.commit()

    ai_msg_resumed = await AIService.process_inbound_message(
        db=db_session,
        organization_id=org_id,
        conversation_id=conv.id,
        inbound_message_id=inbound_3.id
    )
    assert ai_msg_resumed is not None
    assert "plan" in ai_msg_resumed.content.lower() or "price" in ai_msg_resumed.content.lower()

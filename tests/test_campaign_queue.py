import pytest
from app.models.models import Contact, Template, Campaign, CampaignStatus, Message, MessageStatus
from app.workers.campaign_worker import CampaignWorker

@pytest.mark.asyncio
async def test_campaign_queue_and_worker_dispatch(client, org_a_setup, db_session):
    org_id = org_a_setup["org"].id

    # Create Template
    template = Template(
        organization_id=org_id,
        name="Winter Sale",
        content="Hello {{name}}, welcome to our flash sale!"
    )
    db_session.add(template)
    db_session.flush()

    # Create Contacts
    c1 = Contact(organization_id=org_id, name="User One", phone="919876543201")
    c2 = Contact(organization_id=org_id, name="User Two", phone="919876543202")
    db_session.add_all([c1, c2])
    db_session.commit()

    # Create Campaign via API
    payload = {
        "name": "Winter Blast",
        "template_id": template.id,
        "whatsapp_instance_id": org_a_setup["instance"].id,
        "rate_limit_per_second": 100
    }
    create_resp = client.post("/api/v1/campaigns", json=payload, headers=org_a_setup["headers"])
    assert create_resp.status_code == 200
    camp_data = create_resp.json()
    camp_id = camp_data["id"]
    assert camp_data["total_recipients"] == 2

    # Trigger Send Now via API
    send_resp = client.post(f"/api/v1/campaigns/{camp_id}/send-now", headers=org_a_setup["headers"])
    assert send_resp.status_code == 200

    # Process Campaign with Worker using test db session
    await CampaignWorker.process_campaign_batch(camp_id, db=db_session)

    # Verify Campaign status is completed
    campaign = db_session.query(Campaign).filter(Campaign.id == camp_id).first()
    assert campaign.status == CampaignStatus.COMPLETED.value
    assert campaign.sent_count == 2
    assert campaign.failed_count == 0

    # Verify Outbound Messages created
    messages = db_session.query(Message).filter(Message.campaign_id == camp_id).all()
    assert len(messages) == 2
    assert all(m.status == MessageStatus.SENT.value for m in messages)

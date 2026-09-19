from app.models.models import Contact, Template, Campaign, CampaignStatus, Message, Conversation, MessageDirection, MessageType, MessageStatus

def test_tenant_isolation_contacts(client, org_a_setup, org_b_setup, db_session):
    # Create contact in Org A
    contact_a = Contact(
        organization_id=org_a_setup["org"].id,
        name="Alice Contact",
        phone="919876543210"
    )
    # Create contact in Org B
    contact_b = Contact(
        organization_id=org_b_setup["org"].id,
        name="Bob Contact",
        phone="919123456789"
    )
    db_session.add_all([contact_a, contact_b])
    db_session.commit()

    # Org A requests contacts list
    resp_a = client.get("/api/v1/contacts", headers=org_a_setup["headers"])
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    phones_a = [c["phone"] for c in data_a]
    assert "919876543210" in phones_a
    assert "919123456789" not in phones_a  # Proves Org A CANNOT read Org B contacts!

    # Org B requests contacts list
    resp_b = client.get("/api/v1/contacts", headers=org_b_setup["headers"])
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    phones_b = [c["phone"] for c in data_b]
    assert "919123456789" in phones_b
    assert "919876543210" not in phones_b

def test_tenant_isolation_whatsapp_instances(client, org_a_setup, org_b_setup):
    # Org A requests instances
    resp_a = client.get("/api/v1/whatsapp/instances", headers=org_a_setup["headers"])
    assert resp_a.status_code == 200
    names_a = [inst["instance_name"] for inst in resp_a.json()]
    assert "inst_a_main" in names_a
    assert "inst_b_main" not in names_a  # Proves Org A CANNOT access Org B instances!

    # Org A attempts to disconnect Org B's instance
    resp_tamper = client.post(
        f"/api/v1/whatsapp/instances/{org_b_setup['instance'].id}/disconnect",
        headers=org_a_setup["headers"]
    )
    assert resp_tamper.status_code == 404  # Org A cannot access or modify Org B instance

def test_tenant_isolation_campaigns(client, org_a_setup, org_b_setup, db_session):
    # Create template & campaign in Org B
    template_b = Template(
        organization_id=org_b_setup["org"].id,
        name="Org B Promo",
        content="Hello {{name}}"
    )
    db_session.add(template_b)
    db_session.flush()

    camp_b = Campaign(
        organization_id=org_b_setup["org"].id,
        name="Org B Secret Campaign",
        template_id=template_b.id,
        status=CampaignStatus.DRAFT.value
    )
    db_session.add(camp_b)
    db_session.commit()

    # Org A tries to list campaigns
    resp_a = client.get("/api/v1/campaigns", headers=org_a_setup["headers"])
    assert resp_a.status_code == 200
    camp_names_a = [c["name"] for c in resp_a.json()]
    assert "Org B Secret Campaign" not in camp_names_a

    # Org A tries to cancel Org B's campaign
    resp_tamper = client.post(
        f"/api/v1/campaigns/{camp_b.id}/cancel",
        headers=org_a_setup["headers"]
    )
    assert resp_tamper.status_code == 404

def test_tenant_isolation_messages(client, org_a_setup, org_b_setup, db_session):
    # Create conversation and message in Org B
    contact_b = Contact(
        organization_id=org_b_setup["org"].id,
        name="Secret Contact B",
        phone="919999999999"
    )
    db_session.add(contact_b)
    db_session.flush()

    conv_b = Conversation(
        organization_id=org_b_setup["org"].id,
        contact_id=contact_b.id,
        whatsapp_instance_id=org_b_setup["instance"].id
    )
    db_session.add(conv_b)
    db_session.flush()

    msg_b = Message(
        organization_id=org_b_setup["org"].id,
        conversation_id=conv_b.id,
        contact_id=contact_b.id,
        direction=MessageDirection.INBOUND.value,
        content="Confidential message for Org B",
        status=MessageStatus.DELIVERED.value
    )
    db_session.add(msg_b)
    db_session.commit()

    # Org A tries to fetch conversation messages
    resp_tamper = client.get(
        f"/api/v1/conversations/{conv_b.id}/messages",
        headers=org_a_setup["headers"]
    )
    assert resp_tamper.status_code == 404  # Org A CANNOT read Org B messages!

import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, ForeignKey, 
    Index, JSON, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def get_utc_now():
    return datetime.now(timezone.utc)

# Enums
class MemberRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"
    VIEWER = "VIEWER"

class WhatsAppInstanceStatus(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    QR_READY = "QR_READY"
    FAILED = "FAILED"

class ContactStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"

class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"

class MessageType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    LOCATION = "LOCATION"
    TEMPLATE = "TEMPLATE"

class MessageStatus(str, Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"

class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ConversationStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class AIMode(str, Enum):
    AI_ACTIVE = "AI_ACTIVE"
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    AI_RESUMED = "AI_RESUMED"

class EscalationStatus(str, Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

# 1. Organizations
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    default_country_code = Column(String(5), default="IN")
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    whatsapp_instances = relationship("WhatsAppInstance", back_populates="organization", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="organization", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="organization", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")
    ai_agents = relationship("AIAgent", back_populates="organization", cascade="all, delete-orphan")

# 2. Users
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")

# 3. Organization Members
class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default=MemberRole.AGENT.value, nullable=False)
    created_at = Column(DateTime, default=get_utc_now)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )

# 4. Roles & 5. Permissions
class Role(Base):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

# 6. WhatsApp Instances
class WhatsAppInstance(Base):
    __tablename__ = "whatsapp_instances"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_name = Column(String(100), nullable=False, index=True)
    phone_number = Column(String(50), nullable=True)
    status = Column(String(50), default=WhatsAppInstanceStatus.DISCONNECTED.value, nullable=False)
    qr_code = Column(Text, nullable=True)
    provider_id = Column(String(100), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    api_key = Column(String(255), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    organization = relationship("Organization", back_populates="whatsapp_instances")
    conversations = relationship("Conversation", back_populates="whatsapp_instance")

# 7. Contacts & 8. Tags & 9. ContactTags
class Tag(Base):
    __tablename__ = "tags"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#3B82F6")
    created_at = Column(DateTime, default=get_utc_now)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_tag_name"),
    )

class ContactTag(Base):
    __tablename__ = "contact_tags"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("contact_id", "tag_id", name="uq_contact_tag"),
    )

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    status = Column(String(50), default=ContactStatus.ACTIVE.value, nullable=False)
    source = Column(String(50), default="MANUAL")  # MANUAL, CSV, EXCEL, GOOGLE_SHEETS, INBOUND
    custom_fields = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now, index=True)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    organization = relationship("Organization", back_populates="contacts")
    conversations = relationship("Conversation", back_populates="contact", cascade="all, delete-orphan")
    campaign_entries = relationship("CampaignContact", back_populates="contact", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "phone", name="uq_org_contact_phone"),
    )

# 10. Templates
class Template(Base):
    __tablename__ = "templates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), default="MARKETING")
    content = Column(Text, nullable=False)  # Example: "Hi {{name}}, your plan {{plan}} is ready"
    variables = Column(JSON, default=list)  # ["name", "plan"]
    media_id = Column(String(36), ForeignKey("media.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

# 11. Media
class Media(Base):
    __tablename__ = "media"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    public_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

# 12. Campaigns & 13. CampaignContacts
class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    whatsapp_instance_id = Column(String(36), ForeignKey("whatsapp_instances.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(String(36), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default=CampaignStatus.DRAFT.value, nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=True)
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    read_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    rate_limit_per_second = Column(Integer, default=5)
    variables_mapping = Column(JSON, default=dict)
    audience_filter = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    organization = relationship("Organization", back_populates="campaigns")
    recipients = relationship("CampaignContact", back_populates="campaign", cascade="all, delete-orphan")

class CampaignContact(Base):
    __tablename__ = "campaign_contacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default=MessageStatus.QUEUED.value, nullable=False)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    campaign = relationship("Campaign", back_populates="recipients")
    contact = relationship("Contact", back_populates="campaign_entries")

# 14. Messages & 15. Conversations & 16. ConversationParticipants
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    whatsapp_instance_id = Column(String(36), ForeignKey("whatsapp_instances.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default=ConversationStatus.OPEN.value, nullable=False)
    ai_mode = Column(String(50), default=AIMode.AI_ACTIVE.value, nullable=False, index=True)
    assigned_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_message_at = Column(DateTime, default=get_utc_now, index=True)
    unread_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    organization = relationship("Organization", back_populates="conversations")
    contact = relationship("Contact", back_populates="conversations")
    whatsapp_instance = relationship("WhatsAppInstance", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "contact_id", "whatsapp_instance_id", name="uq_org_contact_conv"),
    )

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    whatsapp_instance_id = Column(String(36), ForeignKey("whatsapp_instances.id", ondelete="SET NULL"), nullable=True)
    direction = Column(String(20), default=MessageDirection.OUTBOUND.value, nullable=False)
    message_type = Column(String(20), default=MessageType.TEXT.value, nullable=False)
    content = Column(Text, nullable=True)
    media_id = Column(String(36), ForeignKey("media.id", ondelete="SET NULL"), nullable=True)
    media_url = Column(String(500), nullable=True)
    provider_message_id = Column(String(255), index=True, nullable=True)
    idempotency_key = Column(String(255), index=True, nullable=True)
    status = Column(String(50), default=MessageStatus.QUEUED.value, nullable=False, index=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now, index=True)

    conversation = relationship("Conversation", back_populates="messages")

class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=get_utc_now)

# 17. AI Agents & 18. KnowledgeDocuments & 19. AIRuns & 20. AIToolCalls & 21. Escalations
class AIAgent(Base):
    __tablename__ = "ai_agents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    personality = Column(String(255), default="Helpful, professional and concise")
    model = Column(String(100), default="gpt-4o")
    status = Column(String(50), default="ACTIVE")
    business_description = Column(Text, nullable=True)
    faq_data = Column(JSON, default=list)
    products_services = Column(JSON, default=list)
    working_hours = Column(JSON, default=dict)
    settings = Column(JSON, default=dict)
    handoff_rules = Column(JSON, default=dict)
    allowed_tools = Column(JSON, default=list)
    is_default = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    organization = relationship("Organization", back_populates="ai_agents")
    knowledge_docs = relationship("KnowledgeDocument", back_populates="ai_agent", cascade="all, delete-orphan")

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_agent_id = Column(String(36), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(100), default="GENERAL")
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    ai_agent = relationship("AIAgent", back_populates="knowledge_docs")

class AIRun(Base):
    __tablename__ = "ai_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    inbound_message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    status = Column(String(50), default="SUCCESS")
    created_at = Column(DateTime, default=get_utc_now)

    tool_calls = relationship("AIToolCall", back_populates="ai_run", cascade="all, delete-orphan")

class AIToolCall(Base):
    __tablename__ = "ai_tool_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_run_id = Column(String(36), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    input_arguments = Column(JSON, default=dict)
    output_result = Column(JSON, default=dict)
    is_success = Column(Boolean, default=True)
    executed_at = Column(DateTime, default=get_utc_now)

    ai_run = relationship("AIRun", back_populates="tool_calls")

class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), default=EscalationStatus.PENDING.value, nullable=False)
    assigned_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    resolved_at = Column(DateTime, nullable=True)

    conversation = relationship("Conversation", back_populates="escalations")

# 22. WebhookEvents & 23. AuditLogs
class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), default="EVOLUTION")
    event_type = Column(String(100), nullable=False, index=True)
    provider_event_id = Column(String(255), unique=True, index=True, nullable=True)
    idempotency_key = Column(String(255), unique=True, index=True, nullable=False)
    raw_payload = Column(JSON, nullable=False)
    status = Column(String(50), default="PENDING")  # PENDING, PROCESSED, FAILED, DUPLICATE
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, index=True)

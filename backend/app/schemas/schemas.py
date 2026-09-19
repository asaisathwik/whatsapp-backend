from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# User & Auth Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str
    organization_name: Optional[str] = "My Business"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
    organization: Dict[str, Any]

class UserResponse(UserBase):
    id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Organization Schemas
class OrganizationBase(BaseModel):
    name: str
    default_country_code: str = "IN"
    settings: Optional[Dict[str, Any]] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: str
    slug: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# WhatsApp Instance Schemas
class WhatsAppInstanceCreate(BaseModel):
    instance_name: str
    phone_number: Optional[str] = None
    is_default: Optional[bool] = True

class WhatsAppInstanceResponse(BaseModel):
    id: str
    organization_id: str
    instance_name: str
    phone_number: Optional[str]
    status: str
    qr_code: Optional[str] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Contact & Tag Schemas
class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#3B82F6"

class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ContactBase(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    status: Optional[str] = "ACTIVE"
    source: Optional[str] = "MANUAL"
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tag_ids: Optional[List[str]] = Field(default_factory=list)

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    tag_ids: Optional[List[str]] = None

class ContactResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    phone: str
    email: Optional[str]
    status: str
    source: str
    custom_fields: Dict[str, Any]
    tags: List[TagResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Contact Import Preview & Result
class ContactImportRow(BaseModel):
    row_number: int
    name: str
    raw_phone: str
    normalized_phone: Optional[str] = None
    email: Optional[str] = None
    custom_fields: Dict[str, Any] = {}
    is_valid: bool = True
    is_duplicate: bool = False
    error: Optional[str] = None

class ContactImportPreview(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    sample_rows: List[ContactImportRow]

class ContactImportConfirm(BaseModel):
    rows: List[ContactImportRow]
    tag_ids: Optional[List[str]] = []
    overwrite_existing: bool = False

class ContactImportResult(BaseModel):
    total: int
    imported: int
    failed: int
    duplicates: int
    errors: List[str] = []

# Template Schemas
class TemplateBase(BaseModel):
    name: str
    category: str = "MARKETING"
    content: str
    variables: List[str] = []
    media_id: Optional[str] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateResponse(TemplateBase):
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Campaign Schemas
class CampaignCreate(BaseModel):
    name: str
    whatsapp_instance_id: Optional[str] = None
    template_id: Optional[str] = None
    custom_content: Optional[str] = None
    message_content: Optional[str] = None
    message_type: Optional[str] = None
    media_url: Optional[str] = None
    save_to_store: Optional[bool] = False
    store_asset_name: Optional[str] = None
    contact_ids: Optional[List[str]] = None
    recipient_phones: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    rate_limit_per_second: int = 5
    variables_mapping: Dict[str, str] = {}
    audience_filter: Dict[str, Any] = {}

class CampaignPreview(BaseModel):
    campaign_name: str
    total_recipients: int
    sample_messages: List[Dict[str, Any]]
    variables_needed: List[str]
    invalid_recipients_count: int
    estimated_duration_seconds: int

class CampaignResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    whatsapp_instance_id: Optional[str]
    template_id: Optional[str]
    status: str
    scheduled_at: Optional[datetime]
    total_recipients: int
    sent_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    rate_limit_per_second: int
    audience_filter: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Conversation & Message Schemas
class MessageSendRequest(BaseModel):
    conversation_id: Optional[str] = None
    contact_id: Optional[str] = None
    whatsapp_instance_id: Optional[str] = None
    content: str
    message_type: str = "TEXT"
    media_url: Optional[str] = None

class MessageResponse(BaseModel):
    id: str
    organization_id: str
    conversation_id: Optional[str] = None
    contact_id: Optional[str] = None
    direction: str
    message_type: str
    content: Optional[str]
    media_url: Optional[str]
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ConversationResponse(BaseModel):
    id: str
    organization_id: str
    contact_id: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    whatsapp_instance_id: Optional[str]
    status: str
    ai_mode: str
    assigned_user_id: Optional[str]
    unread_count: int
    last_message_at: datetime
    last_message: Optional[MessageResponse] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class HumanTakeoverRequest(BaseModel):
    reason: Optional[str] = "Manual agent takeover"

# AI Agent & Knowledge Schemas
class AIAgentCreate(BaseModel):
    name: str
    system_prompt: str
    personality: Optional[str] = "Helpful and professional"
    model: Optional[str] = "gpt-4o"
    business_description: Optional[str] = None
    faq_data: Optional[List[Dict[str, str]]] = []
    products_services: Optional[List[Dict[str, Any]]] = []
    working_hours: Optional[Dict[str, str]] = {}
    allowed_tools: Optional[List[str]] = [
        "get_customer_details",
        "get_business_hours",
        "check_availability",
        "create_lead",
        "handoff_to_human"
    ]
    handoff_rules: Optional[Dict[str, Any]] = {
        "keywords": ["human", "agent", "support", "talk to human", "representative", "complaint"],
        "confidence_threshold": 0.6
    }
    is_default: Optional[bool] = True

class AIAgentResponse(AIAgentCreate):
    id: str
    organization_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class KnowledgeDocCreate(BaseModel):
    title: str
    category: str = "GENERAL"
    content: str
    metadata_json: Optional[Dict[str, Any]] = {}

class KnowledgeDocResponse(KnowledgeDocCreate):
    id: str
    organization_id: str
    ai_agent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Dashboard & Analytics Schemas
class DashboardMetrics(BaseModel):
    messages_sent: int
    messages_delivered: int
    messages_read: int
    messages_failed: int
    messages_inbound: int
    messages_outbound: int
    active_conversations: int
    ai_conversations: int
    human_conversations: int
    total_campaigns: int
    total_contacts: int

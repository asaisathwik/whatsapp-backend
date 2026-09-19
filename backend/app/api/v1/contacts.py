from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import Contact, Tag, ContactTag, ContactStatus
from app.schemas.schemas import (
    ContactCreate, ContactUpdate, ContactResponse, 
    TagCreate, TagResponse,
    ContactImportPreview, ContactImportConfirm, ContactImportResult
)
from app.services.phone_normalizer import normalize_phone_number
from app.services.contact_importer import ContactImportService

router = APIRouter(prefix="/contacts", tags=["Contacts & Tags"])

# Tags Endpoints
@router.get("/tags", response_model=List[TagResponse])
def list_tags(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    return db.query(Tag).filter(Tag.organization_id == context.organization_id).all()

@router.post("/tags", response_model=TagResponse)
def create_tag(
    payload: TagCreate,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    tag = Tag(
        organization_id=context.organization_id,
        name=payload.name.strip().upper(),
        color=payload.color or "#3B82F6"
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag

# Contacts Endpoints
@router.get("", response_model=List[ContactResponse])
def list_contacts(
    search: Optional[str] = None,
    status: Optional[str] = None,
    tag_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(Contact).filter(Contact.organization_id == context.organization_id)
    
    if search:
        s = f"%{search}%"
        query = query.filter((Contact.name.ilike(s)) | (Contact.phone.ilike(s)) | (Contact.email.ilike(s)))
    if status:
        query = query.filter(Contact.status == status)
    if tag_id:
        query = query.join(ContactTag).filter(ContactTag.tag_id == tag_id)

    contacts = query.order_by(Contact.created_at.desc()).offset(skip).limit(limit).all()
    
    # Map tags
    results = []
    for c in contacts:
        contact_tags = db.query(Tag).join(ContactTag, ContactTag.tag_id == Tag.id).filter(
            ContactTag.contact_id == c.id
        ).all()
        results.append(ContactResponse(
            id=c.id,
            organization_id=c.organization_id,
            name=c.name,
            phone=c.phone,
            email=c.email,
            status=c.status,
            source=c.source,
            custom_fields=c.custom_fields or {},
            tags=[TagResponse.model_validate(t) for t in contact_tags],
            created_at=c.created_at,
            updated_at=c.updated_at
        ))
    return results

@router.post("", response_model=ContactResponse)
def create_contact(
    payload: ContactCreate,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    # Normalize phone
    is_valid, normalized_phone, err = normalize_phone_number(
        payload.phone,
        default_country=context.organization.default_country_code or "IN"
    )
    if not is_valid or not normalized_phone:
        raise HTTPException(status_code=400, detail=err or "Invalid phone number")

    # Check duplicate
    existing = db.query(Contact).filter(
        Contact.organization_id == context.organization_id,
        Contact.phone == normalized_phone
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A contact with this phone number already exists in your organization.")

    contact = Contact(
        organization_id=context.organization_id,
        name=payload.name,
        phone=normalized_phone,
        email=payload.email,
        status=payload.status or ContactStatus.ACTIVE.value,
        source=payload.source or "MANUAL",
        custom_fields=payload.custom_fields or {}
    )
    db.add(contact)
    db.flush()

    tags = []
    if payload.tag_ids:
        for tid in payload.tag_ids:
            ct = ContactTag(organization_id=context.organization_id, contact_id=contact.id, tag_id=tid)
            db.add(ct)
        tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()

    db.commit()
    db.refresh(contact)

    return ContactResponse(
        id=contact.id,
        organization_id=contact.organization_id,
        name=contact.name,
        phone=contact.phone,
        email=contact.email,
        status=contact.status,
        source=contact.source,
        custom_fields=contact.custom_fields or {},
        tags=[TagResponse.model_validate(t) for t in tags],
        created_at=contact.created_at,
        updated_at=contact.updated_at
    )

@router.delete("/{contact_id}")
def delete_contact(
    contact_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.organization_id == context.organization_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"status": "SUCCESS", "message": "Contact deleted"}

# CSV / Excel Import Flow
@router.post("/import/preview", response_model=ContactImportPreview)
async def preview_contact_import(
    file: UploadFile = File(...),
    context: TenantContext = Depends(get_current_user_and_tenant)
):
    content = await file.read()
    try:
        preview = ContactImportService.parse_file(
            file_bytes=content,
            filename=file.filename or "upload.csv",
            default_country=context.organization.default_country_code or "IN"
        )
        return preview
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/import/confirm", response_model=ContactImportResult)
def confirm_contact_import(
    payload: ContactImportConfirm,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    res = ContactImportService.execute_import(
        db=db,
        organization_id=context.organization_id,
        rows=payload.rows,
        tag_ids=payload.tag_ids,
        source="CSV",
        overwrite_existing=payload.overwrite_existing
    )
    return res

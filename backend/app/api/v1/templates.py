from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import Template
from app.schemas.schemas import TemplateCreate, TemplateResponse
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])

@router.get("", response_model=List[TemplateResponse])
def list_templates(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    return db.query(Template).filter(
        Template.organization_id == context.organization_id,
        Template.category != "CAMPAIGN"
    ).all()

@router.post("", response_model=TemplateResponse)
def create_template(
    payload: TemplateCreate,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    # Auto-extract variables from content
    extracted_vars = TemplateService.extract_variables(payload.content)

    template = Template(
        organization_id=context.organization_id,
        name=payload.name,
        category=payload.category,
        content=payload.content,
        variables=extracted_vars,
        media_id=payload.media_id,
        is_active=True
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

@router.delete("/{template_id}")
def delete_template(
    template_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    tmpl = db.query(Template).filter(
        Template.id == template_id,
        Template.organization_id == context.organization_id
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tmpl)
    db.commit()
    return {"status": "SUCCESS", "message": "Template deleted"}

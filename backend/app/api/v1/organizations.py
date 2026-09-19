from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext, require_roles
from app.models.models import Organization, OrganizationMember, MemberRole
from app.schemas.schemas import OrganizationResponse, OrganizationBase

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.get("/current", response_model=OrganizationResponse)
def get_current_organization(context: TenantContext = Depends(get_current_user_and_tenant)):
    return context.organization

@router.put("/current", response_model=OrganizationResponse)
def update_organization(
    payload: OrganizationBase,
    context: TenantContext = Depends(require_roles([MemberRole.OWNER, MemberRole.ADMIN])),
    db: Session = Depends(get_db)
):
    org = context.organization
    org.name = payload.name
    org.default_country_code = payload.default_country_code
    if payload.settings is not None:
        org.settings = payload.settings
    db.commit()
    db.refresh(org)
    return org

@router.get("/members")
def list_organization_members(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == context.organization_id
    ).all()
    return [
        {
            "id": m.id,
            "user_id": m.user.id,
            "full_name": m.user.full_name,
            "email": m.user.email,
            "role": m.role,
            "joined_at": m.created_at
        }
        for m in members
    ]

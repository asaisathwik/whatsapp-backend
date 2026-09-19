from typing import Optional, List
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import User, Organization, OrganizationMember, MemberRole

security_scheme = HTTPBearer(auto_error=False)

class TenantContext:
    def __init__(self, user: User, organization: Organization, role: str):
        self.user = user
        self.organization = organization
        self.role = role
        self.organization_id = organization.id
        self.user_id = user.id

async def get_current_user_and_tenant(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_organization_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> TenantContext:
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated"
        )
    
    # Organization determination
    org_id = payload.get("org_id") or x_organization_id
    
    if not org_id:
        membership = db.query(OrganizationMember).filter(OrganizationMember.user_id == user.id).first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to any organization"
            )
        org_id = membership.organization_id
        role = membership.role
        organization = membership.organization
    else:
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org_id
        ).first()
        if not membership and not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this organization"
            )
        organization = db.query(Organization).filter(Organization.id == org_id).first()
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        role = membership.role if membership else MemberRole.OWNER.value
    
    return TenantContext(user=user, organization=organization, role=role)

def require_roles(allowed_roles: List[MemberRole]):
    def role_checker(context: TenantContext = Depends(get_current_user_and_tenant)) -> TenantContext:
        role_values = [r.value for r in allowed_roles]
        if context.role not in role_values and not context.user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required role: {', '.join(role_values)}"
            )
        return context
    return role_checker

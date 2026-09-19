import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import User, Organization, OrganizationMember, MemberRole, AIAgent
from app.schemas.schemas import UserCreate, UserLogin, Token, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")

@router.post("/register", response_model=Token)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    # Check existing user
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    # Create User
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password)
    )
    db.add(user)
    db.flush()

    # Create default Organization
    org_name = payload.organization_name or f"{payload.full_name}'s Business"
    base_slug = slugify(org_name)
    slug = f"{base_slug}-{user.id[:6]}"

    org = Organization(
        name=org_name,
        slug=slug
    )
    db.add(org)
    db.flush()

    # Assign OWNER membership
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=MemberRole.OWNER.value
    )
    db.add(member)

    # Create default AI agent for the organization
    default_ai_agent = AIAgent(
        organization_id=org.id,
        name="Assistant",
        system_prompt="You are a smart, professional customer service assistant on WhatsApp for our company. Answer customer questions politely and accurately.",
        business_description="We provide premier automation and customer messaging services."
    )
    db.add(default_ai_agent)
    db.commit()

    token = create_access_token(
        subject=user.id,
        organization_id=org.id,
        role=MemberRole.OWNER.value
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
        organization={"id": org.id, "name": org.name, "slug": org.slug, "role": MemberRole.OWNER.value}
    )

@router.post("/login", response_model=Token)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    # Get user's primary organization membership
    membership = db.query(OrganizationMember).filter(OrganizationMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any active organization."
        )

    org = membership.organization
    token = create_access_token(
        subject=user.id,
        organization_id=org.id,
        role=membership.role
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user={"id": user.id, "email": user.email, "full_name": user.full_name},
        organization={"id": org.id, "name": org.name, "slug": org.slug, "role": membership.role}
    )

@router.get("/me")
def get_current_user_profile(context: TenantContext = Depends(get_current_user_and_tenant)):
    return {
        "user": {
            "id": context.user.id,
            "email": context.user.email,
            "full_name": context.user.full_name,
            "is_superuser": context.user.is_superuser
        },
        "organization": {
            "id": context.organization.id,
            "name": context.organization.name,
            "slug": context.organization.slug,
            "role": context.role,
            "default_country_code": context.organization.default_country_code
        }
    }

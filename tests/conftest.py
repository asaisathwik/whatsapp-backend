import pytest
import os
import sys

# Ensure backend package is in path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.models.models import User, Organization, OrganizationMember, MemberRole, WhatsAppInstance, AIAgent
from app.main import app

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    
    yield db
    
    db.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def org_a_setup(db_session):
    user_a = User(
        email="owner_a@business-a.com",
        full_name="Alice Owner",
        hashed_password=get_password_hash("password123")
    )
    db_session.add(user_a)
    db_session.flush()

    org_a = Organization(
        name="Business A",
        slug=f"business-a-{user_a.id[:6]}"
    )
    db_session.add(org_a)
    db_session.flush()

    mem_a = OrganizationMember(
        organization_id=org_a.id,
        user_id=user_a.id,
        role=MemberRole.OWNER.value
    )
    db_session.add(mem_a)

    instance_a = WhatsAppInstance(
        organization_id=org_a.id,
        instance_name="inst_a_main",
        phone_number="919876543210",
        status="CONNECTED"
    )
    db_session.add(instance_a)

    ai_agent_a = AIAgent(
        organization_id=org_a.id,
        name="Assistant A",
        system_prompt="You are assistant for Business A",
        is_default=True
    )
    db_session.add(ai_agent_a)
    db_session.commit()

    token_a = create_access_token(user_a.id, org_a.id, MemberRole.OWNER.value)
    return {
        "user": user_a,
        "org": org_a,
        "instance": instance_a,
        "token": token_a,
        "headers": {"Authorization": f"Bearer {token_a}"}
    }

@pytest.fixture
def org_b_setup(db_session):
    user_b = User(
        email="owner_b@business-b.com",
        full_name="Bob Owner",
        hashed_password=get_password_hash("password123")
    )
    db_session.add(user_b)
    db_session.flush()

    org_b = Organization(
        name="Business B",
        slug=f"business-b-{user_b.id[:6]}"
    )
    db_session.add(org_b)
    db_session.flush()

    mem_b = OrganizationMember(
        organization_id=org_b.id,
        user_id=user_b.id,
        role=MemberRole.OWNER.value
    )
    db_session.add(mem_b)

    instance_b = WhatsAppInstance(
        organization_id=org_b.id,
        instance_name="inst_b_main",
        phone_number="919123456780",
        status="CONNECTED"
    )
    db_session.add(instance_b)
    db_session.commit()

    token_b = create_access_token(user_b.id, org_b.id, MemberRole.OWNER.value)
    return {
        "user": user_b,
        "org": org_b,
        "instance": instance_b,
        "token": token_b,
        "headers": {"Authorization": f"Bearer {token_b}"}
    }

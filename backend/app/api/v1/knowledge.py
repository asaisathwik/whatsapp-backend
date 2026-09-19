from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import KnowledgeDocument
from app.schemas.schemas import KnowledgeDocCreate, KnowledgeDocResponse

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

@router.get("", response_model=List[KnowledgeDocResponse])
def list_knowledge_docs(
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    return db.query(KnowledgeDocument).filter(
        KnowledgeDocument.organization_id == context.organization_id
    ).all()

@router.post("", response_model=KnowledgeDocResponse)
def create_knowledge_doc(
    payload: KnowledgeDocCreate,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    doc = KnowledgeDocument(
        organization_id=context.organization_id,
        title=payload.title,
        category=payload.category,
        content=payload.content,
        metadata_json=payload.metadata_json or {}
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.delete("/{doc_id}")
def delete_knowledge_doc(
    doc_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.organization_id == context.organization_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"status": "SUCCESS", "message": "Document deleted"}

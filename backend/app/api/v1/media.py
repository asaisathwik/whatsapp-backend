import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user_and_tenant, TenantContext
from app.models.models import Media

router = APIRouter(prefix="/media", tags=["Media Store"])

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "image": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"],
    "document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".zip"]
}

@router.get("")
def list_media(
    media_type: Optional[str] = None,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(Media).filter(Media.organization_id == context.organization_id)
    media_items = query.order_by(Media.created_at.desc()).all()
    
    results = []
    for item in media_items:
        # Determine category based on mime_type or extension
        is_image = item.mime_type.startswith("image/") or any(item.filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS["image"])
        item_type = "image" if is_image else "document"
        
        if media_type and media_type != "all" and item_type != media_type:
            continue
            
        results.append({
            "id": item.id,
            "filename": item.filename,
            "mime_type": item.mime_type,
            "file_size": item.file_size,
            "public_url": item.public_url or f"/uploads/{os.path.basename(item.file_path)}",
            "type": item_type,
            "created_at": item.created_at
        })
    return results

@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    original_filename = file.filename or "file.bin"
    ext = os.path.splitext(original_filename)[1].lower()
    
    unique_filename = f"{uuid.uuid4().hex[:12]}_{original_filename}"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    file_size = 0
    with open(saved_path, "wb") as buffer:
        while content := await file.read(1024 * 1024):  # 1MB chunks
            buffer.write(content)
            file_size += len(content)
            
    mime_type = file.content_type or "application/octet-stream"
    public_url = f"/uploads/{unique_filename}"
    
    media = Media(
        organization_id=context.organization_id,
        filename=original_filename,
        file_path=saved_path,
        mime_type=mime_type,
        file_size=file_size,
        public_url=public_url
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    
    is_image = mime_type.startswith("image/") or any(original_filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS["image"])
    
    return {
        "id": media.id,
        "filename": media.filename,
        "mime_type": media.mime_type,
        "file_size": media.file_size,
        "public_url": public_url,
        "type": "image" if is_image else "document",
        "created_at": media.created_at
    }

@router.delete("/{media_id}")
def delete_media(
    media_id: str,
    context: TenantContext = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    media = db.query(Media).filter(
        Media.id == media_id,
        Media.organization_id == context.organization_id
    ).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
        
    try:
        if os.path.exists(media.file_path):
            os.remove(media.file_path)
    except Exception:
        pass
        
    db.delete(media)
    db.commit()
    return {"status": "SUCCESS", "message": "Media deleted"}

from typing import Type, TypeVar, Generic, List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from fastapi import HTTPException, status
from app.core.database import Base

T = TypeVar("T", bound=Base)

class TenantRepository(Generic[T]):
    def __init__(self, model: Type[T], db: Session, organization_id: str):
        self.model = model
        self.db = db
        self.organization_id = organization_id

    def get_by_id(self, id: str) -> Optional[T]:
        """Fetch a single record by ID belonging strictly to the organization."""
        query = self.db.query(self.model).filter(
            self.model.id == id,
            self.model.organization_id == self.organization_id
        )
        return query.first()

    def get_all(self, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """Fetch records belonging strictly to the organization."""
        query = self.db.query(self.model).filter(self.model.organization_id == self.organization_id)
        for attr, value in filters.items():
            if hasattr(self.model, attr) and value is not None:
                query = query.filter(getattr(self.model, attr) == value)
        return query.offset(skip).limit(limit).all()

    def count(self, **filters) -> int:
        query = self.db.query(self.model).filter(self.model.organization_id == self.organization_id)
        for attr, value in filters.items():
            if hasattr(self.model, attr) and value is not None:
                query = query.filter(getattr(self.model, attr) == value)
        return query.count()

    def create(self, **kwargs) -> T:
        """Create a record strictly binding organization_id from the context."""
        kwargs["organization_id"] = self.organization_id
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, id: str, **kwargs) -> Optional[T]:
        """Update a record strictly verified against organization_id."""
        obj = self.get_by_id(id)
        if not obj:
            return None
        # Ensure organization_id cannot be overwritten
        kwargs.pop("organization_id", None)
        for key, value in kwargs.items():
            if hasattr(obj, key) and value is not None:
                setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: str) -> bool:
        """Delete a record strictly belonging to the organization."""
        obj = self.get_by_id(id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True

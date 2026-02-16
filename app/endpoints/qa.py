from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.core import database

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[schemas.QAResponse])
def read_qa_items(
    page_key: str = None, 
    skip: int = 0, 
    limit: int = 100, 
    active_only: bool = True, 
    db: Session = Depends(get_db)
):
    query = db.query(models.QAItem)
    if active_only:
        query = query.filter(models.QAItem.is_active == True)
    
    if page_key:
        from sqlalchemy import or_
        query = query.filter(or_(models.QAItem.page_key == page_key, models.QAItem.page_key == "all"))
    
    # Sort by display_order (asc) then updated_at (desc)
    query = query.order_by(models.QAItem.display_order.asc(), models.QAItem.updated_at.desc())
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.QAResponse)
def create_qa_item(item: schemas.QACreate, db: Session = Depends(get_db)):
    db_item = models.QAItem(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.put("/{item_id}", response_model=schemas.QAResponse)
def update_qa_item(item_id: int, item: schemas.QAUpdate, db: Session = Depends(get_db)):
    db_item = db.query(models.QAItem).filter(models.QAItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="QA Item not found")
    
    # Update fields
    for k, v in item.dict().items():
        setattr(db_item, k, v)
    
    db.commit()
    db.refresh(db_item)
    return db_item

@router.delete("/{item_id}")
def delete_qa_item(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(models.QAItem).filter(models.QAItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="QA Item not found")
    
    db.delete(db_item)
    db.commit()
    return {"message": "Deleted successfully"}

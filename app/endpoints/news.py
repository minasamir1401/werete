from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core import database
from app import models
from app.schemas import Article, ArticleCreate
from datetime import datetime
import re
import random
from slugify import slugify
from app.core.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[Article])
def read_articles(skip: int = 0, limit: int = 10, db: Session = Depends(database.get_db)):
    """Retrieve published articles"""
    return db.query(models.Article).filter(
        models.Article.status == "published"
    ).order_by(models.Article.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{slug}", response_model=Article)
def read_article(slug: str, db: Session = Depends(database.get_db)):
    """Retrieve a single article by slug or ID"""
    import urllib.parse
    import logging
    logger = logging.getLogger(__name__)

    # Try exact match first
    article = db.query(models.Article).filter(models.Article.slug == slug).first()
    
    # Try URL decoded match
    if not article:
        decoded_slug = urllib.parse.unquote(slug)
        if decoded_slug != slug:
            article = db.query(models.Article).filter(models.Article.slug == decoded_slug).first()
            
    # Try ID if slug is numeric
    if not article and slug.isdigit():
        article = db.query(models.Article).filter(models.Article.id == int(slug)).first()
            
    if not article:
        logger.warning(f"🔍 Article NOT FOUND with slug: {slug}")
        raise HTTPException(status_code=404, detail="Article not found")
    
    article.views += 1
    db.commit()
    return article

@router.post("/", response_model=Article)
def create_article(article: ArticleCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Create a new article"""
    if not article.title or not article.title.strip():
        raise HTTPException(status_code=400, detail="Title is mandatory")
    if not article.content or not article.content.strip():
        raise HTTPException(status_code=400, detail="Content is mandatory")

    # Convert to dict to modify
    article_data = article.dict()
    
    # Use provided slug if available, otherwise generate from title
    if article_data.get('slug') and article_data['slug'].strip():
        base_slug = article_data['slug'].strip()
    else:
        base_slug = slugify(article.title) or "news"
    
    final_slug = base_slug
    counter = 1
    while db.query(models.Article).filter(models.Article.slug == final_slug).first():
        final_slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Update the dict with final slug and status
    article_data['slug'] = final_slug
    article_data['status'] = article_data.get('status', 'published')

    # Set meta fields if not provided
    if not article_data.get('meta_title') or not article_data['meta_title'].strip():
        article_data['meta_title'] = article.title
    
    if not article_data.get('meta_description') or not article_data['meta_description'].strip():
        clean_content = re.sub('<[^<]+?>', '', article.content).strip()
        article_data['meta_description'] = clean_content[:155] + "..." if len(clean_content) > 155 else clean_content
    
    # Create database article
    # Create database article by filtering only valid model fields
    model_fields = {c.name for c in models.Article.__table__.columns}
    filtered_data = {k: v for k, v in article_data.items() if k in model_fields}
    
    db_article = models.Article(**filtered_data)
    db_article.created_at = datetime.utcnow()
    db_article.updated_at = datetime.utcnow()
    
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

@router.put("/{slug}", response_model=Article)
def update_article(slug: str, article: ArticleCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Update an existing article"""
    db_article = db.query(models.Article).filter(models.Article.slug == slug).first()
    if not db_article and slug.isdigit():
        db_article = db.query(models.Article).filter(models.Article.id == int(slug)).first()
             
    if not db_article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if not article.title or not article.title.strip():
        raise HTTPException(status_code=400, detail="Title is mandatory")
    
    # Convert to dict for modification
    article_data = article.dict()
    
    # Check if slug is being changed
    if article_data.get('slug') and article_data['slug'] != db_article.slug:
        existing = db.query(models.Article).filter(models.Article.slug == article_data['slug']).first()
        if existing:
            article_data['slug'] = f"{article_data['slug']}-{random.randint(1000, 9999)}"
    
    # Update all fields except created_at
    for key, value in article_data.items():
        if key != "created_at":
            setattr(db_article, key, value)
    
    db_article.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_article)
    return db_article

@router.delete("/{slug}")
def delete_article(slug: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Delete an article"""
    article = db.query(models.Article).filter(models.Article.slug == slug).first()
    if not article and slug.isdigit():
        article = db.query(models.Article).filter(models.Article.id == int(slug)).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db.delete(article)
    db.commit()
    return {"status": "success", "message": "Article deleted"}

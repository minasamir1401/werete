from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core import database
from app import models
from typing import List, Dict
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class BankDisplayUpdate(BaseModel):
    bank_id: str
    is_enabled: bool
    display_order: int

class BankDisplayResponse(BaseModel):
    bank_id: str
    bank_name: str
    is_enabled: bool
    display_order: int

class SourceUpdate(BaseModel):
    source_id: str
    is_enabled: bool
    priority: int

async def scrape_background_task(db_session_factory):
    """Background task for scraping all banks"""
    from app.scraper.all_banks_scraper import AllBanksScraperManager
    
    db = db_session_factory()
    try:
        manager = AllBanksScraperManager(db_session=db)
        all_banks = await manager.fetch_all_banks_all_currencies()
        
        if not all_banks:
            logger.warning("Background scrape: No banks found.")
            return

        db.query(models.AllBanksCurrencyRate).delete()
        
        for bank in all_banks:
            db_bank = models.AllBanksCurrencyRate(
                bank_id=bank['bank_id'],
                bank_name=bank['bank_name'],
                currency=bank['currency'],
                buy_price=bank['buy_price'],
                sell_price=bank['sell_price'],
                source=bank['source'],
                last_update=bank['timestamp']
            )
            db.add(db_bank)
            
            exists = db.query(models.BankDisplaySettings).filter(
                models.BankDisplaySettings.bank_id == bank['bank_id']
            ).first()
            
            if not exists:
                setting = models.BankDisplaySettings(
                    bank_id=bank['bank_id'],
                    bank_name=bank['bank_name'],
                    is_enabled=True,
                    display_order=999
                )
                db.add(setting)
        
        db.commit()
    except Exception as e:
        logger.error(f"Background scrape failed: {e}")
    finally:
        db.close()

@router.get("/all")
def get_all_banks(db: Session = Depends(database.get_db)):
    """Retrieve all banks and their display settings"""
    banks = db.query(
        models.AllBanksCurrencyRate.bank_id,
        models.AllBanksCurrencyRate.bank_name
    ).distinct().all()
    
    settings = db.query(models.BankDisplaySettings).all()
    settings_dict = {s.bank_id: s for s in settings}
    
    result = []
    for bank_id, bank_name in banks:
        setting = settings_dict.get(bank_id)
        result.append({
            "bank_id": bank_id,
            "bank_name": bank_name,
            "is_enabled": setting.is_enabled if setting else True,
            "display_order": setting.display_order if setting else 999
        })
    
    result.sort(key=lambda x: x['display_order'])
    return result

@router.post("/settings/update")
def update_bank_settings(updates: List[BankDisplayUpdate], db: Session = Depends(database.get_db)):
    """Update display settings for multiple banks"""
    for update in updates:
        setting = db.query(models.BankDisplaySettings).filter(
            models.BankDisplaySettings.bank_id == update.bank_id
        ).first()
        
        if setting:
            setting.is_enabled = update.is_enabled
            setting.display_order = update.display_order
        else:
            bank = db.query(models.AllBanksCurrencyRate).filter(
                models.AllBanksCurrencyRate.bank_id == update.bank_id
            ).first()
            
            if bank:
                setting = models.BankDisplaySettings(
                    bank_id=update.bank_id,
                    bank_name=bank.bank_name,
                    is_enabled=update.is_enabled,
                    display_order=update.display_order
                )
                db.add(setting)
    
    db.commit()
    return {"status": "success", "updated": len(updates)}

@router.get("/enabled")
def get_enabled_banks(db: Session = Depends(database.get_db)):
    """Retrieve enabled banks in display order"""
    settings = db.query(models.BankDisplaySettings).filter(
        models.BankDisplaySettings.is_enabled == True
    ).order_by(models.BankDisplaySettings.display_order).all()
    
    return [
        {
            "bank_id": s.bank_id,
            "bank_name": s.bank_name,
            "display_order": s.display_order
        }
        for s in settings
    ]

@router.post("/scrape-all")
async def trigger_all_banks_scrape(background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    """Manually trigger background scraping for all banks"""
    background_tasks.add_task(scrape_background_task, database.SessionLocal)
    return {
        "status": "accepted",
        "message": "Scraping started in background",
        "timestamp": datetime.utcnow()
    }

@router.get("/sources/all")
def get_all_currency_sources(db: Session = Depends(database.get_db)):
    """Retrieve all currency scraping sources"""
    sources = db.query(models.CurrencySourceSettings).order_by(
        models.CurrencySourceSettings.priority
    ).all()
    
    if not sources:
        default_sources = [
            {"source_id": "ta3weem", "source_name": "Ta3weem", "source_type": "all_banks", "priority": 1},
            {"source_id": "egrates", "source_name": "Egrates", "source_type": "all_banks", "priority": 2},
            {"source_id": "banklive", "source_name": "BankLive", "source_type": "all_banks", "priority": 3},
            {"source_id": "sarf_today", "source_name": "Sarf Today", "source_type": "black_market", "priority": 1},
        ]
        
        for src in default_sources:
            db_src = models.CurrencySourceSettings(**src, is_enabled=True)
            db.add(db_src)
        
        db.commit()
        sources = db.query(models.CurrencySourceSettings).order_by(
            models.CurrencySourceSettings.priority
        ).all()
    
    return [
        {
            "source_id": s.source_id,
            "source_name": s.source_name,
            "source_type": s.source_type,
            "is_enabled": s.is_enabled,
            "priority": s.priority
        }
        for s in sources
    ]

@router.post("/sources/update")
def update_currency_sources(updates: List[SourceUpdate], db: Session = Depends(database.get_db)):
    """Update currency source settings"""
    for update in updates:
        source = db.query(models.CurrencySourceSettings).filter(
            models.CurrencySourceSettings.source_id == update.source_id
        ).first()
        
        if source:
            source.is_enabled = update.is_enabled
            source.priority = update.priority
        else:
            source = models.CurrencySourceSettings(
                source_id=update.source_id,
                source_name=update.source_id.title(),
                source_type="all_banks",
                is_enabled=update.is_enabled,
                priority=update.priority
            )
            db.add(source)
    
    db.commit()
    return {"status": "success", "updated": len(updates)}

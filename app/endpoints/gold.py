from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime, timezone
from app.core import database
from app import models
from app.schemas import GoldPrice

router = APIRouter()

@router.get("/prices", response_model=List[GoldPrice])
def read_current_prices(db: Session = Depends(database.get_db)):
    """Retrieve the latest gold prices from UnifiedPrice (SSoT) with manual overrides"""
    # Use UnifiedPrice instead of GoldPrice to ensure we use the Single Source of Truth
    prices = db.query(models.UnifiedPrice).filter(
        models.UnifiedPrice.type.in_(["gold", "local"]),
        models.UnifiedPrice.country == "egypt"
    ).all()
    
    if not prices:
        return []
    
    # Fetch settings for overrides and offset
    settings_list = db.query(models.Setting).filter(
        (models.Setting.key == "price_offset") | 
        (models.Setting.key.like("manual_price_%"))
    ).all()
    
    settings = {s.key: s.value for s in settings_list}
    offset = float(settings.get("price_offset", "0") or "0")
    
    result = []
    for p in prices:
        # Standardize to GoldPrice schema for the response
        manual_key = f"manual_price_{p.key}"
        sell_price = p.sell_price
        buy_price = p.buy_price
        source_status = p.source_status
        
        if manual_key in settings and settings[manual_key]:
            try:
                manual_val = float(settings[manual_key])
                sell_price = manual_val
                buy_price = manual_val
                source_status = "Manual"
            except ValueError:
                sell_price += offset
                buy_price += offset
        else:
            sell_price += offset
            buy_price += offset
            
        result.append(models.GoldPrice(
            id=p.id,
            karat=p.key,
            sell_price=sell_price,
            buy_price=buy_price,
            currency=p.currency or "EGP",
            country=p.country,
            timestamp=p.last_update,
            date=p.last_update.date() if p.last_update else datetime.now(timezone.utc).date(),
            time=p.last_update.time() if p.last_update else datetime.now(timezone.utc).time(),
            source=p.source_name,
            source_status=source_status,
            type=p.type
        ))

    return result

@router.get("/history", response_model=List[GoldPrice])
def read_price_history(limit: int = 100, db: Session = Depends(database.get_db)):
    """Retrieve historical gold prices from PriceHistory table"""
    history = db.query(models.PriceHistory).filter(
        models.PriceHistory.type.in_(["gold", "local"]),
        models.PriceHistory.country == "egypt"
    ).order_by(models.PriceHistory.timestamp.desc()).limit(limit).all()
    
    return [
        models.GoldPrice(
            id=h.id,
            karat=h.key,
            sell_price=h.sell_price,
            buy_price=h.buy_price,
            currency="EGP",
            country=h.country,
            timestamp=h.timestamp,
            date=h.timestamp.date(),
            time=h.timestamp.time(),
            source=h.source_name,
            source_status="Historical",
            type=h.type
        ) for h in history
    ]

@router.get("/all-countries")
def get_all_countries_latest(db: Session = Depends(database.get_db)):
    """Retrieve latest prices for all countries from UnifiedPrice"""
    prices = db.query(models.UnifiedPrice).filter(
        models.UnifiedPrice.type.in_(["gold", "international", "local"])
    ).all()
    
    result = {}
    for p in prices:
        country_slug = p.country.lower()
        if country_slug not in result:
            result[country_slug] = {
                "current_prices": {}, 
                "timestamp": p.last_update, 
                "last_update": p.last_update.strftime("%Y-%m-%d %H:%M:%S") if p.last_update else None,
                "source": p.source_name
            }
        
        result[country_slug]["current_prices"][p.key] = {
            "sell": p.sell_price,
            "buy": p.buy_price,
            "currency": p.currency
        }
    return result

@router.get("/country/{country_slug}")
def get_single_country_latest(country_slug: str, db: Session = Depends(database.get_db)):
    """Retrieve latest prices for a specific country from UnifiedPrice"""
    prices = db.query(models.UnifiedPrice).filter(
        models.UnifiedPrice.country.ilike(country_slug),
        models.UnifiedPrice.type.in_(["gold", "international", "local"])
    ).all()
    
    if not prices:
        return {"current_prices": {}, "timestamp": None, "source": None}
        
    return {
        "current_prices": {p.key: {"sell": p.sell_price, "buy": p.buy_price, "currency": p.currency} for p in prices},
        "timestamp": prices[0].last_update,
        "last_update": prices[0].last_update.strftime("%Y-%m-%d %H:%M:%S") if prices[0].last_update else None,
        "source": prices[0].source_name
    }

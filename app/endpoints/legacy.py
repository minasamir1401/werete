from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core import database
from app.endpoints.prices import get_full_market_snapshot
from datetime import datetime, timedelta
from app import models

router = APIRouter()

@router.get("/gold-live-prices")
def legacy_live_prices(db: Session = Depends(database.get_db)):
    """Legacy endpoint for live prices format"""
    snapshot = get_full_market_snapshot(db)
    prices = snapshot.get("gold_egypt", {}).get("prices", {})
    
    # Transform to list [ {name, buy, sell} ]
    result = []
    for karat, vals in prices.items():
        result.append({
            "name": f"عيار {karat}",
            "buy": vals["buy"],
            "sell": vals["sell"]
        })
    return result

@router.get("/gold-live-products")
def legacy_live_products(db: Session = Depends(database.get_db)):
    """Legacy endpoint for products (Gold Pound, Ounce, etc.)"""
    snapshot = get_full_market_snapshot(db)
    prices = snapshot.get("gold_egypt", {}).get("prices", {})
    
    # Products usually are Ounce and Pound
    # عيار 21 * 8 = Pound
    # عيار 24 * 31.10 = Ounce
    
    p21 = prices.get("21", {"buy": 0, "sell": 0})
    p24 = prices.get("24", {"buy": 0, "sell": 0})
    
    result = [
        {
            "name": "الجنيه الذهب",
            "weight": "8 جرام",
            "price": p21["sell"] * 8
        },
        {
            "name": "أوقية الذهب",
            "weight": "31.10 جرام",
            "price": p24["sell"] * 31.1035
        }
    ]
    return result

@router.get("/gold-live-history")
def legacy_live_history(db: Session = Depends(database.get_db)):
    """Legacy endpoint for 30-day history table with all karats"""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Fetch all gold history for Egypt in the last 30 days
    history_data = db.query(models.PriceHistory).filter(
        models.PriceHistory.type == "gold",
        models.PriceHistory.country == "egypt",
        models.PriceHistory.timestamp >= thirty_days_ago
    ).order_by(models.PriceHistory.timestamp.desc()).all()
    
    # Group by date
    days_map = {}
    for h in history_data:
        day_str = h.timestamp.date().isoformat()
        if day_str not in days_map:
            days_map[day_str] = {
                "date": day_str,
                "karat_24": 0,
                "karat_22": 0,
                "karat_21": 0,
                "karat_18": 0,
                "karat_14": 0,
                "ounce": 0,
                "pound": 0
            }
        
        # Map karats
        if h.key == "24": days_map[day_str]["karat_24"] = h.sell_price
        elif h.key == "22": days_map[day_str]["karat_22"] = h.sell_price
        elif h.key == "21": days_map[day_str]["karat_21"] = h.sell_price
        elif h.key == "18": days_map[day_str]["karat_18"] = h.sell_price
        elif h.key == "14": days_map[day_str]["karat_14"] = h.sell_price
        
    # Post-process to calculate missing values from Karat 21 if available
    for day in days_map.values():
        p21 = day["karat_21"]
        if p21 > 0:
            if day["karat_24"] == 0: day["karat_24"] = round(p21 * 24 / 21, 2)
            if day["karat_22"] == 0: day["karat_22"] = round(p21 * 22 / 21, 2)
            if day["karat_18"] == 0: day["karat_18"] = round(p21 * 18 / 21, 2)
            if day["karat_14"] == 0: day["karat_14"] = round(p21 * 14 / 21, 2)
            if day["pound"] == 0: day["pound"] = round(p21 * 8, 2)
            if day["ounce"] == 0: day["ounce"] = round(day["karat_24"] * 31.1035, 2)
        elif day["karat_24"] > 0:
            p24 = day["karat_24"]
            if day["karat_21"] == 0: day["karat_21"] = round(p24 * 21 / 24, 2)
            if day["karat_22"] == 0: day["karat_22"] = round(p24 * 22 / 24, 2)
            if day["karat_18"] == 0: day["karat_18"] = round(p24 * 18 / 24, 2)
            if day["karat_14"] == 0: day["karat_14"] = round(p24 * 14 / 24, 2)
            if day["pound"] == 0: day["pound"] = round(day["karat_21"] * 8, 2)
            if day["ounce"] == 0: day["ounce"] = round(p24 * 31.1035, 2)
            
    # Sort by date desc
    result = sorted(days_map.values(), key=lambda x: x["date"], reverse=True)
    return result[:30]

@router.get("/all-countries")
def legacy_all_countries(db: Session = Depends(database.get_db)):
    """Map legacy all-countries to the correct endpoint"""
    from app.endpoints.gold import get_all_countries_latest
    return get_all_countries_latest(db)

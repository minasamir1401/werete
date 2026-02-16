from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func
from app.core import database
from app import models
from app.core.cache import cache
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

router = APIRouter()

@router.get("/snapshot")
def get_full_market_snapshot(db: Session = Depends(database.get_db)):
    """
    THE UNIFIED API: Returns everything needed for Web & Mobile in one request.
    Including latest prices, silver, news, QA, banks, and 7-day small chart preview.
    """
    cache_key = "v1_global_snapshot_final_v3"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Basic data
    latest_news = db.query(models.Article).order_by(models.Article.created_at.desc()).limit(10).all()
    latest_silver = db.query(models.SilverPrice).order_by(models.SilverPrice.created_at.desc()).first()
    settings_list = db.query(models.Setting).all()
    settings = {s.key: s.value for s in settings_list}
    all_prices = db.query(models.UnifiedPrice).all()
    qa_items = db.query(models.QAItem).filter(models.QAItem.is_active == True).order_by(models.QAItem.display_order.asc()).all()
    
    # Gold History Preview (7 days) for chart
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    history_preview = db.query(models.PriceHistory).filter(
        models.PriceHistory.type == "gold",
        models.PriceHistory.country == "egypt",
        models.PriceHistory.key == "21",
        models.PriceHistory.timestamp >= seven_days_ago
    ).order_by(models.PriceHistory.timestamp.asc()).all()

    snapshot = {
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "api_version": "1.4.0"},
        "settings": settings,
        "gold_egypt": {"prices": {}, "source": None, "last_update": None},
        "currencies": {"rates": {}, "source": None, "last_update": None},
        "countries": {},
        "silver": {
            "gram": latest_silver.silver_999_sell if latest_silver else None,
            "sell_price": latest_silver.silver_999_sell if latest_silver else None,
            "buy_price": latest_silver.silver_999_buy if latest_silver else None,
            "ounce": latest_silver.silver_ounce_price if latest_silver else None,
            "ounce_usd": latest_silver.ounce_usd_sell if latest_silver else None,
            "purities": {
                "999": latest_silver.silver_999_sell if latest_silver else None,
                "925": latest_silver.silver_925_sell if latest_silver else None,
                "900": latest_silver.silver_900_sell if latest_silver else None,
                "800": latest_silver.silver_800_sell if latest_silver else None
            },
            "last_update": latest_silver.created_at.isoformat() if latest_silver else None,
        },
        "news": [
            {"title": art.title, "slug": art.slug, "featured_image": art.featured_image, "created_at": art.created_at.isoformat()} 
            for art in latest_news
        ],
        "qa": [
            {"id": q.id, "page_key": q.page_key, "question": q.question, "answer": q.answer}
            for q in qa_items
        ],
        "gold_history_preview": [
            {"date": h.timestamp.strftime("%m-%d"), "price": h.sell_price} for h in history_preview
        ]
    }

    for p in all_prices:
        p_type = p.type.lower() if p.type else ""
        p_country = p.country.lower() if p.country else ""
        if p_type in ["gold", "local"] and p_country == "egypt":
            snapshot["gold_egypt"]["prices"][p.key] = {"sell": p.sell_price, "buy": p.buy_price}
            snapshot["gold_egypt"]["source"] = p.source_name
            snapshot["gold_egypt"]["last_update"] = p.last_update.isoformat() if p.last_update else None
        elif p_type == "currency":
            snapshot["currencies"]["rates"][p.key] = {"sell": p.sell_price, "buy": p.buy_price}
            snapshot["currencies"]["source"] = p.source_name
            snapshot["currencies"]["last_update"] = p.last_update.isoformat() if p.last_update else None

    cache.set(cache_key, snapshot, ttl=60)
    return snapshot

@router.get("/gold/history-range")
def get_gold_history_range(
    days: int = Query(7, description="Number of days for history"),
    karat: str = Query("21", description="Gold karat"),
    db: Session = Depends(database.get_db)
):
    """Fetch gold price history for a specific range and karat for charts & tables"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    history = db.query(models.PriceHistory).filter(
        models.PriceHistory.type == "gold",
        models.PriceHistory.country == "egypt",
        models.PriceHistory.key == karat,
        models.PriceHistory.timestamp >= start_date
    ).order_by(models.PriceHistory.timestamp.desc()).all()
    
    # Calculate daily changes
    result = []
    for i in range(len(history)):
        current = history[i]
        change = 0
        if i < len(history) - 1:
            prev = history[i+1]
            change = current.sell_price - prev.sell_price
            
        result.append({
            "date": current.timestamp.strftime("%Y-%m-%d"),
            "timestamp": current.timestamp.isoformat(),
            "sell": current.sell_price,
            "buy": current.buy_price,
            "change": round(change, 2),
            "change_percent": round((change / history[i+1].sell_price * 100), 2) if i < len(history) - 1 and history[i+1].sell_price > 0 else 0
        })
        
    return {
        "days": days,
        "karat": karat,
        "data": result,
        "chart_labels": [h["date"] for h in reversed(result)],
        "chart_data": [h["sell"] for h in reversed(result)]
    }

@router.get("/gold/today")
def get_gold_today(db: Session = Depends(database.get_db)):
    data = get_full_market_snapshot(db)
    return data["gold_egypt"]

@router.get("/currency/today")
def get_currency_today(db: Session = Depends(database.get_db)):
    data = get_full_market_snapshot(db)
    return data["currencies"]

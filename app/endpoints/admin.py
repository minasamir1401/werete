from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timezone
from app.core import database
from app import models, schemas
from app.core.auth import get_current_user
from app.scraper.engine import ScraperManager

router = APIRouter()

@router.get("/settings", response_model=List[schemas.Setting])
def get_settings(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Retrieve all site settings from database"""
    return db.query(models.Setting).all()

@router.post("/settings", response_model=schemas.Setting)
def update_setting(setting: schemas.SettingBase, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Update or create a site setting in database"""
    db_setting = db.query(models.Setting).filter(models.Setting.key == setting.key).first()
    if db_setting:
        db_setting.value = setting.value
    else:
        db_setting = models.Setting(key=setting.key, value=setting.value)
        db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting

@router.post("/scrape")
async def trigger_gold_scrape(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Trigger manual gold scraping and persist result to database (SSoT)"""
    manager = ScraperManager()
    prices = await manager.get_latest_prices()
    if prices:
        from app.main import save_prices_to_db
        save_prices_to_db(db, prices)
        return {"status": "success", "count": len(prices), "source": prices[0].get("source")}
    return {"status": "failed", "message": "No prices fetched"}

@router.post("/test-gold-source/{source_name}")
async def test_gold_source(source_name: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Test a specific gold source"""
    from app.scraper.engine import ScraperManager
    
    manager = ScraperManager()
    source = manager.all_sources.get(source_name)
    
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")
    
    start_time = datetime.now(timezone.utc)
    try:
        prices = await source.fetch_prices()
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        sample = None
        if prices and len(prices) > 0:
             # Find a sample price (e.g., 21 karat) or just the first one
             # Handle prices being a list of dicts
             p21 = next((p for p in prices if str(p.get('karat')) == '21'), None)
             sample_price = p21 if p21 else prices[0]
             if sample_price:
                sample = f"عيار {sample_price.get('karat')}: {sample_price.get('sell_price')}"

        if not prices and not getattr(source, "last_error", None):
             source.last_error = "No prices found. Possible layout change or bot protection."

        return {
            "status": "success" if prices else "failed",
            "count": len(prices),
            "duration": duration,
            "sample": sample,
            "error": getattr(source, "last_error", None)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.post("/scrape/currency")
async def trigger_currency_scrape(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Trigger manual currency scraping and persist result to database (SSoT)"""
    from app.scraper.currency import get_all_currency_rates
    from app.main import save_currency_prices_to_db
    
    rates = await get_all_currency_rates(db=db)
    if rates:
        save_currency_prices_to_db(db, rates)
        return {"status": "success", "count": len(rates)}
    return {"status": "failed", "message": "No rates fetched"}

# Currency Source Management
@router.get("/currency-sources", response_model=List[schemas.CurrencySourceSetting])
def get_currency_sources(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Get all currency sources and their status"""
    sources = db.query(models.CurrencySourceSettings).order_by(models.CurrencySourceSettings.priority).all()
    # Initialize defaults if empty
    if not sources:
        defaults = [
            {"source_name": "ta3weem", "display_name": "موقع تعويم (الأساسي)", "priority": 1},
            {"source_name": "egrates", "display_name": "موقع إي جي ريتس", "priority": 2},
            {"source_name": "banklive", "display_name": "موقع بنك لايف", "priority": 3},
        ]
        for d in defaults:
            s = models.CurrencySourceSettings(**d)
            db.add(s)
        db.commit()
        sources = db.query(models.CurrencySourceSettings).order_by(models.CurrencySourceSettings.priority).all()
    return sources

@router.post("/currency-sources/{source_name}")
def update_currency_source(source_name: str, update: schemas.CurrencySourceUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Enable/disable or change priority of a currency source"""
    source = db.query(models.CurrencySourceSettings).filter(models.CurrencySourceSettings.source_name == source_name).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if update.is_enabled is not None:
        source.is_enabled = update.is_enabled
    if update.priority is not None:
        source.priority = update.priority
    
    db.commit()
    return source

@router.post("/currency-sources/reorder")
def reorder_currency_sources(order: List[str], db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Bulk reorder currency sources"""
    for i, name in enumerate(order):
        source = db.query(models.CurrencySourceSettings).filter(models.CurrencySourceSettings.source_name == name).first()
        if source:
            source.priority = i + 1
    db.commit()
    return {"status": "success"}

@router.post("/test-currency-source/{source_name}")
async def test_currency_source(source_name: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Test a specific currency source"""
    from app.scraper.currency import CurrencyScraperManager
    manager = CurrencyScraperManager(db_session=db)
    
    # Use the map to find the source for NBE (as a test case)
    source_bank_map = manager.sources_map.get(source_name, {}).get("nbe")
    if not source_bank_map:
        raise HTTPException(status_code=404, detail="Source or test bank not found")
    
    start_time = datetime.now(timezone.utc)
    try:
        rates = await source_bank_map.fetch_rates()
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return {
            "status": "success" if rates else "failed",
            "count": len(rates),
            "duration": duration,
            "sample": f"{rates[0]['currency']}: {rates[0]['sell_price']}" if rates else None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Silver Source Management
@router.get("/silver-sources", response_model=List[schemas.SilverSourceSetting])
def get_silver_sources(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Get all silver sources and their status"""
    sources = db.query(models.SilverSourceSettings).order_by(models.SilverSourceSettings.priority).all()
    # Initialize defaults if empty
    if not sources:
        defaults = [
            {"source_name": "safehavenhub", "display_name": "موقع سيف هافن (الأساسي)", "priority": 1},
            {"source_name": "goldpricelive", "display_name": "موقع جولد برايس لايف", "priority": 2},
        ]
        for d in defaults:
            s = models.SilverSourceSettings(**d)
            db.add(s)
        db.commit()
        sources = db.query(models.SilverSourceSettings).order_by(models.SilverSourceSettings.priority).all()
    return sources

@router.post("/silver-sources/{source_name}")
def update_silver_source(source_name: str, update: schemas.SilverSourceUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Enable/disable or change priority of a silver source"""
    source = db.query(models.SilverSourceSettings).filter(models.SilverSourceSettings.source_name == source_name).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if update.is_enabled is not None:
        source.is_enabled = update.is_enabled
    if update.priority is not None:
        source.priority = update.priority
    
    db.commit()
    return source

@router.post("/silver-sources/reorder")
def reorder_silver_sources(order: List[str], db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Bulk reorder silver sources"""
    for i, name in enumerate(order):
        source = db.query(models.SilverSourceSettings).filter(models.SilverSourceSettings.source_name == name).first()
        if source:
            source.priority = i + 1
    db.commit()
    return {"status": "success"}

@router.post("/test-silver-source/{source_name}")
async def test_silver_source(source_name: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Test a specific silver source"""
    from app.scraper.silver_scraper import SilverScraper
    scraper = SilverScraper()
    
    start_time = datetime.now(timezone.utc)
    try:
        # We need a custom fetch for the specific source to test it correctly
        if source_name == "safehavenhub":
            data = await scraper._scrape_safehavenhub()
        elif source_name == "goldpricelive":
            data = await scraper._scrape_goldpricelive()
        else:
            raise HTTPException(status_code=404, detail="Source not found")
            
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return {
            "status": "success" if data and (data.get('silver_999_sell') or data.get('silver_gram_price')) else "failed",
            "count": 1 if data else 0,
            "duration": duration,
            "sample": f"Price: {data.get('silver_999_sell') or data.get('silver_gram_price')}" if data else None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.get("/stats", response_model=schemas.AdminStats)
def get_stats(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Retrieve system statistics from database tables"""
    # Count totals from the unified and historical tables
    price_count = db.query(models.PriceHistory).count()
    article_count = db.query(models.Article).count()
    
    latest_entry = db.query(models.UnifiedPrice).order_by(models.UnifiedPrice.last_update.desc()).first()
    
    # Calculate unique snapshots using unique timestamps in history
    snapshots_count = db.query(func.count(func.distinct(models.PriceHistory.timestamp))).scalar()
    
    # Fetch current prices for the dashboard display
    egypt_prices = db.query(models.UnifiedPrice).filter(
        models.UnifiedPrice.type.in_(["gold", "local"]),
        models.UnifiedPrice.country == "egypt"
    ).all()
    
    current_prices = {}
    for p in egypt_prices:
        current_prices[f"عيار {p.key}"] = {"sell": p.sell_price, "buy": p.buy_price}
        current_prices[p.key] = {"sell": p.sell_price, "buy": p.buy_price}

    return {
        "total_prices": price_count,
        "total_articles": article_count,
        "last_update": latest_entry.last_update if latest_entry else None,
        "active_source": latest_entry.source_name if latest_entry else "Unknown",
        "db_snapshots_count": snapshots_count or 0,
        "cache_last_updated": latest_entry.last_update if latest_entry else datetime.now(timezone.utc),
        "scraper_status": {},
        "prices": current_prices,
        "news_stats": {"total": article_count}
    }

@router.get("/manual-prices")
def get_manual_prices(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Retrieve all manual price overrides from settings"""
    manual_prices = {}
    settings = db.query(models.Setting).filter(models.Setting.key.like("manual_price_%")).all()
    for s in settings:
        karat = s.key.replace("manual_price_", "")
        manual_prices[karat] = s.value
    return manual_prices

@router.post("/manual-price")
def update_manual_price(update: schemas.ManualPriceUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Set or remove a manual price override in settings"""
    key = f"manual_price_{update.karat}"
    db_setting = db.query(models.Setting).filter(models.Setting.key == key).first()
    
    if update.price is None or update.price == "":
        if db_setting:
            db.delete(db_setting)
    else:
        price_val = float(update.price)
        if db_setting:
            db_setting.value = str(update.price)
        else:
            db_setting = models.Setting(key=key, value=str(update.price))
            db.add(db_setting)
        
        # Also record this in PriceHistory so it appears in the charts/archive
        new_history = models.PriceHistory(
            type="gold",
            country="egypt",
            key=update.karat,
            sell_price=price_val,
            buy_price=price_val,
            source_name="Manual Override",
            timestamp=datetime.now(timezone.utc)
        )
        db.add(new_history)
        
        # Also update UnifiedPrice (SSoT) so the database state matches the setting
        db_unified = db.query(models.UnifiedPrice).filter(
            models.UnifiedPrice.type.in_(["gold", "local"]),
            models.UnifiedPrice.country == "egypt",
            models.UnifiedPrice.key == update.karat
        ).first()
        
        if db_unified:
            db_unified.sell_price = price_val
            db_unified.buy_price = price_val
            db_unified.source_name = "Manual"
            db_unified.source_status = "Manual"
            db_unified.last_update = datetime.utcnow()
            
    db.commit()
    return {"status": "success"}

@router.get("/raw-cache")
def get_raw_cache(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Aggregated snapshot for dashboard debugging, read from database"""
    from app.endpoints.gold import read_current_prices, get_all_countries_latest
    
    egypt_prices = read_current_prices(db)
    prices_map = {f"عيار {p.karat}": {"sell": p.sell_price, "buy": p.buy_price} for p in egypt_prices}
    countries_data = get_all_countries_latest(db)
    
    return {
        "prices": prices_map,
        "countries": countries_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/seed-archive")
async def seed_archive(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Trigger the historical scraper to seed the database with archive data"""
    from app.scraper.history_scraper import scrape_all_historical_periods
    count = await scrape_all_historical_periods(db)
    return {"status": "success", "message": f"Seeded database with {count} historical records."}

@router.post("/scrape-news")
async def trigger_news_scrape(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    """Trigger manual news scraping"""
    from app.scraper.news_scraper import NewsScraperManager
    from app.models import Article
    from slugify import slugify
    import random

    manager = NewsScraperManager()
    articles = await manager.get_latest_news()
    
    count = 0
    for article_data in articles:
        existing = db.query(Article).filter(Article.title == article_data['title']).first()
        if not existing:
            base_slug = slugify(article_data['title'])
            if not base_slug: base_slug = "news-item"
            slug = base_slug
            while db.query(Article).filter(Article.slug == slug).first():
                slug = f"{base_slug}-{random.randint(1000, 9999)}"
            
            new_article = Article(
                title=article_data['title'],
                slug=slug,
                content=f"Original source: {article_data['url']}",
                featured_image=article_data.get('image'),
                author=article_data.get('source'),
                status="published",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_article)
            count += 1
            
    db.commit()
    return {"status": "success", "fetched": len(articles), "added": count}

@router.get("/test-news-sources")
async def test_news_sources(current_user: models.User = Depends(get_current_user)):
    """Test all news sources and return diagnostic info"""
    from app.scraper.news_scraper import NewsScraperManager
    manager = NewsScraperManager()
    results = await manager.test_sources()
    return results

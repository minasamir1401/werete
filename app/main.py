from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
import uvicorn
import asyncio
import os
import shutil
import uuid
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core import database
from app import models
from app.scraper import engine as scraper_engine
from app.scraper import currency as currency_scraper
from app.api import api_router

# Configure logging with dynamic level
logging.basicConfig(level=logging.INFO if settings.ENV == "production" else logging.DEBUG)
logger = logging.getLogger(__name__)

# Smart Initialization Layer
def init_db():
    try:
        logger.info(f"Connecting to Database: {settings.DATABASE_URL.split('@')[-1]}") # Log without credentials
        models.Base.metadata.create_all(bind=database.engine)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization FAILED: {e}")

init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Backend Smart Layer Activated in {settings.ENV} mode.")
    # Start background scraping tasks
    asyncio.create_task(run_scraper_periodically())
    asyncio.create_task(run_country_scraper_periodically())
    asyncio.create_task(run_currency_scraper_periodically())
    asyncio.create_task(run_full_bank_scrape_periodically())
    asyncio.create_task(run_silver_scraper_periodically())
    yield
    logger.info("Backend shutting down gracefully...")

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Allow CORS
# Smart CORS Layer
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for Vercel deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Gold Service Backend"
    }

async def run_scraper_periodically():
    while True:
        logger.info("Starting scheduled gold scrape...")
        db = database.SessionLocal()
        interval = 60
        try:
            setting = db.query(models.Setting).filter(models.Setting.key == "scrape_interval").first()
            if setting and setting.value:
                try:
                    interval = int(setting.value)
                except ValueError:
                    pass

            manager = scraper_engine.ScraperManager()
            prices = await manager.get_latest_prices()
            if prices:
                logger.info(f"Scraped {len(prices)} gold prices.")
                save_prices_to_db(db, prices)
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
        finally:
            db.close()
        
        logger.info(f"Waiting {interval} seconds for next gold scrape...")
        await asyncio.sleep(interval)

async def run_country_scraper_periodically():
    while True:
        logger.info("Starting scheduled country scrape...")
        db = database.SessionLocal()
        interval = 3600
        try:
            setting = db.query(models.Setting).filter(models.Setting.key == "backup_interval").first()
            if setting and setting.value:
                try:
                    interval = int(setting.value)
                except ValueError:
                    pass

            manager = scraper_engine.CountryScraperManager()
            all_country_prices = await manager.get_all_country_prices()
            if all_country_prices:
                logger.info(f"Scraped {len(all_country_prices)} country prices.")
                save_prices_to_db(db, all_country_prices)
        except Exception as e:
            logger.error(f"Country scrape failed: {e}")
        finally:
            db.close()
        
        logger.info(f"Waiting {interval} seconds for next country scrape...")
        await asyncio.sleep(interval)

async def run_currency_scraper_periodically():
    while True:
        logger.info("Starting scheduled currency scrape...")
        db = database.SessionLocal()
        interval = 1200
        try:
            setting = db.query(models.Setting).filter(models.Setting.key == "backup_interval").first()
            if setting and setting.value:
                try:
                    interval = int(setting.value)
                except ValueError:
                    pass

            enabled_setting = db.query(models.Setting).filter(models.Setting.key == "enabled_currency_sources").first()
            enabled_sources = None
            if enabled_setting:
                enabled_sources = [s.strip() for s in enabled_setting.value.split(",") if s.strip()]
            
            rates = await currency_scraper.get_all_currency_rates(enabled_sources)
            if rates:
                logger.info(f"Scraped {len(rates)} currency rates.")
                save_currency_prices_to_db(db, rates)
        except Exception as e:
            logger.error(f"Currency scraping process failed: {e}")
        finally:
            db.close()
        
        logger.info(f"Waiting {interval} seconds for next currency scrape...")
        await asyncio.sleep(interval)

async def run_full_bank_scrape_periodically():
    from app.scraper.all_banks_scraper import AllBanksScraperManager
    
    while True:
        logger.info("Starting scheduled full banks scrape...")
        db = database.SessionLocal()
        interval = 3600
        try:
            setting = db.query(models.Setting).filter(models.Setting.key == "backup_interval").first()
            if setting and setting.value:
                try:
                    interval = int(setting.value)
                except ValueError:
                    pass

            manager = AllBanksScraperManager(db_session=db)
            currencies = ["USD", "EUR", "SAR", "GBP", "KWD", "AED", "QAR", "JOD", "BHD", "OMR", "CAD", "AUD", "CHF", "JPY"]
            
            results = await manager.fetch_all_banks_all_currencies(currencies)
            if results:
                logger.info(f"Scraped {len(results)} bank rates.")
                
                now = datetime.now(timezone.utc)
                today = now.date()
                
                # Delete old rates for this batch update to prevent duplicates
                db.query(models.BankCurrencyRate).delete()
                
                for rate in results:
                    db_rate = models.BankCurrencyRate(
                        bank_name=rate['bank_name'],
                        bank_url=rate.get('bank_url', ''),
                        bank_logo=rate.get('bank_logo', ''),
                        from_currency=rate['currency'],
                        to_currency="EGP",
                        buy_price=rate['buy_price'],
                        sell_price=rate['sell_price'],
                        buy_change=0.0,
                        sell_change=0.0,
                        last_update_time=now.strftime("%I:%M %p"),
                        last_update_date=today.strftime("%d/%m/%Y"),
                        timestamp=now,
                        date=today
                    )
                    db.add(db_rate)
                
                db.commit()
                logger.info("Successfully updated database snapshot.")
            
        except Exception as e:
            logger.error(f"Full banks scraping process failed: {e}")
        finally:
            db.close()
        
        logger.info(f"Waiting {interval} seconds for next full bank scrape...")
        await asyncio.sleep(interval)

def save_prices_to_db(db: Session, prices_data: List[dict]):
    """Atomic update for UnifiedPrice and PriceHistory"""
    if not prices_data:
        return

    update_time = datetime.now(timezone.utc)
    
    for p in prices_data:
        p_type = p.get('type', 'gold').lower()
        country = p.get('country', 'egypt').lower()
        key = str(p.get('karat') or p.get('currency'))
        
        if not key:
            continue

        db_price = db.query(models.UnifiedPrice).filter(
            models.UnifiedPrice.type == p_type,
            models.UnifiedPrice.country == country,
            models.UnifiedPrice.key == key
        ).first()

        price_changed = True
        if db_price:
            price_changed = (db_price.sell_price != p['sell_price'] or db_price.buy_price != p['buy_price'])
            
            db_price.sell_price = p['sell_price']
            db_price.buy_price = p['buy_price']
            db_price.currency = p.get('currency', 'EGP')
            db_price.source_name = p.get('source')
            db_price.source_status = p.get('source_status', 'Fallback')
            db_price.last_update = update_time
        else:
            db_price = models.UnifiedPrice(
                type=p_type,
                country=country,
                key=key,
                sell_price=p['sell_price'],
                buy_price=p['buy_price'],
                currency=p.get('currency', 'EGP'),
                source_name=p.get('source'),
                source_status=p.get('source_status', 'Fallback'),
                last_update=update_time
            )
            db.add(db_price)
            db.flush()

        if price_changed:
            history = models.PriceHistory(
                price_id=db_price.id,
                type=p_type,
                country=country,
                key=key,
                sell_price=p['sell_price'],
                buy_price=p['buy_price'],
                source_name=p.get('source'),
                timestamp=update_time
            )
            db.add(history)

    db.commit()

def save_currency_prices_to_db(db: Session, rates_data: List[dict]):
    """Unified saving for currencies"""
    if not rates_data:
        return
        
    standardized = []
    for r in rates_data:
        standardized.append({
            'type': 'currency',
            'country': 'egypt',
            'currency': r['currency'],
            'sell_price': r['sell_price'],
            'buy_price': r['buy_price'],
            'source': r['source'],
            'source_status': r.get('source_status', 'Primary'),
            'timestamp': r['timestamp'],
            'date': r['timestamp'].date(),
            'time': r['timestamp'].time()
        })
    
    save_prices_to_db(db, standardized)

async def run_silver_scraper_periodically():
    from app.scraper.silver_scraper import scrape_silver_prices
    
    while True:
        logger.info("Starting scheduled silver scrape...")
        db = database.SessionLocal()
        interval = 60
        
        try:
            setting = db.query(models.Setting).filter(
                models.Setting.key == "silver_scrape_interval"
            ).first()
            if setting and setting.value:
                try:
                    interval = int(setting.value)
                except ValueError:
                    pass
            
            # Ensure silver sources are initialized
            sources_count = db.query(models.SilverSourceSettings).count()
            if sources_count == 0:
                defaults = [
                    {"source_name": "safehavenhub", "display_name": "موقع سيف هافن (الأساسي)", "priority": 1},
                    {"source_name": "goldpricelive", "display_name": "موقع جولد برايس لايف", "priority": 2},
                ]
                for d in defaults:
                    s = models.SilverSourceSettings(**d)
                    db.add(s)
                db.commit()

            silver_data = await scrape_silver_prices(db=db)
            
            if silver_data:
                silver_record = models.SilverPrice(
                    source_used=silver_data.get('source_used'),
                    source_status=silver_data.get('source_status'),
                    silver_999_sell=silver_data.get('silver_999_sell'),
                    silver_999_buy=silver_data.get('silver_999_buy'),
                    silver_999_change=silver_data.get('silver_999_change'),
                    silver_999_change_percent=silver_data.get('silver_999_change_percent'),
                    silver_925_sell=silver_data.get('silver_925_sell'),
                    silver_925_buy=silver_data.get('silver_925_buy'),
                    silver_925_change=silver_data.get('silver_925_change'),
                    silver_925_change_percent=silver_data.get('silver_925_change_percent'),
                    silver_900_sell=silver_data.get('silver_900_sell'),
                    silver_900_buy=silver_data.get('silver_900_buy'),
                    silver_900_change=silver_data.get('silver_900_change'),
                    silver_900_change_percent=silver_data.get('silver_900_change_percent'),
                    silver_800_sell=silver_data.get('silver_800_sell'),
                    silver_800_buy=silver_data.get('silver_800_buy'),
                    silver_800_change=silver_data.get('silver_800_change'),
                    silver_800_change_percent=silver_data.get('silver_800_change_percent'),
                    ounce_usd_sell=silver_data.get('ounce_usd_sell'),
                    ounce_usd_buy=silver_data.get('ounce_usd_buy'),
                    ounce_usd_change=silver_data.get('ounce_usd_change'),
                    ounce_usd_change_percent=silver_data.get('ounce_usd_change_percent'),
                    silver_gram_price=silver_data.get('silver_gram_price'),
                    silver_ounce_price=silver_data.get('silver_ounce_price'),
                    silver_999_price=silver_data.get('silver_999_price'),
                    silver_925_price=silver_data.get('silver_925_price'),
                    buy_price=silver_data.get('buy_price'),
                    sell_price=silver_data.get('sell_price'),
                    daily_change=silver_data.get('daily_change'),
                    daily_change_percent=silver_data.get('daily_change_percent'),
                    currency=silver_data.get('currency', 'EGP'),
                    scraped_at=silver_data.get('scraped_at'),
                    source_update_time=silver_data.get('source_update_time'),
                    raw_data=silver_data.get('raw_data')
                )
                
                db.add(silver_record)
                db.commit()
                
                logger.info(f"Silver scrape successful! Source: {silver_data.get('source_used')}")
            else:
                logger.warning("Silver scrape returned no data")
                
        except Exception as e:
            logger.error(f"Silver scraping process failed: {e}")
        finally:
            db.close()
        
        logger.info(f"Waiting {interval} seconds for next silver scrape...")
        await asyncio.sleep(interval)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

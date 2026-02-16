from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import datetime, date

from app import models, schemas
from app.core import database
from app.scraper.currency_scraper import Ta3weemCurrencyScraper

router = APIRouter()

@router.get("/prices", response_model=List[schemas.CurrencyPrice])
@router.get("/sarf-currencies", response_model=List[schemas.CurrencyPrice])
def get_latest_currency_prices(db: Session = Depends(database.get_db)):
    """Get latest exchange rates from UnifiedPrice (SSoT)"""
    prices = db.query(models.UnifiedPrice).filter(
        models.UnifiedPrice.type == "currency"
    ).all()
    
    if not prices:
        return []
    
    return [
        schemas.CurrencyPrice(
            id=p.id,
            currency=p.key,
            sell_price=p.sell_price,
            buy_price=p.buy_price,
            symbol=None,
            timestamp=p.last_update,
            date=p.last_update.date() if p.last_update else datetime.utcnow().date(),
            time=p.last_update.time() if p.last_update else datetime.utcnow().time(),
            source=p.source_name
        ) for p in prices
    ]

@router.get("/rates/{from_currency}/{to_currency}")
def get_currency_rates(from_currency: str, to_currency: str, db: Session = Depends(database.get_db)):
    """Retrieve currency rates and calculated summary from BankCurrencyRate table"""
    latest = db.query(models.BankCurrencyRate).filter(
        and_(
            models.BankCurrencyRate.from_currency == from_currency.upper(),
            models.BankCurrencyRate.to_currency == to_currency.upper()
        )
    ).order_by(desc(models.BankCurrencyRate.timestamp)).first()
    
    if not latest:
        raise HTTPException(status_code=404, detail="No data found in database for this currency pair")
    
    rates = db.query(models.BankCurrencyRate).filter(
        and_(
            models.BankCurrencyRate.from_currency == from_currency.upper(),
            models.BankCurrencyRate.to_currency == to_currency.upper(),
            models.BankCurrencyRate.timestamp == latest.timestamp
        )
    ).all()
    
    buy_prices = [r.buy_price for r in rates if r.buy_price]
    sell_prices = [r.sell_price for r in rates if r.sell_price]
    
    summary = {
        "highest_buy": max(buy_prices) if buy_prices else None,
        "lowest_sell": min(sell_prices) if sell_prices else None,
        "average_buy": sum(buy_prices) / len(buy_prices) if buy_prices else None,
        "average_sell": sum(sell_prices) / len(sell_prices) if sell_prices else None,
    }
    
    return {
        "currency_pair": f"{from_currency.upper()}/{to_currency.upper()}",
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "timestamp": latest.timestamp.isoformat(),
        "summary": summary,
        "banks": [
            {
                "name": r.bank_name,
                "url": r.bank_url,
                "logo": r.bank_logo,
                "buy_price": r.buy_price,
                "sell_price": r.sell_price,
                "buy_change": r.buy_change,
                "sell_change": r.sell_change,
                "last_update_time": r.last_update_time,
                "last_update_date": r.last_update_date,
                "currency_flag": r.currency_flag
            }
            for r in rates
        ],
        "total_banks": len(rates)
    }

@router.post("/scrape/{from_currency}/{to_currency}")
async def scrape_currency_rates(from_currency: str, to_currency: str, db: Session = Depends(database.get_db)):
    """Trigger manual scrape and save to database (Single Source of Truth)"""
    try:
        scraper = Ta3weemCurrencyScraper()
        data = scraper.scrape_currency(from_currency.upper(), to_currency.upper())
        
        if not data:
            raise HTTPException(status_code=500, detail="Failed to scrape data")
        
        now = datetime.now()
        today = date.today()
        
        summary = data['summary']
        db_summary = models.CurrencyMarketSummary(
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
            highest_buy=summary.get('highest_buy'),
            highest_buy_change=summary.get('highest_buy_change'),
            lowest_sell=summary.get('lowest_sell'),
            lowest_sell_change=summary.get('lowest_sell_change'),
            average=summary.get('average'),
            average_change=summary.get('average_change'),
            central_bank_buy=summary.get('central_bank_buy'),
            central_bank_sell=summary.get('central_bank_sell'),
            decision_center_buy=summary.get('decision_center_buy'),
            decision_center_sell=summary.get('decision_center_sell'),
            timestamp=now,
            date=today
        )
        db.add(db_summary)

        saved_count = 0
        for bank in data['banks']:
            db_rate = models.BankCurrencyRate(
                bank_name=bank.get('name'),
                bank_url=bank.get('url'),
                bank_logo=bank.get('logo'),
                from_currency=from_currency.upper(),
                to_currency=to_currency.upper(),
                buy_price=bank.get('buy_price'),
                sell_price=bank.get('sell_price'),
                buy_change=bank.get('buy_change'),
                sell_change=bank.get('sell_change'),
                last_update_time=bank.get('last_update_time'),
                last_update_date=bank.get('last_update_date'),
                timestamp=now,
                date=today
            )
            db.add(db_rate)
            saved_count += 1
        
        db.commit()
        return {
            "status": "success",
            "message": f"Data persisted to database. Found {saved_count} banks.",
            "currency_pair": f"{from_currency.upper()}/{to_currency.upper()}"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/db/rates/latest")
def get_db_latest_rates(db: Session = Depends(database.get_db)):
    """Retrieve the latest bank rates from database"""
    rates = db.query(models.BankCurrencyRate).all()
    return {
        "status": "success",
        "timestamp": rates[0].timestamp if rates else None,
        "data": rates
    }

@router.get("/available-currencies")
def get_available_currencies(db: Session = Depends(database.get_db)):
    """Get list of available currency pairs from database"""
    pairs = db.query(
        models.BankCurrencyRate.from_currency,
        models.BankCurrencyRate.to_currency
    ).distinct().all()
    
    return {
        "currency_pairs": [
            {"from": pair[0], "to": pair[1], "pair": f"{pair[0]}/{pair[1]}"}
            for pair in pairs
        ]
    }

@router.get("/banks")
def get_banks(db: Session = Depends(database.get_db)):
    """Get a list of all unique banks from database"""
    raw_banks = db.query(
        models.BankCurrencyRate.bank_name,
        models.BankCurrencyRate.bank_logo,
        models.BankCurrencyRate.bank_url
    ).distinct().all()
    
    return [{"name": b.bank_name, "logo": b.bank_logo, "url": b.bank_url} for b in raw_banks]

@router.get("/bank/{bank_name}")
def get_bank_rates(bank_name: str, db: Session = Depends(database.get_db)):
    """Get latest rates for a specific bank from database"""
    rates = db.query(models.BankCurrencyRate).filter(
        models.BankCurrencyRate.bank_name.ilike(f"%{bank_name.strip()}%")
    ).order_by(models.BankCurrencyRate.timestamp.desc()).limit(20).all()
    
    if not rates:
        raise HTTPException(status_code=404, detail="Bank not found in database")
        
    return {
        "bank_name": bank_name,
        "rates": rates
    }

@router.get("/summary/{from_currency}/{to_currency}")
def get_market_summary(from_currency: str, to_currency: str, db: Session = Depends(database.get_db)):
    """Retrieve the latest market summary from database, or calculate it on the fly"""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    # Try to get existing summary
    summary = db.query(models.CurrencyMarketSummary).filter(
        and_(
            models.CurrencyMarketSummary.from_currency == from_currency,
            models.CurrencyMarketSummary.to_currency == to_currency
        )
    ).order_by(desc(models.CurrencyMarketSummary.timestamp)).first()
    
    if summary:
        return summary
        
    # If no summary, calculate from bank rates
    latest_rates = db.query(models.BankCurrencyRate).filter(
        and_(
            models.BankCurrencyRate.from_currency == from_currency,
            models.BankCurrencyRate.to_currency == to_currency
        )
    ).all()
    
    if not latest_rates:
        raise HTTPException(status_code=404, detail="No data found for this currency pair")
        
    buy_prices = [r.buy_price for r in latest_rates if r.buy_price]
    sell_prices = [r.sell_price for r in latest_rates if r.sell_price]
    
    # Try to find Central Bank specifically
    cbe_buy = None
    cbe_sell = None
    cbe = next((r for r in latest_rates if "مركز" in r.bank_name or "CBE" in r.bank_name.upper()), None)
    if cbe:
        cbe_buy = cbe.buy_price
        cbe_sell = cbe.sell_price
        
    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "highest_buy": max(buy_prices) if buy_prices else None,
        "highest_buy_change": 0.0,
        "lowest_sell": min(sell_prices) if sell_prices else None,
        "lowest_sell_change": 0.0,
        "average": sum(sell_prices) / len(sell_prices) if sell_prices else None,
        "average_change": 0.0,
        "central_bank_buy": cbe_buy,
        "central_bank_sell": cbe_sell,
        "timestamp": datetime.now()
    }

@router.post("/trigger-scrape")
async def trigger_currency_scrape(db: Session = Depends(database.get_db)):
    """Trigger manual currency scraping for all enabled sources and save to DB"""
    from app.scraper.all_banks_scraper import AllBanksScraperManager
    
    manager = AllBanksScraperManager(db_session=db)
    currencies = ["USD", "EUR", "SAR", "GBP", "KWD", "AED", "QAR", "JOD", "BHD", "OMR", "CAD", "AUD", "CHF", "JPY"]
    results = await manager.fetch_all_banks_all_currencies(currencies)
    
    count = 0
    now = datetime.now()
    today = date.today()
    
    # Save to SSoT
    db.query(models.BankCurrencyRate).delete()
    for rate in results:
        db_rate = models.BankCurrencyRate(
            bank_name=rate['bank_name'], bank_url=rate.get('bank_url', ''), bank_logo=rate.get('bank_logo', ''),
            from_currency=rate['currency'], to_currency="EGP", buy_price=rate['buy_price'], sell_price=rate['sell_price'],
            buy_change=0.0, sell_change=0.0, last_update_time=now.strftime("%I:%M %p"), last_update_date=today.strftime("%d/%m/%Y"),
            timestamp=now, date=today
        )
        db.add(db_rate)
        count += 1
    
    db.commit()
    return {"success": True, "rates_saved": count, "timestamp": now.isoformat()}

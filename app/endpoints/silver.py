"""
Silver Price API Endpoints
Provides read-only access to silver price data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func
from datetime import datetime, date, timedelta
from typing import List, Optional
import logging

from app.core import database
from app import models

router = APIRouter(tags=["Silver"])
logger = logging.getLogger(__name__)


@router.get("/latest")
def get_latest_silver_price(db: Session = Depends(database.get_db)):
    """
    Get the most recent silver price data
    Returns the latest record from database
    """
    try:
        latest = db.query(models.SilverPrice).order_by(
            desc(models.SilverPrice.created_at)
        ).first()
        
        if not latest:
            raise HTTPException(status_code=404, detail="No silver price data available")
        
        return {
            "id": latest.id,
            "source_used": latest.source_used,
            "source_status": latest.source_status,
            "prices": {
                "gram": latest.silver_gram_price,
                "ounce": latest.silver_ounce_price,
                
                # 999
                "silver_999_sell": latest.silver_999_sell,
                "silver_999_buy": latest.silver_999_buy,
                "silver_999_change": latest.silver_999_change,
                "silver_999_change_percent": latest.silver_999_change_percent,
                
                # 925
                "silver_925_sell": latest.silver_925_sell,
                "silver_925_buy": latest.silver_925_buy,
                "silver_925_change": latest.silver_925_change,
                "silver_925_change_percent": latest.silver_925_change_percent,
                
                # 900
                "silver_900_sell": latest.silver_900_sell,
                "silver_900_buy": latest.silver_900_buy,
                "silver_900_change": latest.silver_900_change,
                "silver_900_change_percent": latest.silver_900_change_percent,
                
                # 800
                "silver_800_sell": latest.silver_800_sell,
                "silver_800_buy": latest.silver_800_buy,
                "silver_800_change": latest.silver_800_change,
                "silver_800_change_percent": latest.silver_800_change_percent,
                
                # Ounce USD
                "ounce_usd_sell": latest.ounce_usd_sell,
                "ounce_usd_buy": latest.ounce_usd_buy,
                "ounce_usd_change": latest.ounce_usd_change,
                "ounce_usd_change_percent": latest.ounce_usd_change_percent,

                # Legacy
                "silver_999": latest.silver_999_price,
                "silver_925": latest.silver_925_price,
                "buy": latest.buy_price,
                "sell": latest.sell_price
            },
            "change": {
                "absolute": latest.daily_change,
                "percent": latest.daily_change_percent
            },
            "currency": latest.currency,
            "scraped_at": latest.scraped_at.isoformat() if latest.scraped_at else None,
            "source_update_time": latest.source_update_time,
            "created_at": latest.created_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest silver price: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
def get_silver_price_history(
    limit: int = Query(default=100, le=1000, description="Number of records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    db: Session = Depends(database.get_db)
):
    """
    Get historical silver price data
    Returns paginated list of price records
    """
    try:
        total = db.query(func.count(models.SilverPrice.id)).scalar()
        
        records = db.query(models.SilverPrice).order_by(
            desc(models.SilverPrice.created_at)
        ).limit(limit).offset(offset).all()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "id": record.id,
                    "source_used": record.source_used,
                    "source_status": record.source_status,
                    "prices": {
                        "gram": record.silver_gram_price,
                        "ounce": record.silver_ounce_price,
                        "silver_999": record.silver_999_price,
                        "silver_925": record.silver_925_price,
                        "buy": record.buy_price,
                        "sell": record.sell_price
                    },
                    "change": {
                        "absolute": record.daily_change,
                        "percent": record.daily_change_percent
                    },
                    "currency": record.currency,
                    "scraped_at": record.scraped_at.isoformat() if record.scraped_at else None,
                    "created_at": record.created_at.isoformat()
                }
                for record in records
            ]
        }
    
    except Exception as e:
        logger.error(f"Error fetching silver price history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/by-date")
def get_silver_prices_by_date(
    date_param: str = Query(..., description="Date in YYYY-MM-DD format", alias="date"),
    db: Session = Depends(database.get_db)
):
    """
    Get all silver price records for a specific date
    Returns all scraping records from that day
    """
    try:
        # Parse date
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Query records for that date
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        records = db.query(models.SilverPrice).filter(
            and_(
                models.SilverPrice.created_at >= start_datetime,
                models.SilverPrice.created_at <= end_datetime
            )
        ).order_by(desc(models.SilverPrice.created_at)).all()
        
        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"No silver price data found for date {date_param}"
            )
        
        return {
            "date": date_param,
            "count": len(records),
            "data": [
                {
                    "id": record.id,
                    "source_used": record.source_used,
                    "source_status": record.source_status,
                    "prices": {
                        "gram": record.silver_gram_price,
                        "ounce": record.silver_ounce_price,
                        "silver_999": record.silver_999_price,
                        "silver_925": record.silver_925_price,
                        "buy": record.buy_price,
                        "sell": record.sell_price
                    },
                    "change": {
                        "absolute": record.daily_change,
                        "percent": record.daily_change_percent
                    },
                    "currency": record.currency,
                    "scraped_at": record.scraped_at.isoformat() if record.scraped_at else None,
                    "created_at": record.created_at.isoformat()
                }
                for record in records
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching silver prices by date: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
def get_silver_price_stats(
    days: int = Query(default=7, le=365, description="Number of days to analyze"),
    db: Session = Depends(database.get_db)
):
    """
    Get statistical analysis of silver prices over time
    """
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Query records in range
        records = db.query(models.SilverPrice).filter(
            models.SilverPrice.created_at >= start_date
        ).order_by(models.SilverPrice.created_at).all()
        
        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for the last {days} days"
            )
        
        # Calculate statistics
        gram_prices = [r.silver_gram_price for r in records if r.silver_gram_price]
        ounce_prices = [r.silver_ounce_price for r in records if r.silver_ounce_price]
        
        stats = {
            "period": {
                "days": days,
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_records": len(records),
            "gram_price": {
                "current": gram_prices[-1] if gram_prices else None,
                "min": min(gram_prices) if gram_prices else None,
                "max": max(gram_prices) if gram_prices else None,
                "avg": sum(gram_prices) / len(gram_prices) if gram_prices else None
            },
            "ounce_price": {
                "current": ounce_prices[-1] if ounce_prices else None,
                "min": min(ounce_prices) if ounce_prices else None,
                "max": max(ounce_prices) if ounce_prices else None,
                "avg": sum(ounce_prices) / len(ounce_prices) if ounce_prices else None
            },
            "sources_used": {
                "primary": sum(1 for r in records if r.source_status == "Primary"),
                "fallback": sum(1 for r in records if r.source_status == "Fallback")
            }
        }
        
        return stats
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating silver price stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/source-status")
def get_source_status(db: Session = Depends(database.get_db)):
    """
    Get information about which source was used in recent scrapes
    """
    try:
        # Get last 20 records
        recent = db.query(models.SilverPrice).order_by(
            desc(models.SilverPrice.created_at)
        ).limit(20).all()
        
        if not recent:
            raise HTTPException(status_code=404, detail="No data available")
        
        return {
            "latest_source": recent[0].source_used if recent else None,
            "latest_status": recent[0].source_status if recent else None,
            "latest_scrape": recent[0].created_at.isoformat() if recent else None,
            "recent_scrapes": [
                {
                    "source": r.source_used,
                    "status": r.source_status,
                    "timestamp": r.created_at.isoformat()
                }
                for r in recent
            ],
            "source_reliability": {
                "primary_success_rate": f"{sum(1 for r in recent if r.source_status == 'Primary') / len(recent) * 100:.1f}%",
                "fallback_usage_rate": f"{sum(1 for r in recent if r.source_status == 'Fallback') / len(recent) * 100:.1f}%"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching source status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

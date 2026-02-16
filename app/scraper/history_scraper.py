import httpx
from bs4 import BeautifulSoup
import re
import json
import ast
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger(__name__)

class GoldHistoryScraper:
    BASE_URL = "https://gold-price-live.com/"
    
    def __init__(self, db: Session):
        self.db = db

    async def scrape_history(self, days: int) -> int:
        """Scrape historical data for a specific number of days"""
        url = f"{self.BASE_URL}?days={days}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                scripts = soup.find_all('script')
                
                chart_script = None
                for script in scripts:
                    if script.string and 'goldchart-id' in script.string:
                        chart_script = script.string
                        break
                
                if not chart_script:
                    logger.error(f"Chart script not found for {days} days")
                    return 0

                # Extract labels (dates) and data (prices) using regex
                labels_match = re.search(r'labels:\s*(\[.*?\])', chart_script, re.DOTALL)
                data_match = re.search(r'data:\s*(\[.*?\])', chart_script, re.DOTALL)
                
                if not labels_match or not data_match:
                    logger.error(f"Could not parse labels/data for {days} days")
                    return 0
                
                try:
                    # Use ast.literal_eval to handle trailing commas and non-strict JSON
                    labels = ast.literal_eval(labels_match.group(1).strip())
                    prices = ast.literal_eval(data_match.group(1).strip())
                except Exception as e:
                    logger.error(f"Literal eval failed for {days} days: {e}")
                    # Fallback to cleaning and json.loads
                    labels_str = re.sub(r',\s*\]', ']', labels_match.group(1).strip())
                    prices_str = re.sub(r',\s*\]', ']', data_match.group(1).strip())
                    labels = json.loads(labels_str)
                    prices = json.loads(prices_str)
                
                if len(labels) != len(prices):
                    logger.warning(f"Mismatch between labels and prices length for {days} days")
                
                return self._process_and_save(labels, prices)
                
            except Exception as e:
                logger.error(f"Error scraping gold history ({days} days): {e}")
                return 0

    def _process_and_save(self, labels: List[str], prices: List[Any]) -> int:
        """Convert labels/prices to DB records and save if not exists"""
        records_saved = 0
        current_year = datetime.now().year
        today = datetime.now()
        
        for label, price_val in zip(labels, prices):
            try:
                # price_val might be float or string
                if isinstance(price_val, str):
                    price = float(price_val.replace(',', ''))
                else:
                    price = float(price_val)
                    
                if price <= 0: continue
                
                # Parse date MM-DD from label (e.g. "السبت 02-07")
                match = re.search(r'(\d{1,2}-\d{1,2})', label)
                if not match:
                    logger.warning(f"Could not find date pattern in label: {label}")
                    continue
                
                month_day_str = match.group(1)
                month, day = map(int, month_day_str.split('-'))
                
                # Guess year
                year = current_year
                if month > today.month or (month == today.month and day > today.day):
                    year = current_year - 1
                
                dt = datetime(year, month, day)
                target_dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
                
                exists = self.db.query(models.PriceHistory).filter(
                    models.PriceHistory.type == "gold",
                    models.PriceHistory.country == "egypt",
                    models.PriceHistory.key == "21",
                    models.PriceHistory.timestamp == target_dt
                ).first()
                
                if not exists:
                    # Karat 21
                    self.db.add(models.PriceHistory(
                        type="gold", country="egypt", key="21",
                        sell_price=price, buy_price=price,
                        source_name="GoldPriceLive", timestamp=target_dt
                    ))
                    # Karat 24
                    self.db.add(models.PriceHistory(
                        type="gold", country="egypt", key="24",
                        sell_price=round(price * (24/21), 2),
                        buy_price=round(price * (24/21), 2),
                        source_name="GoldPriceLiveDerived", timestamp=target_dt
                    ))
                    # Karat 18
                    self.db.add(models.PriceHistory(
                        type="gold", country="egypt", key="18",
                        sell_price=round(price * (18/21), 2),
                        buy_price=round(price * (18/21), 2),
                        source_name="GoldPriceLiveDerived", timestamp=target_dt
                    ))
                    records_saved += 3
            except Exception as e:
                logger.warning(f"Skipping record {label}/{price_val}: {e}")
                
        self.db.commit()
        return records_saved

async def scrape_all_historical_periods(db: Session):
    scraper = GoldHistoryScraper(db)
    periods = [7, 30, 90, 180, 365]
    total = 0
    for p in periods:
        logger.info(f"Scraping {p} days of history...")
        count = await scraper.scrape_history(p)
        total += count
    return total

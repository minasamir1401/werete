
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import logging
import re
from app.core.database import SessionLocal
from app.models import Setting

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScraperSource(ABC):
    def __init__(self):
        self.last_error = None

    @abstractmethod
    async def fetch_prices(self) -> List[Dict]:
        self.last_error = None
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    def _clean_price(self, text: str) -> float:
        text = text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
        # Remove any non-numeric/dot characters (except maybe minus)
        text = re.sub(r'[^\d.]', '', text)
        if not text:
            return 0.0
        return float(text)

    def _clean_karat(self, text: str) -> str:
        # Normalize Arabic numerals to Western
        arabic_to_western = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
        }
        for a, w in arabic_to_western.items():
            text = text.replace(a, w)
            
        # Prioritize finding standard karats first
        standard_karats = ["24", "22", "21", "18", "14", "12"]
        for sk in standard_karats:
            if re.search(r'\b' + sk + r'\b', text) or (f"عيار {sk}" in text) or (f" {sk} " in text) or (text.strip() == sk):
                 return sk

        # Fallback to the first sequence of digits if it's reasonable
        match = re.search(r'\d+', text)
        if match:
            val = match.group()
            # If it's a huge number, it's likely not a karat
            if len(val) > 2 and not (len(val) == 3 and val.endswith('0')):
                return ""
            # Common case: if it got 240 from 24.0, or 210 from 21.0
            if len(val) == 3 and val.endswith('0') and val[:2] in standard_karats:
                return val[:2]
            return val
        return ""

class GoldEraSource(ScraperSource):
    URL = "https://egypt.gold-era.com/ar/سعر-الذهب/"
    NAME = "GoldEra"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_prices(self) -> List[Dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'lxml')
                
                prices = []
                # Use a more specific selector if possible
                tables = soup.find_all('table')
                for table in tables:
                     rows = table.find_all('tr')
                     for row in rows:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 3:
                            karat_text = cols[0].get_text(strip=True)
                            if any(k in karat_text for k in ["24", "22", "21", "18", "14"]):
                                karat = self._clean_karat(karat_text)
                                # Gold Era headers: Karat | Sell | Buy
                                sell = self._clean_price(cols[1].get_text(strip=True))
                                buy = self._clean_price(cols[2].get_text(strip=True))
                                
                                if sell > 0:
                                    prices.append({
                                        "karat": karat,
                                        "sell_price": sell,
                                        "buy_price": buy,
                                        "currency": "EGP",
                                        "source": self.NAME,
                                        "type": "Local",
                                        "timestamp": datetime.utcnow()
                                    })
                return prices
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error scraping {self.NAME}: {e}")
                return [] # Return empty instead of raising to allow fallbacks

class IsaghaSource(ScraperSource):
    URL = "https://market.isagha.com/prices"
    NAME = "Isagha"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_prices(self) -> List[Dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'lxml')
                prices = []
                # Isagha: The main prices are in a desktop-table visible div
                rows = soup.select(".desktop-table table tbody tr")
                # If desktop-table yields nothing, try generic
                if not rows:
                    rows = soup.select("table tbody tr")
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        karat_text = cols[0].get_text(strip=True)
                        if "عيار" in karat_text or any(k in karat_text for k in ["24", "21", "18"]):
                            karat = self._clean_karat(karat_text)
                            sell = self._clean_price(cols[1].get_text(strip=True)) # Sell
                            buy = self._clean_price(cols[3].get_text(strip=True)) # Buy (index 3)
                            
                            if sell > 0:
                                prices.append({
                                    "karat": karat,
                                    "sell_price": sell,
                                    "buy_price": buy,
                                    "currency": "EGP", 
                                    "source": self.NAME,
                                    "type": "Local",
                                    "timestamp": datetime.utcnow()
                                })
                return prices
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error scraping {self.NAME}: {e}")
                return []

class GoldBullionSource(ScraperSource):
    URL = "https://goldbullioneg.com/أسعار-الذهب/"
    NAME = "GoldBullion"

    @property
    def name(self) -> str:
        return self.NAME
    
    async def fetch_prices(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                soup = BeautifulSoup(r.text, 'lxml')
                prices = []
                
                rows = soup.select("table tr")
                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 3:
                        karat_text = cols[0].get_text(strip=True)
                        if "عيار" in karat_text:
                            karat = self._clean_karat(karat_text)
                            val1 = self._clean_price(cols[1].get_text(strip=True))
                            val2 = self._clean_price(cols[2].get_text(strip=True))
                            
                            # Usually shops Sell at higher price than they Buy.
                            sell = max(val1, val2)
                            buy = min(val1, val2)

                            prices.append({
                                "karat": karat,
                                "sell_price": sell,
                                "buy_price": buy,
                                "currency": "EGP",
                                "source": self.NAME,
                                "type": "Local",
                                "timestamp": datetime.utcnow()
                            })
                return prices
            except Exception as e:
                 self.last_error = str(e)
                 logger.error(f"Error scraping {self.NAME}: {e}")
                 # raise # Don't raise, return empty to be consistent
                 return []

class EgyptGoldPriceTodaySource(ScraperSource):
    URL = "https://egypt.gold-price-today.com/"
    NAME = "EgyptGoldPriceToday"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_prices(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                soup = BeautifulSoup(r.text, 'lxml')
                prices = []
                
                # Use the first table found (usually the main one)
                table = soup.find('table')
                if not table:
                     header = soup.find(string=re.compile("أسعار الذهب"))
                     if header:
                         table = header.find_next('table')

                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 3:
                            karat_text = cols[0].get_text(strip=True)
                            karat = self._clean_karat(karat_text)
                            if karat:
                                val1 = self._clean_price(cols[1].get_text(strip=True))
                                val2 = self._clean_price(cols[2].get_text(strip=True))
                                
                                if val1 > 500: # Threshold to avoid random numbers
                                    prices.append({
                                        "karat": karat,
                                        "sell_price": max(val1, val2),
                                        "buy_price": min(val1, val2),
                                        "currency": "EGP",
                                        "source": self.NAME,
                                        "type": "Local",
                                        "timestamp": datetime.utcnow()
                                    })
                return prices
            except Exception as e:
                logger.error(f"Error scraping {self.NAME}: {e}")
                return []

class GoldPriceLiveSource(ScraperSource):
    URL = "https://gold-price-live.com/"
    NAME = "GoldPriceLive"

    @property
    def name(self) -> str:
        return self.NAME
    
    async def fetch_prices(self) -> List[Dict]:
       headers = {"User-Agent": "Mozilla/5.0"}
       async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                soup = BeautifulSoup(r.text, 'lxml')
                prices = []
                
                # Better selector for cards to avoid parent text with weights
                cards = soup.select("a[href*='kerat-']")
                for card in cards:
                    full_text = card.get_text(strip=True)
                    karat = self._clean_karat(full_text)
                    if not karat: continue
                    
                    # Target the specific price div if it exists
                    price_div = card.select_one("div.col-12.text-center")
                    source_text = price_div.get_text(strip=True) if price_div else full_text
                    
                    # Find numbers, but ignore small ones like weight (8)
                    # AND ignore huge ones (like Ounce price) to avoid mistaking it for gram
                    numbers = re.findall(r'\d+(?:\.\d+)?', source_text)
                    potential_prices = [float(n) for n in numbers if 500 < float(n) < 15000]
                    
                    if len(potential_prices) >= 2:
                        sell = max(potential_prices)
                        buy = min(potential_prices)
                        if karat and sell < 20000: # Filter out ounce/pound items
                            prices.append({
                                "karat": karat,
                                "sell_price": sell,
                                "buy_price": buy,
                                "currency": "EGP",
                                "source": self.NAME,
                                "type": "Local",
                                "timestamp": datetime.utcnow()
                            })
                
                # Check for table as fallback
                if not prices:
                    rows = soup.select("table tr")
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            karat = self._clean_karat(cols[0].get_text())
                            if karat:
                                p1 = self._clean_price(cols[1].get_text())
                                p2 = self._clean_price(cols[2].get_text())
                                
                                # Apply thresholds in fallback too
                                if 500 < p1 < 15000 and 500 < p2 < 15000:
                                    prices.append({
                                        "karat": karat,
                                        "sell_price": max(p1, p2),
                                        "buy_price": min(p1, p2),
                                        "currency": "EGP",
                                        "source": self.NAME,
                                        "type": "Local",
                                        "timestamp": datetime.utcnow()
                                    })

                unique_prices = {p['karat']: p for p in prices}.values()
                return list(unique_prices)
            except Exception as e:
                logger.error(f"Error scraping {self.NAME}: {e}")
                return []

class SouqPriceTodaySource(ScraperSource):
    URL = "https://souq-price-today.com/"
    NAME = "SouqPriceToday"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_prices(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                soup = BeautifulSoup(r.text, 'lxml')
                prices = []
                
                # Second table is the one with Karats
                tables = soup.find_all('table')
                if len(tables) >= 2:
                    rows = tables[1].find_all('tr')[1:] # Skip header
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            karat_text = cols[0].get_text(strip=True)
                            if "عيار" in karat_text or "ذهب" in karat_text:
                                karat = self._clean_karat(karat_text)
                                val1 = self._clean_price(cols[1].get_text(strip=True))
                                val2 = self._clean_price(cols[2].get_text(strip=True))
                                
                                sell = max(val1, val2)
                                buy = min(val1, val2)
                                if karat and sell < 15000: # Filter out ounce/pound items (gram price < 15k)
                                    prices.append({
                                        "karat": karat,
                                        "sell_price": sell,
                                        "buy_price": buy,
                                        "currency": "EGP",
                                        "source": self.NAME,
                                        "type": "Local",
                                        "timestamp": datetime.utcnow()
                                    })
                return prices
            except Exception as e:
                logger.error(f"Error scraping {self.NAME}: {e}")
                return []


class ScraperManager:
    def __init__(self):
        self.all_sources = {
            "GoldEra": GoldEraSource(), 
            "GoldBullion": GoldBullionSource(),
            "EgyptGoldPriceToday": EgyptGoldPriceTodaySource(),
            "GoldPriceLive": GoldPriceLiveSource(),
            "SouqPriceToday": SouqPriceTodaySource()
        }
        self.default_order = ["GoldEra", "GoldBullion", "EgyptGoldPriceToday", "GoldPriceLive", "SouqPriceToday"]
    
    def _get_ordered_sources(self):
        try:
            db = SessionLocal()
            try:
                setting = db.query(Setting).filter(Setting.key == "gold_source_order").first()
                if setting and setting.value:
                    order = [s.strip() for s in setting.value.split(",") if s.strip()]
                    # Filter out invalid source names and map to objects
                    ordered = []
                    for s in order:
                        if s in self.all_sources:
                            ordered.append(self.all_sources[s])
                    
                    # Add any missing sources from default_order
                    existing_names = [s.name for s in ordered]
                    for s_name in self.default_order:
                        if s_name not in existing_names:
                            ordered.append(self.all_sources[s_name])
                    return ordered
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error reading source order: {e}")
            
        return [self.all_sources[s] for s in self.default_order]

    async def get_latest_prices(self) -> List[Dict]:
        sources = self._get_ordered_sources()
        for index, source in enumerate(sources):
            try:
                logger.info(f"Attempting source {index+1}/{len(sources)}: {source.name}")
                prices = await source.fetch_prices()
                
                # Validation: If we got prices, use them and STOP.
                # Single Source Principle.
                valid_prices = [p for p in prices if p['sell_price'] > 0]
                
                if valid_prices:
                    # Enforce standardization & Metadata
                    status = "Primary" if index == 0 else "Fallback"
                    current_time = datetime.utcnow()
                    
                    normalized_prices = []
                    for p in valid_prices:
                        p['source_status'] = status
                        p['timestamp'] = current_time
                        p['date'] = current_time.date()
                        p['time'] = current_time.time()
                        normalized_prices.append(p)
                        
                    logger.info(f"Success with {source.name} ({status}). Fetched {len(normalized_prices)} prices.")
                    return normalized_prices
                    
            except Exception as e:
                logger.warning(f"Source {source.name} failed: {e}")
                continue
        
        logger.error("All sources failed.")
        return []

class GoldPriceTodayCountrySource:
    BASE_URL = "https://{}.gold-price-today.com/"
    NAME = "GoldPriceToday"
    
    CURRENCY_MAP = {
        "saudi-arabia": "SAR",
        "kuwait": "KWD",
        "united-arab-emirates": "AED",
        "qatar": "QAR",
        "yemen": "YER",
        "jordan": "JOD",
        "iraq": "IQD",
        "lebanon": "LBP",
        "oman": "OMR",
        "bahrain": "BHD",
        "algeria": "DZD",
        "morocco": "MAD",
        "palestine": "ILS",
        "egypt": "EGP"
    }

    def _clean_price(self, text: str) -> float:
        text = text.replace(",", "").strip()
        # Find numeric part
        match = re.search(r'\d+(?:\.\d+)?', text)
        return float(match.group()) if match else 0.0

    def _clean_karat(self, text: str) -> str:
        # Normalize Arabic numerals to Western
        arabic_to_western = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
        }
        for a, w in arabic_to_western.items():
            text = text.replace(a, w)
        match = re.search(r'\d+', text)
        return match.group() if match else ""

    async def fetch_prices(self, subdomain: str) -> List[Dict]:
        url = self.BASE_URL.format(subdomain)
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'lxml')
                prices = []
                
                currency = self.CURRENCY_MAP.get(subdomain, "Local")
                fetch_time = datetime.utcnow()
                
                # Table based scraping for gold-price-today
                table = soup.find('table')
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all(['td', 'th'])
                        if len(cols) >= 2:
                            karat_text = cols[0].get_text(strip=True)
                            karat = self._clean_karat(karat_text)
                            if karat:
                                p_val = self._clean_price(cols[1].get_text(strip=True))
                                if p_val > 0:
                                    prices.append({
                                        "karat": karat,
                                        "sell_price": p_val,
                                        "buy_price": p_val,
                                        "currency": currency,
                                        "source": self.NAME,
                                        "type": "International",
                                        "country": subdomain.lower(),
                                        "timestamp": fetch_time
                                    })
                return prices
            except Exception as e:
                logger.error(f"Error scraping country {subdomain}: {e}")
                return []

class CountryScraperManager:
    def __init__(self):
        self.source = GoldPriceTodayCountrySource()
        self.target_countries = [
            "egypt", "saudi-arabia", "kuwait", "united-arab-emirates", "qatar", 
            "yemen", "jordan", "iraq", "lebanon", "oman", "bahrain", 
            "algeria", "morocco", "palestine"
        ]

    async def get_all_country_prices(self) -> List[Dict]:
        import asyncio
        all_prices = []
        # To avoid being blocked, we could run them in sequence or small batches
        for country in self.target_countries:
            try:
                logger.info(f"Scraping country: {country}")
                prices = await self.source.fetch_prices(country)
                if prices:
                    current_time = datetime.utcnow()
                    for p in prices:
                        p['source_status'] = "International"
                        p['date'] = current_time.date()
                        p['time'] = current_time.time()
                        all_prices.append(p)
                # Small delay to be polite
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed country {country}: {e}")
                continue
        return all_prices

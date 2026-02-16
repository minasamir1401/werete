"""
Comprehensive Bank Currency Scraper
Scrapes ALL banks from aggregate currency pages across multiple sources
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import logging
import re
from typing import List, Dict, Optional
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class AllBanksSource(ABC):
    """Base class for scraping all banks for a specific currency"""
    
    @abstractmethod
    async def fetch_all_banks(self, currency_code: str) -> List[Dict]:
        """Fetch rates from all banks for a specific currency"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    def _clean_price(self, text: str) -> float:
        try:
            cleaned = re.sub(r'[^\d.]', '', text)
            if cleaned:
                return float(cleaned)
        except:
            pass
        return 0.0

    def _get_flag_fallback(self, currency_code: str) -> str:
        """Fallback to FlagCDN if scraper fails to find a flag"""
        mapping = {
            "USD": "us", "EUR": "eu", "SAR": "sa", "GBP": "gb",
            "KWD": "kw", "AED": "ae", "QAR": "qa", "JOD": "jo",
            "BHD": "bh", "OMR": "om", "CAD": "ca", "AUD": "au",
            "CHF": "ch", "JPY": "jp", "TRY": "tr", "CNY": "cn"
        }
        cc = mapping.get(currency_code.upper(), "us")
        return f"https://flagcdn.com/w80/{cc}.png"


class Ta3weemAllBanksSource(AllBanksSource):
    """Scrape all banks from Ta3weem aggregate currency pages"""
    BASE_URL = "https://ta3weem.com/ar/currency-exchange-rates/{currency}-EGP"
    NAME = "Ta3weem_AllBanks"
    
    @property
    def name(self) -> str:
        return self.NAME
    
    async def fetch_all_banks(self, currency_code: str) -> List[Dict]:
        url = self.BASE_URL.format(currency=currency_code)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, 'lxml')
                
                # Find any table with tbody
                tbody = soup.find('tbody')
                if not tbody:
                    logger.warning(f"Ta3weem: No tbody found for {currency_code}")
                    return []
                
                rows = tbody.find_all('tr')
                fetch_time = datetime.now(timezone.utc)
                all_rates = []
                
                # Extract currency flag
                currency_flag = ""
                target_code = currency_code.lower()
                
                # Broad search in all elements for flag patterns
                # Ta3weem flags are often in spans or divs as background images
                flag_patterns = [f"/{target_code}.", f"/{target_code}-", f"flag-{target_code}"]
                
                # Check for spans/divs with background-image
                styled_elements = soup.find_all(True, style=True)
                for el in styled_elements:
                    style = el.get('style', '')
                    if 'background-image' in style:
                        # Find URL in style
                        match = re.search(r'url\((["\']?)(.*?)\1\)', style)
                        if match:
                            img_url = match.group(2)
                            if any(p in img_url.lower() for p in flag_patterns):
                                currency_flag = img_url
                                break
                
                if not currency_flag:
                    # Check all img tags
                    all_imgs = soup.find_all('img')
                    for img in all_imgs:
                        src = img.get('data-src') or img.get('src', '')
                        if any(p in src.lower() for p in flag_patterns) and "logo" not in src.lower():
                            currency_flag = src
                            break
                            
                # Reliable fallback for Ta3weem flags
                if not currency_flag:
                    currency_flag = self._get_flag_fallback(currency_code)
                    
                # Fix relative URL for flag
                if currency_flag and not currency_flag.startswith('http'):
                    currency_flag = "https://ta3weem.com" + (currency_flag if currency_flag.startswith('/') else '/' + currency_flag)
                elif not currency_flag:
                    currency_flag = self._get_flag_fallback(currency_code)

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 3:
                        continue
                        
                    # Bank name is in first column (inside a tag and span)
                    bank_el = cols[0].find('a')
                    if not bank_el:
                        continue
                        
                    bank_name_span = bank_el.find('span')
                    bank_name = bank_name_span.get_text(strip=True) if bank_name_span else bank_el.get_text(strip=True)
                    bank_url = bank_el.get('href', '')
                    
                    # Extract bank ID
                    bank_id_match = re.search(r'/banks/([^/]+)', bank_url)
                    bank_id = bank_id_match.group(1) if bank_id_match else bank_name
                    
                    # Bank logo
                    bank_img = cols[0].find('img')
                    bank_logo = ""
                    if bank_img:
                        bank_logo = bank_img.get('data-src') or bank_img.get('src', '')
                        if bank_logo and not bank_logo.startswith('http'):
                            bank_logo = "https://ta3weem.com" + bank_logo

                    # Buy Price is in second column
                    buy_text = cols[1].get_text(strip=True)
                    # Sell Price is in third column
                    sell_text = cols[2].get_text(strip=True)
                    
                    # Clean prices
                    buy_val = self._extract_first_number(buy_text)
                    sell_val = self._extract_first_number(sell_text)
                    
                    if sell_val > 0:
                        all_rates.append({
                            "bank_id": bank_id,
                            "bank_name": bank_name,
                            "bank_logo": bank_logo,
                            "bank_url": "https://ta3weem.com" + bank_url if bank_url.startswith('/') else bank_url,
                            "currency": currency_code,
                            "currency_flag": currency_flag,
                            "buy_price": buy_val,
                            "sell_price": sell_val,
                            "source": self.NAME,
                            "timestamp": fetch_time
                        })
                
                return all_rates
            except Exception as e:
                logger.error(f"Ta3weem AllBanks failed for {currency_code}: {e}")
                return []

    def _extract_first_number(self, text: str) -> float:
        """Extract only the first valid float number from text"""
        try:
            # Match number at start of string or standalone
            match = re.search(r'^\s*(\d+\.?\d*)', text)
            if match:
                return float(match.group(1))
            # Fallback: scan for any float
            match = re.search(r'(\d+\.?\d*)', text)
            if match:
                return float(match.group(1))
        except:
            pass
        return 0.0


class EgratesAllBanksSource(AllBanksSource):
    """Scrape all banks from Egrates aggregate currency pages"""
    BASE_URL = "https://egrates.com/currency/{currency}"
    NAME = "Egrates_AllBanks"
    
    @property
    def name(self) -> str:
        return self.NAME
    
    async def fetch_all_banks(self, currency_code: str) -> List[Dict]:
        url = self.BASE_URL.format(currency=currency_code)
        headers = {"User-Agent": "Mozilla/5.0"}
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, 'lxml')
                rows = soup.select('table tbody tr')
                fetch_time = datetime.now(timezone.utc)
                all_rates = []
                
                # Extract currency flag
                currency_flag = ""
                flag_img = soup.find('img', alt=re.compile(currency_code, re.I))
                if flag_img:
                    currency_flag = flag_img.get('src', '')
                    if currency_flag and not currency_flag.startswith('http'):
                        currency_flag = "https://egrates.com" + (currency_flag if currency_flag.startswith('/') else '/' + currency_flag)

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        # Bank name is in first column
                        bank_el = cols[0].find('a')
                        if not bank_el:
                            continue
                        
                        bank_name = bank_el.get_text(strip=True)
                        bank_url = bank_el.get('href', '')
                        
                        # Extract bank ID from URL (e.g., banks/4)
                        bank_id_match = re.search(r'banks/(\d+)', bank_url)
                        bank_id = f"egrates_{bank_id_match.group(1)}" if bank_id_match else bank_name
                        
                        # Bank logo
                        bank_img = cols[0].find('img')
                        bank_logo = ""
                        if bank_img:
                            bank_logo = bank_img.get('src', '')
                            if bank_logo and not bank_logo.startswith('http'):
                                # Ensure slash between domain and path
                                path = bank_logo if bank_logo.startswith('/') else '/' + bank_logo
                                bank_logo = "https://egrates.com" + path

                        buy_val = self._clean_price(cols[1].get_text(strip=True))
                        sell_val = self._clean_price(cols[2].get_text(strip=True))
                        
                        if sell_val > 0:
                            all_rates.append({
                                "bank_id": bank_id,
                                "bank_name": bank_name,
                                "bank_logo": bank_logo,
                                "bank_url": "https://egrates.com/" + bank_url.lstrip('/'),
                                "currency": currency_code,
                                "currency_flag": currency_flag or self._get_flag_fallback(currency_code),
                                "buy_price": buy_val,
                                "sell_price": sell_val,
                                "source": self.NAME,
                                "timestamp": fetch_time
                            })
                
                return all_rates
            except Exception as e:
                logger.error(f"Egrates AllBanks failed for {currency_code}: {e}")
                return []


class BankLiveAllBanksSource(AllBanksSource):
    """Scrape all banks from BankLive aggregate currency pages"""
    BASE_URL = "https://banklive.net/ar/exchange-rate-{currency}-to-EGP-today"
    NAME = "BankLive_AllBanks"
    
    @property
    def name(self) -> str:
        return self.NAME
    
    async def fetch_all_banks(self, currency_code: str) -> List[Dict]:
        url = self.BASE_URL.format(currency=currency_code)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, 'lxml')
                
                # Target the specific table class, handle potential typo 'banklive-tablse'
                table = soup.find('table', class_=re.compile(r'banklive-tabl?s?e'))
                if not table:
                    # Fallback to generic table
                    table = soup.find('table')
                
                if not table:
                    return []
                
                rows = table.find_all('tr')
                fetch_time = datetime.now(timezone.utc)
                all_rates = []
                
                # Extract currency flag
                currency_flag = ""
                # BankLive usually has flag in breadcrumbs
                breadcrumb = soup.select_one('.breadcrumb')
                if breadcrumb:
                    flag_img = breadcrumb.find('img')
                    if flag_img:
                        currency_flag = flag_img.get('src', '')
                        if currency_flag and not currency_flag.startswith('http'):
                            currency_flag = "https://banklive.net" + (currency_flag if currency_flag.startswith('/') else '/' + currency_flag)

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 3:
                        continue
                        
                    # Bank name is in first column, specifically in .bankName span
                    bank_col = cols[0]
                    bank_name_el = bank_col.select_one('.bankName')
                    
                    if bank_name_el:
                        bank_name = bank_name_el.get_text(strip=True)
                    else:
                        # Fallback if no .bankName class
                        bank_name = bank_col.get_text(strip=True)
                        # Remove "منذ ..." if present at start (heuristic)
                        if "منذ" in bank_name:
                            # Try to split by newline or just take the end
                            parts = bank_name.split('\n')
                            bank_name = parts[-1].strip() if parts else bank_name

                    bank_link = bank_col.find('a')
                    bank_url = bank_link.get('href', '') if bank_link else ''
                    
                    # Extract bank ID from URL
                    bank_id_match = re.search(r'/currency-exchange-rates-in-([^/]+)', bank_url)
                    bank_id = f"banklive_{bank_id_match.group(1)}" if bank_id_match else bank_name
                    
                    # Prices are in .bankRate
                    buy_el = cols[1].select_one('.bankRate')
                    sell_el = cols[2].select_one('.bankRate')
                    
                    buy_text = buy_el.get_text(strip=True) if buy_el else cols[1].get_text(strip=True)
                    sell_text = sell_el.get_text(strip=True) if sell_el else cols[2].get_text(strip=True)
                    
                    # Extract bank logo
                    bank_img = bank_col.find('img')
                    bank_logo = ""
                    if bank_img:
                        bank_logo = bank_img.get('data-src') or bank_img.get('src', '')
                        if bank_logo and not bank_logo.startswith('http'):
                            bank_logo = "https://banklive.net" + bank_logo

                    buy_val = self._clean_price(buy_text)
                    sell_val = self._clean_price(sell_text)
                    
                    if sell_val > 0:
                        all_rates.append({
                        "bank_id": bank_id,
                        "bank_name": bank_name,
                        "bank_logo": bank_logo,
                        "bank_url": bank_url if bank_url.startswith('http') else ("https://banklive.net" + (bank_url if bank_url.startswith('/') else '/' + bank_url)),
                        "currency": currency_code,
                        "currency_flag": currency_flag or self._get_flag_fallback(currency_code),
                        "buy_price": buy_val,
                        "sell_price": sell_val,
                        "source": self.NAME,
                        "timestamp": fetch_time
                    })
                
                return all_rates
            except Exception as e:
                logger.error(f"BankLive AllBanks failed for {currency_code}: {e}")
                return []


class AllBanksScraperManager:
    """Manages scraping all banks from multiple sources with fallback"""
    
    def __init__(self, db_session=None):
        self.sources = {
            "ta3weem": Ta3weemAllBanksSource(),
            "egrates": EgratesAllBanksSource(),
            "banklive": BankLiveAllBanksSource()
        }
        self.default_currencies = ["USD", "EUR", "SAR", "GBP", "KWD", "AED"]
        self.db_session = db_session
    
    def _get_enabled_sources_in_order(self) -> List[str]:
        """Get enabled sources from database settings, ordered by priority"""
        if not self.db_session:
            # Fallback to default order if no DB session
            return ["ta3weem", "egrates", "banklive"]
        
        try:
            from app.models import CurrencySourceSettings
            settings = self.db_session.query(CurrencySourceSettings).filter(
                CurrencySourceSettings.is_enabled == True
            ).order_by(CurrencySourceSettings.priority).all()
            
            if settings:
                return [s.source_name for s in settings]
            else:
                # No settings found, return default
                return ["ta3weem", "egrates", "banklive"]
        except Exception as e:
            logger.warning(f"Failed to load source settings: {e}")
            return ["ta3weem", "egrates", "banklive"]
    
    async def fetch_all_banks_for_currency(self, currency_code: str) -> List[Dict]:
        """
        Fetch all banks for a specific currency using FALLBACK strategy.
        Tries sources in priority order and stops at the first successful one.
        """
        # Get enabled sources in priority order
        enabled_sources = self._get_enabled_sources_in_order()
        
        for source_id in enabled_sources:
            if source_id not in self.sources:
                continue
                
            source = self.sources[source_id]
            try:
                logger.info(f"Trying {source.name} for {currency_code} (priority {enabled_sources.index(source_id) + 1})")
                banks = await source.fetch_all_banks(currency_code)
                
                if banks and len(banks) > 0:
                    logger.info(f"SUCCESS: {source.name} returned {len(banks)} banks for {currency_code}")
                    logger.info(f"Skipping remaining sources (fallback strategy)")
                    return banks  # Return immediately on first success
                else:
                    logger.warning(f"{source.name} returned 0 banks for {currency_code}, trying next source...")
                    
            except Exception as e:
                logger.warning(f"{source.name} failed for {currency_code}: {e}, trying next source...")
                continue
        
        # If all sources failed
        logger.error(f"All sources failed for {currency_code}")
        return []
    
    async def fetch_all_banks_all_currencies(self, currencies: List[str] = None) -> List[Dict]:
        """Fetch all banks for all specified currencies"""
        currencies = currencies or self.default_currencies
        all_results = []
        
        for currency in currencies:
            banks = await self.fetch_all_banks_for_currency(currency)
            all_results.extend(banks)
        
        return all_results


async def test():
    print("Testing All Banks Scraper...")
    manager = AllBanksScraperManager()
    
    # Test USD only
    usd_banks = await manager.fetch_all_banks_for_currency("USD")
    print(f"\nTotal unique banks found for USD: {len(usd_banks)}")
    
    # Show first 5
    for bank in usd_banks[:5]:
        print(f"  {bank['bank_name']}: {bank['buy_price']} / {bank['sell_price']} ({bank['source']})")


if __name__ == "__main__":
    asyncio.run(test())

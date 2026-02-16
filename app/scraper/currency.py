import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import logging
import re
from typing import List, Dict, Optional
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class CurrencySource(ABC):
    @abstractmethod
    async def fetch_rates(self) -> List[Dict]:
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

class Ta3weemBankSource(CurrencySource):
    """Generic source for specific bank pages on Ta3weem"""
    def __init__(self, bank_id: str, bank_name: str, url: str):
        self.bank_id = bank_id
        self.bank_name = bank_name
        self.url = url

    @property
    def name(self) -> str:
        return f"Ta3weem_{self.bank_id}"

    async def fetch_rates(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                r = await client.get(self.url, headers=headers)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, 'lxml')
                rows = soup.select('table tbody tr')
                fetch_time = datetime.now(timezone.utc)
                all_rates = []

                for row in rows:
                    name_el = row.select_one('td:nth-child(1) a span') or row.select_one('td:nth-child(1)')
                    buy_el = row.select_one('td:nth-child(2) span') or row.select_one('td:nth-child(2)')
                    sell_el = row.select_one('td:nth-child(3) span') or row.select_one('td:nth-child(3)')
                    
                    if name_el and buy_el and sell_el:
                        name_text = name_el.get_text(strip=True)
                        code_match = re.search(r'\((.*?)\)', name_text)
                        code = code_match.group(1) if code_match else name_text
                        
                        buy_val = self._clean_price(buy_el.get_text(strip=True))
                        sell_val = self._clean_price(sell_el.get_text(strip=True))
                        
                        if sell_val > 0:
                            all_rates.append({
                                "currency": code,
                                "currency_name": name_text.split('(')[0].strip(),
                                "buy_price": buy_val,
                                "sell_price": sell_val,
                                "source": self.name,
                                "timestamp": fetch_time
                            })
                return all_rates
            except Exception as e:
                logger.error(f"Ta3weem failed for {self.bank_id}: {e}")
                return []

class EgratesBankSource(CurrencySource):
    def __init__(self, bank_id: str, bank_name: str, url: str):
        self.bank_id = bank_id
        self.bank_name = bank_name
        self.url = url

    @property
    def name(self) -> str:
        return f"Egrates_{self.bank_id}"

    async def fetch_rates(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                r = await client.get(self.url, headers=headers)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, 'lxml')
                rows = soup.select('table tbody tr')
                fetch_time = datetime.now(timezone.utc)
                all_rates = []

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        img = cols[1].find('img')
                        alt_text = img.get('alt', '') if img else ""
                        code = ""
                        curr_name = ""
                        if "/" in alt_text:
                            curr_name, code = alt_text.split('/', 1)
                        else:
                            link = cols[2].find('a') or cols[3].find('a')
                            if link:
                                href = link.get('href', '')
                                code_match = re.search(r'/([A-Z]{3})$', href)
                                code = code_match.group(1) if code_match else ""
                        
                        if not code: continue
                        buy_val = self._clean_price(cols[2].get_text(strip=True))
                        sell_val = self._clean_price(cols[3].get_text(strip=True))
                        
                        if sell_val > 0:
                            all_rates.append({
                                "currency": code.strip(),
                                "currency_name": curr_name.strip() or code.strip(),
                                "buy_price": buy_val,
                                "sell_price": sell_val,
                                "source": self.name,
                                "timestamp": fetch_time
                            })
                return all_rates
            except Exception as e:
                logger.error(f"Egrates failed for {self.bank_id}: {e}")
                return []

class BankLiveBankSource(CurrencySource):
    def __init__(self, bank_id: str, bank_name: str, url: str):
        self.bank_id = bank_id
        self.bank_name = bank_name
        self.url = url

    @property
    def name(self) -> str:
        return f"BankLive_{self.bank_id}"

    async def fetch_rates(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                r = await client.get(self.url, headers=headers)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, 'lxml')
                # Target the specific table class, handle potential typo 'banklive-tablse'
                table = soup.find('table', class_=re.compile(r'banklive-tabl?s?e'))
                if not table:
                    # Fallback to generic table
                    table = soup.find('table')
                
                if not table: return []
                
                rows = table.find_all('tr')[1:] 
                fetch_time = datetime.now(timezone.utc)
                all_rates = []

                for row in rows:
                    code_el = row.select_one('.code')
                    name_el = row.select_one('.currencyName')
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        code_text = code_el.get_text(strip=True) if code_el else ""
                        code = code_text.replace('EGP', '') if code_text.endswith('EGP') else code_text
                        
                        # Prices are in .bankRate span
                        buy_el = cols[1].select_one('.bankRate')
                        sell_el = cols[2].select_one('.bankRate')
                        
                        buy_text = buy_el.get_text(strip=True) if buy_el else cols[1].get_text(strip=True)
                        sell_text = sell_el.get_text(strip=True) if sell_el else cols[2].get_text(strip=True)
                        
                        buy_val = self._clean_price(buy_text)
                        sell_val = self._clean_price(sell_text)
                        
                        if sell_val > 0:
                            all_rates.append({
                                "currency": code,
                                "currency_name": name_el.get_text(strip=True) if name_el else code,
                                "buy_price": buy_val,
                                "sell_price": sell_val,
                                "source": self.name,
                                "timestamp": fetch_time
                            })
                return all_rates
            except Exception as e:
                logger.error(f"BankLive failed for {self.bank_id}: {e}")
                return []

class CurrencyScraperManager:
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.sources_map = {
            "ta3weem": {
                "nbe": Ta3weemBankSource("nbe", "البنك الأهلي المصري", "https://ta3weem.com/ar/banks/national-bank-of-egypt-nbe"),
                "bdc": Ta3weemBankSource("bdc", "بنك القاهرة", "https://ta3weem.com/ar/banks/banque-du-caire-bdc")
            },
            "egrates": {
                "nbe": EgratesBankSource("nbe", "البنك الأهلي المصري", "https://egrates.com/banks/4"),
                "bdc": EgratesBankSource("bdc", "بنك القاهرة", "https://egrates.com/banks/6")
            },
            "banklive": {
                "nbe": BankLiveBankSource("nbe", "البنك الأهلي المصري", "https://banklive.net/ar/currency-exchange-rates-in-national-bank-of-egypt"),
                "bdc": BankLiveBankSource("bdc", "بنك القاهرة", "https://banklive.net/ar/currency-exchange-rates-in-banque-du-caire")
            }
        }

    def _get_enabled_sources_in_order(self) -> List[str]:
        if not self.db_session:
            return ["ta3weem", "egrates", "banklive"]
        
        try:
            from app.models import CurrencySourceSettings
            settings = self.db_session.query(CurrencySourceSettings).filter(
                CurrencySourceSettings.is_enabled == True
            ).order_by(CurrencySourceSettings.priority).all()
            return [s.source_name for s in settings] or ["ta3weem", "egrates", "banklive"]
        except Exception:
            return ["ta3weem", "egrates", "banklive"]

    async def get_latest_rates(self) -> List[Dict]:
        enabled_source_ids = self._get_enabled_sources_in_order()
        all_collected_rates = []
        
        # We need NBE and BDC for averages/primary data
        for bank_key in ["nbe", "bdc"]:
            bank_rates = []
            for source_id in enabled_source_ids:
                source = self.sources_map.get(source_id, {}).get(bank_key)
                if not source: continue
                
                try:
                    logger.info(f"Fetching {bank_key} from {source.name}")
                    rates = await source.fetch_rates()
                    if rates:
                        bank_rates = rates
                        # Add metadata
                        for r in bank_rates:
                            r['source_status'] = "Primary" if source_id == enabled_source_ids[0] else "Fallback"
                        break
                except Exception as e:
                    logger.warning(f"Failed to fetch {bank_key} from {source_id}: {e}")
                    continue
            
            all_collected_rates.extend(bank_rates)
            
        return all_collected_rates

async def get_all_currency_rates(enabled_sources: List[str] = None, db=None) -> List[Dict]:
    manager = CurrencyScraperManager(db_session=db)
    return await manager.get_latest_rates()

async def test():
    print("Testing Currency Dynamic Scraper...")
    manager = CurrencyScraperManager()
    rates = await manager.get_latest_rates()
    print(f"Total rates found: {len(rates)}")
    for r in rates[:5]:
        print(f"  {r['currency']}: {r['buy_price']} / {r['sell_price']} ({r['source']})")

if __name__ == "__main__":
    asyncio.run(test())

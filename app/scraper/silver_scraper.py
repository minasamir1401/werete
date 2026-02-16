"""
Silver Price Scraper
"""

import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SilverScraper:
    """
    Silver price scraper with primary/fallback source logic
    """
    
    PRIMARY_URL = "https://safehavenhub.com/pages/اسعار-الذهب-والفضة"
    FALLBACK_URL = "https://gold-price-live.com/view/silver-price"
    
    TIMEOUT = 15  # seconds
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _get_enabled_sources_in_order(self) -> list[str]:
        """Get enabled sources from database settings, ordered by priority"""
        if not self.db_session:
            return ["safehavenhub", "goldpricelive"]
        
        try:
            from app.models import SilverSourceSettings
            settings = self.db_session.query(SilverSourceSettings).filter(
                SilverSourceSettings.is_enabled == True
            ).order_by(SilverSourceSettings.priority).all()
            
            if settings:
                return [s.source_name for s in settings]
            return ["safehavenhub", "goldpricelive"]
        except Exception as e:
            logger.warning(f"Failed to load silver source settings: {e}")
            return ["safehavenhub", "goldpricelive"]

    async def scrape(self) -> Dict[str, Any]:
        """
        Main scraping method with automatic fallback based on DB settings
        """
        enabled_sources = self._get_enabled_sources_in_order()
        
        for source_name in enabled_sources:
            try:
                if source_name == "safehavenhub":
                    logger.info("Attempting to scrape source: safehavenhub.com")
                    data = await self._scrape_safehavenhub()
                    if data and data.get('silver_999_sell'):
                        data['source_used'] = 'safehavenhub'
                        data['source_status'] = 'Primary' if source_name == enabled_sources[0] else 'Fallback'
                        return data
                elif source_name == "goldpricelive":
                    logger.info("Attempting to scrape source: gold-price-live.com")
                    data = await self._scrape_goldpricelive()
                    if data and data.get('silver_gram_price'):
                        data['source_used'] = 'gold-price-live'
                        data['source_status'] = 'Primary' if source_name == enabled_sources[0] else 'Fallback'
                        return data
            except Exception as e:
                logger.warning(f"Source {source_name} failed: {str(e)}")
        
        # Both sources failed
        logger.error("ALL SOURCES FAILED - No silver data available")
        raise Exception("All silver price sources failed")
    
    async def _scrape_safehavenhub(self) -> Optional[Dict[str, Any]]:
        """Scrape silver prices from safehavenhub.com"""
        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
            try:
                response = await client.get(self.PRIMARY_URL, headers=self.headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                data = {
                    # 999 Purity
                    'silver_999_sell': None,
                    'silver_999_buy': None,
                    'silver_999_change': None,
                    'silver_999_change_percent': None,
                    
                    # 925 Purity
                    'silver_925_sell': None,
                    'silver_925_buy': None,
                    'silver_925_change': None,
                    'silver_925_change_percent': None,
                    
                    # 900 Purity
                    'silver_900_sell': None,
                    'silver_900_buy': None,
                    'silver_900_change': None,
                    'silver_900_change_percent': None,
                    
                    # 800 Purity
                    'silver_800_sell': None,
                    'silver_800_buy': None,
                    'silver_800_change': None,
                    'silver_800_change_percent': None,
                    
                    # Ounce (USD)
                    'ounce_usd_sell': None,
                    'ounce_usd_buy': None,
                    'ounce_usd_change': None,
                    'ounce_usd_change_percent': None,
                    
                    # Legacy fields
                    'silver_gram_price': None,
                    'silver_ounce_price': None,
                    'silver_999_price': None,
                    'silver_925_price': None,
                    'buy_price': None,
                    'sell_price': None,
                    'daily_change': None,
                    'daily_change_percent': None,
                    
                    'currency': 'EGP',
                    'scraped_at': datetime.now(),
                    'source_update_time': None,
                    'raw_data': None
                }
                
                tables = soup.find_all('table')
                
                if tables and len(tables) > 0:
                    table = tables[0]  # First table is Silver
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) < 5:  # Need: Name, Sell, Buy, Change, %
                            continue
                            
                        name = cells[0].get_text(strip=True)
                        sell_text = cells[1].get_text(strip=True)
                        buy_text = cells[2].get_text(strip=True)
                        change_text = cells[3].get_text(strip=True)
                        percent_text = cells[4].get_text(strip=True)
                        
                        sell_val = self._parse_price(sell_text)
                        buy_val = self._parse_price(buy_text)
                        change_val = self._parse_change(change_text)
                        percent_val = self._parse_change_percent(percent_text)
                        
                        if '999' in name:
                            data['silver_999_sell'] = sell_val
                            data['silver_999_buy'] = buy_val
                            data['silver_999_change'] = change_val
                            data['silver_999_change_percent'] = percent_val
                            
                            # Legacy fields
                            data['silver_999_price'] = sell_val
                            data['silver_gram_price'] = sell_val
                            data['sell_price'] = sell_val
                            data['buy_price'] = buy_val
                            data['daily_change'] = change_val
                            data['daily_change_percent'] = percent_val
                            
                        elif '925' in name:
                            data['silver_925_sell'] = sell_val
                            data['silver_925_buy'] = buy_val
                            data['silver_925_change'] = change_val
                            data['silver_925_change_percent'] = percent_val
                            data['silver_925_price'] = sell_val  # Legacy
                            
                        elif '900' in name:
                            data['silver_900_sell'] = sell_val
                            data['silver_900_buy'] = buy_val
                            data['silver_900_change'] = change_val
                            data['silver_900_change_percent'] = percent_val
                            
                        elif '800' in name:
                            data['silver_800_sell'] = sell_val
                            data['silver_800_buy'] = buy_val
                            data['silver_800_change'] = change_val
                            data['silver_800_change_percent'] = percent_val
                            
                        elif 'الأوقية' in name or 'ounce' in name.lower():
                            # Ounce prices are in USD
                            data['ounce_usd_sell'] = sell_val
                            data['ounce_usd_buy'] = buy_val
                            data['ounce_usd_change'] = change_val
                            data['ounce_usd_change_percent'] = percent_val
                            
                    # Calculate EGP ounce price from 999 gram price
                    if data['silver_999_sell']:
                        data['silver_ounce_price'] = round(data['silver_999_sell'] * 31.1035, 2)
                
                # Store raw data for debugging
                data['raw_data'] = json.dumps({
                    'url': self.PRIMARY_URL,
                    'timestamp': datetime.now().isoformat(),
                    'tables_found': len(tables)
                })
                
                # Validation: We need at least 999 sell price
                if data['silver_999_sell']:
                    return data
                    
                return None
                
            except Exception as e:
                logger.error(f"Error parsing safehavenhub data: {str(e)}")
                raise
    
    async def _scrape_goldpricelive(self) -> Optional[Dict[str, Any]]:
        """Scrape silver prices from gold-price-live.com (fallback)"""
        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as client:
            try:
                response = await client.get(self.FALLBACK_URL, headers=self.headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                data = {
                    'silver_gram_price': None,
                    'silver_ounce_price': None,
                    'silver_999_price': None,
                    'silver_925_price': None,
                    'buy_price': None,
                    'sell_price': None,
                    'daily_change': None,
                    'daily_change_percent': None,
                    'currency': 'EGP',
                    'scraped_at': datetime.now(),
                    'source_update_time': None,
                    'raw_data': None
                }
                
                # Method 1: Main display .mb-5
                main_price_el = soup.select_one('.mb-5')
                if main_price_el:
                    text = main_price_el.get_text(strip=True)
                    price = self._parse_price(text)
                    if price:
                        data['silver_gram_price'] = price
                        data['silver_999_price'] = price 
                        data['sell_price'] = price
                        data['silver_ounce_price'] = round(price * 31.1035, 2)
                        data['silver_925_price'] = round(price * 0.925, 2)
                        
                # Method 2: Table fallback
                if not data['silver_gram_price']:
                    table = soup.find('table', class_='local-cur') 
                    if table:
                        rows = table.find_all('tr')
                        for row in rows:
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                name = cells[0].get_text(strip=True)
                                val_text = cells[1].get_text(strip=True)
                                val = self._parse_price(val_text)
                                
                                if '1' in name and 'جرام' in name and val:
                                     data['silver_gram_price'] = val
                                     data['silver_999_price'] = val
                                     data['silver_ounce_price'] = round(val * 31.1035, 2)
                                     break
                
                # Store raw data
                data['raw_data'] = json.dumps({
                    'url': self.FALLBACK_URL,
                    'timestamp': datetime.now().isoformat(),
                    'main_price_found': bool(main_price_el)
                })
                
                if data['silver_gram_price']:
                    return data
                    
                return None
                
            except Exception as e:
                logger.error(f"Error parsing gold-price-live data: {str(e)}")
                raise

    def _parse_price(self, text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not text:
            return None
        
        try:
            # Remove common characters
            cleaned = text.strip()
            # Handle RTL issues or spaced naming
            cleaned = cleaned.replace(',', '')
            cleaned = cleaned.replace('EGP', '')
            cleaned = cleaned.replace('ج.م', '')
            cleaned = cleaned.replace('$', '')
            cleaned = cleaned.replace('USD', '')
            cleaned = cleaned.replace(' ', '')
            
            # Extract first valid number
            import re
            match = re.search(r'[\d.]+', cleaned)
            if match:
                return float(match.group())
        except Exception as e:
            logger.warning(f"Failed to parse price '{text}': {str(e)}")
        
        return None
    
    def _parse_change(self, text: str) -> Optional[float]:
        """Extract absolute change value"""
        if not text:
            return None
        
        try:
            cleaned = text.replace('+', '').replace('%', '').replace('ج.م', '').strip()
            import re
            match = re.search(r'[-]?[\d.]+', cleaned)
            if match:
                return float(match.group())
        except Exception as e:
            logger.warning(f"Failed to parse change '{text}': {str(e)}")
        
        return None
    
    def _parse_change_percent(self, text: str) -> Optional[float]:
        """Extract percentage change"""
        if not text or '%' not in text:
            return None
        
        try:
            # Typical format %0.69 or 0.69%
            cleaned = text.replace('+', '').replace('%', '').strip()
            import re
            match = re.search(r'[-]?[\d.]+', cleaned)
            if match:
                return float(match.group())
        except Exception as e:
            logger.warning(f"Failed to parse change percent '{text}': {str(e)}")
        
        return None


# Convenience function
async def scrape_silver_prices(db=None) -> Dict[str, Any]:
    """Scrape silver prices using primary/fallback logic"""
    scraper = SilverScraper(db_session=db)
    return await scraper.scrape()

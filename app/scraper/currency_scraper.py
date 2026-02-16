"""
Currency Exchange Rates Scraper for ta3weem.com
Scrapes USD/EGP exchange rates from Egyptian banks
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import re
from datetime import datetime


class Ta3weemCurrencyScraper:
    """Scraper for ta3weem.com currency exchange rates"""
    
    BASE_URL = "https://ta3weem.com/ar/currency-exchange-rates"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def scrape_currency(self, from_currency: str = "USD", to_currency: str = "EGP") -> Dict:
        """
        Scrape currency exchange rates
        
        Args:
            from_currency: Source currency code (default: USD)
            to_currency: Target currency code (default: EGP)
            
        Returns:
            Dictionary containing exchange rate data
        """
        url = f"{self.BASE_URL}/{from_currency}-{to_currency}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract summary cards
            summary = self._extract_summary(soup)
            
            # Extract bank rates from table
            banks = self._extract_bank_rates(soup)
            
            return {
                "currency_pair": f"{from_currency}/{to_currency}",
                "from_currency": from_currency,
                "to_currency": to_currency,
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
                "banks": banks,
                "total_banks": len(banks)
            }
            
        except Exception as e:
            print(f"Error scraping {from_currency}/{to_currency}: {e}")
            return None
    
    def _extract_summary(self, soup: BeautifulSoup) -> Dict:
        """Extract summary statistics"""
        summary = {
            "highest_buy": None,
            "highest_buy_change": None,
            "lowest_sell": None,
            "lowest_sell_change": None,
            "average": None,
            "average_change": None,
            "central_bank_buy": None,
            "central_bank_sell": None,
            "decision_center_buy": None,
            "decision_center_sell": None
        }
        
        try:
            # Summary cards often have flex-col and rounded-2xl
            cards = soup.find_all(['div', 'a'], class_=lambda x: x and 'flex-col' in x and 'rounded-2xl' in x)
            
            for card in cards:
                title_elem = card.find('h3', class_='text-xs')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                price_elem = card.find('span', class_='font-medium text-blue-500')
                
                if 'أعلى سعر شراء' in title:
                    if price_elem:
                        summary['highest_buy'] = self._parse_number(price_elem.get_text(strip=True))
                    change_elem = card.find('span', class_=lambda x: x and 'font-medium' in x and 'text-sm' in x)
                    if change_elem:
                        summary['highest_buy_change'] = self._parse_number(change_elem.get_text(strip=True))
                        
                elif 'أقل سعر بيع' in title:
                    if price_elem:
                        summary['lowest_sell'] = self._parse_number(price_elem.get_text(strip=True))
                    change_elem = card.find('span', class_=lambda x: x and 'font-medium' in x and 'text-sm' in x)
                    if change_elem:
                        summary['lowest_sell_change'] = self._parse_number(change_elem.get_text(strip=True))
                        
                elif 'متوسط السعر' in title:
                    if price_elem:
                        summary['average'] = self._parse_number(price_elem.get_text(strip=True))
                    change_elem = card.find('span', class_=lambda x: x and 'font-medium' in x and 'text-sm' in x)
                    if change_elem:
                        summary['average_change'] = self._parse_number(change_elem.get_text(strip=True))
                        
                elif 'البنك المركزي' in title or 'CBE' in title:
                    buy_labels = card.find_all('span', string=re.compile('شراء'))
                    sell_labels = card.find_all('span', string=re.compile('بيع'))
                    
                    for label in buy_labels:
                        price_span = label.find_next('span', class_='font-medium text-blue-500')
                        if price_span:
                            summary['central_bank_buy'] = self._parse_number(price_span.get_text(strip=True))
                            break
                    
                    for label in sell_labels:
                        price_span = label.find_next('span', class_='font-medium text-blue-500')
                        if price_span:
                            summary['central_bank_sell'] = self._parse_number(price_span.get_text(strip=True))
                            break
                            
                elif 'مركز دعم' in title:
                    buy_labels = card.find_all('span', string=re.compile('شراء'))
                    sell_labels = card.find_all('span', string=re.compile('بيع'))
                    
                    for label in buy_labels:
                        price_span = label.find_next('span', class_='font-medium text-blue-500')
                        if price_span:
                            summary['decision_center_buy'] = self._parse_number(price_span.get_text(strip=True))
                            break
                    
                    for label in sell_labels:
                        price_span = label.find_next('span', class_='font-medium text-blue-500')
                        if price_span:
                            summary['decision_center_sell'] = self._parse_number(price_span.get_text(strip=True))
                            break
        
        except Exception as e:
            print(f"Error extracting summary: {e}")
        
        return summary
    
    def _extract_bank_rates(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract exchange rates from banks table"""
        banks = []
        
        try:
            tbody = soup.find('tbody')
            if not tbody:
                return banks
            
            rows = tbody.find_all('tr')
            for row in rows:
                try:
                    bank_data = {}
                    bank_link = row.find('a', href=True)
                    if bank_link:
                        bank_data['name'] = bank_link.get_text(strip=True)
                        bank_data['url'] = f"https://ta3weem.com{bank_link['href']}"
                        
                        logo_img = bank_link.find('img')
                        if logo_img and logo_img.get('src'):
                            logo_src = logo_img['src'].strip()
                            if logo_src.startswith('http'):
                                bank_data['logo'] = logo_src
                            elif logo_src.startswith('//'):
                                bank_data['logo'] = f"https:{logo_src}"
                            else:
                                if not logo_src.startswith('/'):
                                    logo_src = '/' + logo_src
                                bank_data['logo'] = f"https://ta3weem.com{logo_src}"
                    
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        buy_cell = cells[1]
                        buy_spans = buy_cell.find_all('span')
                        for span in buy_spans:
                            text = span.get_text(strip=True)
                            if re.match(r'^\d+\.?\d*$', text):
                                bank_data['buy_price'] = self._parse_number(text)
                                break
                        
                        for span in buy_spans:
                            text = span.get_text(strip=True)
                            if '%' in text:
                                bank_data['buy_change'] = self._parse_number(text)
                                break
                        
                        sell_cell = cells[2]
                        sell_spans = sell_cell.find_all('span')
                        for span in sell_spans:
                            text = span.get_text(strip=True)
                            if re.match(r'^\d+\.?\d*$', text):
                                bank_data['sell_price'] = self._parse_number(text)
                                break
                        
                        for span in sell_spans:
                            text = span.get_text(strip=True)
                            if '%' in text:
                                bank_data['sell_change'] = self._parse_number(text)
                                break
                        
                        if len(cells) >= 4:
                            update_cell = cells[3]
                            time_spans = update_cell.find_all('span', class_='text-nowrap')
                            if len(time_spans) >= 2:
                                bank_data['last_update_time'] = time_spans[0].get_text(strip=True)
                                bank_data['last_update_date'] = time_spans[1].get_text(strip=True)
                    
                    if bank_data.get('name') and (bank_data.get('buy_price') or bank_data.get('sell_price')):
                        banks.append(bank_data)
                
                except Exception as e:
                    print(f"Error parsing bank row: {e}")
                    continue
        
        except Exception as e:
            print(f"Error extracting bank rates: {e}")
        
        return banks
    
    def _parse_number(self, text: str) -> Optional[float]:
        """Parse number from text"""
        try:
            cleaned = re.sub(r'[^\d.-]', '', text)
            if cleaned:
                return float(cleaned)
        except:
            pass
        return None
    
    def scrape_multiple_currencies(self, currency_pairs: List[tuple]) -> Dict:
        """Scrape multiple currency pairs"""
        results = {}
        for from_curr, to_curr in currency_pairs:
            pair_key = f"{from_curr}_{to_curr}"
            data = self.scrape_currency(from_curr, to_curr)
            if data:
                results[pair_key] = data
        return results


if __name__ == "__main__":
    scraper = Ta3weemCurrencyScraper()
    print("Scraping USD/EGP rates...")
    data = scraper.scrape_currency("USD", "EGP")
    
    if data:
        print(f"Successfully scraped {data['currency_pair']}")
        print(f"Summary:")
        print(f"  - Highest Buy: {data['summary']['highest_buy']}")
        print(f"  - Lowest Sell: {data['summary']['lowest_sell']}")
        print(f"  - Average: {data['summary']['average']}")
        print(f"  - Central Bank Buy: {data['summary']['central_bank_buy']}")
        print(f"  - Central Bank Sell: {data['summary']['central_bank_sell']}")
        print(f"Found {data['total_banks']} banks")
    else:
        print("Failed to scrape data")


from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import logging
import re
from app.core import database
from app import models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsScraperSource(ABC):
    @abstractmethod
    async def fetch_news(self) -> List[Dict]:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

class GoldEraNewsSource(NewsScraperSource):
    URL = "https://egypt.gold-era.com/ar/blog/" # Assuming a blog or news section
    NAME = "GoldEra"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_news(self) -> List[Dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                # Try the blog/news URL. If 404, might need to adjust.
                # For now using a likely URL.
                r = await client.get(self.URL, headers=headers)
                if r.status_code != 200:
                    logger.warning(f"GoldEra news URL {self.URL} returned {r.status_code}")
                    return []
                
                soup = BeautifulSoup(r.text, 'lxml')
                articles = []
                
                # Generic attempt to find articles
                # Adjust selectors based on actual site structure if known
                cards = soup.find_all(['article', 'div'], class_=re.compile(r'post|article|blog-item'))
                
                for card in cards:
                    title_tag = card.find(['h2', 'h3', 'h4'])
                    link_tag = card.find('a')
                    
                    if title_tag and link_tag:
                         title = title_tag.get_text(strip=True)
                         link = link_tag.get('href')
                         if link and not link.startswith('http'):
                             link = f"https://egypt.gold-era.com{link}"
                             
                         # Attempt to find image
                         img_tag = card.find('img')
                         image = img_tag.get('src') if img_tag else None
                         if image and not image.startswith('http'):
                             image = f"https://egypt.gold-era.com{image}"
                             
                         articles.append({
                             "title": title,
                             "url": link,
                             "image": image,
                             "source": self.NAME,
                             "created_at": datetime.now(timezone.utc)
                         })
                         
                return articles
            except Exception as e:
                logger.error(f"Error scraping news from {self.NAME}: {e}")
                return []

class GoldBullionNewsSource(NewsScraperSource):
    URL = "https://goldbullioneg.com/blog/"
    NAME = "GoldBullion"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_news(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                if r.status_code != 200: return []
                
                soup = BeautifulSoup(r.text, 'lxml')
                articles = []
                
                # Check for common blog structures
                items = soup.select(".blog-post, .post, .article")
                for item in items:
                    title_elem = item.select_one("h2, h3, .entry-title")
                    if title_elem:
                        link_elem = title_elem.find('a') if title_elem.find('a') else item.find('a')
                        if link_elem:
                            title = title_elem.get_text(strip=True)
                            link = link_elem.get('href')
                            img_elem = item.find('img')
                            image = img_elem.get('src') if img_elem else None
                            
                            articles.append({
                                "title": title,
                                "url": link,
                                "image": image,
                                "source": self.NAME,
                                "created_at": datetime.now(timezone.utc)
                            })
                return articles
            except Exception as e:
                logger.error(f"Error scraping news from {self.NAME}: {e}")
                return []

class EgyptGoldPriceTodayNewsSource(NewsScraperSource):
    URL = "https://egypt.gold-price-today.com/"
    NAME = "EgyptGoldPriceToday"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_news(self) -> List[Dict]:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                if r.status_code != 200: return []
                soup = BeautifulSoup(r.text, 'lxml')
                articles = []
                # Looking for sidebar widget or news section
                # Often in "recent-posts-3" widget or similar
                widgets = soup.select(".widget_recent_entries li a")
                for link_tag in widgets:
                    title = link_tag.get_text(strip=True)
                    link = link_tag.get('href')
                    if link:
                        articles.append({
                            "title": title,
                            "url": link,
                            "image": None,
                            "source": self.NAME,
                            "created_at": datetime.now(timezone.utc)
                        })
                return articles
            except Exception as e:
                logger.error(f"Error scraping news from {self.NAME}: {e}")
                return []

class SouqPriceTodayNewsSource(NewsScraperSource):
    URL = "https://souq-price-today.com/"
    NAME = "SouqPriceToday"

    @property
    def name(self) -> str:
        return self.NAME

    async def fetch_news(self) -> List[Dict]:
        # Implementation similar to others, looking for blog posts
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.URL, headers=headers)
                if r.status_code != 200: return []
                soup = BeautifulSoup(r.text, 'lxml')
                articles = []
                # Souq price today often has a news ticker or latest posts
                posts = soup.select(".post-item, .latest-news li a")
                for post in posts:
                    title = post.get_text(strip=True)
                    link = post.get('href')
                    if link:
                         articles.append({
                            "title": title,
                            "url": link,
                            "image": None,
                            "source": self.NAME,
                            "created_at": datetime.now(timezone.utc)
                        })
                return articles
            except Exception as e:
                logger.error(f"Error scraping news from {self.NAME}: {e}")
                return []

class NewsScraperManager:
    def __init__(self):
        self.sources = [
            GoldEraNewsSource(),
            GoldBullionNewsSource(),
            EgyptGoldPriceTodayNewsSource(),
            SouqPriceTodayNewsSource()
        ]
    
    async def get_latest_news(self) -> List[Dict]:
        all_news = []
        for source in self.sources:
            try:
                logger.info(f"Scraping news from {source.name}...")
                news = await source.fetch_news()
                if news:
                    logger.info(f"Found {len(news)} articles from {source.name}")
                    all_news.extend(news)
            except Exception as e:
                logger.error(f"Failed to scrape news from {source.name}: {e}")
        return all_news
        
    async def test_sources(self) -> Dict[str, Dict]:
        results = {}
        for source in self.sources:
            try:
                start = datetime.now()
                news = await source.fetch_news()
                duration = (datetime.now() - start).total_seconds()
                results[source.name] = {
                    "status": "success" if news else "empty",
                    "count": len(news),
                    "duration": duration,
                    "sample": news[0]['title'] if news else None
                }
            except Exception as e:
                results[source.name] = {
                    "status": "error",
                    "error": str(e)
                }
        return results

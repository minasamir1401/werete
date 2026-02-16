from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, time

class GoldPriceBase(BaseModel):
    karat: str
    sell_price: float
    buy_price: float
    currency: str
    type: str

class GoldPriceCreate(GoldPriceBase):
    pass

class GoldPrice(GoldPriceBase):
    id: int
    timestamp: datetime
    date: date
    time: time
    source: str
    source_status: str
    country: str
    
    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    content: str
    content_json: Optional[str] = None # JSON string
    slug: str
    # UI Customizations
    title_color: Optional[str] = "#000000"
    title_size: Optional[str] = "text-3xl"
    
    # Meta
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    featured_image: Optional[str] = None
    
    # Classification
    author: Optional[str] = "Admin"
    category: Optional[str] = "General"
    tags: Optional[str] = None
    status: Optional[str] = "published"

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    id: int
    views: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QABase(BaseModel):
    page_key: str = "home"
    question: str
    answer: str
    is_active: bool = True
    display_order: int = 0

class QACreate(QABase):
    pass

class QAUpdate(QABase):
    pass

class QAResponse(QABase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingBase(BaseModel):
    key: str
    value: str

class Setting(SettingBase):
    class Config:
        from_attributes = True

class CurrencyPrice(BaseModel):
    id: int
    currency: str
    sell_price: float
    buy_price: float
    symbol: Optional[str] = None
    timestamp: datetime
    date: date
    time: time
    source: str

    class Config:
        from_attributes = True

class ManualPriceUpdate(BaseModel):
    karat: str
    price: Optional[float] = None

class AdminStats(BaseModel):
    total_prices: int
    total_articles: int
    last_update: Optional[datetime] = None
    active_source: str
    db_snapshots_count: int
    cache_last_updated: Optional[datetime] = None
    scraper_status: Optional[dict] = None
    prices: Optional[dict] = None
    news_stats: Optional[dict] = None


# User Authentication Schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "admin"  # "super_admin" or "admin"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class CurrencySourceSetting(BaseModel):
    id: int
    source_name: str
    display_name: str
    is_enabled: bool
    priority: int
    last_updated: datetime

    class Config:
        from_attributes = True

class CurrencySourceUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None

class SilverSourceSetting(BaseModel):
    id: int
    source_name: str
    display_name: str
    is_enabled: bool
    priority: int
    last_updated: datetime

    class Config:
        from_attributes = True

class SilverSourceUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None


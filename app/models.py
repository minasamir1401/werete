from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Date, Time, Boolean, Text
from datetime import datetime
import enum
from app.core.database import Base

class GoldPrice(Base):
    __tablename__ = "gold_prices"

    id = Column(Integer, primary_key=True, index=True)
    karat = Column(String, index=True)
    sell_price = Column(Float)
    buy_price = Column(Float)
    currency = Column(String, default="EGP")
    country = Column(String, default="Egypt", index=True)
    
    # Required strict fields
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, index=True)       # YYYY-MM-DD
    time = Column(Time)                   # HH:MM:SS
    
    # Internal tracking
    source = Column(String)  # internal name e.g. "GoldEra"
    source_status = Column(String) # "Primary" or "Fallback"
    type = Column(String, default="Local") 

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    
    # Header & Meta
    title = Column(String, index=True)
    title_color = Column(String, default="#000000")
    title_size = Column(String, default="text-3xl")
    meta_title = Column(String, nullable=True)
    meta_description = Column(String, nullable=True)
    featured_image = Column(String, nullable=True)
    
    # Content
    content = Column(String) # Plain text fallback or HTML
    content_json = Column(String, nullable=True) # Storing JSON blocks as string for SQLite compatibility
    
    # Classification
    author = Column(String, default="Admin")
    category = Column(String, default="General")
    tags = Column(String, nullable=True) # Comma separated
    
    # Status
    status = Column(String, default="published") # published, draft, archived
    views = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String)

class CurrencyPrice(Base):
    __tablename__ = "currency_prices"

    id = Column(Integer, primary_key=True, index=True)
    currency = Column(String, index=True)
    sell_price = Column(Float)
    buy_price = Column(Float)
    symbol = Column(String, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, index=True)
    time = Column(Time)
    
    source = Column(String)

class BankCurrencyRate(Base):
    """Bank exchange rates from ta3weem.com"""
    __tablename__ = "bank_currency_rates"

    id = Column(Integer, primary_key=True, index=True)
    bank_name = Column(String, index=True)
    bank_url = Column(String, nullable=True)
    bank_logo = Column(String, nullable=True)
    # currency_flag = Column(String, nullable=True) # Check if this exists in your DB, if not leave commented
    
    from_currency = Column(String, index=True)  # USD, EUR, etc.
    to_currency = Column(String, index=True)    # EGP
    
    buy_price = Column(Float)
    sell_price = Column(Float)
    buy_change = Column(Float, nullable=True)   # Percentage change
    sell_change = Column(Float, nullable=True)
    
    last_update_time = Column(String, nullable=True)
    last_update_date = Column(String, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, index=True)

class CurrencyMarketSummary(Base):
    """Market-wide summary for a currency pair"""
    __tablename__ = "currency_market_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String, index=True)
    to_currency = Column(String, index=True)
    
    highest_buy = Column(Float, nullable=True)
    highest_buy_change = Column(Float, nullable=True)
    lowest_sell = Column(Float, nullable=True)
    lowest_sell_change = Column(Float, nullable=True)
    average = Column(Float, nullable=True)
    average_change = Column(Float, nullable=True)
    
    central_bank_buy = Column(Float, nullable=True)
    central_bank_sell = Column(Float, nullable=True)
    decision_center_buy = Column(Float, nullable=True)
    decision_center_sell = Column(Float, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    date = Column(Date, index=True)

class UnifiedPrice(Base):
    """
    Single Source of Truth for current prices.
    Each (type, country, karat/code) must have exactly one row.
    """
    __tablename__ = "unified_prices"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True) # gold, currency
    country = Column(String, index=True) # egypt, global, or country slug
    key = Column(String, index=True) # karat (24, 21) or currency code (USD, EUR)
    
    sell_price = Column(Float)
    buy_price = Column(Float)
    currency = Column(String) # Price currency (EGP, USD, etc.)
    
    source_name = Column(String)
    source_status = Column(String) # Primary, Fallback, Manual
    
    last_update = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")

class PriceHistory(Base):
    """Historical archive of all price changes."""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    price_id = Column(Integer, index=True) # Relation to metadata if needed
    type = Column(String, index=True)
    country = Column(String, index=True)
    key = Column(String, index=True)
    
    sell_price = Column(Float)
    buy_price = Column(Float)
    
    source_name = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class AllBanksCurrencyRate(Base):
    """Stores currency rates from ALL banks across all sources"""
    __tablename__ = "all_banks_currency_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(String, index=True)  # Unique identifier (e.g., "national-bank-of-egypt-nbe")
    bank_name = Column(String, index=True)  # Display name (e.g., "البنك الأهلي المصري")
    
    currency = Column(String, index=True)  # USD, EUR, SAR, etc.
    buy_price = Column(Float)
    sell_price = Column(Float)
    
    source = Column(String)  # Ta3weem_AllBanks, Egrates_AllBanks, etc.
    last_update = Column(DateTime, default=datetime.utcnow, index=True)
    
class CurrencySourceSettings(Base):
    """Settings for currency data sources (Ta3weem, Egrates, BankLive)"""
    __tablename__ = "currency_source_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, unique=True, index=True) # ta3weem, egrates, banklive
    display_name = Column(String) # Arabic name for UI
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SilverSourceSettings(Base):
    """Settings for silver data sources (SafeHavenHub, GoldPriceLive)"""
    __tablename__ = "silver_source_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, unique=True, index=True) # safehavenhub, goldpricelive
    display_name = Column(String) # Arabic name for UI
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BankDisplaySettings(Base):
    """Controls which banks are displayed and their order"""
    __tablename__ = "bank_display_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(String, unique=True, index=True)
    bank_name = Column(String)
    
    is_enabled = Column(Boolean, default=True)  # True = show, False = hide
    display_order = Column(Integer, default=999)  # Lower numbers appear first
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SilverPrice(Base):
    """Silver price tracking with historical data"""
    __tablename__ = "silver_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source tracking
    source_used = Column(String, index=True)  # 'safehavenhub' or 'gold-price-live'
    source_status = Column(String)  # 'Primary' or 'Fallback'
    
    # Price data - 999 Purity (Pure Silver)
    silver_999_sell = Column(Float, nullable=True)
    silver_999_buy = Column(Float, nullable=True)
    silver_999_change = Column(Float, nullable=True)
    silver_999_change_percent = Column(Float, nullable=True)
    
    # Price data - 925 Purity (Sterling Silver)
    silver_925_sell = Column(Float, nullable=True)
    silver_925_buy = Column(Float, nullable=True)
    silver_925_change = Column(Float, nullable=True)
    silver_925_change_percent = Column(Float, nullable=True)
    
    # Price data - 900 Purity
    silver_900_sell = Column(Float, nullable=True)
    silver_900_buy = Column(Float, nullable=True)
    silver_900_change = Column(Float, nullable=True)
    silver_900_change_percent = Column(Float, nullable=True)
    
    # Price data - 800 Purity
    silver_800_sell = Column(Float, nullable=True)
    silver_800_buy = Column(Float, nullable=True)
    silver_800_change = Column(Float, nullable=True)
    silver_800_change_percent = Column(Float, nullable=True)
    
    # Ounce price (in USD)
    ounce_usd_sell = Column(Float, nullable=True)
    ounce_usd_buy = Column(Float, nullable=True)
    ounce_usd_change = Column(Float, nullable=True)
    ounce_usd_change_percent = Column(Float, nullable=True)
    
    # Legacy fields (for backward compatibility)
    silver_gram_price = Column(Float, nullable=True)  # Same as silver_999_sell
    silver_ounce_price = Column(Float, nullable=True)  # Calculated from 999 * 31.1035
    silver_999_price = Column(Float, nullable=True)  # Same as silver_999_sell
    silver_925_price = Column(Float, nullable=True)  # Same as silver_925_sell
    buy_price = Column(Float, nullable=True)  # Same as silver_999_buy
    sell_price = Column(Float, nullable=True)  # Same as silver_999_sell
    daily_change = Column(Float, nullable=True)
    daily_change_percent = Column(Float, nullable=True)
    
    # Metadata
    currency = Column(String, default="EGP")
    scraped_at = Column(DateTime, index=True)  # When we scraped it
    source_update_time = Column(String, nullable=True)  # Update time from source
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Additional data (JSON for flexibility)
    raw_data = Column(Text, nullable=True)  # Store raw scraped data as JSON string


class QAItem(Base):
    """Q&A items for the main page"""
    __tablename__ = "qa_items"
    
    id = Column(Integer, primary_key=True, index=True)
    page_key = Column(String, default="home", index=True) # home, gold, silver, currencies
    question = Column(String, index=True)
    answer = Column(Text)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="admin")  # "super_admin" or "admin"
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, nullable=True)  # ID of super_admin who created this user


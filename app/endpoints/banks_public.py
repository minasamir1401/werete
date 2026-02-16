"""
Public endpoints for displaying bank currency rates
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core import database
from app import models
from typing import List, Dict

router = APIRouter()

@router.get("/rates/{currency}")
def get_bank_rates_for_currency(
    currency: str,
    db: Session = Depends(database.get_db)
):
    """
    Get currency rates from all ENABLED banks for a specific currency.
    Returns banks in the order specified by admin settings.
    """
    # Get enabled banks in order
    enabled_settings = db.query(models.BankDisplaySettings).filter(
        models.BankDisplaySettings.is_enabled == True
    ).order_by(models.BankDisplaySettings.display_order).all()
    
    enabled_bank_ids = [s.bank_id for s in enabled_settings]
    
    # Get rates for these banks
    rates = db.query(models.AllBanksCurrencyRate).filter(
        models.AllBanksCurrencyRate.currency == currency.upper(),
        models.AllBanksCurrencyRate.bank_id.in_(enabled_bank_ids)
    ).all()
    
    # Create a dict for quick lookup
    rates_dict = {r.bank_id: r for r in rates}
    
    # Build result in the correct order
    result = []
    for bank_id in enabled_bank_ids:
        rate = rates_dict.get(bank_id)
        if rate:
            result.append({
                "bank_id": rate.bank_id,
                "bank_name": rate.bank_name,
                "currency": rate.currency,
                "buy_price": rate.buy_price,
                "sell_price": rate.sell_price,
                "last_update": rate.last_update
            })
    
    return {
        "currency": currency.upper(),
        "banks": result,
        "total": len(result)
    }

@router.get("/rates/all")
def get_all_enabled_bank_rates(db: Session = Depends(database.get_db)):
    """
    Get all currency rates from all enabled banks.
    Organized by currency.
    """
    # Get enabled banks
    enabled_settings = db.query(models.BankDisplaySettings).filter(
        models.BankDisplaySettings.is_enabled == True
    ).order_by(models.BankDisplaySettings.display_order).all()
    
    enabled_bank_ids = [s.bank_id for s in enabled_settings]
    
    # Get all rates for enabled banks
    rates = db.query(models.AllBanksCurrencyRate).filter(
        models.AllBanksCurrencyRate.bank_id.in_(enabled_bank_ids)
    ).all()
    
    # Organize by currency
    by_currency = {}
    for rate in rates:
        if rate.currency not in by_currency:
            by_currency[rate.currency] = []
        
        by_currency[rate.currency].append({
            "bank_id": rate.bank_id,
            "bank_name": rate.bank_name,
            "buy_price": rate.buy_price,
            "sell_price": rate.sell_price,
            "last_update": rate.last_update
        })
    
    # Sort each currency's banks by the display order
    bank_order = {s.bank_id: i for i, s in enumerate(enabled_settings)}
    for currency in by_currency:
        by_currency[currency].sort(key=lambda x: bank_order.get(x['bank_id'], 999))
    
    return by_currency

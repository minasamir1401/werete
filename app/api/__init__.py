from fastapi import APIRouter
from app.endpoints import gold, news, admin, currency, upload, prices, banks_admin, banks_public, silver, qa, legacy, auth

api_router = APIRouter()
api_router.include_router(legacy.router, tags=["Legacy Support"])

# Unified Production Endpoints
api_router.include_router(prices.router, prefix="/v1", tags=["Production Prices"])
api_router.include_router(news.router, prefix="/v1/news", tags=["news"])

# Banks endpoints
api_router.include_router(banks_public.router, prefix="/v1/banks", tags=["Banks Public"])
api_router.include_router(banks_admin.router, prefix="/admin/banks", tags=["Banks Admin"])

# Gold specific (for /api/gold/prices)
api_router.include_router(gold.router, prefix="/gold", tags=["gold"])
api_router.include_router(currency.router, prefix="/currency", tags=["currency"])
api_router.include_router(silver.router, prefix="/silver", tags=["silver"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])


# Legacy / Root level (for /api/history, /api/sarf-currencies, etc)
api_router.include_router(gold.router, tags=["gold-root"])
api_router.include_router(currency.router, tags=["currency-root"])
# Legacy router removed as per cleanup request

# Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

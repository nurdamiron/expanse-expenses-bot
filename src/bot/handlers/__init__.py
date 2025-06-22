from aiogram import Router

from . import start, expense, photo, document, stats, categories, currency, export, settings, reports, keyboard

def setup_handlers() -> Router:
    """Setup all handlers"""
    router = Router()
    
    # Include all handler routers
    # Order matters! More specific handlers should come first
    router.include_router(start.router)
    router.include_router(photo.router)
    router.include_router(document.router)
    router.include_router(stats.router)
    router.include_router(reports.router)
    router.include_router(categories.router)
    router.include_router(currency.router)
    router.include_router(export.router)
    router.include_router(settings.router)
    router.include_router(keyboard.router)
    # Expense router should be last as it catches all text messages
    router.include_router(expense.router)
    
    return router
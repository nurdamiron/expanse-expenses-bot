from .user import UserService
from .category import CategoryService
from .transaction import TransactionService
from .currency import CurrencyService, currency_service
from .export import ExportService

# Try to import OCRService, but make it optional
try:
    from .ocr import OCRService
    OCR_AVAILABLE = True
except ImportError:
    OCRService = None
    OCR_AVAILABLE = False

__all__ = [
    "UserService", "CategoryService", "TransactionService", 
    "CurrencyService", "currency_service", "ExportService"
]

# Only include OCRService if it's available
if OCR_AVAILABLE:
    __all__.append("OCRService")
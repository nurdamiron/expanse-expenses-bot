import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.utils.i18n import i18n

logger = logging.getLogger(__name__)


class ClarificationHelper:
    """Helper for handling uncertain data clarification"""
    
    def __init__(self):
        self.confidence_thresholds = {
            'very_low': 0.3,
            'low': 0.5,
            'medium': 0.7,
            'high': 0.9
        }
    
    def needs_amount_clarification(self, ocr_result: Dict[str, Any], caption_data: Dict[str, Any]) -> bool:
        """Check if amount needs clarification"""
        # No amount found at all
        if not ocr_result.get('amount') and not caption_data.get('amount'):
            return True
        
        # Very low OCR confidence
        if ocr_result.get('confidence', 1) < self.confidence_thresholds['low']:
            return True
        
        # Conflicting amounts from OCR and caption
        if (ocr_result.get('amount') and caption_data.get('amount') and 
            abs(Decimal(str(ocr_result['amount'])) - caption_data['amount']) > Decimal('0.01')):
            return True
        
        return False
    
    def needs_category_clarification(self, detected_category: Optional[str], confidence: float = 1.0) -> bool:
        """Check if category needs clarification"""
        # No category detected
        if not detected_category or detected_category == 'other':
            return True
        
        # Low confidence in category detection
        if confidence < self.confidence_thresholds['medium']:
            return True
        
        return False
    
    def get_amount_clarification_keyboard(self, locale: str, suggested_amounts: list = None) -> InlineKeyboardMarkup:
        """Get keyboard for amount clarification"""
        keyboard = []
        
        # Add suggested amounts if available
        if suggested_amounts:
            row = []
            for amount in suggested_amounts[:3]:  # Max 3 suggestions
                row.append(InlineKeyboardButton(
                    text=str(amount),
                    callback_data=f"clarify_amount:{amount}"
                ))
            keyboard.append(row)
        
        # Add manual input option
        keyboard.append([
            InlineKeyboardButton(
                text=i18n.get("buttons.enter_manually", locale),
                callback_data="clarify_amount:manual"
            )
        ])
        
        # Add cancel button
        keyboard.append([
            InlineKeyboardButton(
                text=i18n.get("buttons.cancel", locale),
                callback_data="cancel"
            )
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_category_suggestions_keyboard(self, locale: str, text: str) -> InlineKeyboardMarkup:
        """Get keyboard with category suggestions based on text"""
        from src.bot.keyboards import get_default_categories_keyboard
        # This will be replaced with actual category keyboard
        # For now, return None
        return None
    
    def format_clarification_message(self, locale: str, clarification_type: str, 
                                    context: Dict[str, Any]) -> str:
        """Format clarification message based on type and context"""
        if clarification_type == 'amount':
            msg = i18n.get("clarification.amount_unclear", locale)
            
            # Add context if available
            if context.get('ocr_amount') and context.get('caption_amount'):
                msg += f"\n\n{i18n.get('clarification.found_different_amounts', locale)}"
                msg += f"\n• {i18n.get('clarification.from_image', locale)}: {context['ocr_amount']}"
                msg += f"\n• {i18n.get('clarification.from_caption', locale)}: {context['caption_amount']}"
            elif context.get('low_confidence'):
                msg += f"\n{i18n.get('clarification.low_confidence_hint', locale)}"
            
            return msg
        
        elif clarification_type == 'category':
            msg = i18n.get("clarification.category_unclear", locale)
            
            if context.get('description'):
                msg += f"\n\n{i18n.get('clarification.transaction_description', locale)}: {context['description']}"
            
            msg += f"\n\n{i18n.get('clarification.choose_category_hint', locale)}"
            
            return msg
        
        return ""
    
    def merge_clarified_data(self, original_data: Dict[str, Any], 
                            clarified_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge clarified data with original data"""
        result = original_data.copy()
        
        # Update with clarified values
        for key, value in clarified_data.items():
            if value is not None:
                result[key] = value
                
                # Mark as user-confirmed
                result[f'{key}_confirmed'] = True
        
        # Update confidence
        if 'amount_confirmed' in result or 'category_confirmed' in result:
            result['confidence'] = 1.0
        
        return result
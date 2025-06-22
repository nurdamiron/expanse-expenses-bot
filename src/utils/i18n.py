import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class I18n:
    """Internationalization support for the bot"""
    
    def __init__(self, locales_dir: str = "src/locales"):
        self.locales_dir = Path(locales_dir)
        self.translations: Dict[str, Dict[str, Any]] = {}
        self._load_translations()
    
    def _load_translations(self):
        """Load all translation files"""
        for locale_file in self.locales_dir.glob("*.yaml"):
            locale_code = locale_file.stem
            with open(locale_file, 'r', encoding='utf-8') as f:
                self.translations[locale_code] = yaml.safe_load(f)
    
    def get(self, key: str, locale: str = 'ru', **kwargs) -> str:
        """
        Get translated text by key
        
        Args:
            key: Dot-separated key path (e.g., 'welcome.greeting')
            locale: Language code ('ru' or 'kz')
            **kwargs: Format parameters for string interpolation
            
        Returns:
            Translated and formatted string
        """
        if locale not in self.translations:
            locale = 'ru'  # Fallback to Russian
        
        keys = key.split('.')
        value = self.translations.get(locale, {})
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        if value is None:
            # Try fallback to Russian
            if locale != 'ru':
                fallback_value = self.get(key, 'ru', **kwargs)
                logger.warning(f"Translation not found for key '{key}' in locale '{locale}', using Russian fallback: {fallback_value}")
                return fallback_value
            logger.error(f"Translation not found for key '{key}' in any locale")
            return f"[{key}]"  # Return key if translation not found
        
        # Format string with provided kwargs
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        
        return value
    
    def get_button(self, button_key: str, locale: str = 'ru') -> str:
        """Get button text"""
        return self.get(f"buttons.{button_key}", locale)
    
    def get_category(self, category_key: str, locale: str = 'ru') -> str:
        """Get category name"""
        return self.get(f"categories.{category_key}", locale)
    
    def get_error(self, error_key: str, locale: str = 'ru', **kwargs) -> str:
        """Get error message"""
        return self.get(f"errors.{error_key}", locale, **kwargs)
    
    def get_command_description(self, command: str, locale: str = 'ru') -> str:
        """Get command description"""
        return self.get(f"commands.{command}", locale)


# Create global instance
i18n = I18n()
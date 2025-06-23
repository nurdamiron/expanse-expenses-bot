import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # Bot Configuration
    bot_token: str = Field(..., env="BOT_TOKEN")
    bot_username: str = Field(..., env="BOT_USERNAME")
    
    # Database Configuration
    database_url: Optional[str] = Field(None, env="DATABASE_URL")
    db_host: Optional[str] = Field(None, env="DB_HOST")
    db_port: int = Field(3306, env="DB_PORT")
    db_username: Optional[str] = Field(None, env="DB_USERNAME")
    db_password: Optional[str] = Field(None, env="DB_PASSWORD")
    db_name: str = Field("expanse_bot", env="DB_NAME")
    
    # Redis Configuration
    redis_host: str = Field("localhost", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_db: int = Field(0, env="REDIS_DB")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    
    # AWS S3 Configuration
    aws_access_key_id: Optional[str] = Field(None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(None, env="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field("eu-north-1", env="AWS_REGION")
    s3_bucket_name: Optional[str] = Field(None, env="S3_BUCKET_NAME")
    s3_receipts_prefix: str = Field("receipts/", env="S3_RECEIPTS_PREFIX")
    s3_exports_prefix: str = Field("exports/", env="S3_EXPORTS_PREFIX")
    
    # Currency API Keys
    fixer_api_key: Optional[str] = Field(None, env="FIXER_API_KEY")
    exchangerate_api_key: Optional[str] = Field(None, env="EXCHANGERATE_API_KEY")
    
    # OCR Configuration
    tesseract_path: str = Field("/usr/local/bin/tesseract", env="TESSERACT_PATH")
    tesseract_lang: str = Field("rus+kaz+eng", env="TESSERACT_LANG")
    tessdata_prefix: Optional[str] = Field(None, env="TESSDATA_PREFIX")
    google_cloud_credentials: Optional[str] = Field(None, env="GOOGLE_CLOUD_CREDENTIALS")
    use_google_vision: bool = Field(False, env="USE_GOOGLE_VISION")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    use_openai_vision: bool = Field(False, env="USE_OPENAI_VISION")
    
    # Application Settings
    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    timezone: str = Field("Asia/Almaty", env="TIMEZONE")
    default_language: str = Field("ru", env="DEFAULT_LANGUAGE")
    default_currency: str = Field("KZT", env="DEFAULT_CURRENCY")
    
    # Hot Reload Configuration
    enable_hot_reload: bool = Field(False, env="ENABLE_HOT_RELOAD")
    hot_reload_paths: List[str] = Field(default_factory=lambda: ["src/bot/handlers", "src/bot/keyboards"], env="HOT_RELOAD_PATHS")
    dynamic_config_url: Optional[str] = Field(None, env="DYNAMIC_CONFIG_URL")
    dynamic_config_update_interval: int = Field(60, env="DYNAMIC_CONFIG_UPDATE_INTERVAL")
    
    # Webhook Configuration
    webhook_host: Optional[str] = Field(None, env="WEBHOOK_HOST")
    webhook_path: str = Field("/webhook", env="WEBHOOK_PATH")
    webhook_port: int = Field(8443, env="WEBHOOK_PORT")
    
    # Feature Flags
    enable_ocr: bool = Field(True, env="ENABLE_OCR")
    enable_currency_conversion: bool = Field(True, env="ENABLE_CURRENCY_CONVERSION")
    enable_notifications: bool = Field(True, env="ENABLE_NOTIFICATIONS")
    enable_export: bool = Field(True, env="ENABLE_EXPORT")
    
    # Rate Limiting
    max_transactions_per_day: int = Field(50, env="MAX_TRANSACTIONS_PER_DAY")
    max_image_size_mb: int = Field(20, env="MAX_IMAGE_SIZE_MB")
    rate_limit_requests_per_minute: int = Field(30, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    
    # Supported currencies
    supported_currencies: List[str] = [
        "KZT", "RUB", "USD", "EUR", "CNY", "KRW", "TRY", "SGD", "GBP", "JPY", 
        "AED", "THB", "MYR", "CAD", "AUD", "NZD", "CHF", "SEK", "NOK", "DKK",
        "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "INR", "IDR", "PHP", "VND",
        "BRL", "MXN", "ARS", "CLP", "COP", "PEN", "UYU", "ZAR", "SAR", "QAR",
        "BHD", "KWD", "OMR", "EGP", "ILS", "UAH", "KGS", "UZS", "AZN", "AMD",
        "GEL", "BYN", "MDL", "PKR", "BDT", "LKR", "NPR", "MMK", "LAK", "KHR",
        "HKD", "TWD", "MOP", "MAD", "TND", "NGN", "KES", "GHS", "ETB", "TZS"
    ]
    
    # Supported languages
    supported_languages: List[str] = ["ru", "kz"]
    
    @property
    def get_database_url(self) -> str:
        """Get database URL"""
        if self.database_url:
            return self.database_url
        return f"mysql+aiomysql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
    
    @property
    def redis_url(self) -> str:
        """Get Redis URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def webhook_url(self) -> Optional[str]:
        """Get webhook URL if configured"""
        if self.webhook_host:
            return f"https://{self.webhook_host}{self.webhook_path}"
        return None
    
    @property
    def environment(self) -> str:
        """Get environment alias"""
        return self.app_env
    
    @property
    def max_image_size_bytes(self) -> int:
        """Get max image size in bytes"""
        return self.max_image_size_mb * 1024 * 1024
    
    @validator("default_language")
    def validate_language(cls, v):
        if v not in ["ru", "kz"]:
            raise ValueError("Default language must be 'ru' or 'kz'")
        return v
    
    @validator("default_currency")
    def validate_currency(cls, v):
        supported = ["KZT", "RUB", "USD", "EUR", "CNY", "KRW", "TRY", "MYR"]
        if v not in supported:
            raise ValueError(f"Default currency must be one of {supported}")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.app_env == "production"
    
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.app_env == "development"


# Create global settings instance
settings = Settings()
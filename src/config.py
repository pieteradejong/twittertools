"""
DEPRECATED: This file is no longer used. All configuration is now managed in src/settings.py using Pydantic BaseSettings.

Configuration management for Twitter Tools.

Handles environment variables, Twitter API credentials, and application settings.
Provides validation and template generation for required environment variables.
"""
import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)

# Environment file paths
ENV_FILE = Path(__file__).parent.parent / '.env'
ENV_TEMPLATE = """# Twitter API Credentials
# Get these from https://developer.twitter.com/en/portal/dashboard
TWITTER_API_KEY=your_api_key_here
TWITTER_API_SECRET=your_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here
TWITTER_BEARER_TOKEN=your_bearer_token_here

# Application Settings
# Database settings
DATABASE_URL=sqlite:///./data/twittertools.db

# API Settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=true

# Frontend Settings
FRONTEND_URL=http://localhost:5173
"""

class TwitterConfig:
    """Manages Twitter API credentials and configuration."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TwitterConfig, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._load_env()
            self._initialized = True
    
    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        if not ENV_FILE.exists():
            logger.warning(f".env file not found at {ENV_FILE}")
            return
        
        load_dotenv(ENV_FILE)
        logger.info(f"Loaded environment from {ENV_FILE}")
    
    @staticmethod
    def get_api_key() -> str:
        """Get Twitter API key."""
        key = os.getenv('TWITTER_API_KEY')
        if not key:
            raise ValueError("TWITTER_API_KEY not found in environment variables")
        return key
    
    @staticmethod
    def get_api_secret() -> str:
        """Get Twitter API secret."""
        secret = os.getenv('TWITTER_API_SECRET')
        if not secret:
            raise ValueError("TWITTER_API_SECRET not found in environment variables")
        return secret
    
    @staticmethod
    def get_access_token() -> str:
        """Get Twitter access token."""
        token = os.getenv('TWITTER_ACCESS_TOKEN')
        if not token:
            raise ValueError("TWITTER_ACCESS_TOKEN not found in environment variables")
        return token
    
    @staticmethod
    def get_access_token_secret() -> str:
        """Get Twitter access token secret."""
        secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        if not secret:
            raise ValueError("TWITTER_ACCESS_TOKEN_SECRET not found in environment variables")
        return secret
    
    @staticmethod
    def get_bearer_token() -> str:
        """Get Twitter bearer token."""
        token = os.getenv('TWITTER_BEARER_TOKEN')
        if not token:
            raise ValueError("TWITTER_BEARER_TOKEN not found in environment variables")
        return token
    
    @classmethod
    def validate_credentials(cls) -> bool:
        """Validate that all required Twitter credentials are present."""
        try:
            cls.get_api_key()
            cls.get_api_secret()
            cls.get_access_token()
            cls.get_access_token_secret()
            cls.get_bearer_token()
            return True
        except ValueError as e:
            logger.error(f"Credential validation failed: {str(e)}")
            return False

class AppConfig:
    """Manages application-wide configuration settings."""
    
    def __init__(self):
        self._load_env()
    
    def _load_env(self) -> None:
        """Load environment variables."""
        load_dotenv(ENV_FILE)
    
    @property
    def database_url(self) -> str:
        """Get database URL."""
        return os.getenv('DATABASE_URL', 'sqlite:///./data/twittertools.db')
    
    @property
    def api_host(self) -> str:
        """Get API host."""
        return os.getenv('API_HOST', '127.0.0.1')
    
    @property
    def api_port(self) -> int:
        """Get API port."""
        return int(os.getenv('API_PORT', '8000'))
    
    @property
    def debug(self) -> bool:
        """Get debug mode setting."""
        return os.getenv('DEBUG', 'false').lower() == 'true'
    
    @property
    def frontend_url(self) -> str:
        """Get frontend URL."""
        return os.getenv('FRONTEND_URL', 'http://localhost:5173')

def create_env_template() -> None:
    """Create a template .env file if it doesn't exist."""
    if ENV_FILE.exists():
        logger.info(f".env file already exists at {ENV_FILE}")
        return
    
    try:
        ENV_FILE.write_text(ENV_TEMPLATE)
        logger.info(f"Created .env template at {ENV_FILE}")
    except Exception as e:
        logger.error(f"Failed to create .env template: {str(e)}")
        raise

# Create singleton instances
twitter_config = TwitterConfig()
app_config = AppConfig() 
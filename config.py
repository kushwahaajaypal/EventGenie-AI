"""
EventGenie AI - Application Configuration
Secured session parameters, strict environment mappings, and database configuration.
"""
import os
from typing import Type
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'eventgenie-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # Cookie & Session Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'

    # Gemini AI
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    @staticmethod
    def get_database_uri() -> str:
        """Return the database URI, using instance/ folder for SQLite."""
        db_url = os.getenv('DATABASE_URL', 'sqlite:///eventgenie.db')
        return db_url


class DevelopmentConfig(Config):
    """Development configuration with debugging enabled."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri()


class ProductionConfig(Config):
    """Production configuration with strict security settings."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri()


class TestingConfig(Config):
    """Testing configuration with in-memory database."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    GEMINI_API_KEY = 'test-api-key'
    WTF_CSRF_ENABLED = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}


def get_config() -> Type[Config]:
    """Retrieve configuration class matching the active FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)

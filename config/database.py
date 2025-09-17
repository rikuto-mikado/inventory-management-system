"""
Database configuration settings for the Inventory Management System.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str
    port: int
    database: str
    username: str
    password: str
    schema: str = "public"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    echo: bool = False  # Set to True for SQL query logging

    @property
    def connection_url(self) -> str:
        """Generate SQLAlchemy connection URL."""
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def connection_url_async(self) -> str:
        """Generate async SQLAlchemy connection URL."""
        return (
            f"postgresql+asyncpg://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        # Check if DATABASE_URL is provided (common in production)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            return cls.from_url(database_url)

        # Otherwise, use individual environment variables
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "inventory_management"),
            username=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            schema=os.getenv("DB_SCHEMA", "public"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            echo=os.getenv("DB_ECHO", "False").lower() == "true",
        )

    @classmethod
    def from_url(cls, database_url: str) -> "DatabaseConfig":
        """Create configuration from database URL."""
        from urllib.parse import urlparse

        parsed = urlparse(database_url)
        return cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "inventory_management",
            username=parsed.username or "postgres",
            password=parsed.password or "",
        )

    def validate(self) -> bool:
        """Validate configuration parameters."""
        required_fields = ["host", "database", "username"]
        for field in required_fields:
            if not getattr(self, field):
                raise ValueError(
                    f"Database configuration missing required field: {field}"
                )

        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port number: {self.port}")

        return True


@dataclass
class AppConfig:
    """Application configuration settings."""

    name: str = "Inventory Management System"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # UI Settings
    window_width: int = 1200
    window_height: int = 800
    theme: str = "light"

    # Business Logic
    default_currency: str = "JPY"
    low_stock_threshold: int = 10
    backup_interval_hours: int = 24

    # File Paths
    export_path: str = "./exports"
    backup_path: str = "./backup"
    log_path: str = "./logs"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        return cls(
            name=os.getenv("APP_NAME", cls.name),
            version=os.getenv("APP_VERSION", cls.version),
            debug=os.getenv("DEBUG", "False").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            window_width=int(os.getenv("WINDOW_WIDTH", str(cls.window_width))),
            window_height=int(os.getenv("WINDOW_HEIGHT", str(cls.window_height))),
            theme=os.getenv("THEME", cls.theme),
            default_currency=os.getenv("DEFAULT_CURRENCY", cls.default_currency),
            low_stock_threshold=int(
                os.getenv("LOW_STOCK_THRESHOLD", str(cls.low_stock_threshold))
            ),
            backup_interval_hours=int(
                os.getenv("BACKUP_INTERVAL_HOURS", str(cls.backup_interval_hours))
            ),
            export_path=os.getenv("EXPORT_PATH", cls.export_path),
            backup_path=os.getenv("BACKUP_PATH", cls.backup_path),
            log_path=os.getenv("LOG_PATH", cls.log_path),
        )


# Global configuration instances
db_config = DatabaseConfig.from_env()
app_config = AppConfig.from_env()


def get_database_config() -> DatabaseConfig:
    """Get the database configuration instance."""
    return db_config


def get_app_config() -> AppConfig:
    """Get the application configuration instance."""
    return app_config


def validate_config() -> bool:
    """Validate all configuration settings."""
    try:
        db_config.validate()

        # Create necessary directories
        os.makedirs(app_config.export_path, exist_ok=True)
        os.makedirs(app_config.backup_path, exist_ok=True)
        os.makedirs(app_config.log_path, exist_ok=True)

        return True
    except Exception as e:
        print(f"Configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    # Test configuration loading
    print("Database Configuration:")
    print(f"  Host: {db_config.host}")
    print(f"  Port: {db_config.port}")
    print(f"  Database: {db_config.database}")
    print(f"  Username: {db_config.username}")
    print(f"  Connection URL: {db_config.connection_url}")

    print("\nApplication Configuration:")
    print(f"  Name: {app_config.name}")
    print(f"  Version: {app_config.version}")
    print(f"  Debug: {app_config.debug}")
    print(f"  Theme: {app_config.theme}")

    print(f"\nConfiguration Valid: {validate_config()}")

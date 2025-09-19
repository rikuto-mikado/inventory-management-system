"""
Database connection management for the Inventory Management System.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from config.database import get_database_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        self.config = get_database_config()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @property
    def engine(self) -> Engine:
        """Get or create the database engine."""
        if self._engine is None:
            self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get or create the session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    def _create_engine(self) -> None:
        """Create the SQLAlchemy engine with connection pooling."""
        try:
            self._engine = create_engine(
                self.config.connection_url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.echo,
                pool_pre_ping=True,
                connect_args={
                    "options": f"-csearch_path={self.config.schema}",
                    "sslmode": "prefer",
                    "connect_timeout": 10,
                    "application_name": "inventory_management_system",
                },
            )

        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise

    def test_connection(self) -> bool:
        """Test the database connection."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def create_database_if_not_exists(self) -> bool:
        """Create the database if it doesn't exist."""
        try:
            admin_config = self.config
            admin_url = (
                f"postgresql://{admin_config.username}:{admin_config.password}"
                f"@{admin_config.host}:{admin_config.port}/postgres"
            )

            admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

            with admin_engine.connect() as connection:
                # Check if database exists
                result = connection.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                    {"dbname": self.config.database},
                )

                if not result.fetchone():
                    # Create database
                    connection.execute(
                        text(f'CREATE DATABASE "{self.config.database}"')
                    )
                    logger.info(
                        f"Database '{self.config.database}' created successfully"
                    )
                else:
                    logger.info(f"Database '{self.config.database}' already exists")

            admin_engine.dispose()
            return True

        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False

    def run_migrations(self) -> bool:
        """Run database migrations."""
        try:
            import os
            from pathlib import Path

            # Get the directory containing migration files
            current_dir = Path(__file__).parent
            migrations_dir = current_dir / "migrations"

            # Get all SQL migration files
            migration_files = sorted(migrations_dir.glob("*.sql"))

            if not migration_files:
                logger.warning("No migration files found")
                return True

            with self.engine.connect() as connection:
                # Create migrations tracking table if it doesn't exist
                connection.execute(
                    text(
                        """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                    )
                )
                connection.commit()

                # Get already applied migrations
                result = connection.execute(
                    text("SELECT version FROM schema_migrations")
                )
                applied_migrations = {row[0] for row in result}

                # Apply new migrations
                for migration_file in migration_files:
                    migration_name = migration_file.stem

                    if migration_name not in applied_migrations:
                        logger.info(f"Applying migration: {migration_name}")

                        # Read and execute migration
                        with open(migration_file, "r", encoding="utf-8") as f:
                            migration_sql = f.read()

                        # Execute migration in a transaction
                        trans = connection.begin()
                        try:
                            connection.execute(text(migration_sql))
                            connection.execute(
                                text(
                                    "INSERT INTO schema_migrations (version) VALUES (:version)"
                                ),
                                {"version": migration_name},
                            )
                            trans.commit()
                            logger.info(
                                f"Migration {migration_name} applied successfully"
                            )
                        except Exception as e:
                            trans.rollback()
                            logger.error(
                                f"Failed to apply migration {migration_name}: {e}"
                            )
                            raise
                    else:
                        logger.debug(f"Migration {migration_name} already applied")

            logger.info("All migrations applied successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            return False

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get a database session (manual cleanup required)."""
        return self.session_factory()

    def close(self) -> None:
        """Close all database connections."""
        if self._engine:
            self._engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Convenience function to get a database session."""
    with db_manager.get_session() as session:
        yield session


def init_database() -> bool:
    """Initialize the database (create if needed and run migrations)."""
    try:
        logger.info("Initializing database...")

        # Validate configuration
        db_manager.config.validate()

        # Create database if it doesn't exist
        if not db_manager.create_database_if_not_exists():
            return False

        # Test connection
        if not db_manager.test_connection():
            return False

        # Run migrations
        if not db_manager.run_migrations():
            return False

        logger.info("Database initialization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def check_database_health() -> dict:
    """Check database health and return status information."""
    health_info = {
        "status": "unknown",
        "connection": False,
        "tables_exist": False,
        "sample_data": False,
        "error": None,
    }

    try:
        # Test basic connection
        health_info["connection"] = db_manager.test_connection()

        if health_info["connection"]:
            with get_db_session() as session:
                # Check if core tables exist
                result = session.execute(
                    text(
                        """
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('categories', 'suppliers', 'products', 'inventory', 'transactions')
                """
                    )
                )
                table_count = result.scalar()
                health_info["tables_exist"] = table_count >= 5

                # Check if there's sample data
                if health_info["tables_exist"]:
                    result = session.execute(text("SELECT COUNT(*) FROM categories"))
                    category_count = result.scalar()
                    health_info["sample_data"] = category_count > 0

        # Determine overall status
        if health_info["connection"] and health_info["tables_exist"]:
            health_info["status"] = "healthy"
        elif health_info["connection"]:
            health_info["status"] = "needs_setup"
        else:
            health_info["status"] = "unhealthy"

    except Exception as e:
        health_info["error"] = str(e)
        health_info["status"] = "error"

    return health_info


if __name__ == "__main__":
    # Test database functionality
    import sys

    print("Testing database connection...")

    # Initialize database
    if init_database():
        print("✓ Database initialization successful")

        # Check health
        health = check_database_health()
        print(f"✓ Database health: {health}")

        # Test session
        try:
            with get_db_session() as session:
                result = session.execute(text("SELECT current_timestamp"))
                timestamp = result.scalar()
                print(f"✓ Current database time: {timestamp}")
        except Exception as e:
            print(f"✗ Session test failed: {e}")

    else:
        print("✗ Database initialization failed")
        sys.exit(1)

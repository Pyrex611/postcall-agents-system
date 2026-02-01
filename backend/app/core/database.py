"""
Database configuration and utilities.
"""
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    async_sessionmaker, 
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy base class
Base = declarative_base()

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url_async,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before using
    connect_args={
        "server_settings": {
            "jit": "off",  # Disable JIT for better performance
            "statement_timeout": "30000"  # 30 second timeout
        }
    }
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    Yields an async session and ensures it's closed after use.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            await session.close()

async def init_db() -> None:
    """
    Initialize database by creating all tables.
    Should be called on application startup.
    """
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

async def close_db() -> None:
    """
    Close database connections.
    Should be called on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")

async def health_check() -> Dict[str, Any]:
    """
    Perform database health check.
    Returns status and metrics.
    """
    try:
        async with async_session_factory() as session:
            # Test connection and get database info
            start_time = datetime.now()
            result = await session.execute(text("SELECT version(), current_timestamp"))
            end_time = datetime.now()
            
            row = result.fetchone()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            # Get connection pool info
            pool = engine.pool
            pool_status = {
                "checkedin": pool.checkedin(),
                "checkedout": pool.checkedout(),
                "size": pool.size(),
                "max_overflow": pool.max_overflow(),
                "timeout": pool.timeout(),
            }
            
            return {
                "status": "healthy",
                "database_version": row[0] if row else None,
                "database_time": str(row[1]) if row and len(row) > 1 else None,
                "response_time_ms": round(response_time, 2),
                "pool_status": pool_status,
                "url": str(engine.url).split('@')[1] if '@' in str(engine.url) else str(engine.url)
            }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None,
            "database_version": None,
            "database_time": None
        }

async def execute_raw_sql(query: str, params: Optional[Dict] = None) -> List[Dict]:
    """
    Execute raw SQL query and return results as dictionaries.
    Use with caution - prefer ORM when possible.
    """
    async with async_session_factory() as session:
        result = await session.execute(text(query), params or {})
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]

class DatabaseManager:
    """Database manager for advanced operations."""
    
    @staticmethod
    async def get_table_stats(table_name: str) -> Dict[str, Any]:
        """Get statistics for a specific table."""
        query = text("""
            SELECT 
                schemaname,
                tablename,
                tableowner,
                tablespace,
                hasindexes,
                hasrules,
                hastriggers,
                rowsecurity
            FROM pg_tables 
            WHERE tablename = :table_name
        """)
        
        async with async_session_factory() as session:
            result = await session.execute(query, {"table_name": table_name})
            stats = result.fetchone()
            
            if stats:
                return dict(stats._mapping)
            return {}
    
    @staticmethod
    async def vacuum_table(table_name: str) -> Dict[str, Any]:
        """Run VACUUM on a table (for maintenance)."""
        query = text(f"VACUUM ANALYZE {table_name}")
        
        try:
            async with async_session_factory() as session:
                await session.execute(query)
                await session.commit()
                
                return {
                    "status": "success",
                    "message": f"VACUUM completed on table {table_name}",
                    "table": table_name
                }
        except Exception as e:
            logger.error(f"VACUUM failed for table {table_name}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "table": table_name
            }
    
    @staticmethod
    async def get_database_size() -> Dict[str, Any]:
        """Get database size information."""
        queries = {
            "total_size": "SELECT pg_database_size(current_database()) as size_bytes",
            "table_sizes": """
                SELECT 
                    schemaname,
                    tablename,
                    pg_relation_size(schemaname || '.' || tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY size_bytes DESC
            """
        }
        
        async with async_session_factory() as session:
            results = {}
            
            # Get total size
            result = await session.execute(text(queries["total_size"]))
            total_row = result.fetchone()
            results["total_size_bytes"] = total_row[0] if total_row else 0
            
            # Get table sizes
            result = await session.execute(text(queries["table_sizes"]))
            tables = result.fetchall()
            
            results["tables"] = [
                {
                    "schema": row[0],
                    "table": row[1],
                    "size_bytes": row[2]
                }
                for row in tables
            ]
            
            # Calculate human-readable sizes
            def format_size(bytes_size):
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if bytes_size < 1024.0:
                        return f"{bytes_size:.2f} {unit}"
                    bytes_size /= 1024.0
                return f"{bytes_size:.2f} PB"
            
            results["total_size_human"] = format_size(results["total_size_bytes"])
            
            return results
    
    @staticmethod
    async def backup_database() -> Dict[str, Any]:
        """
        Create database backup.
        Note: This requires pg_dump and appropriate permissions.
        """
        import subprocess
        import tempfile
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = tempfile.NamedTemporaryFile(
            suffix=f"_salesintel_backup_{timestamp}.sql",
            delete=False
        )
        
        try:
            # Extract database connection info
            db_url = settings.database_url_sync
            # Parse URL to get connection parameters
            
            # This is a simplified example - in production, use proper pg_dump with connection string
            cmd = [
                "pg_dump",
                "--dbname", db_url,
                "--file", backup_file.name,
                "--verbose",
                "--format", "custom"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "backup_file": backup_file.name,
                    "size_bytes": os.path.getsize(backup_file.name),
                    "timestamp": timestamp
                }
            else:
                return {
                    "status": "failed",
                    "error": result.stderr,
                    "backup_file": None
                }
                
        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "backup_file": None
            }
        finally:
            # Clean up backup file (in production, you'd want to keep it)
            try:
                os.unlink(backup_file.name)
            except:
                pass

# Create sync engine for migrations and admin tasks
from sqlalchemy import create_engine as create_sync_engine

sync_engine = create_sync_engine(
    settings.database_url_sync,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)
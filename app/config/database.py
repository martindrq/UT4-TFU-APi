"""
Configuración de la base de datos PostgreSQL con SQLAlchemy.
Implementa patrón Singleton para la conexión y gestión de sesiones.
Incluye mecanismo de retry con backoff exponencial para alta disponibilidad.
"""

import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, DBAPIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

# Importar configuración centralizada (External Configuration Store Pattern)
from .config import settings

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL de conexión a PostgreSQL desde configuración externa
DATABASE_URL = settings.DATABASE_URL

# Configuración de reintentos desde configuración externa
MAX_RETRY_ATTEMPTS = settings.DB_MAX_RETRY_ATTEMPTS
RETRY_MIN_WAIT = settings.DB_RETRY_MIN_WAIT
RETRY_MAX_WAIT = settings.DB_RETRY_MAX_WAIT

# Crear el motor de base de datos con configuración para ACID
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Verificar conexión antes de usar
    pool_recycle=300,        # Reciclar conexiones cada 5 minutos
    pool_size=10,            # Tamaño del pool de conexiones
    max_overflow=20,         # Conexiones adicionales permitidas
    pool_timeout=30,         # Timeout para obtener conexión del pool
    echo=False,              # No mostrar SQL queries en producción
    connect_args={
        "connect_timeout": 10,  # Timeout de conexión inicial
        "options": "-c statement_timeout=30000"  # Timeout de queries (30s)
    }
)

# Factory de sesiones para transacciones ACID
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos ORM
Base = declarative_base()

@retry(
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type((OperationalError, DBAPIError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
def test_connection():
    """
    Verifica la conexión a la base de datos con reintentos automáticos.
    
    Implementa backoff exponencial:
    - Intento 1: inmediato
    - Intento 2: espera 1s
    - Intento 3: espera 2s
    - Intento 4: espera 4s
    - Intento 5: espera 8s (máximo 10s)
    
    Raises:
        OperationalError: Si no se puede conectar después de todos los reintentos
    """
    logger.info("🔄 Intentando conectar a la base de datos...")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            logger.info("✅ Conexión a la base de datos establecida exitosamente")
            return True
    except (OperationalError, DBAPIError) as e:
        logger.error(f"❌ Error al conectar a la base de datos: {str(e)}")
        raise

@retry(
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type((OperationalError, DBAPIError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
def create_tables():
    """
    Crear todas las tablas definidas en los modelos con reintentos automáticos.
    Se ejecuta al inicio de la aplicación.
    
    Implementa el mismo mecanismo de retry que test_connection.
    """
    logger.info("📋 Creando/verificando tablas en la base de datos...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas creadas/verificadas correctamente")
    except (OperationalError, DBAPIError) as e:
        logger.error(f"❌ Error al crear tablas: {str(e)}")
        raise

def get_db():
    """
    Generador de sesiones de base de datos.
    Asegura que las transacciones se cierren correctamente (ACID).
    
    En caso de error de conexión durante una transacción,
    pool_pre_ping=True intentará reconectar automáticamente.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health():
    """
    Verifica el estado de salud de la conexión a la base de datos.
    Útil para health checks y monitoreo.
    
    Returns:
        dict: Estado de la conexión con detalles
    """
    try:
        with engine.connect() as connection:
            start_time = time.time()
            connection.execute(text("SELECT 1"))
            response_time = (time.time() - start_time) * 1000  # ms
            
            # Obtener información del pool
            pool = engine.pool
            
            return {
                "status": "healthy",
                "database": "connected",
                "response_time_ms": round(response_time, 2),
                "pool_size": pool.size(),
                "pool_checked_in": pool.checkedin(),
                "pool_checked_out": pool.checkedout(),
                "pool_overflow": pool.overflow()
            }
    except Exception as e:
        logger.error(f"❌ Health check falló: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


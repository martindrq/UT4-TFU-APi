"""
Módulo de Configuración - External Configuration Store Pattern
Centraliza la gestión de variables de configuración externas.
Permite modificar parámetros sin recompilar ni redeployar la aplicación.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env si existe
load_dotenv()


class Settings:
    """
    Clase de configuración que centraliza todas las variables de entorno.
    Implementa el patrón External Configuration Store para separar
    la configuración del código fuente.
    """
    
    # =========================================
    # INFORMACIÓN DE LA APLICACIÓN
    # =========================================
    APP_NAME: str = "Mini Gestor de Proyectos API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # =========================================
    # CONFIGURACIÓN DEL SERVIDOR
    # =========================================
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_RELOAD: bool = os.getenv("API_RELOAD", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    
    # =========================================
    # BASE DE DATOS POSTGRESQL
    # =========================================
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "password")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "gestor_proyectos")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5433")
    
    # URL completa de conexión
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    # Configuración de reintentos (Retry Pattern)
    DB_MAX_RETRY_ATTEMPTS: int = int(os.getenv("DB_MAX_RETRY_ATTEMPTS", "5"))
    DB_RETRY_MIN_WAIT: int = int(os.getenv("DB_RETRY_MIN_WAIT", "1"))
    DB_RETRY_MAX_WAIT: int = int(os.getenv("DB_RETRY_MAX_WAIT", "10"))
    
    # =========================================
    # REDIS - CACHE-ASIDE PATTERN
    # =========================================
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutos por defecto
    
    # =========================================
    # LDAP - FEDERATED IDENTITY PATTERN
    # =========================================
    LDAP_SERVER: str = os.getenv("LDAP_SERVER", "ldap://localhost:389")
    LDAP_BASE_DN: str = os.getenv("LDAP_BASE_DN", "dc=example,dc=org")
    LDAP_USER_DN_TEMPLATE: str = os.getenv(
        "LDAP_USER_DN_TEMPLATE",
        "uid={username},ou=users,dc=example,dc=org"
    )
    LDAP_BIND_USER: Optional[str] = os.getenv("LDAP_BIND_USER", None)
    LDAP_BIND_PASSWORD: Optional[str] = os.getenv("LDAP_BIND_PASSWORD", None)
    
    # =========================================
    # JWT Y SEGURIDAD - GATEKEEPER PATTERN
    # =========================================
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # =========================================
    # GATEKEEPER - RATE LIMITING
    # =========================================
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    
    # =========================================
    # CORS
    # =========================================
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    
    @classmethod
    def is_development(cls) -> bool:
        """Verifica si estamos en entorno de desarrollo"""
        return cls.ENVIRONMENT.lower() in ["development", "dev"]
    
    @classmethod
    def is_production(cls) -> bool:
        """Verifica si estamos en entorno de producción"""
        return cls.ENVIRONMENT.lower() in ["production", "prod"]
    
    @classmethod
    def validate_config(cls) -> list[str]:
        """
        Valida la configuración y retorna una lista de advertencias.
        Útil para verificar la configuración al inicio de la aplicación.
        """
        warnings = []
        
        # Verificar secreto JWT en producción
        if cls.is_production() and cls.JWT_SECRET_KEY == "your-secret-key-change-in-production":
            warnings.append(
                "⚠️  CRÍTICO: JWT_SECRET_KEY está usando el valor por defecto en producción!"
            )
        
        # Verificar contraseña de base de datos
        if cls.is_production() and cls.POSTGRES_PASSWORD == "password":
            warnings.append(
                "⚠️  ADVERTENCIA: Contraseña de base de datos débil en producción"
            )
        
        # Verificar reload en producción
        if cls.is_production() and cls.API_RELOAD:
            warnings.append(
                "⚠️  ADVERTENCIA: API_RELOAD está activado en producción"
            )
        
        return warnings
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """
        Retorna un resumen de la configuración actual (sin datos sensibles).
        Útil para logging y debugging.
        """
        return {
            "app_name": cls.APP_NAME,
            "version": cls.APP_VERSION,
            "environment": cls.ENVIRONMENT,
            "api_host": cls.API_HOST,
            "api_port": cls.API_PORT,
            "database_host": cls.POSTGRES_HOST,
            "database_name": cls.POSTGRES_DB,
            "redis_host": cls.REDIS_HOST,
            "redis_port": cls.REDIS_PORT,
            "cache_ttl": cls.CACHE_TTL,
            "ldap_server": cls.LDAP_SERVER,
            "token_expire_minutes": cls.ACCESS_TOKEN_EXPIRE_MINUTES,
            "reload_enabled": cls.API_RELOAD,
            "log_level": cls.LOG_LEVEL
        }


# Instancia global de configuración
settings = Settings()


# Validar configuración al cargar el módulo
def check_configuration():
    """
    Verifica la configuración al iniciar la aplicación.
    Muestra advertencias si hay problemas de configuración.
    """
    warnings = settings.validate_config()
    
    if warnings:
        print("\n" + "="*60)
        print("⚠️  ADVERTENCIAS DE CONFIGURACIÓN")
        print("="*60)
        for warning in warnings:
            print(warning)
        print("="*60 + "\n")
    
    # Mostrar resumen de configuración en desarrollo
    if settings.is_development():
        print("\n" + "="*60)
        print("📋 CONFIGURACIÓN ACTUAL (External Configuration Store)")
        print("="*60)
        summary = settings.get_config_summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print("="*60 + "\n")


# Ejecutar verificación al importar el módulo
check_configuration()


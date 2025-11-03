#!/usr/bin/env python3
"""
Script de Verificación de Configuración - External Configuration Store Pattern
Verifica que todas las variables de configuración estén correctamente definidas.
"""

import sys
import os

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings


def print_header(title: str):
    """Imprime un encabezado decorado"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_success(message: str):
    """Imprime mensaje de éxito"""
    print(f"✅ {message}")


def print_warning(message: str):
    """Imprime mensaje de advertencia"""
    print(f"⚠️  {message}")


def print_error(message: str):
    """Imprime mensaje de error"""
    print(f"❌ {message}")


def print_info(key: str, value: str, is_secret: bool = False):
    """Imprime información de configuración"""
    if is_secret:
        # Ocultar valor secreto, mostrar solo longitud
        if value and len(value) > 0:
            display_value = f"{'*' * min(len(value), 20)} (longitud: {len(value)})"
        else:
            display_value = "⚠️  NO DEFINIDO"
    else:
        display_value = value
    
    print(f"  {key:30} : {display_value}")


def verify_environment_file():
    """Verifica que exista el archivo .env"""
    print_header("VERIFICACIÓN DE ARCHIVO .env")
    
    env_file = ".env"
    if os.path.exists(env_file):
        print_success(f"Archivo {env_file} encontrado")
        return True
    else:
        print_error(f"Archivo {env_file} NO encontrado")
        print_info("Solución", "Crear archivo .env basado en .env.example")
        print_info("Comando", "cp .env.example .env")
        return False


def verify_database_config():
    """Verifica configuración de base de datos"""
    print_header("CONFIGURACIÓN DE BASE DE DATOS")
    
    issues = []
    
    print_info("POSTGRES_USER", settings.POSTGRES_USER)
    print_info("POSTGRES_PASSWORD", settings.POSTGRES_PASSWORD, is_secret=True)
    print_info("POSTGRES_DB", settings.POSTGRES_DB)
    print_info("DATABASE_URL", settings.DATABASE_URL)
    
    # Verificar configuración de reintentos
    print_info("DB_MAX_RETRY_ATTEMPTS", str(settings.DB_MAX_RETRY_ATTEMPTS))
    print_info("DB_RETRY_MIN_WAIT", f"{settings.DB_RETRY_MIN_WAIT}s")
    print_info("DB_RETRY_MAX_WAIT", f"{settings.DB_RETRY_MAX_WAIT}s")
    
    # Validaciones
    if settings.is_production() and settings.POSTGRES_PASSWORD == "password":
        issues.append("Contraseña de base de datos débil en producción")
    
    return issues


def verify_redis_config():
    """Verifica configuración de Redis"""
    print_header("CONFIGURACIÓN DE REDIS (Cache-Aside)")
    
    print_info("REDIS_HOST", settings.REDIS_HOST)
    print_info("REDIS_PORT", str(settings.REDIS_PORT))
    print_info("CACHE_TTL", f"{settings.CACHE_TTL}s")
    
    return []


def verify_ldap_config():
    """Verifica configuración de LDAP"""
    print_header("CONFIGURACIÓN DE LDAP (Federated Identity)")
    
    print_info("LDAP_SERVER", settings.LDAP_SERVER)
    print_info("LDAP_BASE_DN", settings.LDAP_BASE_DN)
    print_info("LDAP_USER_DN_TEMPLATE", settings.LDAP_USER_DN_TEMPLATE)
    
    if settings.LDAP_BIND_USER:
        print_info("LDAP_BIND_USER", settings.LDAP_BIND_USER)
        print_info("LDAP_BIND_PASSWORD", settings.LDAP_BIND_PASSWORD or "", is_secret=True)
    else:
        print_info("LDAP_BIND_USER", "No configurado (modo bind directo)")
    
    return []


def verify_jwt_config():
    """Verifica configuración de JWT"""
    print_header("CONFIGURACIÓN DE JWT (Gatekeeper)")
    
    issues = []
    
    print_info("JWT_SECRET_KEY", settings.JWT_SECRET_KEY, is_secret=True)
    print_info("JWT_ALGORITHM", settings.JWT_ALGORITHM)
    print_info("ACCESS_TOKEN_EXPIRE_MINUTES", f"{settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutos")
    
    # Validaciones críticas
    if settings.JWT_SECRET_KEY == "your-secret-key-change-in-production":
        if settings.is_production():
            issues.append("CRÍTICO: JWT_SECRET_KEY usando valor por defecto en producción!")
        else:
            print_warning("JWT_SECRET_KEY usando valor por defecto (OK para desarrollo)")
    
    if len(settings.JWT_SECRET_KEY) < 32:
        issues.append("JWT_SECRET_KEY muy corta (mínimo recomendado: 32 caracteres)")
    
    return issues


def verify_app_config():
    """Verifica configuración de la aplicación"""
    print_header("CONFIGURACIÓN DE APLICACIÓN")
    
    issues = []
    
    print_info("APP_NAME", settings.APP_NAME)
    print_info("APP_VERSION", settings.APP_VERSION)
    print_info("ENVIRONMENT", settings.ENVIRONMENT)
    print_info("API_HOST", settings.API_HOST)
    print_info("API_PORT", str(settings.API_PORT))
    print_info("API_RELOAD", str(settings.API_RELOAD))
    print_info("LOG_LEVEL", settings.LOG_LEVEL)
    
    # Validaciones
    if settings.is_production() and settings.API_RELOAD:
        issues.append("API_RELOAD activado en producción (desactivar para mejor rendimiento)")
    
    if settings.is_production() and settings.LOG_LEVEL in ["debug", "DEBUG"]:
        issues.append("LOG_LEVEL en debug en producción (cambiar a warning o error)")
    
    return issues


def verify_security_config():
    """Verifica configuración de seguridad"""
    print_header("CONFIGURACIÓN DE SEGURIDAD")
    
    issues = []
    
    print_info("CORS_ORIGINS", str(settings.CORS_ORIGINS))
    print_info("RATE_LIMIT_REQUESTS", str(settings.RATE_LIMIT_REQUESTS))
    print_info("RATE_LIMIT_WINDOW_SECONDS", f"{settings.RATE_LIMIT_WINDOW_SECONDS}s")
    
    # Validaciones
    if settings.is_production() and "*" in settings.CORS_ORIGINS:
        issues.append("CORS_ORIGINS permite todos los orígenes en producción (riesgo de seguridad)")
    
    return issues


def verify_all():
    """Ejecuta todas las verificaciones"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "VERIFICACIÓN DE CONFIGURACIÓN EXTERNA" + " " * 20 + "║")
    print("║" + " " * 10 + "External Configuration Store Pattern" + " " * 21 + "║")
    print("╚" + "═" * 68 + "╝")
    
    all_issues = []
    
    # Verificar archivo .env
    env_exists = verify_environment_file()
    
    if not env_exists:
        print_header("RESUMEN")
        print_error("No se puede continuar sin archivo .env")
        print_info("Acción requerida", "Crear archivo .env basado en .env.example")
        return False
    
    # Verificar cada sección
    all_issues.extend(verify_database_config())
    all_issues.extend(verify_redis_config())
    all_issues.extend(verify_ldap_config())
    all_issues.extend(verify_jwt_config())
    all_issues.extend(verify_app_config())
    all_issues.extend(verify_security_config())
    
    # Agregar validaciones del módulo settings
    all_issues.extend(settings.validate_config())
    
    # Resumen
    print_header("RESUMEN DE VERIFICACIÓN")
    
    if not all_issues:
        print_success("Todas las verificaciones pasaron correctamente")
        print_info("Estado", "Configuración lista para usar ✓")
        return True
    else:
        print_warning(f"Se encontraron {len(all_issues)} problemas:")
        print()
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
        print()
        
        # Determinar severidad
        critical_keywords = ["CRÍTICO", "crítico", "CRITICAL"]
        has_critical = any(keyword in issue for issue in all_issues for keyword in critical_keywords)
        
        if has_critical:
            print_error("Hay problemas CRÍTICOS que deben resolverse antes de producción")
            return False
        else:
            print_warning("Hay advertencias que deberían revisarse")
            return True


def main():
    """Función principal"""
    try:
        success = verify_all()
        
        print_header("AYUDA")
        print("  📚 Ver plantillas de configuración: ENV_TEMPLATE.md")
        print("  📖 Documentación completa: EXTERNAL_CONFIGURATION_STORE.md")
        print("  🔧 Generar JWT secret: openssl rand -hex 32")
        print()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print_header("ERROR")
        print_error(f"Error durante verificación: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()


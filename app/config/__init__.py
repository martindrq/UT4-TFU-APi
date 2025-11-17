"""
Módulo de Configuración

Contiene:
- Configuración centralizada (External Configuration Store Pattern)
- Configuración de base de datos con retry pattern
- Middleware de confianza con Gateway
- Sistema de permisos y roles
"""

from .config import settings
from .database import (
    engine,
    SessionLocal,
    get_db,
    create_tables,
    test_connection,
    check_db_health,
    Base
)
from .gateway_trust import (
    gateway_trust_middleware,
    get_current_user_from_gateway,
    GatewayTrustMiddleware
)
from .permissions import PermissionChecker

__all__ = [
    # Configuración
    "settings",
    # Base de datos
    "engine",
    "SessionLocal",
    "get_db",
    "create_tables",
    "test_connection",
    "check_db_health",
    "Base",
    # Gateway trust
    "gateway_trust_middleware",
    "get_current_user_from_gateway",
    "GatewayTrustMiddleware",
    # Permisos
    "PermissionChecker"
]

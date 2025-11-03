"""
Middleware Gatekeeper - Patrón Gatekeeper (API Gateway)
Centraliza el control de acceso a recursos internos de la aplicación.
Todas las solicitudes externas pasan por este punto de validación antes de llegar a los servicios internos.
Valida tokens, verifica permisos, filtra solicitudes maliciosas y reduce la superficie de ataque.
"""

from typing import Optional, List, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from functools import wraps
import re
import time

# Importar configuración centralizada (External Configuration Store Pattern)
from app.config import settings
from app.services.auth_service import token_service


# Configuración del bearer token
security = HTTPBearer()


class GatekeeperMiddleware:
    """
    Middleware de seguridad que implementa el patrón Gatekeeper.
    Actúa como punto de entrada único para validar y filtrar todas las solicitudes.
    """
    
    # Patrones sospechosos para detectar intentos de ataque
    SUSPICIOUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # XSS
        r"javascript:",                  # XSS
        r"on\w+\s*=",                   # Event handlers (XSS)
        r"(union|select|insert|update|delete|drop|create|alter)\s+",  # SQL Injection
        r"\.\./",                        # Path traversal
        r"\\x[0-9a-fA-F]{2}",           # Hex encoding
        r"%[0-9a-fA-F]{2}",             # URL encoding sospechoso en exceso
    ]
    
    # Endpoints públicos que no requieren autenticación
    PUBLIC_ENDPOINTS = [
        "/",
        "/health",
        "/stats",
        "/cache/stats",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/auth/login",
        "/api/v1/auth/status",
        "/demo"
    ]
    
    # Límites de rate limiting por endpoint (requests por minuto)
    RATE_LIMITS = {}
    
    def __init__(self):
        self.request_logs = {}  # Para rate limiting simple
        
    async def __call__(self, request: Request, call_next):
        """
        Procesa cada request antes de que llegue a los endpoints.
        Implementa las validaciones de seguridad del Gatekeeper.
        """
        start_time = time.time()
        
        # Debug: Log para requests a endpoints protegidos
        if not self._is_public_endpoint(request.url.path):
            print(f"🔐 Gatekeeper procesando: {request.method} {request.url.path}")
            auth_headers = {k: v for k, v in request.headers.items() if 'auth' in k.lower() or 'token' in k.lower()}
            if auth_headers:
                print(f"   Headers de auth encontrados: {list(auth_headers.keys())}")
        
        # 1. Verificar si es un endpoint público
        if self._is_public_endpoint(request.url.path):
            response = await call_next(request)
            return response
        
        # 2. Filtrar solicitudes maliciosas (IDS/IPS básico)
        if self._is_suspicious_request(request):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Solicitud rechazada: contenido sospechoso detectado"}
            )
        
        # 3. Rate Limiting básico
        if not self._check_rate_limit(request):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Demasiadas solicitudes. Por favor intente más tarde."}
            )
        
        # 4. Validar token JWT
        token = self._extract_token(request)
        if not token:
            # Log detallado para debugging
            print(f"🚫 Token no encontrado para {request.method} {request.url.path}")
            print(f"   Headers disponibles: {[h for h in request.headers.keys() if h.lower() in ['authorization', 'authorization-token', 'x-auth-token']]}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "No se proporcionó token de autenticación"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 5. Decodificar y validar token
        payload = token_service.decode_token(token)
        if not payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token inválido o expirado"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 6. Agregar información del usuario al request state
        request.state.user = payload
        
        # 7. Procesar request
        response = await call_next(request)
        
        # 8. Agregar headers de seguridad a la respuesta
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # 9. Logging de tiempo de procesamiento
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Verifica si el endpoint es público"""
        # Verificar coincidencias exactas primero
        if path in self.PUBLIC_ENDPOINTS:
            return True
        
        # Verificar paths con trailing slash
        if path.rstrip('/') in self.PUBLIC_ENDPOINTS:
            return True
        
        # Verificar prefijos específicos (solo para docs y openapi)
        for endpoint in self.PUBLIC_ENDPOINTS:
            if endpoint in ["/docs", "/openapi.json", "/redoc"]:
                if path.startswith(endpoint):
                    return True
        
        return False
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extrae el token JWT del header Authorization o alternativas"""
        # Método 1: Intentar obtener el header Authorization (case-insensitive)
        auth_header = None
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "authorization":
                auth_header = header_value
                break
        
        if auth_header:
            # Normalizar el header (eliminar espacios extra y hacer case-insensitive)
            auth_header = auth_header.strip()
            
            # Verificar que comience con "Bearer" (case-insensitive)
            if auth_header.lower().startswith("bearer "):
                # Extraer el token (después de "Bearer ")
                token = auth_header[7:].strip()  # "Bearer " tiene 7 caracteres
                if token:
                    return token
            elif auth_header.lower().startswith("bearer"):
                # Sin espacio después de Bearer (formato no estándar pero común)
                token = auth_header[6:].strip()
                if token:
                    return token
            else:
                # Asumir que todo el header es el token (fallback)
                if auth_header and len(auth_header) > 10:  # Los JWT típicamente son largos
                    return auth_header
        
        # Método 2: Intentar desde query parameter (fallback para debugging)
        token = request.query_params.get("token")
        if token:
            return token
        
        # Método 3: Intentar desde header personalizado (fallback)
        for header_name in ["X-Auth-Token", "X-Access-Token", "Authorization-Token"]:
            token = request.headers.get(header_name)
            if token:
                return token.strip()
        
        # Log para debugging si no se encontró token
        print(f"⚠️  No se encontró token. Headers recibidos: {list(request.headers.keys())}")
        return None
    
    def _is_suspicious_request(self, request: Request) -> bool:
        """
        Detecta patrones sospechosos en la solicitud.
        Implementa un IDS/IPS básico.
        """
        # Verificar URL
        url_str = str(request.url)
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, url_str, re.IGNORECASE):
                print(f"🚨 Patrón sospechoso detectado en URL: {pattern}")
                return True
        
        # Verificar query parameters
        for key, value in request.query_params.items():
            for pattern in self.SUSPICIOUS_PATTERNS:
                if re.search(pattern, f"{key}={value}", re.IGNORECASE):
                    print(f"🚨 Patrón sospechoso detectado en query param: {key}")
                    return True
        
        # Verificar headers sospechosos
        suspicious_headers = ['X-Forwarded-For', 'X-Real-IP']
        for header in suspicious_headers:
            value = request.headers.get(header, "")
            if ".." in value or ";" in value:
                print(f"🚨 Header sospechoso: {header}")
                return True
        
        return False
    
    def _check_rate_limit(self, request: Request) -> bool:
        """
        Implementa rate limiting básico por IP.
        Retorna True si está dentro del límite, False si excede.
        """
        # Obtener IP del cliente
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Inicializar si no existe
        if client_ip not in self.request_logs:
            self.request_logs[client_ip] = []
        
        # Limpiar requests antiguos (configurado externamente)
        window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        self.request_logs[client_ip] = [
            timestamp for timestamp in self.request_logs[client_ip]
            if current_time - timestamp < window_seconds
        ]
        
        # Verificar límite (configurado externamente)
        max_requests = settings.RATE_LIMIT_REQUESTS
        if len(self.request_logs[client_ip]) >= max_requests:
            print(f"🚨 Rate limit excedido para IP: {client_ip}")
            return False
        
        # Agregar request actual
        self.request_logs[client_ip].append(current_time)
        return True


class PermissionChecker:
    """
    Verificador de permisos basado en roles.
    Parte del sistema Gatekeeper para control de acceso granular.
    """
    
    # Definición de permisos por rol
    ROLE_PERMISSIONS = {
        "admin": ["*"],  # Acceso total
        "manager": [
            "usuarios:read",
            "usuarios:create",
            "proyectos:*",
            "tareas:*"
        ],
        "desarrollador": [
            "usuarios:read",
            "proyectos:read",
            "tareas:read",
            "tareas:update"
        ]
    }
    
    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        """
        Verifica si un rol tiene un permiso específico.
        
        Args:
            role: Rol del usuario (admin, manager, desarrollador)
            permission: Permiso a verificar (e.g., "usuarios:create")
            
        Returns:
            True si tiene permiso, False en caso contrario
        """
        if role not in cls.ROLE_PERMISSIONS:
            return False
        
        role_perms = cls.ROLE_PERMISSIONS[role]
        
        # Verificar wildcard total
        if "*" in role_perms:
            return True
        
        # Verificar permiso específico
        if permission in role_perms:
            return True
        
        # Verificar wildcard de recurso (e.g., "proyectos:*")
        resource = permission.split(":")[0]
        if f"{resource}:*" in role_perms:
            return True
        
        return False


# Instancia global del middleware
gatekeeper_middleware_instance = GatekeeperMiddleware()

# Función middleware compatible con FastAPI/Starlette
async def gatekeeper_middleware(request: Request, call_next):
    """
    Función middleware que delega a la instancia de GatekeeperMiddleware.
    Compatible con FastAPI/Starlette BaseHTTPMiddleware.
    """
    return await gatekeeper_middleware_instance(request, call_next)


# Dependency para obtener el usuario actual desde el token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency que valida el token y retorna la información del usuario.
    Usado en endpoints protegidos para obtener el usuario autenticado.
    """
    token = credentials.credentials
    
    payload = token_service.decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


# Dependency para verificar permisos específicos
def require_permission(permission: str) -> Callable:
    """
    Factory de dependency para requerir un permiso específico.
    
    Usage:
        @app.get("/endpoint", dependencies=[Depends(require_permission("usuarios:create"))])
    """
    async def permission_checker(current_user: dict = Depends(get_current_user)):
        role = current_user.get("rol", "desarrollador")
        
        if not PermissionChecker.has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado. Requiere: {permission}"
            )
        
        return current_user
    
    return permission_checker


# Dependency para requerir rol específico
def require_role(allowed_roles: List[str]) -> Callable:
    """
    Factory de dependency para requerir uno o más roles específicos.
    
    Usage:
        @app.get("/endpoint", dependencies=[Depends(require_role(["admin", "manager"]))])
    """
    async def role_checker(current_user: dict = Depends(get_current_user)):
        role = current_user.get("rol", "desarrollador")
        
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Roles permitidos: {', '.join(allowed_roles)}"
            )
        
        return current_user
    
    return role_checker


# Decorator para proteger funciones
def protected(permission: Optional[str] = None, roles: Optional[List[str]] = None):
    """
    Decorator para proteger funciones con verificación de permisos.
    
    Usage:
        @protected(permission="usuarios:create")
        async def crear_usuario(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Obtener usuario del request (debe estar inyectado)
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario no autenticado"
                )
            
            role = current_user.get("rol", "desarrollador")
            
            # Verificar permiso si se especificó
            if permission and not PermissionChecker.has_permission(role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permiso denegado. Requiere: {permission}"
                )
            
            # Verificar rol si se especificó
            if roles and role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado. Roles permitidos: {', '.join(roles)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


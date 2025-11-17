"""
Servicio de Autenticación - Microservicio Independiente
Servicio dedicado para autenticación con LDAP (Federated Identity) y generación de tokens JWT.
Implementa patrón Gatekeeper como servicio desacoplado.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import os
import logging

# LDAP y JWT
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPException, LDAPBindError
from jose import JWTError, jwt
from passlib.context import CryptContext

# Pydantic
from pydantic import BaseModel, Field, EmailStr

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Variables de entorno
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://ldap:389")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=example,dc=org")
LDAP_USER_DN_TEMPLATE = os.getenv("LDAP_USER_DN_TEMPLATE", "uid={username},ou=users,dc=example,dc=org")
LDAP_BIND_USER = os.getenv("LDAP_BIND_USER", "")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")

# JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Context para hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================================================
# SCHEMAS Pydantic
# ============================================================================

class LoginRequest(BaseModel):
    """Schema para solicitud de login"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1)

class TokenResponse(BaseModel):
    """Schema de respuesta después de login exitoso"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class UserInfo(BaseModel):
    """Schema para información del usuario"""
    username: str
    email: str
    nombre: str
    rol: str
    ldap_dn: Optional[str] = None

class ErrorResponse(BaseModel):
    """Schema para respuestas de error"""
    detail: str

# ============================================================================
# SERVICIO LDAP - Federated Identity
# ============================================================================

class LDAPAuthService:
    """
    Servicio de autenticación LDAP implementando Federated Identity.
    Delega la autenticación a LDAP y genera tokens JWT internos.
    """
    
    def __init__(self):
        self.server = Server(LDAP_SERVER, get_info=ALL)
        self.base_dn = LDAP_BASE_DN
        self.user_dn_template = LDAP_USER_DN_TEMPLATE
        
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Autentica un usuario contra el servidor LDAP.
        Implementa el patrón Federated Identity delegando la autenticación.
        """
        try:
            # Construir DN del usuario
            user_dn = self.user_dn_template.format(username=username)
            
            # Intentar bind con las credenciales del usuario
            conn = Connection(
                self.server,
                user=user_dn,
                password=password,
                auto_bind=True
            )
            
            # Si llegamos aquí, la autenticación fue exitosa
            logger.info(f"✅ Autenticación exitosa para usuario: {username}")
            
            # Buscar información adicional del usuario
            user_info = self._get_user_info(conn, username, user_dn)
            
            conn.unbind()
            return user_info
            
        except LDAPBindError as e:
            logger.error(f"❌ Error de autenticación LDAP para {username}: {str(e)}")
            return None
        except LDAPException as e:
            logger.error(f"❌ Error LDAP: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado durante autenticación: {str(e)}")
            return None
    
    def _get_user_info(self, conn: Connection, username: str, user_dn: str) -> Dict[str, Any]:
        """
        Obtiene información adicional del usuario desde LDAP.
        """
        try:
            # Buscar usuario en LDAP usando su DN directamente
            conn.search(
                search_base=user_dn,
                search_filter='(objectClass=*)',
                search_scope='BASE',
                attributes=['cn', 'mail', 'uid', 'ou', 'employeeType']
            )
            
            if conn.entries:
                entry = conn.entries[0]
                
                # Determinar rol basado en atributos LDAP
                role = "desarrollador"
                if hasattr(entry, 'employeeType') and entry.employeeType:
                    employee_type_raw = entry.employeeType.value if hasattr(entry.employeeType, 'value') else entry.employeeType
                    
                    if isinstance(employee_type_raw, list):
                        employee_type_raw = employee_type_raw[0] if employee_type_raw else ""
                    
                    employee_type = str(employee_type_raw).lower().strip()
                    
                    # Mapear employeeType a roles
                    if "admin" in employee_type:
                        role = "admin"
                    elif "manager" in employee_type:
                        role = "manager"
                    elif "developer" in employee_type or "desarrollador" in employee_type:
                        role = "desarrollador"
                
                logger.info(f"✅ Usuario autenticado: {username} | Rol: {role}")
                
                return {
                    "username": str(entry.uid) if hasattr(entry, 'uid') else username,
                    "email": str(entry.mail) if hasattr(entry, 'mail') else f"{username}@example.org",
                    "nombre": str(entry.cn) if hasattr(entry, 'cn') else username,
                    "rol": role,
                    "ldap_dn": entry.entry_dn
                }
            else:
                logger.warning(f"⚠️  No se encontró información LDAP para {username}")
                return {
                    "username": username,
                    "email": f"{username}@example.org",
                    "nombre": username,
                    "rol": "desarrollador",
                    "ldap_dn": user_dn
                }
                
        except Exception as e:
            logger.error(f"⚠️  Error obteniendo información del usuario: {str(e)}")
            return {
                "username": username,
                "email": f"{username}@example.org",
                "nombre": username,
                "rol": "desarrollador",
                "ldap_dn": user_dn
            }
    
    def verify_ldap_connection(self) -> bool:
        """Verifica que el servidor LDAP esté disponible."""
        try:
            if LDAP_BIND_USER and LDAP_BIND_PASSWORD:
                conn = Connection(
                    self.server,
                    user=LDAP_BIND_USER,
                    password=LDAP_BIND_PASSWORD,
                    auto_bind=True
                )
            else:
                conn = Connection(self.server, auto_bind=True)
            
            conn.unbind()
            return True
        except Exception as e:
            logger.error(f"❌ Error verificando conexión LDAP: {str(e)}")
            return False

# ============================================================================
# SISTEMA DE PERMISOS
# ============================================================================

class PermissionChecker:
    """
    Verificador de permisos basado en roles.
    Define qué puede hacer cada rol en el sistema.
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
    
    @classmethod
    def get_role_permissions(cls, role: str) -> list:
        """
        Obtiene todos los permisos de un rol.
        
        Args:
            role: Rol del usuario
            
        Returns:
            Lista de permisos del rol
        """
        return cls.ROLE_PERMISSIONS.get(role, [])

# ============================================================================
# SERVICIO JWT - Token Management
# ============================================================================

class TokenService:
    """Servicio para generación y validación de tokens JWT."""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crea un token JWT de acceso."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """Decodifica y valida un token JWT."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.error(f"❌ Error validando token: {str(e)}")
            return None

# Instancias globales
ldap_service = LDAPAuthService()
token_service = TokenService()

# ============================================================================
# APLICACIÓN FASTAPI
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida del servicio"""
    logger.info("🚀 Iniciando Servicio de Autenticación...")
    try:
        # Verificar conexión a LDAP
        ldap_connected = ldap_service.verify_ldap_connection()
        if ldap_connected:
            logger.info("✅ Conexión a LDAP establecida")
        else:
            logger.warning("⚠️  No se pudo conectar a LDAP")
        
        logger.info("✅ Servicio de Autenticación inicializado")
        logger.info("🔐 Federated Identity con LDAP configurado")
        logger.info("🌐 Servicio disponible en puerto 8002")
        
    except Exception as e:
        logger.error(f"❌ Error crítico durante el inicio: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Servicio de Autenticación detenido")

app = FastAPI(
    title="Servicio de Autenticación",
    description="Microservicio dedicado para autenticación con LDAP y generación de tokens JWT",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ENDPOINTS DEL SERVICIO DE AUTENTICACIÓN
# ============================================================================

@app.get("/", tags=["Sistema"])
async def root():
    """Endpoint raíz del servicio"""
    return {
        "service": "Servicio de Autenticación",
        "version": "1.0.0",
        "status": "Operacional",
        "authentication": "LDAP (Federated Identity)",
        "tokens": "JWT"
    }

@app.get("/health", tags=["Sistema"])
async def health_check():
    """Health check del servicio"""
    ldap_connected = ldap_service.verify_ldap_connection()
    
    return {
        "status": "healthy" if ldap_connected else "degraded",
        "service": "auth-service",
        "ldap_connection": "connected" if ldap_connected else "disconnected"
    }

@app.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(credentials: LoginRequest):
    """
    Login con Federated Identity (LDAP) y generación de token JWT.
    
    Autentica al usuario contra el servidor LDAP externo y genera un token JWT interno.
    
    **Usuarios LDAP de prueba:**
    - Admin: username=`admin`, password=`admin_password`
    - Manager: username=`manager`, password=`manager_password`
    - Developer: username=`developer`, password=`developer_password`
    """
    # Autenticar contra LDAP
    user_info = ldap_service.authenticate_user(
        credentials.username,
        credentials.password
    )
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Verifique su usuario y contraseña LDAP.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crear token JWT
    token_data = {
        "sub": user_info["username"],
        "username": user_info["username"],
        "email": user_info["email"],
        "nombre": user_info["nombre"],
        "rol": user_info["rol"],
    }
    
    access_token = token_service.create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_info
    }

@app.get("/auth/me", response_model=UserInfo)
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Obtener información del usuario del token JWT.
    
    Requiere token JWT válido en el header Authorization.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extraer token
    token = authorization.replace("Bearer ", "").strip()
    
    # Decodificar token
    payload = token_service.decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return UserInfo(
        username=payload.get("username", ""),
        email=payload.get("email", ""),
        nombre=payload.get("nombre", ""),
        rol=payload.get("rol", "desarrollador"),
        ldap_dn=payload.get("ldap_dn")
    )

@app.get("/auth/status")
async def auth_status():
    """
    Verificar el estado del sistema de autenticación.
    Endpoint público.
    """
    ldap_connected = ldap_service.verify_ldap_connection()
    
    return {
        "status": "operational" if ldap_connected else "degraded",
        "ldap_connection": "connected" if ldap_connected else "disconnected",
        "authentication_method": "LDAP (Federated Identity)",
        "token_type": "JWT",
        "token_expiration_minutes": ACCESS_TOKEN_EXPIRE_MINUTES
    }

@app.post("/auth/validate")
async def validate_token(authorization: Optional[str] = Header(None)):
    """
    Validar un token JWT.
    Útil para que otros servicios validen tokens.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    payload = token_service.decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )
    
    return {
        "valid": True,
        "user": {
            "username": payload.get("username"),
            "rol": payload.get("rol"),
            "email": payload.get("email")
        },
        "expires_at": payload.get("exp")
    }

@app.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Cerrar sesión del usuario.
    Con JWT stateless, el logout se maneja en el cliente eliminando el token.
    """
    return {
        "message": "Sesión cerrada exitosamente",
        "status": "success",
        "note": "Elimine el token del cliente"
    }

@app.get("/auth/permissions")
async def get_permissions(authorization: Optional[str] = Header(None)):
    """
    Obtener permisos del usuario autenticado basados en su rol.
    
    Requiere token JWT válido en el header Authorization.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extraer token
    token = authorization.replace("Bearer ", "").strip()
    
    # Decodificar token
    payload = token_service.decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Obtener información del usuario del token
    username = payload.get("username", "")
    rol = payload.get("rol", "desarrollador")
    
    # Obtener permisos del rol
    permissions = PermissionChecker.get_role_permissions(rol)
    
    # Calcular flags de permisos específicos
    can_admin = PermissionChecker.has_permission(rol, "*") or rol == "admin"
    can_manage_projects = (
        PermissionChecker.has_permission(rol, "proyectos:*") or
        PermissionChecker.has_permission(rol, "*")
    )
    
    return {
        "username": username,
        "rol": rol,
        "permissions": permissions,
        "can_admin": can_admin,
        "can_manage_projects": can_manage_projects
    }

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )


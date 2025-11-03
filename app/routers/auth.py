"""
Router de Autenticación - Patrón Federated Identity con LDAP
Implementa endpoints para login delegando la autenticación a LDAP.
Parte del sistema Gatekeeper para control de acceso centralizado.
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict

from app.schemas import LoginRequest, TokenResponse, UserInfo, ErrorResponse
from app.services.auth_service import (
    LDAPAuthService,
    TokenService,
    get_ldap_service,
    get_token_service,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.middlewares.gatekeeper import get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
    responses={401: {"model": ErrorResponse}},
)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest,
    ldap_service: LDAPAuthService = Depends(get_ldap_service),
    token_service: TokenService = Depends(get_token_service)
):
    """
    ### Login con Federated Identity (LDAP)
    
    Autentica al usuario contra el servidor LDAP externo y genera un token JWT interno.
    
    **Patrón Federated Identity:**
    - Delega la autenticación a un proveedor externo confiable (LDAP)
    - No gestiona contraseñas localmente
    - Aumenta la seguridad al aprovechar mecanismos robustos externos
    
    **Flujo:**
    1. El cliente envía credenciales (username + password)
    2. El sistema valida las credenciales contra LDAP
    3. Si es exitoso, se genera un token JWT interno
    4. El token se utiliza para acceder a recursos protegidos
    
    **Campos:**
    - **username**: Nombre de usuario en el directorio LDAP
    - **password**: Contraseña del usuario
    
    **Respuesta:**
    - **access_token**: Token JWT para autenticación en requests subsiguientes
    - **token_type**: Tipo de token (bearer)
    - **expires_in**: Tiempo de expiración en segundos
    - **user**: Información del usuario autenticado
    
    **Ejemplos de usuarios LDAP de prueba:**
    - Admin: username=`admin`, password=`admin_password`
    - Manager: username=`manager`, password=`manager_password`
    - Developer: username=`developer`, password=`developer_password`
    """
    # Autenticar contra LDAP (Federated Identity)
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
    
    # Crear token JWT interno
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


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Obtener información del usuario actualmente autenticado.
    
    Requiere token JWT válido en el header Authorization.
    
    **Header requerido:**
    ```
    Authorization: Bearer <token>
    ```
    """
    return UserInfo(
        username=current_user.get("username", ""),
        email=current_user.get("email", ""),
        nombre=current_user.get("nombre", ""),
        rol=current_user.get("rol", "desarrollador"),
        ldap_dn=current_user.get("ldap_dn")
    )


@router.get("/status")
async def auth_status():
    """
    Verificar el estado del sistema de autenticación.
    
    Endpoint público para verificar que el servicio de autenticación está funcionando.
    """
    ldap_service = get_ldap_service()
    ldap_connected = ldap_service.verify_ldap_connection()
    
    return {
        "status": "operational" if ldap_connected else "degraded",
        "ldap_connection": "connected" if ldap_connected else "disconnected",
        "authentication_method": "LDAP (Federated Identity)",
        "token_type": "JWT",
        "security_patterns": [
            "Gatekeeper",
            "Federated Identity"
        ]
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Cerrar sesión del usuario actual.
    
    **Nota:** Con JWT stateless, el logout se maneja típicamente en el cliente
    eliminando el token. Este endpoint está disponible para tracking o
    implementaciones futuras con blacklist de tokens.
    """
    return {
        "message": f"Sesión cerrada para usuario {current_user.get('username')}",
        "status": "success"
    }


@router.get("/permissions")
async def get_user_permissions(current_user: dict = Depends(get_current_user)):
    """
    Obtener los permisos del usuario actual según su rol.
    
    Útil para que el frontend determine qué acciones puede realizar el usuario.
    """
    from app.gatekeeper import PermissionChecker
    
    role = current_user.get("rol", "desarrollador")
    permissions = PermissionChecker.ROLE_PERMISSIONS.get(role, [])
    
    return {
        "username": current_user.get("username"),
        "rol": role,
        "permissions": permissions,
        "can_admin": role == "admin",
        "can_manage_projects": role in ["admin", "manager"],
        "can_manage_users": role in ["admin", "manager"]
    }


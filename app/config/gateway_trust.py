"""
Gateway Trust Middleware
Middleware ligero que confía en la validación del API Gateway.
La aplicación ya no hace validación de seguridad, confía en el Gateway.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
import json
from typing import Optional


class GatewayTrustMiddleware:
    """
    Middleware que extrae información del usuario desde los headers
    proporcionados por el API Gateway.
    
    Este middleware NO valida tokens ni aplica seguridad.
    Toda la seguridad es responsabilidad del Gateway.
    """
    
    async def __call__(self, request: Request, call_next):
        """
        Extrae información del usuario desde el header X-User-Info
        proporcionado por el Gateway.
        """
        # Extraer información del usuario desde el header del gateway
        user_info_header = request.headers.get("X-User-Info")
        
        if user_info_header:
            try:
                # Decodificar la información del usuario
                user_info = json.loads(user_info_header)
                # Agregar al request state para que esté disponible en los endpoints
                request.state.user = user_info
            except json.JSONDecodeError:
                print(f"⚠️  Error decodificando X-User-Info: {user_info_header}")
                request.state.user = None
        else:
            request.state.user = None
        
        # Procesar request
        response = await call_next(request)
        
        return response


# Instancia global del middleware
gateway_trust_middleware_instance = GatewayTrustMiddleware()


# Función middleware compatible con FastAPI/Starlette
async def gateway_trust_middleware(request: Request, call_next):
    """
    Función middleware que delega a la instancia de GatewayTrustMiddleware.
    Compatible con FastAPI/Starlette BaseHTTPMiddleware.
    """
    return await gateway_trust_middleware_instance(request, call_next)


# Dependency simplificado para obtener el usuario actual
async def get_current_user_from_gateway(request: Request) -> Optional[dict]:
    """
    Dependency que obtiene el usuario desde el request state
    (ya validado por el Gateway).
    
    Uso:
        @app.get("/endpoint")
        async def endpoint(user: dict = Depends(get_current_user_from_gateway)):
            ...
    """
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user
    return None


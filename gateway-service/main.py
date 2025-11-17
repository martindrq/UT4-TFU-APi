"""
API Gateway Service - Patrón Gatekeeper Desacoplado
Servicio independiente de seguridad que actúa como punto de entrada único.
Todas las solicitudes externas pasan por este gateway antes de llegar a la aplicación.
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx
import os
import re
import time
from typing import Optional
from contextlib import asynccontextmanager

# Configuración
BACKEND_URL = os.getenv("BACKEND_URL", "http://app:8000")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth:8002")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SECRET_KEY = os.getenv("SECRET_KEY", "tu-clave-secreta-super-segura-cambiar-en-produccion")
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Cliente HTTP para comunicación con el backend
http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida del gateway"""
    global http_client
    http_client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0)
    print("🚀 API Gateway Service iniciado")
    print(f"🔄 Proxy hacia: {BACKEND_URL}")
    print("🛡️  Seguridad y validación activa")
    yield
    await http_client.aclose()
    print("🛑 API Gateway Service detenido")

app = FastAPI(
    title="API Gateway Service",
    description="Servicio de seguridad y enrutamiento - Patrón Gatekeeper",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================================================================
# CLASE GATEKEEPER - Lógica de seguridad centralizada
# ========================================================================================

class GatewaySecurityValidator:
    """Validador de seguridad del Gateway"""
    
    # Patrones sospechosos para detectar ataques
    SUSPICIOUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # XSS
        r"javascript:",                  # XSS
        r"on\w+\s*=",                   # Event handlers (XSS)
        r"(union|select|insert|update|delete|drop|create|alter)\s+",  # SQL Injection
        r"\.\./",                        # Path traversal
        r"\\x[0-9a-fA-F]{2}",           # Hex encoding
        r"%[0-9a-fA-F]{2}%[0-9a-fA-F]{2}%[0-9a-fA-F]{2}",  # Exceso de URL encoding
    ]
    
    # Endpoints públicos (no requieren autenticación)
    PUBLIC_ENDPOINTS = [
        "/",
        "/health",
        "/gateway/health",
        "/stats",
        "/cache/stats",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/auth/login",
        "/api/v1/auth/status",
        "/demo"
    ]
    
    def __init__(self):
        self.request_logs = {}  # Rate limiting en memoria
        
    def is_public_endpoint(self, path: str) -> bool:
        """Verifica si el endpoint es público"""
        if path in self.PUBLIC_ENDPOINTS:
            return True
        if path.rstrip('/') in self.PUBLIC_ENDPOINTS:
            return True
        for endpoint in self.PUBLIC_ENDPOINTS:
            if endpoint in ["/docs", "/openapi.json", "/redoc"]:
                if path.startswith(endpoint):
                    return True
        return False
    
    def extract_token(self, request: Request) -> Optional[str]:
        """Extrae el token JWT del header Authorization"""
        auth_header = None
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "authorization":
                auth_header = header_value
                break
        
        if auth_header:
            auth_header = auth_header.strip()
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
                if token:
                    return token
            elif auth_header.lower().startswith("bearer"):
                token = auth_header[6:].strip()
                if token:
                    return token
            else:
                if auth_header and len(auth_header) > 10:
                    return auth_header
        
        # Fallback: query parameter
        token = request.query_params.get("token")
        if token:
            return token
        
        # Fallback: headers personalizados
        for header_name in ["X-Auth-Token", "X-Access-Token", "Authorization-Token"]:
            token = request.headers.get(header_name)
            if token:
                return token.strip()
        
        return None
    
    def is_suspicious_request(self, request: Request) -> bool:
        """Detecta patrones sospechosos en la solicitud"""
        url_str = str(request.url)
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, url_str, re.IGNORECASE):
                print(f"🚨 Gateway: Patrón sospechoso detectado en URL: {pattern}")
                return True
        
        for key, value in request.query_params.items():
            for pattern in self.SUSPICIOUS_PATTERNS:
                if re.search(pattern, f"{key}={value}", re.IGNORECASE):
                    print(f"🚨 Gateway: Patrón sospechoso detectado en query param: {key}")
                    return True
        
        suspicious_headers = ['X-Forwarded-For', 'X-Real-IP']
        for header in suspicious_headers:
            value = request.headers.get(header, "")
            if ".." in value or ";" in value:
                print(f"🚨 Gateway: Header sospechoso: {header}")
                return True
        
        return False
    
    def check_rate_limit(self, request: Request) -> bool:
        """Implementa rate limiting por IP"""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        if client_ip not in self.request_logs:
            self.request_logs[client_ip] = []
        
        # Limpiar requests antiguos
        self.request_logs[client_ip] = [
            timestamp for timestamp in self.request_logs[client_ip]
            if current_time - timestamp < RATE_LIMIT_WINDOW_SECONDS
        ]
        
        # Verificar límite
        if len(self.request_logs[client_ip]) >= RATE_LIMIT_REQUESTS:
            print(f"🚨 Gateway: Rate limit excedido para IP: {client_ip}")
            return False
        
        # Agregar request actual
        self.request_logs[client_ip].append(current_time)
        return True
    
    async def validate_token(self, token: str) -> Optional[dict]:
        """
        Valida el token JWT.
        En una implementación completa, esto podría:
        - Validar contra un servicio de autenticación
        - Verificar firma JWT
        - Consultar caché de tokens revocados
        """
        # Importar el validador de tokens (usando el servicio existente)
        from jose import jwt, JWTError
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return payload
        except JWTError as e:
            print(f"⚠️  Gateway: Token inválido: {str(e)}")
            return None

# Instancia global del validador
security_validator = GatewaySecurityValidator()

# ========================================================================================
# MIDDLEWARE DE SEGURIDAD
# ========================================================================================

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """
    Middleware principal del gateway que valida todas las solicitudes
    """
    start_time = time.time()
    
    # 1. Verificar si es un endpoint público
    if security_validator.is_public_endpoint(request.url.path):
        response = await call_next(request)
        return response
    
    # 2. Filtrar solicitudes maliciosas (IDS/IPS)
    if security_validator.is_suspicious_request(request):
        print(f"🚨 Gateway: Solicitud sospechosa detectada para {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Solicitud rechazada: contenido sospechoso detectado"}
        )
    
    # 3. Rate Limiting
    if not security_validator.check_rate_limit(request):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Demasiadas solicitudes. Por favor intente más tarde."}
        )
    
    # 4. Validar token JWT
    token = security_validator.extract_token(request)
    if not token:
        print(f"🚫 Gateway: Token no encontrado para {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "No se proporcionó token de autenticación"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 5. Validar token
    payload = await security_validator.validate_token(token)
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
    
    # 8. Agregar headers de seguridad
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # 9. Logging de tiempo de procesamiento
    process_time = time.time() - start_time
    response.headers["X-Gateway-Process-Time"] = str(process_time)
    
    return response

# ========================================================================================
# ENDPOINTS DEL GATEWAY (definidos ANTES del proxy catch-all para tener prioridad)
# ========================================================================================

@app.get("/gateway/health")
async def gateway_health():
    """Health check del gateway"""
    return {
        "status": "healthy",
        "service": "api-gateway",
        "backend_url": BACKEND_URL,
        "auth_service_url": AUTH_SERVICE_URL
    }

@app.get("/")
async def gateway_root():
    """Endpoint raíz del gateway"""
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "status": "Operacional",
        "descripcion": "Gateway de seguridad - Patrón Gatekeeper",
        "microservicios": {
            "backend": BACKEND_URL,
            "auth": AUTH_SERVICE_URL
        },
        "enrutamiento": {
            "/api/v1/auth": "Servicio de Autenticación (puerto 8002)",
            "/api/v1/usuarios": "Backend Principal (puerto 8000)",
            "/api/v1/proyectos": "Backend Principal (puerto 8000)",
            "/api/v1/tareas": "Backend Principal (puerto 8000)"
        }
    }

# ========================================================================================
# PROXY ENDPOINTS - Redirección al backend
# ========================================================================================

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def gateway_proxy(request: Request, path: str):
    """
    Proxy que redirige todas las solicitudes validadas al backend correspondiente.
    Enruta solicitudes de auth al servicio de autenticación dedicado.
    """
    # Determinar el servicio de destino basado en la ruta
    if path.startswith("api/v1/auth") or path.startswith("auth/"):
        # Enrutar al servicio de autenticación
        target_url = AUTH_SERVICE_URL
        # Ajustar la ruta para el servicio de auth
        # Si viene como api/v1/auth, lo convertimos a auth/
        if path.startswith("api/v1/"):
            service_path = path.replace("api/v1/", "")
        else:
            service_path = path
    else:
        # Enrutar al backend principal
        target_url = BACKEND_URL
        service_path = path
    
    # Construir URL del servicio destino
    backend_url = f"{target_url}/{service_path}"
    if request.url.query:
        backend_url = f"{backend_url}?{request.url.query}"
    
    # Preparar headers para el backend
    headers = dict(request.headers)
    
    # Agregar información del usuario si existe (desde la validación)
    if hasattr(request.state, "user") and request.state.user:
        import json
        headers["X-User-Info"] = json.dumps(request.state.user)
    
    # Eliminar headers que no deben ser reenviados
    headers_to_remove = ["host", "content-length"]
    for header in headers_to_remove:
        headers.pop(header, None)
    
    # Asegurar que Content-Type esté presente para requests con body
    if request.method in ["POST", "PUT", "PATCH"]:
        if "content-type" not in headers and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
    
    try:
        # Leer el body de la solicitud
        body = await request.body()
        
        # Debug: Log para requests POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            print(f"🔄 Gateway: Proxying {request.method} {backend_url}")
            print(f"   Content-Type: {headers.get('Content-Type', 'not set')}")
            print(f"   Body length: {len(body) if body else 0} bytes")
            if body and len(body) < 500:  # Solo log body pequeño para debug
                try:
                    import json
                    body_str = body.decode('utf-8')
                    print(f"   Body: {body_str}")
                except:
                    pass
        
        # Hacer la solicitud al servicio correspondiente
        response = await http_client.request(
            method=request.method,
            url=backend_url,
            headers=headers,
            content=body,
            follow_redirects=True
        )
        
        # Debug: Log respuesta
        if response.status_code >= 400:
            print(f"❌ Gateway: Backend respondió con {response.status_code} para {request.method} {backend_url}")
            try:
                error_body = response.text[:500]  # Primeros 500 caracteres
                print(f"   Error response: {error_body}")
            except:
                pass
        
        # Preparar headers para la respuesta (excluir headers que FastAPI maneja automáticamente)
        response_headers = {}
        headers_to_exclude = ["content-length", "transfer-encoding", "connection", "server"]
        for key, value in response.headers.items():
            if key.lower() not in headers_to_exclude:
                response_headers[key] = value
        
        # Obtener el tipo de contenido de la respuesta
        content_type = response.headers.get("content-type", "").lower()
        
        # Retornar la respuesta del backend según su tipo de contenido
        if content_type.startswith("application/json"):
            # Respuesta JSON
            try:
                return JSONResponse(
                    status_code=response.status_code,
                    content=response.json(),
                    headers=response_headers
                )
            except Exception:
                # Si falla el parseo JSON, devolver como texto
                return Response(
                    status_code=response.status_code,
                    content=response.text,
                    headers=response_headers,
                    media_type=content_type
                )
        else:
            # Respuesta HTML, texto plano u otros tipos de contenido
            return Response(
                status_code=response.status_code,
                content=response.content,
                headers=response_headers,
                media_type=content_type if content_type else "text/html"
            )
        
    except httpx.RequestError as e:
        print(f"❌ Gateway: Error al comunicarse con el servicio: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Servicio no disponible"}
        )
    except Exception as e:
        print(f"❌ Gateway: Error inesperado: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Error interno del gateway"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )


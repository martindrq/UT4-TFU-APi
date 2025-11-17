"""
Aplicación principal FastAPI - Mini Gestor de Proyectos
Implementa arquitectura modular con componentes independientes y sin estado.
Cumple con principios ACID, escalabilidad horizontal y despliegue en contenedores.
"""

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
from uvicorn.logging import AccessFormatter
from pathlib import Path
from sqlalchemy.orm import Session
import logging

# Importar configuración centralizada (External Configuration Store Pattern)
from app.config import settings, create_tables, test_connection, check_db_health, get_db

# Importar servicios
from app.services import cache_service as cache

# Importar middleware de confianza con Gateway (la seguridad la maneja el Gateway)
# Ya no usamos middleware de seguridad local, confiamos en el API Gateway
from app.config.gateway_trust import gateway_trust_middleware

# Importar routers de cada componente
from app.routers import usuarios, proyectos, tareas

# ============================================================================
# CONFIGURACIÓN DE LOGGING - Filtrar health checks
# ============================================================================

class HealthCheckFilter(logging.Filter):
    """Filtro que excluye logs de health checks"""
    SILENT_PATHS = ["/health", "/gateway/health"]
    
    def filter(self, record):
        message = record.getMessage()
        for silent_path in self.SILENT_PATHS:
            if silent_path in message:
                return False  # No loguear
        return True  # Loguear normalmente

# Configurar el filtro para uvicorn.access logger
# Esto se ejecuta cuando se importa el módulo, antes de que uvicorn inicie
def setup_logging_filter():
    """Configura el filtro de logging para health checks"""
    access_logger = logging.getLogger("uvicorn.access")
    health_filter = HealthCheckFilter()
    
    # Aplicar el filtro a todos los handlers existentes
    for handler in access_logger.handlers:
        if health_filter not in handler.filters:
            handler.addFilter(health_filter)
    
    # También aplicar al logger raíz por si uvicorn usa handlers allí
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if hasattr(handler, 'name') and 'uvicorn' in str(handler.name).lower():
            if health_filter not in handler.filters:
                handler.addFilter(health_filter)
    
    # Configurar el logger para que también filtre a nivel de logger
    # Esto asegura que incluso si se crean nuevos handlers, el filtro se aplique
    access_logger.addFilter(health_filter)

# Ejecutar la configuración al importar el módulo
setup_logging_filter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación.
    Verifica conexión, crea tablas con reintentos automáticos y limpia recursos al final.
    Inicializa Redis para caché (patrón Cache-Aside).
    """
    # Startup: Configurar filtro de logging para health checks
    # Esto se ejecuta después de que uvicorn haya configurado sus loggers
    import asyncio
    await asyncio.sleep(0.1)  # Pequeño delay para que uvicorn configure sus loggers
    setup_logging_filter()
    
    # Startup: Verificar conexión y crear tablas de base de datos con retry
    print("🚀 Iniciando API Mini Gestor de Proyectos...")
    try:
        # Primero verificar que podemos conectar a la base de datos
        test_connection()
        
        # Luego crear/verificar las tablas
        create_tables()
        
        # Inicializar conexión a Redis para caché
        cache.init_redis()
        
        print("✅ Sistema inicializado correctamente")
        print("📊 Base de datos conectada y lista")
        print("💾 Sistema de caché Redis configurado (Cache-Aside)")
        print("🔐 Autenticación: Servicio independiente en puerto 8002")
        print("🛡️  Confiando en API Gateway para seguridad")
        print("🌐 API Backend disponible en http://localhost:8000 (a través de Gateway)")
        print("📚 Documentación en http://localhost:8000/docs")
        
    except Exception as e:
        print(f"❌ Error crítico durante el inicio: {str(e)}")
        print("⚠️  La aplicación no pudo conectar a la base de datos después de múltiples reintentos")
        raise
    
    yield
    
    # Shutdown: Limpiar recursos si es necesario
    cache.close_redis()
    print("🛑 API Mini Gestor de Proyectos detenida")

# Crear instancia de FastAPI con configuración
app = FastAPI(
    title="Mini Gestor de Proyectos API",
    description="""
    ## API REST para gestión de proyectos, usuarios y tareas
    
    Esta API implementa tres componentes modulares principales:
    
    ###  GestorUsuarios
    - Gestión CRUD completa de usuarios
    - Validación de emails únicos
    - Roles de usuario (admin, manager, desarrollador)
    
    ###  GestorProyectos
    - Gestión CRUD completa de proyectos
    - Asignación/desasignación de usuarios a proyectos
    - Estados de proyecto (activo, pausado, completado)
    - **Cache-Aside**: Optimización de consultas frecuentes con Redis
    
    ###  GestorTareas
    - Gestión CRUD completa de tareas
    - Asignación de responsables con validación cruzada
    - Estados y prioridades de tareas
    - Validación de pertenencia usuario-proyecto
    - **Cache-Aside**: Optimización de consultas frecuentes con Redis
    
    ### Patrones de Seguridad
    - **Gatekeeper**: API Gateway externo que centraliza control de acceso
    - **Federated Identity**: Autenticación delegada a LDAP externo
    - Seguridad delegada al Gateway (tokens, rate limiting, IDS/IPS)
    - Control de permisos basado en roles (RBAC)
    - Backend confía en la validación del Gateway
    
    ### Arquitectura
    - **Microservicios**: Gateway, Backend Principal, Servicio de Autenticación (puerto 8002)
    - **Base de datos**: PostgreSQL para persistencia de datos
    - **Servicios sin estado**: Cada request es independiente
    - **Escalabilidad horizontal**: Puede ejecutarse en múltiples instancias
    - **ACID**: Transacciones consistentes con PostgreSQL
    - **Cache-Aside Pattern**: Redis para optimizar consultas frecuentes
    - **Gatekeeper Pattern**: Gateway externo para control de acceso
    - **Federated Identity**: Autenticación con LDAP en servicio dedicado
    - **Modular**: Componentes independientes con interfaces claras
    - **Contenedores**: Preparado para Docker y orquestación
    """,
    version="1.0.0",
    contact={
        "name": "Equipo de Desarrollo",
        "email": "desarrollo@minigestor.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# Configurar CORS para permitir requests desde diferentes orígenes
# La configuración se obtiene desde External Configuration Store
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Configurado externamente
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agregar middleware de confianza con Gateway
# La seguridad (tokens, rate limiting, IDS) es manejada por el API Gateway
# Este middleware solo extrae la información del usuario desde los headers del Gateway
from starlette.middleware.base import BaseHTTPMiddleware

app.add_middleware(BaseHTTPMiddleware, dispatch=gateway_trust_middleware)

# Middleware para prevenir redirects de barras finales en métodos que tienen body
# Esto evita que POST/PUT/PATCH/DELETE pierdan el body en redirects 307
# FastAPI redirige automáticamente rutas sin barra final a rutas con barra final,
# pero en métodos con body esto causa que se pierda el contenido
class NoRedirectSlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Si la ruta NO termina con / y el método tiene body, agregar la barra final
        # Esto previene el redirect 307 que hace perder el body
        if not request.url.path.endswith("/") and request.url.path != "/":
            # Métodos que pueden tener body
            if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                # Agregar barra final directamente en el scope para evitar redirect
                request.scope["path"] = request.url.path + "/"
        
        response = await call_next(request)
        return response

app.add_middleware(NoRedirectSlashMiddleware)

# Router de autenticación movido a servicio independiente (auth-service en puerto 8002)
# El Gateway enruta las solicitudes /api/v1/auth al servicio de autenticación

# Registrar routers de cada componente con prefijos específicos
app.include_router(
    usuarios.router,
    prefix="/api/v1",
    tags=["GestorUsuarios"]
)

app.include_router(
    proyectos.router,
    prefix="/api/v1", 
    tags=["GestorProyectos"]
)

app.include_router(
    tareas.router,
    prefix="/api/v1",
    tags=["GestorTareas"] 
)

# Endpoint raíz para verificación de estado
@app.get("/", tags=["Sistema"])
async def root():
    """
    Endpoint raíz para verificar que la API está funcionando.
    Útil para health checks en contenedores.
    """
    return {
        "message": "Mini Gestor de Proyectos API",
        "status": "Operacional",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "componentes": [
            "Autenticación (/api/v1/auth) - Servicio Independiente (puerto 8002)",
            "GestorUsuarios (/api/v1/usuarios)",
            "GestorProyectos (/api/v1/proyectos)", 
            "GestorTareas (/api/v1/tareas)"
        ],
        "patrones_seguridad": [
            "Gateway Service - Control de acceso centralizado (puerto 8080)",
            "Backend Service - Confía en validación del Gateway (puerto 8000)",
            "Federated Identity - Autenticación con LDAP"
        ],
        "nota": "Todas las solicitudes deben pasar por el Gateway (puerto 8080)"
    }

# Endpoint de health check para Docker
@app.get("/health", tags=["Sistema"])
async def health_check():
    """
    Health check endpoint para monitoreo de contenedores y aplicaciones.
    Verifica que la aplicación y la base de datos estén respondiendo correctamente.
    
    Si la conexión falla después de todos los reintentos, retorna estado "unhealthy"
    sin lanzar excepción HTTP (para que el monitoreo pueda detectar el problema).
    """
    try:
        db_health = check_db_health()
        
        # Determinar el estado general del sistema
        overall_status = "healthy" if db_health["status"] == "healthy" else "unhealthy"
        
        return {
            "status": overall_status,
            "service": "mini-gestor-proyectos-api",
            "database": db_health
        }
    except Exception as e:
        # Si después de todos los reintentos aún falla, retornar estado unhealthy
        # sin lanzar excepción HTTP para que el monitoreo pueda detectarlo
        return {
            "status": "unhealthy",
            "service": "mini-gestor-proyectos-api",
            "database": {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        }

# Endpoint público para estadísticas generales
@app.get("/stats", tags=["Sistema"])
async def get_stats(db: Session = Depends(get_db)):
    """
    Obtener estadísticas generales del sistema (conteos).
    Endpoint público para mostrar métricas básicas sin exponer datos sensibles.
    """
    from app.models import Usuario, Proyecto, Tarea
    
    try:
        user_count = db.query(Usuario).count()
        project_count = db.query(Proyecto).count()
        task_count = db.query(Tarea).count()
        
        return {
            "usuarios": user_count,
            "proyectos": project_count,
            "tareas": task_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas: {str(e)}"
        )

# Endpoint para estadísticas de caché
@app.get("/cache/stats", tags=["Sistema"])
async def cache_stats():
    """
    Obtener estadísticas del sistema de caché Redis.
    Muestra información sobre el rendimiento del Cache-Aside pattern.
    """
    return cache.get_cache_stats()

# Endpoint para servir la demo web
@app.get("/demo", response_class=HTMLResponse, tags=["Sistema"])
async def demo_page():
    """
    Interfaz web interactiva para demostración del sistema.
    Incluye gestión de usuarios, proyectos, tareas y visualización del sistema de retry.
    """
    demo_file = Path(__file__).parent / "demo.html"
    if demo_file.exists():
        return HTMLResponse(content=demo_file.read_text(), status_code=200)
    else:
        raise HTTPException(status_code=404, detail="Demo page not found")

# Manejo global de errores
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Maneja errores de validación de Pydantic"""
    import logging
    logger = logging.getLogger(__name__)
    
    errors = exc.errors()
    error_details = []
    for error in errors:
        error_details.append({
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg"),
            "type": error.get("type")
        })
    
    logger.error(f"❌ Error de validación en {request.method} {request.url.path}: {error_details}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Error de validación en los datos enviados",
            "errors": error_details
        }
    )

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Endpoint no encontrado",
            "path": str(request.url),
            "method": request.method
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "message": "Por favor contacte al administrador del sistema"
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Maneja excepciones HTTP personalizadas (después de los manejadores específicos)"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.error(f"❌ HTTPException {exc.status_code} en {request.method} {request.url.path}: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Punto de entrada para ejecutar la aplicación
if __name__ == "__main__":
    # Configuración desde External Configuration Store
    # Los parámetros se obtienen de variables de entorno
    print(f"\n🚀 Iniciando servidor en {settings.API_HOST}:{settings.API_PORT}")
    print(f"🌍 Entorno: {settings.ENVIRONMENT}")
    print(f"🔄 Hot Reload: {'Activado' if settings.API_RELOAD else 'Desactivado'}")
    print(f"📊 Log Level: {settings.LOG_LEVEL}\n")
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level=settings.LOG_LEVEL
    )
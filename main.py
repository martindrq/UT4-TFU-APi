"""
Aplicación principal FastAPI - Mini Gestor de Proyectos
Implementa arquitectura modular con componentes independientes y sin estado.
Cumple con principios ACID, escalabilidad horizontal y despliegue en contenedores.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path

# Importar configuración centralizada (External Configuration Store Pattern)
from app.config import settings, create_tables, test_connection, check_db_health

# Importar servicios
from app.services import cache_service as cache

# Importar middleware Gatekeeper
from app.middlewares.gatekeeper import gatekeeper_middleware

# Importar routers de cada componente
from app.routers import usuarios, proyectos, tareas, auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación.
    Verifica conexión, crea tablas con reintentos automáticos y limpia recursos al final.
    Inicializa Redis para caché (patrón Cache-Aside).
    """
    # Startup: Verificar conexión y crear tablas de base de datos con retry
    print("🚀 Iniciando API Mini Gestor de Proyectos...")
    try:
        # Primero verificar que podemos conectar a la base de datos
        test_connection()
        
        # Luego crear/verificar las tablas
        create_tables()
        
        # Inicializar conexión a Redis para caché
        cache.init_redis()
        
        # Verificar conexión LDAP
        from app.services.auth_service import ldap_service
        ldap_status = "✅ Conectado" if ldap_service.verify_ldap_connection() else "⚠️  Desconectado"
        
        print("✅ Sistema inicializado correctamente")
        print("📊 Base de datos conectada y lista")
        print("💾 Sistema de caché Redis configurado (Cache-Aside)")
        print(f"🔐 Servidor LDAP (Federated Identity): {ldap_status}")
        print("🛡️  Middleware Gatekeeper activado")
        print("🌐 API disponible en http://localhost:8000")
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
    - **Gatekeeper**: API Gateway que centraliza control de acceso
    - **Federated Identity**: Autenticación delegada a LDAP externo
    - Validación de tokens JWT
    - Control de permisos basado en roles (RBAC)
    - Protección contra ataques comunes (XSS, SQL Injection, Path Traversal)
    - Rate Limiting para prevenir abuso
    
    ### Arquitectura
    - **Servicios sin estado**: Cada request es independiente
    - **Escalabilidad horizontal**: Puede ejecutarse en múltiples instancias
    - **ACID**: Transacciones consistentes con PostgreSQL
    - **Cache-Aside Pattern**: Redis para optimizar consultas frecuentes
    - **Gatekeeper Pattern**: Control de acceso centralizado
    - **Federated Identity**: Autenticación con LDAP
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

# Agregar middleware Gatekeeper para seguridad
# Este middleware valida tokens, verifica permisos y filtra solicitudes maliciosas
# Nota: En FastAPI, los middlewares HTTP se ejecutan en orden inverso al registro
from starlette.middleware.base import BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=gatekeeper_middleware)

# Registrar router de autenticación (Gatekeeper + Federated Identity)
app.include_router(
    auth.router,
    prefix="/api/v1",
    tags=["Autenticación"]
)

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
            "Autenticación (/api/v1/auth) - Gatekeeper + Federated Identity",
            "GestorUsuarios (/api/v1/usuarios)",
            "GestorProyectos (/api/v1/proyectos)", 
            "GestorTareas (/api/v1/tareas)"
        ],
        "patrones_seguridad": [
            "Gatekeeper - Control de acceso centralizado",
            "Federated Identity - Autenticación con LDAP"
        ]
    }

# Endpoint de health check para Docker
@app.get("/health", tags=["Sistema"])
async def health_check():
    """
    Health check endpoint para monitoreo de contenedores.
    Verifica que la aplicación esté respondiendo correctamente.
    """
    return {
        "status": "healthy",
        "service": "mini-gestor-proyectos-api"
    }

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
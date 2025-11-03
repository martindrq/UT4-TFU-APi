# README - Mini Gestor de Proyectos API

## Descripción del Proyecto

API REST completa para un mini gestor de proyectos que implementa tres componentes modulares:
- **GestorUsuarios**: Gestión de usuarios del sistema
- **GestorProyectos**: Gestión de proyectos y asignación de usuarios
- **GestorTareas**: Gestión de tareas con validaciones cruzadas

## Conceptos Arquitectónicos Implementados

### 1. Componentes e Interfaces
- **Separación de responsabilidades**: Cada componente maneja su dominio específico
- **APIs REST claras**: Endpoints bien definidos para cada operación
- **Validación de entrada/salida**: Schemas Pydantic para consistencia

### 2. Propiedades ACID
- **Atomicidad**: Transacciones completas o rollback automático
- **Consistencia**: Validaciones de integridad referencial
- **Aislamiento**: Sesiones de base de datos independientes
- **Durabilidad**: Persistencia en PostgreSQL

### 3. Escalabilidad Horizontal
- **Servicios sin estado**: No hay variables de sesión en memoria
- **Stateless**: Cada request es completamente independiente
- **Paginación**: Soporte para grandes volúmenes de datos
- **Múltiples instancias**: Puede ejecutarse en paralelo

### 4. Contenedores
- **Docker**: Aplicación completamente containerizada
- **Orquestación**: docker-compose para múltiples servicios
- **Networking**: Red privada para comunicación entre contenedores
- **Volúmenes persistentes**: Datos de BD no se pierden

### 5. Alta Disponibilidad y Resiliencia
- **Sistema de Retry**: Reintentos automáticos con backoff exponencial
- **Health Checks**: Monitoreo de salud de BD y aplicación
- **Pool de Conexiones**: Gestión optimizada de conexiones a BD
- **Tolerancia a Fallos**: Recuperación automática ante fallos temporales

### 6. Queue-Based Load Leveling (Patrón de Nivelación de Carga)
- **Cola de Mensajes**: Redis como broker para desacoplar operaciones
- **Procesamiento Asíncrono**: Workers en background procesan tareas
- **Respuesta Rápida**: Cliente recibe respuesta inmediata (< 50ms)
- **Nivelación de Carga**: Absorbe picos de demanda sin degradación
- **Reintentos Automáticos**: Sistema robusto de reintentos con límites
- **Seguimiento de Estado**: job_id para monitorear procesamiento
- **Ver documentación detallada**: [RESUMEN_QUEUE_LOAD_LEVELING.md](./RESUMEN_QUEUE_LOAD_LEVELING.md)

### 7. Patrones de Seguridad

#### 7.1. Gatekeeper (API Gateway)
- **Control de Acceso Centralizado**: Todas las solicitudes pasan por un punto de control único
- **Validación de Tokens JWT**: Autenticación y autorización en cada request
- **Protección contra Ataques**: Detección de XSS, SQL Injection, Path Traversal
- **Rate Limiting**: Prevención de abuso con límites por IP (100 req/min)
- **Headers de Seguridad**: X-Content-Type-Options, X-Frame-Options, HSTS
- **Control de Permisos RBAC**: Permisos granulares por rol (admin, manager, desarrollador)
- **IDS/IPS Básico**: Detección de patrones maliciosos en requests
- **Reducción de Superficie de Ataque**: Servicios internos protegidos

##### 7.2. Federated Identity con LDAP
- **Autenticación Externa**: Delega autenticación a servidor LDAP
- **Single Sign-On (SSO)**: Mismas credenciales en múltiples sistemas
- **Sin Gestión de Contraseñas**: No almacena credenciales localmente
- **Mapeo Automático de Roles**: Roles basados en atributos LDAP (employeeType)
- **Tokens JWT Internos**: Generación de tokens después de validación LDAP
- **Integración Empresarial**: Compatible con Active Directory y OpenLDAP
- **Gestión Centralizada**: Usuarios gestionados en directorio único
- **Ver documentación detallada**: [PATRONES_SEGURIDAD.md](./PATRONES_SEGURIDAD.md)

### 8. External Configuration Store (Configuración Externa)
- **Separación Código-Configuración**: Variables de entorno externas al código
- **Multi-Entorno**: Mismo código para desarrollo, staging y producción
- **Configuración Centralizada**: Módulo `app/config.py` único punto de acceso
- **Gestión de Secretos**: Credenciales y claves fuera del código fuente
- **Docker Integration**: Variables interpoladas en docker-compose.yaml
- **Validación Automática**: Verificación de configuración al inicio
- **Sin Recompilación**: Modificar parámetros sin cambiar código
- **12 Factor App Compliant**: Siguiendo mejores prácticas de cloud native
- **Ver documentación detallada**: [EXTERNAL_CONFIGURATION_STORE.md](./EXTERNAL_CONFIGURATION_STORE.md)

## Estructura del Proyecto

### Arquitectura en Capas Técnicas

El proyecto está organizado siguiendo una **arquitectura en capas técnicas** que facilita la mantenibilidad, escalabilidad y separación de responsabilidades.

**Capas principales:**
- **config/**: Configuración centralizada y conexión a base de datos
- **models/**: Modelos ORM (SQLAlchemy) que representan las entidades
- **schemas/**: DTOs con Pydantic para validación de entrada/salida
- **services/**: Lógica de negocio reutilizable (auth, cache, queue)
- **middlewares/**: Procesamiento transversal de requests (seguridad, logging)
- **routers/**: Controladores que exponen los endpoints HTTP

> 📖 **Ver documentación completa de la arquitectura**: [ARQUITECTURA.md](./ARQUITECTURA.md)

```
UT3-TFU-APi/
├── app/
│   ├── __init__.py
│   │
│   ├── config/             # 🔧 Capa de Configuración
│   │   ├── __init__.py
│   │   ├── config.py       # ⚙️ External Configuration Store Pattern
│   │   └── database.py     # 🗄️ SQLAlchemy + Retry Pattern
│   │
│   ├── models/             # 📊 Capa de Modelos (ORM)
│   │   ├── __init__.py
│   │   └── models.py       # Usuario, Proyecto, Tarea
│   │
│   ├── schemas/            # ✅ Capa de Validación (DTOs)
│   │   ├── __init__.py
│   │   └── schemas.py      # Pydantic Schemas
│   │
│   ├── services/           # 💼 Capa de Lógica de Negocio
│   │   ├── __init__.py
│   │   ├── auth_service.py    # 🔐 Federated Identity + JWT
│   │   ├── cache_service.py   # ⚡ Cache-Aside Pattern
│   │   └── queue_service.py   # 📋 Queue-Based Load Leveling
│   │
│   ├── middlewares/        # 🛡️ Capa de Middlewares
│   │   ├── __init__.py
│   │   └── gatekeeper.py   # Gatekeeper Pattern (seguridad)
│   │
│   ├── routers/            # 🌐 Capa de Controladores (API)
│   │   ├── __init__.py
│   │   ├── auth.py         # 🔐 Endpoints de autenticación
│   │   ├── usuarios.py     # 👥 CRUD de usuarios
│   │   ├── proyectos.py    # 📁 CRUD de proyectos + caché
│   │   └── tareas.py       # ✓ CRUD de tareas + queue
│   │
│   └── worker.py           # 🔄 Worker de procesamiento asíncrono
├── scripts/
│   ├── demo_completa.sh     # Script demostración (Linux/Mac)
│   ├── demo_completa.bat    # Script demostración (Windows)
│   ├── start_worker.sh      # ⚡ Iniciar worker de colas (Linux/Mac)
│   ├── start_worker.bat     # ⚡ Iniciar worker de colas (Windows)
│   ├── demo_load_leveling.py # 🚀 Demo de Queue-Based Load Leveling
│   └── README.md            # Documentación de scripts
├── main.py                  # Aplicación FastAPI principal
├── demo.html                # 🎨 Demo web interactiva (servida por FastAPI)
├── requirements.txt         # Dependencias Python (incluye redis, tenacity)
├── Dockerfile              # Imagen Docker para la API
├── docker-compose.yaml     # Orquestación completa (PostgreSQL + Redis)
├── .env                    # Variables de entorno
├── .dockerignore           # Archivos ignorados por Docker
├── init-db.sql             # Script inicialización PostgreSQL
├── init-ldap.ldif          # 🔐 Script inicialización LDAP con usuarios de prueba
├── README.md               # Este archivo
```

##  Instrucciones de Despliegue

### Prerrequisitos
- Docker y docker-compose instalados
- Puerto 8000, 5432 y 8080 disponibles

### Despliegue con Docker

1. **Clonar/Descargar el proyecto**
   ```bash
   # Si está en Git
   git clone <repository-url>
   cd UT3-TFU-APi
   ```

2. **Construir y ejecutar los contenedores**
   ```bash
   docker-compose up --build -d
   ```

3. **Verificar que los servicios están ejecutándose**
   ```bash
   docker-compose ps
   ```

4. **Verificar la API**
   ```bash
   curl http://localhost:8000/health
   ```

### Servicios Disponibles

- **API FastAPI**: http://localhost:8000
  - **Demo Web Interactiva**: http://localhost:8000/demo 🎨 ⭐ **NUEVO**
  - Documentación: http://localhost:8000/docs
  - ReDoc: http://localhost:8000/redoc
  - Health Check: http://localhost:8000/health
  - **Login LDAP**: http://localhost:8000/api/v1/auth/login 🔐 **NUEVO**
  - **Estado Auth**: http://localhost:8000/api/v1/auth/status 🔐 **NUEVO**
- **PostgreSQL**: localhost:5432
  - Usuario: postgres
  - Contraseña: password
  - Base de datos: gestor_proyectos
- **OpenLDAP** (Federated Identity): ldap://localhost:389 🔐 **NUEVO**
  - Base DN: dc=example,dc=org
  - Admin DN: cn=admin,dc=example,dc=org
  - Admin Password: admin_password
  - **phpLDAPadmin**: http://localhost:8082 (Interfaz web de administración)
- **Redis** (Cache + Queue): localhost:6379
- **Adminer** (Administrador BD): http://localhost:8080

> 💡 **Tip**: La demo web interactiva incluye interfaz completa para gestionar usuarios, proyectos, tareas y ver el sistema de retry en acción. Ver [DEMO_INSTRUCCIONES.md](DEMO_INSTRUCCIONES.md)

## Endpoints Principales

### GestorUsuarios (`/api/v1/usuarios`)
- `POST /` - Crear usuario
- `GET /` - Listar usuarios (con paginación)
- `GET /{id}` - Obtener usuario específico
- `PUT /{id}` - Actualizar usuario
- `DELETE /{id}` - Eliminar usuario

### GestorProyectos (`/api/v1/proyectos`)
- `POST /` - Crear proyecto
- `GET /` - Listar proyectos (con filtros)
- `GET /{id}` - Obtener proyecto específico
- `PUT /{id}` - Actualizar proyecto
- `DELETE /{id}` - Eliminar proyecto
- `POST /{id}/asignar_usuario` - Asignar usuario a proyecto
- `DELETE /{id}/desasignar_usuario/{user_id}` - Desasignar usuario

### GestorTareas (`/api/v1/tareas`)
- `POST /` - Crear tarea (⚡ **CON COLA ASÍNCRONA**)
- `GET /` - Listar tareas (con filtros múltiples)
- `GET /{id}` - Obtener tarea específica
- `PUT /{id}` - Actualizar tarea
- `DELETE /{id}` - Eliminar tarea
- `POST /{id}/asignar_usuario` - Asignar responsable
- `DELETE /{id}/desasignar_usuario` - Desasignar responsable
- `GET /jobs/{job_id}` - 🆕 Consultar estado de job
- `GET /jobs/{job_id}/result` - 🆕 Obtener resultado de job completado
- `GET /queue/stats` - 🆕 Estadísticas de la cola

### 🔐 Autenticación (Gatekeeper + Federated Identity) (`/api/v1/auth`)
- `POST /login` - 🔐 Login con LDAP (Federated Identity)
- `GET /me` - 🔐 Información del usuario actual
- `GET /status` - Estado del sistema de autenticación
- `POST /logout` - Cerrar sesión
- `GET /permissions` - 🔐 Permisos del usuario según rol

## ⚡ Queue-Based Load Leveling - Uso Rápido

El patrón **Queue-Based Load Leveling** está implementado para la creación de tareas. Proporciona:
- ✅ Respuesta inmediata al cliente (< 50ms)
- ✅ Nivelación de carga bajo alta demanda
- ✅ Procesamiento asíncrono confiable

### Inicio Rápido

**Terminal 1 - Iniciar Worker:**
```bash
./scripts/start_worker.sh   # Linux/Mac
scripts\start_worker.bat    # Windows
```

**Terminal 2 - Crear Tarea:**
```bash
curl -X POST http://localhost:8000/tareas/ \
  -H "Content-Type: application/json" \
  -d '{"titulo":"Mi tarea","proyecto_id":1}'

# Respuesta inmediata con job_id:
# {"job_id":"f47ac10b-...","status":"pending","queue_position":5}
```

**Consultar Estado:**
```bash
curl http://localhost:8000/tareas/jobs/f47ac10b-...
# {"status":"completed","message":"Tarea creada exitosamente"}
```

**Demo Completa:**
```bash
python scripts/demo_load_leveling.py
```

📚 **Documentación completa**: Ver [RESUMEN_QUEUE_LOAD_LEVELING.md](./RESUMEN_QUEUE_LOAD_LEVELING.md)

## 🔐 Gatekeeper + Federated Identity - Uso Rápido

Los patrones **Gatekeeper** y **Federated Identity** están implementados para proporcionar seguridad robusta:
- ✅ Control de acceso centralizado (API Gateway)
- ✅ Autenticación delegada a LDAP externo
- ✅ Validación de tokens JWT
- ✅ Control de permisos por roles (RBAC)
- ✅ Protección contra ataques (XSS, SQL Injection, Path Traversal)
- ✅ Rate Limiting (100 req/min por IP)

### Inicio Rápido

**1. Inicializar usuarios LDAP (primera vez):**
```bash
./scripts/init_ldap.sh
```

**2. Hacer login:**
```bash
# Login con usuario admin
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin_password"}'

# Respuesta con token JWT:
# {
#   "access_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 1800,
#   "user": { "username": "admin", "rol": "admin", ... }
# }
```

**3. Usar el token en requests protegidas:**
```bash
# Guardar token
TOKEN="eyJhbGc..."

# Hacer request protegida
curl -X GET http://localhost:8000/api/v1/proyectos \
  -H "Authorization: Bearer $TOKEN"

# Ver información del usuario
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Usuarios LDAP de Prueba

| Username   | Password          | Rol          | Permisos                    |
|-----------|-------------------|--------------|----------------------------|
| admin     | admin_password    | admin        | ✅ Acceso total            |
| manager   | manager_password  | manager      | ✅ Usuarios read/create    |
|           |                   |              | ✅ Proyectos y Tareas full |
| developer | developer_password| desarrollador| ✅ Solo lectura mayoría    |
| jdoe      | jdoe123           | manager      | ✅ Permisos de manager     |
| jsmith    | jsmith123         | desarrollador| ✅ Permisos de developer   |

### Administración LDAP

**phpLDAPadmin**: http://localhost:8082
- Login DN: `cn=admin,dc=example,dc=org`
- Password: `admin_password`

## 🎨 Demo Interactiva Web

**Interfaz visual profesional integrada en FastAPI** ⭐ **RECOMENDADA PARA PRESENTACIONES**

```
URL: http://localhost:8000/demo
```

**Características**:
- ✅ Diseño sobrio y profesional
- ✅ Dashboard con health check y estadísticas en tiempo real
- ✅ Demo automática completa con un solo clic
- ✅ Gestión visual de usuarios, proyectos y tareas
- ✅ Simulación de reintentos con backoff exponencial
- ✅ Panel de logs en tiempo real con colores
- ✅ Test de performance del pool de conexiones

**Uso**: 
1. Asegúrate de que la API esté corriendo: `docker-compose up -d`
2. Abre en tu navegador: `http://localhost:8000/demo`
3. Haz clic en "Ejecutar Demo Completa"

---

## 📜 Scripts de Demostración Alternativos

### Linux/Mac:
```bash
chmod +x scripts/demo_completa.sh
./scripts/demo_completa.sh
```

### Windows:
```cmd
scripts\demo_completa.bat
```

### Python (Interactivo):
```bash
python3 -m venv venv
source venv/bin/activate
pip install requests
python3 scripts/demo_retry.py
```

### Con Postman:
Importar la colección desde: http://localhost:8000/docs → "Download OpenAPI schema"

## Validaciones Implementadas

### Validaciones de Integridad
- **Emails únicos**: No se permiten usuarios con emails duplicados
- **Nombres de proyecto únicos**: Evita proyectos duplicados
- **Referencias válidas**: IDs de usuario/proyecto deben existir

### Validaciones Cruzadas
- **Asignación a proyecto**: Usuario debe existir antes de asignar
- **Responsable de tarea**: Usuario debe estar asignado al proyecto de la tarea
- **Eliminación en cascada**: Eliminar proyecto elimina sus tareas

### Validaciones de Negocio
- **Estados válidos**: Solo estados predefinidos para proyectos/tareas
- **Roles válidos**: Solo admin, manager, desarrollador
- **Prioridades válidas**: Solo alta, media, baja

## Tecnologías Utilizadas

- **Backend**: FastAPI 0.104.1
- **Base de Datos**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0.23
- **Validación**: Pydantic 2.5.0
- **Reintentos**: Tenacity 8.2.3
- **Contenedores**: Docker + docker-compose
- **Servidor**: Uvicorn
- **Administrador BD**: Adminer

## Métricas de Escalabilidad

- **Stateless**: ✅ Sin estado en memoria
- **Paginación**: ✅ Límite configurable de resultados
- **Conexiones BD**: ✅ Pool de conexiones optimizado
- **Health Checks**: ✅ Monitoreo de contenedores
- **Horizontal Scaling**: ✅ Múltiples instancias compatibles

## Comandos Docker Útiles

```bash
# Ver logs de la API
docker-compose logs api

# Ver logs de PostgreSQL
docker-compose logs db

# Reiniciar servicios
docker-compose restart

# Parar servicios
docker-compose down

# Limpiar volúmenes (¡Atención: elimina datos!)
docker-compose down -v

# Reconstruir imágenes
docker-compose build --no-cache
```

## ⚙️ External Configuration Store (Configuración Externa)

El proyecto implementa el patrón **External Configuration Store** para separar la configuración del código fuente.

### Configuración Rápida

**1. Crear archivo `.env` en la raíz del proyecto:**
```bash
touch .env
```

```env
# Base de Datos
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=gestor_proyectos
DATABASE_URL=postgresql://postgres:password@localhost:5433/gestor_proyectos

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
CACHE_TTL=300

# LDAP
LDAP_SERVER=ldap://localhost:389
LDAP_BASE_DN=dc=example,dc=org

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Aplicación
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development
```

### Módulo de Configuración

Toda la configuración se accede a través de `app/config.py`:

```python
from app.config import settings

# Acceder a variables
database_url = settings.DATABASE_URL
redis_host = settings.REDIS_HOST
jwt_secret = settings.JWT_SECRET_KEY
```

### Configuración por Entorno

El mismo código se puede desplegar en múltiples entornos con diferentes configuraciones:

- **Desarrollo Local**: `.env` con localhost
- **Docker**: `.env` con nombres de servicios Docker
- **Staging**: `.env` con servidores de staging
- **Producción**: `.env` con configuración productiva

### Variables Principales

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `DATABASE_URL` | URL de conexión a PostgreSQL | Auto-construida |
| `DB_MAX_RETRY_ATTEMPTS` | Reintentos de conexión | `5` |
| `REDIS_HOST` | Host de Redis | `localhost` |
| `CACHE_TTL` | TTL del caché (segundos) | `300` |
| `LDAP_SERVER` | Servidor LDAP | `ldap://localhost:389` |
| `JWT_SECRET_KEY` | Clave secreta JWT | ⚠️ Cambiar en producción |
| `API_PORT` | Puerto de la API | `8000` |
| `ENVIRONMENT` | Entorno de ejecución | `development` |
| `RATE_LIMIT_REQUESTS` | Límite de requests | `100` |

> 💡 **Tip**: Para producción, generar clave JWT segura con: `openssl rand -hex 32`

## Monitoreo y Logs

- **Health Check API**: http://localhost:8000/health
- **Logs en tiempo real**: `docker-compose logs -f`
- **Estado de contenedores**: `docker-compose ps`
- **Uso de recursos**: `docker stats`

## Evaluación de Conceptos

### Componentes e Interfaces
- [x] Separación clara en GestorUsuarios, GestorProyectos, GestorTareas
- [x] APIs REST bien definidas para cada componente
- [x] Interfaces consistentes con schemas Pydantic

### ACID
- [x] Transacciones explícitas con commit/rollback
- [x] Integridad referencial con claves foráneas
- [x] Validaciones para mantener consistencia
- [x] PostgreSQL como base ACID completa

### Escalabilidad Horizontal
- [x] API completamente stateless
- [x] Sin variables de sesión o estado compartido
- [x] Puede ejecutarse en múltiples instancias
- [x] Paginación para grandes volúmenes

### Contenedores
- [x] Dockerfile optimizado para producción
- [x] docker-compose con orquestación completa
- [x] Networking privado entre servicios
- [x] Volúmenes persistentes para datos
- [x] Health checks para monitoreo

### Alta Disponibilidad y Resiliencia
- [x] Sistema de retry con backoff exponencial
- [x] Reintentos automáticos en conexión inicial
- [x] Pool de conexiones optimizado
- [x] Health check con información de BD
- [x] Timeouts configurables
- [x] Logging detallado de reintentos
- [x] Configuración flexible vía variables de entorno

---

## Soporte

Para preguntas sobre la implementación o conceptos, revisar:
1. Documentación interactiva: http://localhost:8000/docs
2. Scripts de demostración en `/scripts/`
3. Logs de la aplicación: `docker-compose logs api`


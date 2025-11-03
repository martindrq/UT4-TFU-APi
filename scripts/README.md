# Scripts de Demostración - Mini Gestor de Proyectos API

Este directorio contiene scripts para demostrar todos los conceptos implementados en la API:

## 🧑‍💼 GestorUsuarios
- **Componente modular**: Gestión independiente de usuarios
- **CRUD completo**: Crear, leer, actualizar y eliminar usuarios
- **Validación de datos**: Emails únicos, roles válidos
- **Escalabilidad**: Paginación en listados

## 📋 GestorProyectos  
- **Interfaces claras**: Separación de responsabilidades
- **Relaciones**: Asignación muchos-a-muchos con usuarios
- **Validación cruzada**: Verificar existencia de usuarios antes de asignar

## ✅ GestorTareas
- **Servicios sin estado**: Cada request es independiente
- **Validación completa**: Usuario debe estar en proyecto para ser responsable
- **Integridad referencial**: Tareas pertenecen a proyectos válidos

## 🏗️ Conceptos Arquitectónicos Demostrados

### ACID (Atomicidad, Consistencia, Aislamiento, Durabilidad)
- Transacciones explícitas con commit/rollback
- Integridad referencial con claves foráneas
- Validaciones para mantener consistencia

### Escalabilidad Horizontal
- API stateless: sin estado en memoria
- Puede ejecutarse en múltiples instancias
- Base de datos centralizada para coherencia

### Contenedores
- Dockerfile optimizado para producción
- docker-compose para orquestación
- Networking y volúmenes persistentes
- Health checks para monitoreo

### Alta Disponibilidad y Resiliencia
- Sistema de retry con backoff exponencial
- Reconexión automática ante fallos de BD
- Pool de conexiones optimizado
- Tolerancia a fallos temporales

### Queue-Based Load Leveling (Nivelación de Carga)
- Cola de mensajes con Redis para desacoplar operaciones
- Procesamiento asíncrono en background con workers
- Respuesta rápida al cliente (< 50ms)
- Nivelación de carga bajo alta demanda
- Sistema de reintentos automáticos
- Seguimiento de estado de procesamiento

### Componentes e Interfaces
- Separación clara de responsabilidades
- APIs REST bien definidas
- Validación de entrada/salida con Pydantic
- Manejo de errores consistente

## 📁 Archivos de Scripts

### Scripts de Demostración
- `demo_completa.sh/bat`: Script completo de demostración de funcionalidad
- `test_usuarios.sh/bat`: Pruebas específicas de usuarios
- `test_proyectos.sh/bat`: Pruebas específicas de proyectos
- `test_tareas.sh/bat`: Pruebas específicas de tareas
- `test_validaciones.sh/bat`: Pruebas de validaciones cruzadas

### Scripts de Pruebas de Resiliencia
- **`test_retry.sh/bat`**: 🔄 Prueba del sistema de retry y reconexión automática
  - Prueba inicio normal con BD disponible
  - Simula reinicio de base de datos
  - Demuestra reintentos con backoff exponencial
  - Verifica recuperación automática

### Scripts de Queue-Based Load Leveling
- **`start_worker.sh/bat`**: ⚡ **Nuevo** - Inicia el worker de procesamiento en background
  - Consume mensajes de la cola Redis
  - Procesa creación de tareas asíncronamente
  - Maneja errores con reintentos automáticos
  - Shutdown graceful con CTRL+C
  
- **`demo_load_leveling.py`**: 🚀 **Nuevo** - Demostración del patrón de nivelación de carga
  - Crea múltiples tareas concurrentemente
  - Mide tiempos de respuesta y throughput
  - Monitorea estado de procesamiento
  - Estadísticas detalladas de rendimiento

## 🚀 Uso de Scripts

### Linux/Mac
```bash
chmod +x scripts/*.sh
./scripts/demo_completa.sh      # Demostración completa
./scripts/test_retry.sh         # Prueba sistema de retry
./scripts/start_worker.sh       # Iniciar worker de colas
python scripts/demo_load_leveling.py  # Demo de load leveling
```

### Windows
```cmd
scripts\demo_completa.bat       # Demostración completa
scripts\test_retry.bat          # Prueba sistema de retry
scripts\start_worker.bat        # Iniciar worker de colas
python scripts\demo_load_leveling.py  # Demo de load leveling
```

## 📚 Flujo de Queue-Based Load Leveling

1. **Iniciar Worker**: 
   ```bash
   ./scripts/start_worker.sh
   ```

2. **Crear Tareas** (el API encola automáticamente):
   ```bash
   curl -X POST http://localhost:8000/tareas/ \
     -H "Content-Type: application/json" \
     -d '{"titulo":"Mi tarea","proyecto_id":1}'
   # Retorna: {"job_id": "abc-123", "status": "pending"}
   ```

3. **Consultar Estado**:
   ```bash
   curl http://localhost:8000/tareas/jobs/abc-123
   # Retorna: {"status": "completed", "message": "..."}
   ```

4. **Obtener Resultado**:
   ```bash
   curl http://localhost:8000/tareas/jobs/abc-123/result
   # Retorna: {"result": {"id": 1, "titulo": "Mi tarea", ...}}
   ```
#!/bin/bash

# Script para iniciar el worker de procesamiento de tareas
# Patrón Queue-Based Load Leveling

echo "=================================================="
echo "  Iniciando Worker - Queue-Based Load Leveling"
echo "=================================================="

# Cambiar al directorio del proyecto
cd "$(dirname "$0")/.." || exit

# Verificar que existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual (venv)"
    echo "   Ejecute: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activar entorno virtual
echo "🔧 Activando entorno virtual..."
source venv/bin/activate

# Verificar que Redis está disponible
echo "🔍 Verificando conexión a Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Advertencia: Redis no está disponible en localhost:6379"
    echo "   Asegúrese de que Redis está ejecutándose o configure REDIS_HOST/REDIS_PORT"
    echo ""
fi

# Configurar variables de entorno
export REDIS_HOST=${REDIS_HOST:-localhost}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_DB_QUEUE=${REDIS_DB_QUEUE:-1}

# Configurar base de datos (usar puerto 5433 que es el mapeado en docker-compose)
export DATABASE_URL=${DATABASE_URL:-postgresql://postgres:password@localhost:5433/gestor_proyectos}

echo ""
echo "📋 Configuración:"
echo "   Redis: $REDIS_HOST:$REDIS_PORT (DB $REDIS_DB_QUEUE)"
echo "   PostgreSQL: localhost:5433"
echo ""

# Ejecutar worker
echo "🚀 Iniciando worker..."
python -m app.worker

# Mensaje de salida
echo ""
echo "👋 Worker detenido"


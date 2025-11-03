"""
Módulo de gestión de colas para patrón Queue-Based Load Leveling.
Utiliza Redis como broker de mensajes para desacoplar la recepción 
de solicitudes de su procesamiento.
"""

import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
import redis
import os

# Configuración de Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB_QUEUE = int(os.getenv("REDIS_DB_QUEUE", "1"))  # DB separada para colas

# Nombres de colas
TAREA_QUEUE = "tareas:queue"
JOB_STATUS_PREFIX = "job:status:"
JOB_RESULT_PREFIX = "job:result:"

# TTL para estados de jobs (1 hora)
JOB_TTL = 3600

# Conexión a Redis para colas
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB_QUEUE,
        decode_responses=True,
        socket_connect_timeout=5
    )
    # Verificar conexión
    redis_client.ping()
    print(f"✓ Conexión exitosa a Redis Queue (DB {REDIS_DB_QUEUE})")
except redis.ConnectionError as e:
    print(f"✗ Error al conectar con Redis Queue: {e}")
    redis_client = None


class JobStatus:
    """Estados posibles de un job"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def enqueue_tarea_creation(tarea_data: Dict[str, Any]) -> str:
    """
    Encolar solicitud de creación de tarea.
    
    Args:
        tarea_data: Datos de la tarea a crear
        
    Returns:
        job_id: ID único del job para seguimiento
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    # Generar ID único para el job
    job_id = str(uuid.uuid4())
    
    # Preparar mensaje
    message = {
        "job_id": job_id,
        "type": "create_tarea",
        "data": tarea_data,
        "timestamp": datetime.utcnow().isoformat(),
        "retry_count": 0
    }
    
    # Guardar estado inicial del job
    job_status = {
        "status": JobStatus.PENDING,
        "job_id": job_id,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "message": "Solicitud encolada, esperando procesamiento"
    }
    
    redis_client.setex(
        f"{JOB_STATUS_PREFIX}{job_id}",
        JOB_TTL,
        json.dumps(job_status)
    )
    
    # Encolar mensaje en la cola de tareas
    redis_client.rpush(TAREA_QUEUE, json.dumps(message))
    
    return job_id


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtener estado actual de un job.
    
    Args:
        job_id: ID del job
        
    Returns:
        Estado del job o None si no existe
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    status_data = redis_client.get(f"{JOB_STATUS_PREFIX}{job_id}")
    
    if not status_data:
        return None
    
    return json.loads(status_data)


def get_job_result(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtener resultado de un job completado.
    
    Args:
        job_id: ID del job
        
    Returns:
        Resultado del job o None si no existe
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    result_data = redis_client.get(f"{JOB_RESULT_PREFIX}{job_id}")
    
    if not result_data:
        return None
    
    return json.loads(result_data)


def update_job_status(
    job_id: str, 
    status: str, 
    message: str, 
    error: Optional[str] = None
) -> None:
    """
    Actualizar estado de un job.
    
    Args:
        job_id: ID del job
        status: Nuevo estado (pending, processing, completed, failed)
        message: Mensaje descriptivo
        error: Mensaje de error (opcional)
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    job_status = {
        "status": status,
        "job_id": job_id,
        "updated_at": datetime.utcnow().isoformat(),
        "message": message
    }
    
    if error:
        job_status["error"] = error
    
    redis_client.setex(
        f"{JOB_STATUS_PREFIX}{job_id}",
        JOB_TTL,
        json.dumps(job_status)
    )


def save_job_result(job_id: str, result: Dict[str, Any]) -> None:
    """
    Guardar resultado de un job completado.
    
    Args:
        job_id: ID del job
        result: Resultado del procesamiento
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    redis_client.setex(
        f"{JOB_RESULT_PREFIX}{job_id}",
        JOB_TTL,
        json.dumps(result)
    )


def get_queue_size() -> int:
    """
    Obtener tamaño actual de la cola de tareas.
    
    Returns:
        Número de mensajes pendientes en la cola
    """
    if not redis_client:
        return 0
    
    return redis_client.llen(TAREA_QUEUE)


def dequeue_tarea_creation() -> Optional[Dict[str, Any]]:
    """
    Extraer siguiente mensaje de la cola de tareas (operación bloqueante con timeout).
    
    Returns:
        Mensaje de la cola o None si timeout
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    # BLPOP: operación bloqueante con timeout de 5 segundos
    result = redis_client.blpop(TAREA_QUEUE, timeout=5)
    
    if result:
        queue_name, message_data = result
        return json.loads(message_data)
    
    return None


def requeue_tarea_creation(message: Dict[str, Any], max_retries: int = 3) -> bool:
    """
    Reencolar mensaje que falló en el procesamiento.
    
    Args:
        message: Mensaje original
        max_retries: Número máximo de reintentos
        
    Returns:
        True si se reencoló, False si excedió reintentos
    """
    if not redis_client:
        raise Exception("Redis no está disponible")
    
    retry_count = message.get("retry_count", 0) + 1
    
    if retry_count > max_retries:
        # Marcar job como fallido
        update_job_status(
            message["job_id"],
            JobStatus.FAILED,
            f"Job fallido después de {max_retries} reintentos",
            error="Máximo de reintentos excedido"
        )
        return False
    
    # Actualizar contador de reintentos
    message["retry_count"] = retry_count
    message["last_retry_at"] = datetime.utcnow().isoformat()
    
    # Reencolar mensaje
    redis_client.rpush(TAREA_QUEUE, json.dumps(message))
    
    return True


def get_queue_stats() -> Dict[str, Any]:
    """
    Obtener estadísticas de la cola.
    
    Returns:
        Diccionario con estadísticas
    """
    if not redis_client:
        return {
            "queue_size": 0,
            "redis_available": False
        }
    
    return {
        "queue_size": get_queue_size(),
        "redis_available": True,
        "queue_name": TAREA_QUEUE
    }


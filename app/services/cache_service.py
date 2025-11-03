"""
Módulo de caché usando Redis - Implementa patrón Cache-Aside
Proporciona funciones para optimizar consultas frecuentes reduciendo carga en la base de datos.
"""

import json
import redis
from typing import Optional, Any, Union
from datetime import datetime

# Importar configuración centralizada (External Configuration Store Pattern)
from app.config import settings

# Configuración de Redis desde configuración externa
REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT
CACHE_TTL = settings.CACHE_TTL

# Cliente Redis global
redis_client: Optional[redis.Redis] = None


def init_redis() -> redis.Redis:
    """
    Inicializar conexión a Redis con reintentos.
    Se llama al inicio de la aplicación.
    """
    global redis_client
    
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Verificar conexión
        redis_client.ping()
        print(f"✅ Redis conectado exitosamente en {REDIS_HOST}:{REDIS_PORT}")
        return redis_client
        
    except redis.ConnectionError as e:
        print(f"⚠️  Advertencia: No se pudo conectar a Redis: {str(e)}")
        print("⚠️  La aplicación continuará sin caché")
        redis_client = None
        return None
    except Exception as e:
        print(f"⚠️  Error inesperado al conectar Redis: {str(e)}")
        redis_client = None
        return None


def close_redis():
    """
    Cerrar conexión a Redis.
    Se llama al apagar la aplicación.
    """
    global redis_client
    
    if redis_client:
        try:
            redis_client.close()
            print("🛑 Conexión Redis cerrada")
        except Exception as e:
            print(f"⚠️  Error al cerrar Redis: {str(e)}")
    
    redis_client = None


def get_redis() -> Optional[redis.Redis]:
    """
    Obtener cliente Redis activo.
    Retorna None si Redis no está disponible.
    """
    return redis_client


def serialize_value(value: Any) -> str:
    """
    Serializar valor para almacenar en Redis.
    Maneja objetos complejos convirtiéndolos a JSON.
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def deserialize_value(value: str, value_type: type = dict) -> Any:
    """
    Deserializar valor desde Redis.
    """
    try:
        if value_type in (dict, list):
            return json.loads(value)
        return value
    except json.JSONDecodeError:
        return value


def get_from_cache(key: str) -> Optional[Any]:
    """
    Obtener valor desde la caché.
    
    Args:
        key: Clave de caché
        
    Returns:
        Valor deserializado o None si no existe o Redis no está disponible
    """
    if not redis_client:
        return None
    
    try:
        value = redis_client.get(key)
        if value:
            print(f"🎯 Cache HIT: {key}")
            return deserialize_value(value)
        print(f"❌ Cache MISS: {key}")
        return None
    except redis.RedisError as e:
        print(f"⚠️  Error al leer de caché {key}: {str(e)}")
        return None


def set_in_cache(key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
    """
    Guardar valor en la caché con TTL (Time To Live).
    
    Args:
        key: Clave de caché
        value: Valor a almacenar
        ttl: Tiempo de vida en segundos (default: CACHE_TTL)
        
    Returns:
        True si se guardó exitosamente, False en caso contrario
    """
    if not redis_client:
        return False
    
    try:
        serialized = serialize_value(value)
        redis_client.setex(key, ttl, serialized)
        print(f"💾 Cache SET: {key} (TTL: {ttl}s)")
        return True
    except redis.RedisError as e:
        print(f"⚠️  Error al escribir en caché {key}: {str(e)}")
        return False


def delete_from_cache(key: str) -> bool:
    """
    Eliminar una clave específica de la caché.
    
    Args:
        key: Clave de caché a eliminar
        
    Returns:
        True si se eliminó exitosamente, False en caso contrario
    """
    if not redis_client:
        return False
    
    try:
        deleted = redis_client.delete(key)
        if deleted:
            print(f"🗑️  Cache DELETE: {key}")
        return deleted > 0
    except redis.RedisError as e:
        print(f"⚠️  Error al eliminar de caché {key}: {str(e)}")
        return False


def invalidate_pattern(pattern: str) -> int:
    """
    Invalidar múltiples claves que coincidan con un patrón.
    Útil para invalidar caché relacionada (ej: todos los proyectos).
    
    Args:
        pattern: Patrón de búsqueda (ej: "proyectos:*")
        
    Returns:
        Número de claves eliminadas
    """
    if not redis_client:
        return 0
    
    try:
        keys = redis_client.keys(pattern)
        if keys:
            deleted = redis_client.delete(*keys)
            print(f"🗑️  Cache INVALIDATE: {pattern} ({deleted} claves)")
            return deleted
        return 0
    except redis.RedisError as e:
        print(f"⚠️  Error al invalidar patrón {pattern}: {str(e)}")
        return 0


def build_cache_key(*parts: Union[str, int]) -> str:
    """
    Construir clave de caché consistente a partir de múltiples partes.
    
    Args:
        *parts: Partes de la clave (ej: "proyectos", "list", "skip=0")
        
    Returns:
        Clave formateada (ej: "proyectos:list:skip=0")
    """
    return ":".join(str(part) for part in parts)


# Funciones específicas para el dominio de la aplicación

def get_proyecto_from_cache(proyecto_id: int) -> Optional[dict]:
    """
    Obtener proyecto específico desde caché (patrón Cache-Aside).
    """
    key = build_cache_key("proyecto", proyecto_id)
    return get_from_cache(key)


def set_proyecto_in_cache(proyecto_id: int, proyecto_data: dict) -> bool:
    """
    Guardar proyecto en caché.
    """
    key = build_cache_key("proyecto", proyecto_id)
    return set_in_cache(key, proyecto_data)


def invalidate_proyecto_cache(proyecto_id: int = None):
    """
    Invalidar caché de proyectos.
    Si se proporciona proyecto_id, invalida solo ese proyecto.
    Si no, invalida todos los proyectos.
    """
    if proyecto_id:
        key = build_cache_key("proyecto", proyecto_id)
        delete_from_cache(key)
    
    # Invalidar lista de proyectos (cualquier filtro/paginación)
    invalidate_pattern("proyectos:list:*")


def get_proyectos_list_from_cache(skip: int, limit: int, estado: Optional[str] = None) -> Optional[list]:
    """
    Obtener lista de proyectos desde caché.
    """
    key_parts = ["proyectos", "list", f"skip={skip}", f"limit={limit}"]
    if estado:
        key_parts.append(f"estado={estado}")
    
    key = build_cache_key(*key_parts)
    return get_from_cache(key)


def set_proyectos_list_in_cache(proyectos_data: list, skip: int, limit: int, estado: Optional[str] = None) -> bool:
    """
    Guardar lista de proyectos en caché.
    """
    key_parts = ["proyectos", "list", f"skip={skip}", f"limit={limit}"]
    if estado:
        key_parts.append(f"estado={estado}")
    
    key = build_cache_key(*key_parts)
    return set_in_cache(key, proyectos_data)


def get_tarea_from_cache(tarea_id: int) -> Optional[dict]:
    """
    Obtener tarea específica desde caché (patrón Cache-Aside).
    """
    key = build_cache_key("tarea", tarea_id)
    return get_from_cache(key)


def set_tarea_in_cache(tarea_id: int, tarea_data: dict) -> bool:
    """
    Guardar tarea en caché.
    """
    key = build_cache_key("tarea", tarea_id)
    return set_in_cache(key, tarea_data)


def invalidate_tarea_cache(tarea_id: int = None):
    """
    Invalidar caché de tareas.
    Si se proporciona tarea_id, invalida solo esa tarea.
    Si no, invalida todas las tareas.
    """
    if tarea_id:
        key = build_cache_key("tarea", tarea_id)
        delete_from_cache(key)
    
    # Invalidar lista de tareas (cualquier filtro/paginación)
    invalidate_pattern("tareas:list:*")


def get_tareas_list_from_cache(
    skip: int, 
    limit: int, 
    proyecto_id: Optional[int] = None,
    estado: Optional[str] = None,
    usuario_responsable_id: Optional[int] = None
) -> Optional[list]:
    """
    Obtener lista de tareas desde caché.
    """
    key_parts = ["tareas", "list", f"skip={skip}", f"limit={limit}"]
    if proyecto_id:
        key_parts.append(f"proyecto={proyecto_id}")
    if estado:
        key_parts.append(f"estado={estado}")
    if usuario_responsable_id:
        key_parts.append(f"usuario={usuario_responsable_id}")
    
    key = build_cache_key(*key_parts)
    return get_from_cache(key)


def set_tareas_list_in_cache(
    tareas_data: list, 
    skip: int, 
    limit: int,
    proyecto_id: Optional[int] = None,
    estado: Optional[str] = None,
    usuario_responsable_id: Optional[int] = None
) -> bool:
    """
    Guardar lista de tareas en caché.
    """
    key_parts = ["tareas", "list", f"skip={skip}", f"limit={limit}"]
    if proyecto_id:
        key_parts.append(f"proyecto={proyecto_id}")
    if estado:
        key_parts.append(f"estado={estado}")
    if usuario_responsable_id:
        key_parts.append(f"usuario={usuario_responsable_id}")
    
    key = build_cache_key(*key_parts)
    return set_in_cache(key, tareas_data)


def get_cache_stats() -> dict:
    """
    Obtener estadísticas de la caché.
    Útil para monitoreo y debugging.
    """
    if not redis_client:
        return {
            "available": False,
            "message": "Redis no está disponible"
        }
    
    try:
        info = redis_client.info()
        return {
            "available": True,
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "total_keys": redis_client.dbsize(),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0) / 
                (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
            ) * 100
        }
    except redis.RedisError as e:
        return {
            "available": False,
            "error": str(e)
        }


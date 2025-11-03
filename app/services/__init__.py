"""
Capa de servicios - Lógica de negocio
"""
from .cache_service import (
    init_redis,
    close_redis,
    get_redis,
    get_from_cache,
    set_in_cache,
    delete_from_cache,
    invalidate_pattern,
    build_cache_key,
    get_proyecto_from_cache,
    set_proyecto_in_cache,
    invalidate_proyecto_cache,
    get_proyectos_list_from_cache,
    set_proyectos_list_in_cache,
    get_tarea_from_cache,
    set_tarea_in_cache,
    invalidate_tarea_cache,
    get_tareas_list_from_cache,
    set_tareas_list_in_cache,
    get_cache_stats
)

from .queue_service import (
    JobStatus,
    enqueue_tarea_creation,
    get_job_status,
    get_job_result,
    update_job_status,
    save_job_result,
    get_queue_size,
    dequeue_tarea_creation,
    requeue_tarea_creation,
    get_queue_stats,
    TAREA_QUEUE,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB_QUEUE
)

from .auth_service import (
    LDAPAuthService,
    TokenService,
    ldap_service,
    token_service,
    get_ldap_service,
    get_token_service
)

__all__ = [
    # Cache
    "init_redis",
    "close_redis",
    "get_redis",
    "get_from_cache",
    "set_in_cache",
    "delete_from_cache",
    "invalidate_pattern",
    "build_cache_key",
    "get_proyecto_from_cache",
    "set_proyecto_in_cache",
    "invalidate_proyecto_cache",
    "get_proyectos_list_from_cache",
    "set_proyectos_list_in_cache",
    "get_tarea_from_cache",
    "set_tarea_in_cache",
    "invalidate_tarea_cache",
    "get_tareas_list_from_cache",
    "set_tareas_list_in_cache",
    "get_cache_stats",
    
    # Queue
    "JobStatus",
    "enqueue_tarea_creation",
    "get_job_status",
    "get_job_result",
    "update_job_status",
    "save_job_result",
    "get_queue_size",
    "dequeue_tarea_creation",
    "requeue_tarea_creation",
    "get_queue_stats",
    "TAREA_QUEUE",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_DB_QUEUE",
    
    # Auth
    "LDAPAuthService",
    "TokenService",
    "ldap_service",
    "token_service",
    "get_ldap_service",
    "get_token_service"
]


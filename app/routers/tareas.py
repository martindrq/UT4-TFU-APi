"""
Router para gestión de tareas - Componente GestorTareas
Implementa endpoints CRUD con validaciones cruzadas entre usuarios y proyectos.
Servicio sin estado (stateless) - cada request es independiente.
Incluye patrón Cache-Aside para optimización de consultas frecuentes.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import get_db
from app.models import Tarea, Usuario, Proyecto
from app.schemas import (
    TareaCreate, TareaUpdate, TareaResponse, 
    AsignarUsuarioTarea, ErrorResponse, SuccessResponse,
    JobResponse, JobStatusResponse, JobResultResponse
)
from app.services import cache_service as cache
from app.services import queue_service as queue

router = APIRouter(
    prefix="/tareas",
    tags=["tareas"],
    responses={404: {"model": ErrorResponse}},
)

@router.post("/", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def crear_tarea(
    tarea: TareaCreate,
    db: Session = Depends(get_db)
):
    """
    Encolar solicitud de creación de tarea (Queue-Based Load Leveling).
    
    **Patrón Queue-Based Load Leveling aplicado:**
    1. Valida que el proyecto exista (pre-validación rápida)
    2. Encola la solicitud en Redis para procesamiento asíncrono
    3. Retorna inmediatamente con un job_id para seguimiento
    4. Un worker en background procesa la cola y crea las tareas
    
    **Beneficios:**
    - Respuesta inmediata al cliente (< 50ms)
    - Nivelación de carga bajo alta demanda
    - Evita sobrecarga del sistema con picos de tráfico
    - Procesamiento confiable con reintentos automáticos
    
    - **titulo**: Título de la tarea (3-200 caracteres)
    - **descripcion**: Descripción opcional de la tarea
    - **estado**: Estado de la tarea (pendiente, en_progreso, completada)
    - **prioridad**: Prioridad de la tarea (alta, media, baja)
    - **fecha_vencimiento**: Fecha de vencimiento (opcional)
    - **proyecto_id**: ID del proyecto al que pertenece (requerido)
    
    **Retorna:**
    - **job_id**: ID único para consultar el estado del procesamiento
    - **status**: Estado inicial (pending)
    - **message**: Mensaje descriptivo
    """
    # Pre-validación: verificar que el proyecto existe
    # Esto evita encolar solicitudes inválidas
    proyecto = db.query(Proyecto).filter(Proyecto.id == tarea.proyecto_id).first()
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proyecto con ID {tarea.proyecto_id} no encontrado"
        )
    
    try:
        # Convertir a dict para serialización en cola
        tarea_data = tarea.model_dump()
        
        # Encolar solicitud para procesamiento asíncrono
        job_id = queue.enqueue_tarea_creation(tarea_data)
        
        # Obtener tamaño de cola para informar posición aproximada
        queue_size = queue.get_queue_size()
        
        return JobResponse(
            job_id=job_id,
            message=f"Solicitud encolada exitosamente. Use GET /tareas/jobs/{job_id} para consultar el estado.",
            status=queue.JobStatus.PENDING,
            queue_position=queue_size
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al encolar solicitud: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def obtener_estado_job(job_id: str):
    """
    Consultar el estado de un job de creación de tarea.
    
    **Estados posibles:**
    - **pending**: Encolado, esperando procesamiento
    - **processing**: Siendo procesado por el worker
    - **completed**: Completado exitosamente
    - **failed**: Falló el procesamiento
    
    - **job_id**: ID único del job (retornado al crear la tarea)
    """
    try:
        job_status = queue.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job con ID {job_id} no encontrado o expiró (TTL: 1 hora)"
            )
        
        return JobStatusResponse(**job_status)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar estado del job: {str(e)}"
        )


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
async def obtener_resultado_job(job_id: str):
    """
    Obtener el resultado de un job completado (tarea creada).
    
    Este endpoint retorna la tarea creada si el job fue exitoso,
    o el error si el job falló.
    
    - **job_id**: ID único del job
    """
    try:
        # Obtener estado del job
        job_status = queue.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job con ID {job_id} no encontrado o expiró"
            )
        
        # Si está completado, obtener resultado
        if job_status["status"] == queue.JobStatus.COMPLETED:
            result = queue.get_job_result(job_id)
            
            return JobResultResponse(
                job_id=job_id,
                status=queue.JobStatus.COMPLETED,
                result=result.get("tarea") if result else None
            )
        
        # Si falló, retornar error
        elif job_status["status"] == queue.JobStatus.FAILED:
            return JobResultResponse(
                job_id=job_id,
                status=queue.JobStatus.FAILED,
                error=job_status.get("error", "Error desconocido")
            )
        
        # Si está pendiente o procesando
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job aún está en estado '{job_status['status']}'. Use GET /tareas/jobs/{job_id} para consultar el estado."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener resultado del job: {str(e)}"
        )


@router.get("/queue/stats")
async def obtener_estadisticas_cola():
    """
    Obtener estadísticas de la cola de procesamiento.
    
    Útil para monitoreo y observabilidad del sistema.
    
    **Retorna:**
    - **queue_size**: Número de tareas pendientes en la cola
    - **redis_available**: Estado de conexión a Redis
    - **queue_name**: Nombre de la cola
    """
    try:
        stats = queue.get_queue_stats()
        return {
            "message": "Estadísticas de cola obtenidas exitosamente",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas: {str(e)}"
        )


@router.get("/", response_model=List[TareaResponse])
async def listar_tareas(
    skip: int = 0,
    limit: int = 100,
    proyecto_id: int = None,
    estado: str = None,
    usuario_responsable_id: int = None,
    db: Session = Depends(get_db)
):
    """
    Obtener lista de todas las tareas con filtros opcionales.
    Soporta filtrado por proyecto, estado, usuario responsable y paginación.
    
    **Patrón Cache-Aside aplicado:**
    1. Intenta obtener datos desde Redis
    2. Si no existe en caché (cache miss), consulta PostgreSQL
    3. Guarda resultado en caché para futuras consultas
    
    - **skip**: Número de registros a omitir (default: 0)
    - **limit**: Número máximo de registros a devolver (default: 100)
    - **proyecto_id**: Filtrar por proyecto específico
    - **estado**: Filtrar por estado (pendiente, en_progreso, completada)
    - **usuario_responsable_id**: Filtrar por usuario responsable
    """
    #Intentar obtener desde caché (Cache-Aside)
    cached_tareas = cache.get_tareas_list_from_cache(
        skip, limit, proyecto_id, estado, usuario_responsable_id
    )
    if cached_tareas is not None:
        return cached_tareas
    
    #Si no está en caché, consultar base de datos
    query = db.query(Tarea)
    
    # Aplicar filtros
    if proyecto_id:
        query = query.filter(Tarea.proyecto_id == proyecto_id)
    if estado:
        query = query.filter(Tarea.estado == estado)
    if usuario_responsable_id:
        query = query.filter(Tarea.usuario_responsable_id == usuario_responsable_id)
    
    tareas = query.offset(skip).limit(limit).all()
    
    # PASO 3: Convertir a dict para serialización y guardar en caché
    tareas_dict = [
        {
            "id": t.id,
            "titulo": t.titulo,
            "descripcion": t.descripcion,
            "estado": t.estado,
            "prioridad": t.prioridad,
            "fecha_creacion": t.fecha_creacion.isoformat() if t.fecha_creacion else None,
            "fecha_vencimiento": t.fecha_vencimiento.isoformat() if t.fecha_vencimiento else None,
            "proyecto_id": t.proyecto_id,
            "usuario_responsable_id": t.usuario_responsable_id,
            "usuario_responsable": {
                "id": t.usuario_responsable.id,
                "nombre": t.usuario_responsable.nombre,
                "email": t.usuario_responsable.email,
                "rol": t.usuario_responsable.rol
            } if t.usuario_responsable else None,
            "proyecto": {
                "id": t.proyecto.id,
                "nombre": t.proyecto.nombre,
                "estado": t.proyecto.estado
            } if t.proyecto else None
        } for t in tareas
    ]
    
    cache.set_tareas_list_in_cache(
        tareas_dict, skip, limit, proyecto_id, estado, usuario_responsable_id
    )
    
    return tareas

@router.get("/{tarea_id}", response_model=TareaResponse)
async def obtener_tarea(
    tarea_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener información detallada de una tarea específica.
    Incluye información del usuario responsable si está asignado.
    
    **Patrón Cache-Aside aplicado:**
    1. Intenta obtener datos desde Redis
    2. Si no existe en caché (cache miss), consulta PostgreSQL
    3. Guarda resultado en caché para futuras consultas
    
    - **tarea_id**: ID único de la tarea
    """
    # PASO 1: Intentar obtener desde caché (Cache-Aside)
    cached_tarea = cache.get_tarea_from_cache(tarea_id)
    if cached_tarea is not None:
        return cached_tarea
    
    # PASO 2: Si no está en caché, consultar base de datos
    tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    
    if not tarea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea con ID {tarea_id} no encontrada"
        )
    
    # PASO 3: Convertir a dict para serialización y guardar en caché
    tarea_dict = {
        "id": tarea.id,
        "titulo": tarea.titulo,
        "descripcion": tarea.descripcion,
        "estado": tarea.estado,
        "prioridad": tarea.prioridad,
        "fecha_creacion": tarea.fecha_creacion.isoformat() if tarea.fecha_creacion else None,
        "fecha_vencimiento": tarea.fecha_vencimiento.isoformat() if tarea.fecha_vencimiento else None,
        "proyecto_id": tarea.proyecto_id,
        "usuario_responsable_id": tarea.usuario_responsable_id,
        "usuario_responsable": {
            "id": tarea.usuario_responsable.id,
            "nombre": tarea.usuario_responsable.nombre,
            "email": tarea.usuario_responsable.email,
            "rol": tarea.usuario_responsable.rol
        } if tarea.usuario_responsable else None,
        "proyecto": {
            "id": tarea.proyecto.id,
            "nombre": tarea.proyecto.nombre,
            "estado": tarea.proyecto.estado
        } if tarea.proyecto else None
    }
    
    cache.set_tarea_in_cache(tarea_id, tarea_dict)
    
    return tarea

@router.put("/{tarea_id}", response_model=TareaResponse)
async def actualizar_tarea(
    tarea_id: int,
    tarea_update: TareaUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar información de una tarea existente.
    Solo actualiza los campos proporcionados (PATCH semantics).
    Valida proyecto_id si se proporciona.
    
    - **tarea_id**: ID único de la tarea
    - **titulo**: Nuevo título (opcional)
    - **descripcion**: Nueva descripción (opcional)
    - **estado**: Nuevo estado (opcional)
    - **prioridad**: Nueva prioridad (opcional)
    - **fecha_vencimiento**: Nueva fecha de vencimiento (opcional)
    - **proyecto_id**: Nuevo proyecto (opcional)
    """
    # Buscar tarea existente
    db_tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    
    if not db_tarea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea con ID {tarea_id} no encontrada"
        )
    
    try:
        # Actualizar solo los campos proporcionados
        update_data = tarea_update.model_dump(exclude_unset=True)
        
        # Validar proyecto_id si se está actualizando
        if "proyecto_id" in update_data:
            proyecto = db.query(Proyecto).filter(Proyecto.id == update_data["proyecto_id"]).first()
            if not proyecto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Proyecto con ID {update_data['proyecto_id']} no encontrado"
                )
        
        # Aplicar actualizaciones
        for field, value in update_data.items():
            setattr(db_tarea, field, value)
        
        db.commit()  # Commit explícito para ACID
        db.refresh(db_tarea)
        
        # Invalidar caché de la tarea actualizada
        cache.invalidate_tarea_cache(tarea_id)
        
        return db_tarea
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error de integridad en la base de datos"
        )

@router.delete("/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_tarea(
    tarea_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar una tarea del sistema.
    
    - **tarea_id**: ID único de la tarea a eliminar
    """
    db_tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    
    if not db_tarea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea con ID {tarea_id} no encontrada"
        )
    
    try:
        db.delete(db_tarea)
        db.commit()  # Commit explícito para ACID
        
        # Invalidar caché de la tarea eliminada
        cache.invalidate_tarea_cache(tarea_id)
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar la tarea debido a dependencias"
        )

@router.post("/{tarea_id}/asignar_usuario", response_model=SuccessResponse)
async def asignar_usuario_tarea(
    tarea_id: int,
    asignacion: AsignarUsuarioTarea,
    db: Session = Depends(get_db)
):
    """
    Asignar un usuario responsable a una tarea.
    Valida que tanto la tarea como el usuario existan y que el usuario
    esté asignado al proyecto de la tarea (validación cruzada completa).
    
    - **tarea_id**: ID único de la tarea
    - **usuario_id**: ID único del usuario a asignar como responsable
    """
    # Verificar que la tarea existe
    tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if not tarea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea con ID {tarea_id} no encontrada"
        )
    
    # Verificar que el usuario existe (validación cruzada con GestorUsuarios)
    usuario = db.query(Usuario).filter(Usuario.id == asignacion.usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {asignacion.usuario_id} no encontrado"
        )
    
    # Verificar que el usuario está asignado al proyecto de la tarea
    # (validación cruzada completa entre los tres componentes)
    proyecto = tarea.proyecto
    if usuario not in proyecto.usuarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {usuario.nombre} no está asignado al proyecto {proyecto.nombre}. " +
                   f"Debe asignarse al proyecto antes de asignar tareas."
        )
    
    # Verificar si la tarea ya tiene un responsable asignado
    if tarea.usuario_responsable_id is not None:
        usuario_actual = db.query(Usuario).filter(Usuario.id == tarea.usuario_responsable_id).first()
        if usuario_actual:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La tarea ya tiene asignado como responsable a {usuario_actual.nombre}. " +
                       f"Use PUT para cambiar el responsable."
            )
    
    try:
        # Asignar usuario responsable a la tarea
        tarea.usuario_responsable_id = asignacion.usuario_id
        db.commit()  # Commit explícito para ACID
        
        # Invalidar caché de la tarea modificada
        cache.invalidate_tarea_cache(tarea_id)
        
        return SuccessResponse(
            message=f"Usuario {usuario.nombre} asignado como responsable de la tarea '{tarea.titulo}'",
            data={
                "tarea_id": tarea_id,
                "usuario_id": asignacion.usuario_id,
                "tarea_titulo": tarea.titulo,
                "usuario_nombre": usuario.nombre,
                "proyecto_nombre": proyecto.nombre
            }
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al asignar usuario responsable a la tarea"
        )

@router.delete("/{tarea_id}/desasignar_usuario", response_model=SuccessResponse)
async def desasignar_usuario_tarea(
    tarea_id: int,
    db: Session = Depends(get_db)
):
    """
    Desasignar el usuario responsable de una tarea.
    
    - **tarea_id**: ID único de la tarea
    """
    # Verificar que la tarea existe
    tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if not tarea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea con ID {tarea_id} no encontrada"
        )
    
    # Verificar si la tarea tiene un responsable asignado
    if tarea.usuario_responsable_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La tarea '{tarea.titulo}' no tiene un usuario responsable asignado"
        )
    
    # Obtener información del usuario antes de desasignar
    usuario_responsable = tarea.usuario_responsable
    usuario_nombre = usuario_responsable.nombre if usuario_responsable else "Usuario eliminado"
    
    try:
        # Desasignar usuario responsable
        tarea.usuario_responsable_id = None
        db.commit()  # Commit explícito para ACID
        
        # Invalidar caché de la tarea modificada
        cache.invalidate_tarea_cache(tarea_id)
        
        return SuccessResponse(
            message=f"Usuario {usuario_nombre} desasignado como responsable de la tarea '{tarea.titulo}'",
            data={
                "tarea_id": tarea_id,
                "tarea_titulo": tarea.titulo,
                "usuario_anterior": usuario_nombre
            }
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al desasignar usuario responsable de la tarea"
        )
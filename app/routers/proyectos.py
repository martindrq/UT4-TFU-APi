"""
Router para gestión de proyectos - Componente GestorProyectos
Implementa endpoints CRUD y asignación de usuarios con validaciones cruzadas.
Servicio sin estado (stateless) - cada request es independiente.
Incluye patrón Cache-Aside para optimización de consultas frecuentes.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import get_db
from app.models import Proyecto, Usuario
from app.schemas import (
    ProyectoCreate, ProyectoUpdate, ProyectoResponse, 
    AsignarUsuarioProyecto, ErrorResponse, SuccessResponse
)
from app.services import cache_service as cache

router = APIRouter(
    prefix="/proyectos",
    tags=["proyectos"],
    responses={404: {"model": ErrorResponse}},
)

@router.post("/", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
async def crear_proyecto(
    proyecto: ProyectoCreate,
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo proyecto en el sistema.
    
    - **nombre**: Nombre del proyecto (3-200 caracteres)
    - **descripcion**: Descripción opcional del proyecto
    - **estado**: Estado del proyecto (activo, pausado, completado)
    - **fecha_fin**: Fecha de finalización estimada (opcional)
    """
    try:
        # Verificar si ya existe un proyecto con el mismo nombre
        proyecto_existente = db.query(Proyecto).filter(Proyecto.nombre == proyecto.nombre).first()
        if proyecto_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un proyecto con el nombre '{proyecto.nombre}'"
            )
        
        # Crear nuevo proyecto
        db_proyecto = Proyecto(**proyecto.model_dump())
        db.add(db_proyecto)
        db.commit()  # Commit explícito para ACID
        db.refresh(db_proyecto)
        
        # Invalidar caché de listas de proyectos
        cache.invalidate_proyecto_cache()
        
        return db_proyecto
        
    except IntegrityError:
        db.rollback()  # Rollback en caso de error para mantener ACID
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error de integridad en la base de datos"
        )

@router.get("/", response_model=List[ProyectoResponse])
async def listar_proyectos(
    skip: int = 0,
    limit: int = 100,
    estado: str = None,
    db: Session = Depends(get_db)
):
    """
    Obtener lista de todos los proyectos con sus usuarios asignados.
    Soporta filtrado por estado y paginación para escalabilidad.
    
    **Patrón Cache-Aside aplicado:**
    1. Intenta obtener datos desde Redis
    2. Si no existe en caché (cache miss), consulta PostgreSQL
    3. Guarda resultado en caché para futuras consultas
    
    - **skip**: Número de registros a omitir (default: 0)
    - **limit**: Número máximo de registros a devolver (default: 100)
    - **estado**: Filtrar por estado (activo, pausado, completado)
    """
    #Intentar obtener desde caché (Cache-Aside)
    cached_proyectos = cache.get_proyectos_list_from_cache(skip, limit, estado)
    if cached_proyectos is not None:
        return cached_proyectos
    
    #Si no está en caché, consultar base de datos
    query = db.query(Proyecto)
    
    # Filtrar por estado si se proporciona
    if estado:
        query = query.filter(Proyecto.estado == estado)
    
    proyectos = query.offset(skip).limit(limit).all()
    
    #Convertir a dict para serialización y guardar en caché
    proyectos_dict = [
        {
            "id": p.id,
            "nombre": p.nombre,
            "descripcion": p.descripcion,
            "estado": p.estado,
            "fecha_inicio": p.fecha_inicio.isoformat() if p.fecha_inicio else None,
            "fecha_fin": p.fecha_fin.isoformat() if p.fecha_fin else None,
            "fecha_creacion": p.fecha_creacion.isoformat() if p.fecha_creacion else None,
            "fecha_actualizacion": p.fecha_actualizacion.isoformat() if p.fecha_actualizacion else None,
            "usuarios": [
                {
                    "id": u.id,
                    "nombre": u.nombre,
                    "email": u.email,
                    "rol": u.rol,
                    "fecha_creacion": u.fecha_creacion.isoformat() if u.fecha_creacion else None,
                    "fecha_actualizacion": u.fecha_actualizacion.isoformat() if u.fecha_actualizacion else None
                } for u in p.usuarios
            ]
        } for p in proyectos
    ]
    
    cache.set_proyectos_list_in_cache(proyectos_dict, skip, limit, estado)
    
    return proyectos_dict

@router.get("/{proyecto_id}", response_model=ProyectoResponse)
async def obtener_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener información detallada de un proyecto específico.
    Incluye usuarios asignados al proyecto.
    
    **Patrón Cache-Aside aplicado:**
    1. Intenta obtener datos desde Redis
    2. Si no existe en caché (cache miss), consulta PostgreSQL
    3. Guarda resultado en caché para futuras consultas
    
    - **proyecto_id**: ID único del proyecto
    """
    #Intentar obtener desde caché (Cache-Aside)
    cached_proyecto = cache.get_proyecto_from_cache(proyecto_id)
    if cached_proyecto is not None:
        return cached_proyecto
    
    #Si no está en caché, consultar base de datos
    proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proyecto con ID {proyecto_id} no encontrado"
        )
    
    #Convertir a dict para serialización y guardar en caché
    proyecto_dict = {
        "id": proyecto.id,
        "nombre": proyecto.nombre,
        "descripcion": proyecto.descripcion,
        "estado": proyecto.estado,
        "fecha_inicio": proyecto.fecha_inicio.isoformat() if proyecto.fecha_inicio else None,
        "fecha_fin": proyecto.fecha_fin.isoformat() if proyecto.fecha_fin else None,
        "fecha_creacion": proyecto.fecha_creacion.isoformat() if proyecto.fecha_creacion else None,
        "fecha_actualizacion": proyecto.fecha_actualizacion.isoformat() if proyecto.fecha_actualizacion else None,
        "usuarios": [
            {
                "id": u.id,
                "nombre": u.nombre,
                "email": u.email,
                "rol": u.rol,
                "fecha_creacion": u.fecha_creacion.isoformat() if u.fecha_creacion else None,
                "fecha_actualizacion": u.fecha_actualizacion.isoformat() if u.fecha_actualizacion else None
            } for u in proyecto.usuarios
        ]
    }
    
    cache.set_proyecto_in_cache(proyecto_id, proyecto_dict)
    
    return proyecto_dict

@router.put("/{proyecto_id}", response_model=ProyectoResponse)
async def actualizar_proyecto(
    proyecto_id: int,
    proyecto_update: ProyectoUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar información de un proyecto existente.
    Solo actualiza los campos proporcionados (PATCH semantics).
    
    - **proyecto_id**: ID único del proyecto
    - **nombre**: Nuevo nombre (opcional)
    - **descripcion**: Nueva descripción (opcional)
    - **estado**: Nuevo estado (opcional)
    - **fecha_fin**: Nueva fecha de finalización (opcional)
    """
    # Buscar proyecto existente
    db_proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    
    if not db_proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proyecto con ID {proyecto_id} no encontrado"
        )
    
    try:
        # Actualizar solo los campos proporcionados
        update_data = proyecto_update.model_dump(exclude_unset=True)
        
        # Verificar nombre único si se está actualizando
        if "nombre" in update_data:
            existing_nombre = db.query(Proyecto).filter(
                Proyecto.nombre == update_data["nombre"],
                Proyecto.id != proyecto_id
            ).first()
            if existing_nombre:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un proyecto con el nombre '{update_data['nombre']}'"
                )
        
        # Aplicar actualizaciones
        for field, value in update_data.items():
            setattr(db_proyecto, field, value)
        
        db.commit()  # Commit explícito para ACID
        db.refresh(db_proyecto)
        
        # Invalidar caché del proyecto actualizado
        cache.invalidate_proyecto_cache(proyecto_id)
        
        return db_proyecto
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error de integridad en la base de datos"
        )

@router.delete("/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar un proyecto del sistema.
    También elimina todas las tareas asociadas (CASCADE).
    
    - **proyecto_id**: ID único del proyecto a eliminar
    """
    db_proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    
    if not db_proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proyecto con ID {proyecto_id} no encontrado"
        )
    
    try:
        db.delete(db_proyecto)
        db.commit()  # Commit explícito para ACID
        
        # Invalidar caché del proyecto eliminado
        cache.invalidate_proyecto_cache(proyecto_id)
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el proyecto debido a dependencias"
        )

@router.post("/{proyecto_id}/asignar_usuario", response_model=SuccessResponse)
async def asignar_usuario_proyecto(
    proyecto_id: int,
    asignacion: AsignarUsuarioProyecto,
    db: Session = Depends(get_db)
):
    """
    Asignar un usuario existente a un proyecto.
    Valida que tanto el proyecto como el usuario existan (validación cruzada).
    
    - **proyecto_id**: ID único del proyecto
    - **usuario_id**: ID único del usuario a asignar
    """
    # Verificar que el proyecto existe
    proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proyecto con ID {proyecto_id} no encontrado"
        )
    
    # Verificar que el usuario existe (validación cruzada con GestorUsuarios)
    usuario = db.query(Usuario).filter(Usuario.id == asignacion.usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {asignacion.usuario_id} no encontrado"
        )
    
    # Verificar si el usuario ya está asignado al proyecto
    if usuario in proyecto.usuarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {usuario.nombre} ya está asignado al proyecto {proyecto.nombre}"
        )
    
    try:
        # Asignar usuario al proyecto
        proyecto.usuarios.append(usuario)
        db.commit()  # Commit explícito para ACID
        
        # Invalidar caché del proyecto modificado
        cache.invalidate_proyecto_cache(proyecto_id)
        
        return SuccessResponse(
            message=f"Usuario {usuario.nombre} asignado exitosamente al proyecto {proyecto.nombre}",
            data={
                "proyecto_id": proyecto_id,
                "usuario_id": asignacion.usuario_id,
                "proyecto_nombre": proyecto.nombre,
                "usuario_nombre": usuario.nombre
            }
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al asignar usuario al proyecto"
        )

@router.delete("/{proyecto_id}/desasignar_usuario/{usuario_id}", response_model=SuccessResponse)
async def desasignar_usuario_proyecto(
    proyecto_id: int,
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Desasignar un usuario de un proyecto.
    
    - **proyecto_id**: ID único del proyecto
    - **usuario_id**: ID único del usuario a desasignar
    """
    # Verificar que el proyecto existe
    proyecto = db.query(Proyecto).filter(Proyecto.id == proyecto_id).first()
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proyecto con ID {proyecto_id} no encontrado"
        )
    
    # Verificar que el usuario existe
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )
    
    # Verificar si el usuario está asignado al proyecto
    if usuario not in proyecto.usuarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El usuario {usuario.nombre} no está asignado al proyecto {proyecto.nombre}"
        )
    
    try:
        # Desasignar usuario del proyecto
        proyecto.usuarios.remove(usuario)
        db.commit()  # Commit explícito para ACID
        
        # Invalidar caché del proyecto modificado
        cache.invalidate_proyecto_cache(proyecto_id)
        
        return SuccessResponse(
            message=f"Usuario {usuario.nombre} desasignado exitosamente del proyecto {proyecto.nombre}",
            data={
                "proyecto_id": proyecto_id,
                "usuario_id": usuario_id,
                "proyecto_nombre": proyecto.nombre,
                "usuario_nombre": usuario.nombre
            }
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al desasignar usuario del proyecto"
        )
"""
Router para gestión de usuarios - Componente GestorUsuarios
Implementa endpoints CRUD con validación y manejo de errores.
Servicio sin estado (stateless) - cada request es independiente.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import get_db
from app.models import Usuario
from app.schemas import UsuarioCreate, UsuarioUpdate, UsuarioResponse, ErrorResponse

router = APIRouter(
    prefix="/usuarios",
    tags=["usuarios"],
    responses={404: {"model": ErrorResponse}},
)

@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    usuario: UsuarioCreate,
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo usuario en el sistema.
    
    - **nombre**: Nombre del usuario (2-100 caracteres)
    - **email**: Email único del usuario
    - **rol**: Rol del usuario (admin, manager, desarrollador)
    """
    try:
        # Verificar si el email ya existe
        db_usuario_existante = db.query(Usuario).filter(Usuario.email == usuario.email).first()
        if db_usuario_existante:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El email {usuario.email} ya está registrado"
            )
        
        # Crear nuevo usuario
        db_usuario = Usuario(**usuario.model_dump())
        db.add(db_usuario)
        db.commit()  # Commit explícito para ACID
        db.refresh(db_usuario)
        
        return db_usuario
        
    except IntegrityError:
        db.rollback()  # Rollback en caso de error para mantener ACID
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error de integridad en la base de datos"
        )

@router.get("/", response_model=List[UsuarioResponse])
async def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtener lista de todos los usuarios.
    Soporta paginación para escalabilidad.
    
    - **skip**: Número de registros a omitir (default: 0)
    - **limit**: Número máximo de registros a devolver (default: 100)
    """
    usuarios = db.query(Usuario).offset(skip).limit(limit).all()
    return usuarios

@router.get("/{usuario_id}", response_model=UsuarioResponse)
async def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener información detallada de un usuario específico.
    
    - **usuario_id**: ID único del usuario
    """
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )
    
    return usuario

@router.put("/{usuario_id}", response_model=UsuarioResponse)
async def actualizar_usuario(
    usuario_id: int,
    usuario_update: UsuarioUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualizar información de un usuario existente.
    Solo actualiza los campos proporcionados (PATCH semantics).
    
    - **usuario_id**: ID único del usuario
    - **nombre**: Nuevo nombre (opcional)
    - **email**: Nuevo email (opcional)
    - **rol**: Nuevo rol (opcional)
    """
    # Buscar usuario existente
    db_usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    if not db_usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )
    
    try:
        # Actualizar solo los campos proporcionados
        update_data = usuario_update.model_dump(exclude_unset=True)
        
        # Verificar email único si se está actualizando
        if "email" in update_data:
            existing_email = db.query(Usuario).filter(
                Usuario.email == update_data["email"],
                Usuario.id != usuario_id
            ).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El email {update_data['email']} ya está en uso"
                )
        
        # Aplicar actualizaciones
        for field, value in update_data.items():
            setattr(db_usuario, field, value)
        
        db.commit()  # Commit explícito para ACID
        db.refresh(db_usuario)
        
        return db_usuario
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error de integridad en la base de datos"
        )

@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar un usuario del sistema.
    Las tareas asignadas se marcarán sin responsable (SET NULL).
    
    - **usuario_id**: ID único del usuario a eliminar
    """
    db_usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    if not db_usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )
    
    try:
        db.delete(db_usuario)
        db.commit()  # Commit explícito para ACID
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el usuario debido a dependencias"
        )
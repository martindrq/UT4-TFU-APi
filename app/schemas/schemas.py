"""
Schemas Pydantic para validación de datos de entrada y salida.
Implementa validación estricta para mantener integridad de datos (ACID).
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# ===== SCHEMAS PARA USUARIOS =====

class UsuarioBase(BaseModel):
    """Schema base para usuarios"""
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre del usuario")
    email: EmailStr = Field(..., description="Email único del usuario")
    rol: str = Field(default="desarrollador", pattern="^(admin|manager|desarrollador)$", description="Rol del usuario")

class UsuarioCreate(UsuarioBase):
    """Schema para crear usuario"""
    pass

class UsuarioUpdate(BaseModel):
    """Schema para actualizar usuario (campos opcionales)"""
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    rol: Optional[str] = Field(None, pattern="^(admin|manager|desarrollador)$")

class UsuarioResponse(UsuarioBase):
    """Schema de respuesta para usuario"""
    id: int
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

# ===== SCHEMAS PARA PROYECTOS =====

class ProyectoBase(BaseModel):
    """Schema base para proyectos"""
    nombre: str = Field(..., min_length=3, max_length=200, description="Nombre del proyecto")
    descripcion: Optional[str] = Field(None, max_length=1000, description="Descripción del proyecto")
    estado: str = Field(default="activo", pattern="^(activo|pausado|completado)$", description="Estado del proyecto")
    fecha_fin: Optional[datetime] = Field(None, description="Fecha de finalización estimada")

class ProyectoCreate(ProyectoBase):
    """Schema para crear proyecto"""
    pass

class ProyectoUpdate(BaseModel):
    """Schema para actualizar proyecto"""
    nombre: Optional[str] = Field(None, min_length=3, max_length=200)
    descripcion: Optional[str] = Field(None, max_length=1000)
    estado: Optional[str] = Field(None, pattern="^(activo|pausado|completado)$")
    fecha_fin: Optional[datetime] = None

class ProyectoResponse(ProyectoBase):
    """Schema de respuesta para proyecto"""
    id: int
    fecha_inicio: datetime
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    usuarios: List[UsuarioResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class AsignarUsuarioProyecto(BaseModel):
    """Schema para asignar usuario a proyecto"""
    usuario_id: int = Field(..., gt=0, description="ID del usuario a asignar")

# ===== SCHEMAS PARA TAREAS =====

class TareaBase(BaseModel):
    """Schema base para tareas"""
    titulo: str = Field(..., min_length=3, max_length=200, description="Título de la tarea")
    descripcion: Optional[str] = Field(None, max_length=1000, description="Descripción de la tarea")
    estado: str = Field(default="pendiente", pattern="^(pendiente|en_progreso|completada)$", description="Estado de la tarea")
    prioridad: str = Field(default="media", pattern="^(alta|media|baja)$", description="Prioridad de la tarea")
    fecha_vencimiento: Optional[datetime] = Field(None, description="Fecha de vencimiento")
    proyecto_id: int = Field(..., gt=0, description="ID del proyecto al que pertenece")

class TareaCreate(TareaBase):
    """Schema para crear tarea"""
    pass

class TareaUpdate(BaseModel):
    """Schema para actualizar tarea"""
    titulo: Optional[str] = Field(None, min_length=3, max_length=200)
    descripcion: Optional[str] = Field(None, max_length=1000)
    estado: Optional[str] = Field(None, pattern="^(pendiente|en_progreso|completada)$")
    prioridad: Optional[str] = Field(None, pattern="^(alta|media|baja)$")
    fecha_vencimiento: Optional[datetime] = None
    proyecto_id: Optional[int] = Field(None, gt=0)

class TareaResponse(TareaBase):
    """Schema de respuesta para tarea"""
    id: int
    usuario_responsable_id: Optional[int] = None
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    usuario_responsable: Optional[UsuarioResponse] = None
    
    model_config = ConfigDict(from_attributes=True)

class AsignarUsuarioTarea(BaseModel):
    """Schema para asignar usuario responsable a tarea"""
    usuario_id: int = Field(..., gt=0, description="ID del usuario responsable")

# ===== SCHEMAS DE RESPUESTA GENÉRICA =====

class ErrorResponse(BaseModel):
    """Schema para respuestas de error"""
    detail: str
    code: Optional[str] = None

class SuccessResponse(BaseModel):
    """Schema para respuestas exitosas"""
    message: str
    data: Optional[dict] = None

# ===== SCHEMAS PARA QUEUE-BASED LOAD LEVELING =====

class JobResponse(BaseModel):
    """Schema de respuesta para job encolado"""
    job_id: str = Field(..., description="ID único del job")
    message: str = Field(..., description="Mensaje descriptivo")
    status: str = Field(..., description="Estado del job (pending, processing, completed, failed)")
    queue_position: Optional[int] = Field(None, description="Posición aproximada en la cola")

class JobStatusResponse(BaseModel):
    """Schema de respuesta para estado de job"""
    job_id: str
    status: str = Field(..., description="Estado del job")
    message: str
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class JobResultResponse(BaseModel):
    """Schema de respuesta para resultado de job completado"""
    job_id: str
    status: str
    result: Optional[TareaResponse] = None
    error: Optional[str] = None

# ===== SCHEMAS PARA AUTENTICACIÓN (Gatekeeper + Federated Identity) =====

class LoginRequest(BaseModel):
    """Schema para solicitud de login con LDAP"""
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario LDAP")
    password: str = Field(..., min_length=1, description="Contraseña del usuario")

class TokenResponse(BaseModel):
    """Schema de respuesta después de login exitoso"""
    access_token: str = Field(..., description="Token JWT de acceso")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Tiempo de expiración en segundos")
    user: dict = Field(..., description="Información del usuario autenticado")

class UserInfo(BaseModel):
    """Schema para información del usuario actual"""
    username: str
    email: str
    nombre: str
    rol: str
    ldap_dn: Optional[str] = None


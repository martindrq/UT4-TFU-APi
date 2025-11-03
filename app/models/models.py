"""
Modelos SQLAlchemy para usuarios, proyectos y tareas.
Implementa relaciones y restricciones para garantizar integridad ACID.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base

# Tabla de asociación para relación muchos-a-muchos entre proyectos y usuarios
proyecto_usuario_association = Table(
    'proyecto_usuario',
    Base.metadata,
    Column('proyecto_id', Integer, ForeignKey('proyectos.id', ondelete='CASCADE')),
    Column('usuario_id', Integer, ForeignKey('usuarios.id', ondelete='CASCADE'))
)

class Usuario(Base):
    """
    Modelo para gestión de usuarios del sistema.
    Componente: GestorUsuarios
    """
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    rol = Column(String(50), default="desarrollador")
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    proyectos = relationship("Proyecto", secondary=proyecto_usuario_association, back_populates="usuarios")
    tareas_asignadas = relationship("Tarea", back_populates="usuario_responsable")

    def __repr__(self):
        return f"<Usuario(id={self.id}, nombre='{self.nombre}', email='{self.email}')>"

class Proyecto(Base):
    """
    Modelo para gestión de proyectos.
    Componente: GestorProyectos
    """
    __tablename__ = "proyectos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False, index=True)
    descripcion = Column(Text)
    estado = Column(String(50), default="activo")  # activo, pausado, completado
    fecha_inicio = Column(DateTime(timezone=True), server_default=func.now())
    fecha_fin = Column(DateTime(timezone=True), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    usuarios = relationship("Usuario", secondary=proyecto_usuario_association, back_populates="proyectos")
    tareas = relationship("Tarea", back_populates="proyecto", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Proyecto(id={self.id}, nombre='{self.nombre}', estado='{self.estado}')>"

class Tarea(Base):
    """
    Modelo para gestión de tareas dentro de proyectos.
    Componente: GestorTareas
    """
    __tablename__ = "tareas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False, index=True)
    descripcion = Column(Text)
    estado = Column(String(50), default="pendiente")  # pendiente, en_progreso, completada
    prioridad = Column(String(20), default="media")  # alta, media, baja
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())

    # Claves foráneas
    proyecto_id = Column(Integer, ForeignKey("proyectos.id", ondelete="CASCADE"), nullable=False)
    usuario_responsable_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    proyecto = relationship("Proyecto", back_populates="tareas")
    usuario_responsable = relationship("Usuario", back_populates="tareas_asignadas")

    def __repr__(self):
        return f"<Tarea(id={self.id}, titulo='{self.titulo}', estado='{self.estado}', proyecto_id={self.proyecto_id})>"


"""
Router para gestión de proyectos - Componente GestorProyectos
Implementa endpoints CRUD y asignación de usuarios con validaciones cruzadas.
Servicio sin estado (stateless) - cada request es independiente.
Incluye patrón Cache-Aside para optimización de consultas frecuentes.
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from lxml import etree

from app.config import get_db
from app.config.permissions import PermissionChecker
from app.models import Proyecto, Usuario
from app.schemas import (
    ProyectoCreate, ProyectoUpdate, ProyectoResponse, 
    AsignarUsuarioProyecto, ErrorResponse, SuccessResponse
)
from app.services import cache_service as cache
from fastapi import Request

router = APIRouter(
    prefix="/proyectos",
    tags=["proyectos"],
    responses={404: {"model": ErrorResponse}},
)

# ============================================================================
# FUNCIÓN AUXILIAR: Lógica común para crear proyectos
# ============================================================================
def _crear_proyecto_logic(
    proyecto_data: Dict,
    request: Request,
    db: Session
) -> Proyecto:
    """
    Lógica común para crear un proyecto.
    Reutilizada por endpoints REST y SOAP.
    
    Args:
        proyecto_data: Diccionario con datos del proyecto
        request: Request de FastAPI (para obtener usuario del gateway)
        db: Sesión de base de datos
        
    Returns:
        Proyecto creado
        
    Raises:
        HTTPException: Si hay errores de validación, permisos o integridad
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📝 Crear proyecto: nombre={proyecto_data.get('nombre')}, estado={proyecto_data.get('estado')}")
    
    # Validar permisos del usuario
    # El usuario viene del gateway a través del header X-User-Info
    user_info_header = request.headers.get("X-User-Info")
    logger.info(f"🔐 X-User-Info header: {user_info_header}")
    
    if user_info_header:
        import json
        try:
            user_info = json.loads(user_info_header)
            request.state.user = user_info
            logger.info(f"✅ Usuario parseado: {user_info}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando X-User-Info: {e}")
            pass
    
    if not hasattr(request.state, "user") or not request.state.user:
        logger.error("❌ Usuario no encontrado en request.state")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado. El token no fue validado correctamente por el Gateway."
        )
    
    user_role = request.state.user.get("rol", "desarrollador")
    username = request.state.user.get("username", "unknown")
    logger.info(f"👤 Usuario: {username}, Rol: {user_role}")
    
    # Verificar permisos: solo admin y manager pueden crear proyectos
    has_create_permission = (
        PermissionChecker.has_permission(user_role, "proyectos:create") or
        PermissionChecker.has_permission(user_role, "proyectos:*") or
        PermissionChecker.has_permission(user_role, "*")
    )
    
    logger.info(f"🔑 Permiso crear proyecto: {has_create_permission}")
    
    if not has_create_permission:
        logger.warning(f"🚫 Permiso denegado para {username} (rol: {user_role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso denegado. El usuario '{username}' con rol '{user_role}' no tiene permisos para crear proyectos. Se requiere rol 'admin' o 'manager'."
        )
    
    try:
        # Verificar si ya existe un proyecto con el mismo nombre
        proyecto_existente = db.query(Proyecto).filter(Proyecto.nombre == proyecto_data.get("nombre")).first()
        if proyecto_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un proyecto con el nombre '{proyecto_data.get('nombre')}'"
            )
        
        # Crear nuevo proyecto
        db_proyecto = Proyecto(**proyecto_data)
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

@router.post("/", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
async def crear_proyecto(
    proyecto: ProyectoCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo proyecto en el sistema (REST/JSON).
    
    Requiere permisos: admin o manager (proyectos:*)
    
    - **nombre**: Nombre del proyecto (3-200 caracteres)
    - **descripcion**: Descripción opcional del proyecto
    - **estado**: Estado del proyecto (activo, pausado, completado)
    - **fecha_fin**: Fecha de finalización estimada (opcional)
    """
    # Usar la función auxiliar común
    proyecto_data = proyecto.model_dump()
    return _crear_proyecto_logic(proyecto_data, request, db)

# ============================================================================
# ENDPOINT SOAP: Crear proyecto con SOAP/XML
# ============================================================================
@router.post("/soap/", response_class=Response)
async def crear_proyecto_soap(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo proyecto en el sistema usando SOAP/XML.
    
    Requiere permisos: admin o manager (proyectos:*)
    
    **Formato SOAP Request:**
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <CrearProyecto xmlns="http://minigestor.com/proyectos">
                <nombre>Nombre del Proyecto</nombre>
                <descripcion>Descripción opcional</descripcion>
                <estado>activo</estado>
                <fecha_fin>2024-12-31T23:59:59</fecha_fin>
            </CrearProyecto>
        </soap:Body>
    </soap:Envelope>
    ```
    
    **Formato SOAP Response:**
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <CrearProyectoResponse xmlns="http://minigestor.com/proyectos">
                <id>1</id>
                <nombre>Nombre del Proyecto</nombre>
                <descripcion>Descripción opcional</descripcion>
                <estado>activo</estado>
                <fecha_inicio>2024-01-01T00:00:00</fecha_inicio>
                <fecha_fin>2024-12-31T23:59:59</fecha_fin>
                <fecha_creacion>2024-01-01T00:00:00</fecha_creacion>
            </CrearProyectoResponse>
        </soap:Body>
    </soap:Envelope>
    ```
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Namespaces SOAP
    SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
    PROYECTOS_NS = "http://minigestor.com/proyectos"
    
    try:
        # Leer el body del request como XML
        body = await request.body()
        logger.info(f"📥 SOAP Request recibido: {len(body)} bytes")
        
        # Parsear el XML SOAP
        try:
            root = etree.fromstring(body)
        except etree.XMLSyntaxError as e:
            logger.error(f"❌ Error parseando XML SOAP: {e}")
            return _crear_respuesta_soap_error(
                "Error de sintaxis XML",
                "El XML proporcionado no es válido",
                SOAP_NS,
                PROYECTOS_NS
            )
        
        # Registrar namespaces
        nsmap = {
            "soap": SOAP_NS,
            "proj": PROYECTOS_NS
        }
        
        # Extraer el Body del SOAP
        soap_body = root.find(f".//{{{SOAP_NS}}}Body")
        if soap_body is None:
            return _crear_respuesta_soap_error(
                "Estructura SOAP inválida",
                "No se encontró el elemento soap:Body",
                SOAP_NS,
                PROYECTOS_NS
            )
        
        # Extraer el elemento CrearProyecto
        crear_proyecto = soap_body.find(f".//{{{PROYECTOS_NS}}}CrearProyecto")
        if crear_proyecto is None:
            # Intentar sin namespace
            crear_proyecto = soap_body.find(".//CrearProyecto")
            if crear_proyecto is None:
                return _crear_respuesta_soap_error(
                    "Operación no encontrada",
                    "No se encontró el elemento CrearProyecto",
                    SOAP_NS,
                    PROYECTOS_NS
                )
        
        # Extraer datos del proyecto desde el XML
        proyecto_data = {}
        
        # Nombre (requerido)
        nombre_elem = crear_proyecto.find(f".//{{{PROYECTOS_NS}}}nombre")
        if nombre_elem is None:
            nombre_elem = crear_proyecto.find(".//nombre")
        if nombre_elem is None or nombre_elem.text is None:
            return _crear_respuesta_soap_error(
                "Campo requerido faltante",
                "El campo 'nombre' es requerido",
                SOAP_NS,
                PROYECTOS_NS
            )
        proyecto_data["nombre"] = nombre_elem.text.strip()
        
        # Descripción (opcional)
        descripcion_elem = crear_proyecto.find(f".//{{{PROYECTOS_NS}}}descripcion")
        if descripcion_elem is None:
            descripcion_elem = crear_proyecto.find(".//descripcion")
        if descripcion_elem is not None and descripcion_elem.text:
            proyecto_data["descripcion"] = descripcion_elem.text.strip()
        else:
            proyecto_data["descripcion"] = None
        
        # Estado (opcional, default: activo)
        estado_elem = crear_proyecto.find(f".//{{{PROYECTOS_NS}}}estado")
        if estado_elem is None:
            estado_elem = crear_proyecto.find(".//estado")
        if estado_elem is not None and estado_elem.text:
            proyecto_data["estado"] = estado_elem.text.strip()
        else:
            proyecto_data["estado"] = "activo"
        
        # Fecha fin (opcional)
        fecha_fin_elem = crear_proyecto.find(f".//{{{PROYECTOS_NS}}}fecha_fin")
        if fecha_fin_elem is None:
            fecha_fin_elem = crear_proyecto.find(".//fecha_fin")
        if fecha_fin_elem is not None and fecha_fin_elem.text:
            try:
                # Intentar parsear la fecha en formato ISO
                proyecto_data["fecha_fin"] = datetime.fromisoformat(fecha_fin_elem.text.strip().replace("Z", "+00:00"))
            except ValueError:
                return _crear_respuesta_soap_error(
                    "Formato de fecha inválido",
                    f"La fecha '{fecha_fin_elem.text}' no está en formato ISO válido",
                    SOAP_NS,
                    PROYECTOS_NS
                )
        else:
            proyecto_data["fecha_fin"] = None
        
        logger.info(f"📋 Datos extraídos del SOAP: {proyecto_data}")
        
        # Validar datos básicos
        if len(proyecto_data["nombre"]) < 3 or len(proyecto_data["nombre"]) > 200:
            return _crear_respuesta_soap_error(
                "Validación fallida",
                "El nombre del proyecto debe tener entre 3 y 200 caracteres",
                SOAP_NS,
                PROYECTOS_NS
            )
        
        if proyecto_data["estado"] not in ["activo", "pausado", "completado"]:
            return _crear_respuesta_soap_error(
                "Estado inválido",
                f"El estado '{proyecto_data['estado']}' no es válido. Debe ser: activo, pausado o completado",
                SOAP_NS,
                PROYECTOS_NS
            )
        
        # Crear el proyecto usando la lógica común
        try:
            db_proyecto = _crear_proyecto_logic(proyecto_data, request, db)
            
            # Generar respuesta SOAP exitosa
            return _crear_respuesta_soap_exitosa(db_proyecto, SOAP_NS, PROYECTOS_NS)
            
        except HTTPException as e:
            # Convertir HTTPException a respuesta SOAP de error
            return _crear_respuesta_soap_error(
                "Error al crear proyecto",
                e.detail,
                SOAP_NS,
                PROYECTOS_NS,
                status_code=e.status_code
            )
        
    except Exception as e:
        logger.error(f"❌ Error inesperado en SOAP: {e}", exc_info=True)
        return _crear_respuesta_soap_error(
            "Error interno del servidor",
            f"Error inesperado: {str(e)}",
            SOAP_NS,
            PROYECTOS_NS,
            status_code=500
        )


def _crear_respuesta_soap_exitosa(proyecto: Proyecto, soap_ns: str, proyectos_ns: str) -> Response:
    """
    Crea una respuesta SOAP exitosa con los datos del proyecto creado.
    """
    # Crear el XML de respuesta SOAP con namespaces correctos
    nsmap = {
        "soap": soap_ns,
        "proj": proyectos_ns
    }
    envelope = etree.Element(f"{{{soap_ns}}}Envelope", nsmap=nsmap)
    body = etree.SubElement(envelope, f"{{{soap_ns}}}Body")
    response = etree.SubElement(body, f"{{{proyectos_ns}}}CrearProyectoResponse")
    
    # Agregar campos del proyecto
    etree.SubElement(response, f"{{{proyectos_ns}}}id").text = str(proyecto.id)
    etree.SubElement(response, f"{{{proyectos_ns}}}nombre").text = proyecto.nombre
    if proyecto.descripcion:
        etree.SubElement(response, f"{{{proyectos_ns}}}descripcion").text = proyecto.descripcion
    etree.SubElement(response, f"{{{proyectos_ns}}}estado").text = proyecto.estado
    
    if proyecto.fecha_inicio:
        etree.SubElement(response, f"{{{proyectos_ns}}}fecha_inicio").text = proyecto.fecha_inicio.isoformat()
    if proyecto.fecha_fin:
        etree.SubElement(response, f"{{{proyectos_ns}}}fecha_fin").text = proyecto.fecha_fin.isoformat()
    if proyecto.fecha_creacion:
        etree.SubElement(response, f"{{{proyectos_ns}}}fecha_creacion").text = proyecto.fecha_creacion.isoformat()
    if proyecto.fecha_actualizacion:
        etree.SubElement(response, f"{{{proyectos_ns}}}fecha_actualizacion").text = proyecto.fecha_actualizacion.isoformat()
    
    # Convertir a string XML
    try:
        xml_string = etree.tostring(envelope, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    except TypeError:
        # Si pretty_print no está disponible, usar sin formato
        xml_string = etree.tostring(envelope, encoding="UTF-8", xml_declaration=True)
    
    return Response(
        content=xml_string,
        media_type="application/xml; charset=utf-8",
        status_code=200
    )


def _crear_respuesta_soap_error(
    fault_code: str,
    fault_string: str,
    soap_ns: str,
    proyectos_ns: str,
    status_code: int = 500
) -> Response:
    """
    Crea una respuesta SOAP de error (SOAP Fault).
    """
    # Crear el XML de respuesta SOAP Fault con namespaces correctos
    nsmap = {
        "soap": soap_ns,
        "proj": proyectos_ns
    }
    envelope = etree.Element(f"{{{soap_ns}}}Envelope", nsmap=nsmap)
    body = etree.SubElement(envelope, f"{{{soap_ns}}}Body")
    fault = etree.SubElement(body, f"{{{soap_ns}}}Fault")
    
    etree.SubElement(fault, f"{{{soap_ns}}}faultcode").text = "SOAP-ENV:Server"
    etree.SubElement(fault, f"{{{soap_ns}}}faultstring").text = fault_string
    detail = etree.SubElement(fault, f"{{{soap_ns}}}detail")
    error_detail = etree.SubElement(detail, f"{{{proyectos_ns}}}ErrorDetail")
    etree.SubElement(error_detail, f"{{{proyectos_ns}}}code").text = fault_code
    etree.SubElement(error_detail, f"{{{proyectos_ns}}}message").text = fault_string
    
    # Convertir a string XML
    try:
        xml_string = etree.tostring(envelope, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    except TypeError:
        # Si pretty_print no está disponible, usar sin formato
        xml_string = etree.tostring(envelope, encoding="UTF-8", xml_declaration=True)
    
    return Response(
        content=xml_string,
        media_type="application/xml; charset=utf-8",
        status_code=status_code
    )

@router.get("", response_model=List[ProyectoResponse])
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


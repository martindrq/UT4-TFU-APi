"""
Worker para procesamiento de tareas en background.
Implementa el patrón Queue-Based Load Leveling consumiendo mensajes de Redis.
"""

import time
import signal
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import SessionLocal
from app.models import Tarea
from app.services import queue_service as queue
from app.services import cache_service as cache

# Bandera para shutdown graceful
shutdown_requested = False


def signal_handler(signum, frame):
    """Manejar señales de terminación para shutdown graceful"""
    global shutdown_requested
    print(f"\n⚠ Señal de terminación recibida ({signum}). Finalizando worker gracefully...")
    shutdown_requested = True


def process_tarea_creation(message: dict, db: Session) -> dict:
    """
    Procesar mensaje de creación de tarea.
    
    Args:
        message: Mensaje de la cola con datos de la tarea
        db: Sesión de base de datos
        
    Returns:
        Diccionario con resultado del procesamiento
    """
    job_id = message["job_id"]
    tarea_data = message["data"]
    
    try:
        # Actualizar estado a "processing"
        queue.update_job_status(
            job_id,
            queue.JobStatus.PROCESSING,
            "Procesando creación de tarea..."
        )
        
        # Crear tarea en la base de datos
        db_tarea = Tarea(**tarea_data)
        db.add(db_tarea)
        db.commit()
        db.refresh(db_tarea)
        
        # Invalidar caché de tareas
        cache.invalidate_tarea_cache()
        
        # Preparar resultado
        tarea_result = {
            "id": db_tarea.id,
            "titulo": db_tarea.titulo,
            "descripcion": db_tarea.descripcion,
            "estado": db_tarea.estado,
            "prioridad": db_tarea.prioridad,
            "fecha_creacion": db_tarea.fecha_creacion.isoformat() if db_tarea.fecha_creacion else None,
            "fecha_vencimiento": db_tarea.fecha_vencimiento.isoformat() if db_tarea.fecha_vencimiento else None,
            "proyecto_id": db_tarea.proyecto_id,
            "usuario_responsable_id": db_tarea.usuario_responsable_id,
            "usuario_responsable": None,  # No cargamos relaciones aquí para optimizar
        }
        
        # Actualizar estado a "completed"
        queue.update_job_status(
            job_id,
            queue.JobStatus.COMPLETED,
            f"Tarea '{db_tarea.titulo}' creada exitosamente"
        )
        
        # Guardar resultado
        queue.save_job_result(job_id, {"tarea": tarea_result})
        
        return {
            "success": True,
            "tarea_id": db_tarea.id,
            "titulo": db_tarea.titulo
        }
        
    except IntegrityError as e:
        db.rollback()
        error_msg = f"Error de integridad en la base de datos: {str(e)}"
        
        queue.update_job_status(
            job_id,
            queue.JobStatus.FAILED,
            "Error al crear tarea",
            error=error_msg
        )
        
        return {
            "success": False,
            "error": error_msg
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error inesperado: {str(e)}"
        
        queue.update_job_status(
            job_id,
            queue.JobStatus.FAILED,
            "Error al crear tarea",
            error=error_msg
        )
        
        return {
            "success": False,
            "error": error_msg
        }


def run_worker():
    """
    Ejecutar el worker principal que consume mensajes de la cola.
    """
    global shutdown_requested
    
    # Registrar handlers para shutdown graceful
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("🚀 Worker de Queue-Based Load Leveling iniciado")
    print("=" * 60)
    print(f"📋 Cola: {queue.TAREA_QUEUE}")
    print(f"🔧 Redis: {queue.REDIS_HOST}:{queue.REDIS_PORT} (DB {queue.REDIS_DB_QUEUE})")
    print(f"⏰ Esperando mensajes... (CTRL+C para detener)")
    print("=" * 60)
    
    processed_count = 0
    failed_count = 0
    start_time = time.time()
    
    while not shutdown_requested:
        try:
            # Obtener mensaje de la cola (bloqueante con timeout)
            message = queue.dequeue_tarea_creation()
            
            if message is None:
                # Timeout - no hay mensajes, continuar esperando
                continue
            
            job_id = message.get("job_id", "unknown")
            message_type = message.get("type", "unknown")
            
            print(f"\n📨 [Job {job_id[:8]}...] Mensaje recibido: {message_type}")
            
            # Crear sesión de base de datos para este mensaje
            db = SessionLocal()
            
            try:
                if message_type == "create_tarea":
                    result = process_tarea_creation(message, db)
                    
                    if result["success"]:
                        processed_count += 1
                        print(f"✓ [Job {job_id[:8]}...] Tarea '{result['titulo']}' creada (ID: {result['tarea_id']})")
                    else:
                        failed_count += 1
                        print(f"✗ [Job {job_id[:8]}...] Error: {result['error']}")
                        
                        # Intentar reencolar si no excede reintentos
                        if queue.requeue_tarea_creation(message, max_retries=3):
                            print(f"↻ [Job {job_id[:8]}...] Reencolado para reintento")
                else:
                    print(f"⚠ [Job {job_id[:8]}...] Tipo de mensaje desconocido: {message_type}")
                    
            finally:
                db.close()
                
        except KeyboardInterrupt:
            print("\n⚠ Interrupción detectada. Finalizando...")
            break
            
        except Exception as e:
            failed_count += 1
            print(f"✗ Error al procesar mensaje: {str(e)}")
            time.sleep(1)  # Pausa breve antes de continuar
    
    # Estadísticas finales
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 Estadísticas del Worker")
    print("=" * 60)
    print(f"✓ Mensajes procesados exitosamente: {processed_count}")
    print(f"✗ Mensajes fallidos: {failed_count}")
    print(f"⏱ Tiempo total de ejecución: {elapsed_time:.2f} segundos")
    
    if processed_count > 0:
        avg_time = elapsed_time / processed_count
        print(f"⚡ Tiempo promedio por mensaje: {avg_time:.2f} segundos")
    
    print("=" * 60)
    print("👋 Worker finalizado correctamente")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_worker()
    except Exception as e:
        print(f"💥 Error fatal en el worker: {str(e)}")
        sys.exit(1)


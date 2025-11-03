"""
Servicio de Autenticación LDAP - Patrón Federated Identity
Delega la autenticación a un proveedor externo (LDAP) en lugar de gestionar contraseñas localmente.
Aumenta la seguridad al evitar almacenar credenciales en la aplicación.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError
from jose import JWTError, jwt
from passlib.context import CryptContext

# Importar configuración centralizada (External Configuration Store Pattern)
from app.config import settings

# Configuración JWT desde configuración externa
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# Configuración LDAP desde configuración externa
LDAP_SERVER = settings.LDAP_SERVER
LDAP_BASE_DN = settings.LDAP_BASE_DN
LDAP_USER_DN_TEMPLATE = settings.LDAP_USER_DN_TEMPLATE
LDAP_BIND_USER = settings.LDAP_BIND_USER
LDAP_BIND_PASSWORD = settings.LDAP_BIND_PASSWORD

# Context para hashing (usado solo para fallback local si es necesario)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LDAPAuthService:
    """
    Servicio de autenticación LDAP implementando Federated Identity.
    Delega la autenticación a LDAP y genera tokens JWT internos.
    """
    
    def __init__(self):
        self.server = Server(LDAP_SERVER, get_info=ALL)
        self.base_dn = LDAP_BASE_DN
        self.user_dn_template = LDAP_USER_DN_TEMPLATE
        
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Autentica un usuario contra el servidor LDAP.
        Implementa el patrón Federated Identity delegando la autenticación.
        
        Args:
            username: Nombre de usuario LDAP
            password: Contraseña del usuario
            
        Returns:
            Dict con información del usuario si la autenticación es exitosa, None en caso contrario
        """
        try:
            # Construir DN del usuario
            user_dn = self.user_dn_template.format(username=username)
            
            # Intentar bind con las credenciales del usuario
            conn = Connection(
                self.server,
                user=user_dn,
                password=password,
                auto_bind=True
            )
            
            # Si llegamos aquí, la autenticación fue exitosa
            print(f"✅ Autenticación exitosa para usuario: {username}")
            
            # Buscar información adicional del usuario usando la conexión autenticada
            user_info = self._get_user_info(conn, username, user_dn)
            
            conn.unbind()
            return user_info
            
        except LDAPBindError as e:
            print(f"❌ Error de autenticación LDAP para {username}: {str(e)}")
            return None
        except LDAPException as e:
            print(f"❌ Error LDAP: {str(e)}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado durante autenticación: {str(e)}")
            return None
    
    def _get_user_info(self, conn: Connection, username: str, user_dn: str) -> Dict[str, Any]:
        """
        Obtiene información adicional del usuario desde LDAP.
        
        Args:
            conn: Conexión LDAP autenticada
            username: Nombre de usuario
            user_dn: DN completo del usuario
            
        Returns:
            Dict con información del usuario
        """
        try:
            # Buscar usuario en LDAP usando su DN directamente
            # El usuario autenticado siempre tiene permisos para leer sus propios atributos
            conn.search(
                search_base=user_dn,
                search_filter='(objectClass=*)',
                search_scope='BASE',
                attributes=['cn', 'mail', 'uid', 'ou', 'employeeType']
            )
            
            if conn.entries:
                entry = conn.entries[0]
                
                # Determinar rol basado en atributos LDAP
                # Por defecto es 'desarrollador', puede ser 'admin' o 'manager' según el employeeType
                role = "desarrollador"
                if hasattr(entry, 'employeeType') and entry.employeeType:
                    # Manejar diferentes formatos de respuesta de LDAP (string, objeto Attribute, lista)
                    employee_type_raw = entry.employeeType.value if hasattr(entry.employeeType, 'value') else entry.employeeType
                    
                    # Si es una lista, tomar el primer elemento
                    if isinstance(employee_type_raw, list):
                        employee_type_raw = employee_type_raw[0] if employee_type_raw else ""
                    
                    employee_type = str(employee_type_raw).lower().strip()
                    
                    # Mapear employeeType a roles de la aplicación
                    if "admin" in employee_type:
                        role = "admin"
                    elif "manager" in employee_type:
                        role = "manager"
                    elif "developer" in employee_type or "desarrollador" in employee_type:
                        role = "desarrollador"
                
                print(f"✅ Usuario autenticado: {username} | Rol: {role}")
                
                return {
                    "username": str(entry.uid) if hasattr(entry, 'uid') else username,
                    "email": str(entry.mail) if hasattr(entry, 'mail') else f"{username}@example.org",
                    "nombre": str(entry.cn) if hasattr(entry, 'cn') else username,
                    "rol": role,
                    "ldap_dn": entry.entry_dn
                }
            else:
                # Si no se encuentran entradas, devolver datos básicos
                print(f"⚠️  No se encontró información LDAP para {username}, usando valores por defecto")
                return {
                    "username": username,
                    "email": f"{username}@example.org",
                    "nombre": username,
                    "rol": "desarrollador",
                    "ldap_dn": user_dn
                }
                
        except Exception as e:
            print(f"⚠️  Error obteniendo información del usuario: {str(e)}")
            # Devolver información básica en caso de error
            return {
                "username": username,
                "email": f"{username}@example.org",
                "nombre": username,
                "rol": "desarrollador",
                "ldap_dn": user_dn
            }
    
    def verify_ldap_connection(self) -> bool:
        """
        Verifica que el servidor LDAP esté disponible.
        
        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        try:
            if LDAP_BIND_USER and LDAP_BIND_PASSWORD:
                conn = Connection(
                    self.server,
                    user=LDAP_BIND_USER,
                    password=LDAP_BIND_PASSWORD,
                    auto_bind=True
                )
            else:
                conn = Connection(self.server, auto_bind=True)
            
            conn.unbind()
            return True
        except Exception as e:
            print(f"❌ Error verificando conexión LDAP: {str(e)}")
            return False


class TokenService:
    """
    Servicio para generación y validación de tokens JWT.
    Parte del sistema Gatekeeper para autenticación interna después de validar con LDAP.
    """
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Crea un token JWT de acceso.
        
        Args:
            data: Datos a incluir en el token (username, rol, etc.)
            expires_delta: Tiempo de expiración personalizado
            
        Returns:
            Token JWT codificado
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decodifica y valida un token JWT.
        
        Args:
            token: Token JWT a validar
            
        Returns:
            Dict con los datos del token si es válido, None en caso contrario
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            print(f"❌ Error validando token: {str(e)}")
            return None
    
    @staticmethod
    def verify_token_signature(token: str) -> bool:
        """
        Verifica solo la firma del token sin decodificarlo completamente.
        Útil para validaciones rápidas.
        
        Args:
            token: Token JWT a verificar
            
        Returns:
            True si la firma es válida, False en caso contrario
        """
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return True
        except JWTError:
            return False


# Instancia global del servicio LDAP
ldap_service = LDAPAuthService()
token_service = TokenService()


def get_ldap_service() -> LDAPAuthService:
    """Dependency para obtener el servicio LDAP"""
    return ldap_service


def get_token_service() -> TokenService:
    """Dependency para obtener el servicio de tokens"""
    return token_service


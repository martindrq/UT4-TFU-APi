"""
Sistema de Permisos y Roles
Define los roles y permisos del sistema.
"""

from typing import List


class PermissionChecker:
    """
    Verificador de permisos basado en roles.
    Define qué puede hacer cada rol en el sistema.
    """
    
    # Definición de permisos por rol
    ROLE_PERMISSIONS = {
        "admin": ["*"],  # Acceso total
        "manager": [
            "usuarios:read",
            "usuarios:create",
            "proyectos:*",
            "tareas:*"
        ],
        "desarrollador": [
            "usuarios:read",
            "proyectos:read",
            "tareas:read",
            "tareas:update"
        ]
    }
    
    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        """
        Verifica si un rol tiene un permiso específico.
        
        Args:
            role: Rol del usuario (admin, manager, desarrollador)
            permission: Permiso a verificar (e.g., "usuarios:create")
            
        Returns:
            True si tiene permiso, False en caso contrario
        """
        if role not in cls.ROLE_PERMISSIONS:
            return False
        
        role_perms = cls.ROLE_PERMISSIONS[role]
        
        # Verificar wildcard total
        if "*" in role_perms:
            return True
        
        # Verificar permiso específico
        if permission in role_perms:
            return True
        
        # Verificar wildcard de recurso (e.g., "proyectos:*")
        resource = permission.split(":")[0]
        if f"{resource}:*" in role_perms:
            return True
        
        return False
    
    @classmethod
    def get_role_permissions(cls, role: str) -> List[str]:
        """
        Obtiene todos los permisos de un rol.
        
        Args:
            role: Rol del usuario
            
        Returns:
            Lista de permisos del rol
        """
        return cls.ROLE_PERMISSIONS.get(role, [])


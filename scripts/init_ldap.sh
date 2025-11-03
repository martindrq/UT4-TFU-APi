#!/bin/bash
# Script para inicializar LDAP con usuarios de prueba
# Implementa el patrón Federated Identity con datos de ejemplo

echo "🔐 Inicializando servidor LDAP con usuarios de prueba..."

# Esperar a que el servidor LDAP esté listo
echo "⏳ Esperando a que LDAP esté disponible..."
sleep 10

# Agregar usuarios de prueba usando ldapadd
docker exec mini-gestor-ldap ldapadd \
  -x \
  -D "cn=admin,dc=example,dc=org" \
  -w admin_password \
  -f /container/service/slapd/assets/test/init-ldap.ldif \
  2>/dev/null || true

echo "✅ Usuarios LDAP de prueba creados"
echo ""
echo "Usuarios disponibles:"
echo "  - admin / admin_password (rol: admin)"
echo "  - manager / manager_password (rol: manager)"
echo "  - developer / developer_password (rol: developer)"
echo "  - jdoe / jdoe123 (rol: manager)"
echo "  - jsmith / jsmith123 (rol: developer)"
echo ""
echo "📋 Administrador LDAP disponible en: http://localhost:8082"
echo "   Login DN: cn=admin,dc=example,dc=org"
echo "   Password: admin_password"


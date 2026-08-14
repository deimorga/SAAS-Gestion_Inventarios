#!/usr/bin/env bash
#
# Crea (o realinea) el rol restringido de aplicación dentro de un contenedor
# PostgreSQL ya en marcha, y verifica que quede sin superuser ni BYPASSRLS.
#
# Uso:
#   APP_DB_PASSWORD='...' ./create_app_role.sh <contenedor> [rol]
#
# Ejemplos:
#   APP_DB_PASSWORD='xxx' ./create_app_role.sh inv-postgres-staging
#   APP_DB_PASSWORD='yyy' ./create_app_role.sh inv-postgres inv_app
#
# El owner y la base se leen del propio contenedor, así que no hay que
# repetirlos ni mantenerlos sincronizados con el .env.

set -euo pipefail

CONTAINER="${1:?Falta el nombre del contenedor de PostgreSQL}"
APP_ROLE="${2:-inv_app}"
APP_PASSWORD="${APP_DB_PASSWORD:?Falta la variable de entorno APP_DB_PASSWORD}"

OWNER="$(docker exec "$CONTAINER" printenv POSTGRES_USER)"
DB_NAME="$(docker exec "$CONTAINER" printenv POSTGRES_DB)"

echo "Contenedor : $CONTAINER"
echo "Base       : $DB_NAME"
echo "Owner      : $OWNER"
echo "Rol de app : $APP_ROLE"
echo

docker exec -i "$CONTAINER" psql \
    -U "$OWNER" -d "$DB_NAME" \
    -v ON_ERROR_STOP=1 \
    -v app_role="$APP_ROLE" \
    -v app_password="$APP_PASSWORD" \
    -v owner="$OWNER" \
    -v db_name="$DB_NAME" \
    -f - < "$(dirname "$0")/create_app_role.sql"

echo
echo "Comprobando que el rol no pueda saltarse RLS..."
BAD="$(docker exec "$CONTAINER" psql -U "$OWNER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM pg_roles WHERE rolname='$APP_ROLE' AND (rolsuper OR rolbypassrls);")"

if [ "$BAD" != "0" ]; then
    echo "ERROR: $APP_ROLE conserva superuser o BYPASSRLS. RLS seguiría inerte." >&2
    exit 1
fi

echo "OK: $APP_ROLE está sujeto a RLS."

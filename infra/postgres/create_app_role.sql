-- Crea el rol restringido con el que debe correr la aplicación.
--
-- Contexto: el rol por defecto de la imagen de PostgreSQL (POSTGRES_USER) es el
-- superusuario de bootstrap, y los superusuarios ignoran RLS incluso con FORCE.
-- Si la app se conecta con él, las políticas de aislamiento por tenant quedan
-- inertes. Este script crea un rol sin superuser ni BYPASSRLS y le concede los
-- permisos mínimos para operar.
--
-- Idempotente: se puede ejecutar varias veces sin efecto adicional.
-- Se invoca normalmente desde create_app_role.sh, no a mano.
--
-- Variables requeridas: app_role, app_password, owner, db_name

\set ON_ERROR_STOP on

-- 1. El rol ------------------------------------------------------------------
-- Nota: se usa \gexec en lugar de un bloque DO porque psql no interpola
-- variables dentro de cadenas con comillas de dólar.

SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE',
    :'app_role', :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role')
\gexec

-- Si el rol ya existía, se realinean contraseña y atributos. El ALTER de
-- atributos es deliberado: corrige el caso en que el rol hubiera quedado con
-- privilegios de más, que es justo el defecto que este script viene a arreglar.
SELECT format(
    'ALTER ROLE %I PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE',
    :'app_role', :'app_password'
)
\gexec

-- 2. Permisos sobre el esquema -----------------------------------------------
GRANT CONNECT ON DATABASE :"db_name" TO :"app_role";
GRANT USAGE ON SCHEMA public TO :"app_role";

-- 3. Permisos sobre lo que ya existe ------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_role";
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO :"app_role";

-- 4. Permisos sobre lo que cree Alembic en el futuro --------------------------
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO :"app_role";

-- 5. Verificación --------------------------------------------------------------
SELECT rolname,
       rolsuper     AS es_superusuario,
       rolbypassrls AS ignora_rls
FROM pg_roles
WHERE rolname = :'app_role';

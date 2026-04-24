-- Función helper para obtener el tenant actual (inyectado desde la aplicación)
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS uuid AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true)::uuid;
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Nota: Las políticas RLS específicas (CREATE POLICY) se crearán mediante Alembic
-- en las migraciones de SQLAlchemy para cada tabla transaccional (products, stock_balances, etc)

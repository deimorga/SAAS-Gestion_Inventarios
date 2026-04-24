# Reglas de Gobernanza y Negocio - SaaS Gestión de Inventarios (MicroNuba Inventory)

Este documento define las directrices operativas, técnicas y de negocio vinculantes para el proyecto. Complementa a `RULES.md` y debe ser consultado por el Orquestador antes de cada ciclo de desarrollo.

## 1. Stack Tecnológico Unificado (SSoT)
- **Frontend:** Angular 17+ (PWA). 
    - Uso de **Signals** para estado reactivo.
    - **Standalone Components** por defecto.
    - Estilizado con CSS nativo / Flexible UI.
- **Backend:** FastAPI (Python 3.11+).
    - Tipado estricto con **Pydantic v2**.
    - Inyección de dependencias para contexto de Tenant.
- **Base de Datos:** PostgreSQL 16+.
    - Implementación obligatoria de **Row Level Security (RLS)**.
    - Herramienta de migración: Alembic.

## 2. Pilares Multi-Tenancy
> [!IMPORTANT]
> El aislamiento de datos es la prioridad #1. Ninguna funcionalidad debe comprometer la segregación de tenants.

- **Identificación:** El `tenant_id` se extrae automáticamente del token JWT o subdominio.
- **RLS:** Todas las tablas transaccionales deben tener habilitado RLS y una política vinculada a `current_setting('app.current_tenant')`.
- **Branding:** Soporte White-Label mediante tokens CSS cargados dinámicamente desde la configuración del tenant en la DB.

## 3. Modelo Operativo del Inventario (Ciclo de Vida)
El sistema debe gestionar el flujo de inventario bajo estas capacidades críticas:
1. **Catálogo de Productos:** SKUs con atributos dinámicos, categorías y unidades de medida.
2. **Gestión Multi-Sede:** Jerarquía de almacenes, bodegas y tiendas (nodos de árbol).
3. **Motor Transaccional Atómico:** Operaciones ACID de entrada, salida y transferencia de stock.
4. **Costo Promedio Ponderado (CPP):** Recálculo automático del costo unitario ante cada entrada.
5. **Kardex Histórico:** Registro inmutable y auditable de todos los movimientos.
6. **Alertas y Reposición:** Reorder Point, webhooks de stock crítico y notificaciones.
7. **Reservas (Soft Reservation):** Bloqueo temporal de stock para pedidos pendientes.
8. **Reportes y Valoración:** Balance Snapshots, valoración contable, exportación masiva.

## 4. Gobernanza Documental e Infraestructura
Para cualquier modificación, el agente DEBE regirse por los documentos en:
- **Estructura:** `doc/Estructura/estructura_proyecto.md` (Referencia inamovible de rutas).
- **Arquitectura:** `doc/Arquitectura/Arquitectura definida/` (Física e infraestructura).
- **Funcional:** `doc/Funcional/mejorado/` (Definición SaaS y Requerimientos).
- **Planeación/Técnico:** `doc/Planeacion/` y `doc/Tecnico/` para el diseño y seguimiento de tareas.

## 5. Ecosistema de Habilidades (Skills)
El agente debe apoyarse en las herramientas especializadas ubicadas en `.agent/skills/`:
- **Orquestador Principal (`orquestador_proyecto`):** Punto de entrada obligatorio para cualquier flujo.
- **Especialistas:** Consultar skills dedicadas (Backend Python, Frontend Angular, DB Postgres, UX/UI, etc.).

## 6. Reglas de Desarrollo y Calidad
- **Cero Hardcoding:** Valores de configuración siempre vía variables de entorno supervisadas por Docker.
- **Pensamiento Crítico:** El agente debe cuestionar cambios que violen el aislamiento RLS, la atomicidad transaccional o el modelo Multi-Tenant.
- **Verificación:** Prohibido dar por terminada una tarea de UI sin validación mediante `browser_subagent`.
- **Commits:** Mensajes bajo estándar Conventional Commits.

## 7. Estándares de Testing por Capa

> [!IMPORTANT]
> Estos estándares son **obligatorios**. El `verificador_calidad` evalúa contra estos estándares en cada cierre de tarea.

### 7.1 — Estándar Backend (Pytest + mypy + ruff)

**Estructura de tests obligatoria:**
```
core_backend/
└── tests/
    ├── unit/          # Tests por función/servicio
    │   ├── test_auth_service.py
    │   ├── test_inventory_service.py
    │   ├── test_cpp_calculator.py
    │   └── ...
    ├── integration/   # Tests por endpoint HTTP
    │   ├── test_auth_endpoints.py
    │   ├── test_products_endpoints.py
    │   ├── test_movements_endpoints.py
    │   └── ...
    ├── security/      # Tests de aislamiento RLS y OWASP
    │   ├── test_rls_isolation.py
    │   └── test_auth_security.py
    └── conftest.py    # Fixtures compartidos
```

**Comandos y umbrales obligatorios:**
```bash
pytest core_backend/tests/ --cov=app --cov-report=term-missing --cov-fail-under=80
pytest core_backend/tests/ --cov=app/api/auth --cov=app/core --cov-fail-under=100
mypy core_backend/app/ --ignore-missing-imports
ruff check core_backend/app/
```

**Reglas de escritura de tests:**
- Patrón **AAA** obligatorio: Arrange → Act → Assert.
- IDs: `test_[modulo]_[accion]_[escenario]` (ej: `test_inventory_transfer_insufficient_stock`).
- Tests de integración deben usar DB real de test (fixture `test_db`).
- Tests RLS: probar con `tenant_a` y `tenant_b`, verificar aislamiento.

### 7.2 — Estándar Frontend (Jest/Karma + Playwright)

**Comandos y umbrales obligatorios:**
```bash
cd web_frontend && ng test --watch=false --code-coverage --browsers=ChromeHeadless
cd web_frontend && ng build --configuration=production
cd web_frontend && ng lint
```

**Reglas:**
- Todo Standalone Component debe tener `.spec.ts`.
- Todo Service debe tener `.spec.ts` con mocks HTTP.
- Guards e Interceptors: tests con token válido e inválido.

### 7.3 — Estándar Base de Datos (Alembic + PostgreSQL RLS)

- Cada migración: `upgrade()` y `downgrade()` completas.
- `downgrade()` probado antes de cerrar tarea.
- Seeds solo en `tests/conftest.py`, nunca en migraciones.
- Nombres: `YYYY_MM_DD_HHMM_descripcion_corta.py`.

**RLS obligatorio:**
```sql
ALTER TABLE nombre_tabla ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON nombre_tabla
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### 7.4 — Estándar E2E / Funcional

- 100% de criterios Gherkin cubiertos por RF.
- Happy path: siempre automatizado o con evidencia manual.
- Flujos `Must`: siempre cubiertos. Flujos `Should`: ≥50%.
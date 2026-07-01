# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MicroNuba Inventory Management** — A multi-tenant SaaS platform for inventory and warehouse management. Built with FastAPI (Python backend), NiceGUI (Python admin portal frontend), PostgreSQL with Row-Level Security (RLS), Redis, and Celery for async tasks.

The system manages products, warehouses, stock balances, reservations, batches, suppliers, webhooks, and includes comprehensive audit logging and API key management. Multi-tenancy is enforced at the database level using PostgreSQL RLS policies.

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend API** | FastAPI 0.110.0, Uvicorn, SQLAlchemy 2.0 async |
| **Database** | PostgreSQL 15 with RLS, Alembic migrations |
| **Cache/Queue** | Redis 7, Celery 5.3 (worker + beat scheduler) |
| **Admin Portal** | NiceGUI 2.0 (Python, server-side rendered) |
| **Auth** | JWT + API Keys, BCrypt hashing |
| **Email** | Resend SDK (transactional) |
| **Testing** | pytest, pytest-asyncio, httpx, coverage |
| **Code Quality** | Ruff (linter), mypy (type checker) |

## Project Structure

```
core_backend/                   # FastAPI backend
├── app/
│   ├── main.py               # App init, background task loops
│   ├── tasks.py              # Celery tasks (email, API key rotation)
│   ├── api/
│   │   ├── deps.py           # Auth, RLS session injection, rate limiting
│   │   ├── v1/               # Tenant API endpoints
│   │   │   ├── endpoints/    # 20+ route modules (auth, products, inventory, etc.)
│   │   │   └── router.py     # Aggregates all v1 endpoints
│   │   └── admin/            # Admin-only endpoints (super_admin management)
│   ├── services/             # Business logic (24+ service modules)
│   ├── schemas/              # Pydantic request/response schemas
│   ├── models/               # SQLAlchemy ORM models
│   └── core/
│       ├── config.py         # Settings from .env
│       ├── database.py       # Async engine, RLS session helpers
│       ├── security.py       # JWT, API key, password hashing
│       ├── redis_client.py   # Redis connection pool
│       └── exceptions.py     # Custom exception handlers
├── alembic/                  # Database migrations (13 revisions)
├── tests/                    # 23+ test modules (RLS isolation, auth, etc.)
├── scripts/                  # Utilities (export_openapi.py)
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Ruff, pytest, coverage config
└── Dockerfile.dev            # Development Docker image

web_frontend/                 # NiceGUI admin portal
├── app/
│   ├── main.py              # UI pages (login, tenants, API keys, etc.)
│   └── api.py               # HTTP client wrapper for backend API
├── requirements.txt         # NiceGUI, httpx
└── Dockerfile               # Production-ready image

docker-compose.dev.yml       # Dev stack: API, worker, beat, postgres, redis, portal
docker-compose.prod.yml      # Prod stack with Traefik, external net
```


## Running & Development

### Prerequisites

- Docker & Docker Compose
- Python 3.12 (for local dev without Docker)
- `.env` file (copy from `.env.example`)

### Development Stack

```bash
# Start all services
docker compose -f docker-compose.dev.yml up -d

# Access:
# - API docs:     http://localhost:8002/docs
# - Admin portal: http://localhost:8081
# - DB:           localhost:5433 (postgres)
# - Redis:        localhost:6380

# View logs
docker compose -f docker-compose.dev.yml logs -f api

# Stop
docker compose -f docker-compose.dev.yml down
```

### Backend Development (Local)

```bash
cd core_backend

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest                          # All tests
pytest tests/test_auth.py      # Single file
pytest -k test_login           # By name
pytest --cov=app               # With coverage
pytest -s                      # Show print output

# Code quality
ruff check app/ --fix          # Lint & auto-fix
mypy app/                      # Type check

# Database
alembic current                # Show current revision
alembic upgrade head           # Apply migrations
alembic revision --autogenerate -m "description"  # Generate from models

# Run API locally
uvicorn app.main:app --reload
```

## Architecture Highlights

### Multi-Tenancy & Row-Level Security

**Core Pattern**: All tenant data isolation enforced at the PostgreSQL RLS level, not application logic.

- Per-request tenant context: `SET LOCAL app.current_tenant = <tenant_id>`
- Auth flow: JWT/API Key → `get_current_auth()` → `get_auth_db()` (RLS-enabled session)
- Super admin bypass: Uses sentinel value `__super_admin__` to bypass RLS (migration 012)
- RLS is FORCE on sensitive tables (`users`, `api_keys`, `audit_logs`) — prevents accidental unprotected queries

**Key Files**:
- `app/api/deps.py` — Auth extraction and session injection
- `app/core/database.py` — Session factories with RLS context
- `alembic/versions/012_admin_bootstrap.py` — RLS policy definitions

### Authentication & Authorization

**JWT Tokens**:
- `access_token` (30 min): Contains user_id, tenant_id, role, scope
- `refresh_token` (7 days): Opaque, stored in Redis, single-use (rotates on refresh)

**API Keys**:
- Format: `mk_live_*` (key_id) + `mk_secret_*` (secret)
- Secret hashed with SHA-256 before DB storage
- Scoped (e.g., `["ADMIN"]`) and expirable with grace period (default 30 days)

**Roles**: `super_admin`, `tenant_admin`, `inventory_manager`, `viewer`

**Rate Limiting**: Per-tenant based on subscription tier (STARTER: 60 rpm, PROFESSIONAL: 1k rpm, ENTERPRISE: 10k rpm)

**Key Files**:
- `app/api/deps.py` — Role guards (`require_admin`, `require_catalog_write`)
- `app/core/security.py` — Token generation, API key hashing, rate limit tiers
- `app/api/v1/endpoints/auth.py` — User login/refresh
- `app/api/admin/endpoints/admin_auth.py` — Admin registration/login

### Services & Dependency Injection

**Pattern**: 
1. FastAPI endpoint receives dependencies via `Depends()`
2. Dependencies inject auth context + RLS-enabled DB session
3. Service layer performs business logic
4. Endpoint validates + returns response

Example: `POST /v1/products`:
```
endpoint(products.py)
  └─ Depends(get_auth_db, require_catalog_write)
     └─ calls: service.create_product(session, auth, body)
        └─ persists, audit logs, returns response
```

**Codebase Structure**:
- `app/api/v1/endpoints/` — 20+ endpoint modules (thin, validation-focused)
- `app/services/` — 24+ service modules (thick, business logic)


### Async Database Access

**Design**: All database operations async via SQLAlchemy 2.0 + asyncpg.

- Sessions never leak across requests (context vars + dependency injection)
- Pool: 5 base connections, 10 overflow (tuned for typical load)
- Alembic supports async migrations (`env.py`)

**Key Files**:
- `app/core/database.py` — Async engine config
- `alembic/env.py` — Async migration runner

### Inventory & Stock Management

**Entity Hierarchy**:
- `Product` (SKU, name, UOM) → `StockBalance` (qty_on_hand, reserved_qty, available_qty)
- `Warehouse` → `Zone` (physical location hierarchy)
- `Transaction` (stock movement log: IN, OUT, ADJUST, RESERVE, etc.)
- `InventoryLedger` (immutable audit trail for reporting)
- `Reservation` (temporary stock hold, auto-expires)
- `Batch` + `SerialNumber` (lot tracking)

**Concurrency Safety**:
- Optimistic locking via `StockBalance.version`
- Bin-level exclusivity via `LocationLock` table
- Transactions are ACID-compliant (PostgreSQL enforces)

**Key Files**:
- `app/services/inventory.py` — Core stock adjustment logic
- `app/models/stock_balance.py`, `transaction.py`, `inventory_ledger.py` — Models

### Background Tasks & Scheduling

**Celery Workers**:
- `inv-worker` — Processes `default`, `webhooks`, `bulk` queues (4 concurrency)
- `inv-beat` — Scheduler (runs API key expiry check daily at 8 AM UTC)

**Tasks**:
- `send_email` — Via Resend SDK (retry 3x exponential backoff)
- `check_expiring_api_keys` — Detects keys expiring in 30/7/1/0 days
- `revoke_grace_period_key` — Auto-revoke expired key after grace

**Webhook Dispatch** (in `app/main.py`, not Celery):
- Polls for pending deliveries every 10 sec
- Retries with backoff: 30s → 5min → 30min (max 3 attempts)
- HMAC-SHA256 signature in `X-Signature` header

**Key Files**:
- `app/tasks.py` — Task definitions, Beat schedule
- `app/main.py` — Background loops (webhook dispatch, reservation expiry)

### Admin Portal (NiceGUI)

**Architecture**: Server-side rendered Python UI (no separate frontend build).

- Single `main.py` with page decorators (`@ui.page`)
- Client state in `app.storage.user` (browser localStorage)
- HTTP client (`app.api`) abstracts backend calls
- Pages: login, tenant list, API keys, audit logs, webhooks

**Pages implemented:**
- `/login` — Super admin login
- `/tenants` — List with view/suspend buttons per row
- `/tenants/{id}` — Detail with Acciones: Suspender, Gestionar Productos, Gestionar Stock
- `/tenants/{id}/products` — CRUD productos (SKU, nombre, precio venta, UOM, descripción)
- `/tenants/{id}/stock` — Ver saldos, entrada de stock, ajuste por fila, eliminar (ajuste a 0)

**Key Files**:
- `web_frontend/app/main.py` — All UI pages
- `web_frontend/app/api.py` — HTTP client wrapper

## Database & Migrations

### Schema Outline

**Multi-Tenancy** (NOT under RLS):
- `tenants` — Org accounts

**Users & Auth** (RLS FORCE):
- `users` — User accounts
- `api_keys` — API credentials
- `audit_logs` — User action log

**Catalog**:
- `categories`, `products`, `product_uoms` — Product master
- `suppliers`, `supplier_products` — Supplier relationships
- `kits`, `kit_components` — Product bundles

**Warehouse**:
- `warehouses`, `zones`, `bins` — Physical locations
- `location_locks` — Bin-level exclusivity

**Inventory**:
- `stock_balances` — Current stock (qty_on_hand, reserved_qty, available_qty)
- `transactions` — Stock movements
- `inventory_ledgers` — Immutable audit trail
- `reservations`, `reservation_items` — Temporary holds
- `batches`, `serial_numbers` — Batch tracking
- `cycle_count_sessions`, `cycle_count_items` — Physical counts
- `channel_allocations` — Channel stock reservations
- `webhooks` — Endpoint definitions
- `webhook_deliveries` — Async delivery queue

### Alembic Migrations

12 revisions in `core_backend/alembic/versions/`:
1. **001** — Initial schema
2. **002** — Catalog enhancements
3. **003** — Inventory (transactions, ledgers, reservations)
4. **004** — Reports & ledger fixes
5. **005** — Ledger transaction nullable fields
6. **006** — Webhooks
7. **007** — Cycle counts
8. **008** — Suppliers
9. **009** — Batches & serials
10. **010** — Bins & location locks
11. **011** — Channel allocations
12. **012** — Admin bootstrap & RLS policies
13. **013** — `sale_price` (Numeric 18,4, nullable) en tabla `products`

**Migration Commands**:
```bash
cd core_backend
alembic upgrade head              # Apply all pending
alembic downgrade -1              # Rollback one revision
alembic revision --autogenerate -m "desc"  # Generate from model changes
```


## Environment Variables

Critical settings in `.env`:

| Variable | Purpose | Dev Default |
|----------|---------|-------------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | DB credentials | inventory_user / devpassword123 / inventory_db |
| `REDIS_PASSWORD` | Redis auth (prod only) | devpassword123 |
| `JWT_SECRET_KEY` | JWT signing key | dev-secret-key-change-in-production |
| `ADMIN_BOOTSTRAP_SECRET` | First super_admin protection | change-me-bootstrap-secret |
| `ENABLE_SWAGGER` | Swagger UI visibility | true (dev) / false (prod) |
| `RESEND_API_KEY` | Email provider (Resend) | re_test_placeholder |
| `ACTIVATION_BASE_URL` | User activation link base | http://api.inventarios.local:8090 |
| `ACTIVATION_TOKEN_TTL_HOURS` | Activation email link validity | 48 |
| `API_KEY_EXPIRY_DAYS` | Default API key lifetime | 365 |
| `WEBHOOK_POLL_SECONDS` | Webhook dispatch polling interval | 10 |

## Testing

### Test Modules

All tests in `core_backend/tests/`:
- `test_auth.py`, `test_admin_auth.py`, `test_activation.py` — Auth & admin
- `test_inventory.py`, `test_reservations.py`, `test_cycle_counts.py` — Inventory
- `test_products.py`, `test_categories.py`, `test_suppliers.py` — Catalog
- `test_warehouses.py`, `test_bins.py`, `test_batches.py` — Warehouse
- `test_rls_isolation.py`, `test_api_key_rotation.py` — Security
- `test_webhooks.py`, `test_tasks.py` — Async & webhooks

### Running Tests

```bash
cd core_backend
pytest                       # All tests
pytest tests/test_auth.py   # Single file
pytest -k test_login        # By name
pytest --cov=app            # With coverage
pytest -v --tb=short        # Verbose with short tracebacks
pytest -s                   # Show print statements
```

### Fixtures (conftest.py)

- `async_client` — HTTPX test client
- `db_session` — Fresh per-test DB (rollback cleanup)
- `redis_client` — Test Redis instance
- `auth_token()` — Generate JWT for tests
- `api_key()` — Generate API key for tests
- `tenant()` — Create test tenant with users

Tests are async-aware (`pytest-asyncio`). Database uses transaction rollback for cleanup.

## Debugging Tips

### Common Issues

**RLS Policy Violations**
- Error: `new row violates row-level security policy`
- Cause: Missing `app.current_tenant` context var
- Fix: Use `Depends(get_auth_db)` not `Depends(get_db)`
- Debug: Check `request.state.auth.tenant_id`

**JWT Token Fails**
- Error: `401 No autenticado` on every request
- Check: Bearer token format, `JWT_SECRET_KEY` consistency, expiry

**Connection Pool Exhaustion**
- Symptom: Timeouts, `QueuePool timeout exceeded`
- Cause: Sessions not properly closed
- Fix: Verify all `async with AsyncSessionLocal()` have matching `yield`

**Redis Connection Fails**
- Error: `ConnectionError` in worker logs
- Check: `docker compose logs redis`, `REDIS_PASSWORD` in .env

**Webhook Delivery Stuck**
- Cause: Target endpoint unreachable or erroring
- Check: `webhook_deliveries.status`, response_body, retry count
- Logs: `docker compose logs api` for dispatch loop errors

### Useful SQL Queries

```sql
-- Check RLS policies active for a table
SELECT * FROM pg_policies WHERE tablename = 'users';

-- Bypass RLS for debugging (super_admin only, DANGEROUS)
SET app.current_tenant = '__super_admin__';
SELECT COUNT(*) FROM users;  -- Shows all users

-- Tenant isolation check
SET app.current_tenant = '<tenant-uuid>';
SELECT * FROM users;  -- Only shows that tenant's users

-- Audit trail for a user
SELECT * FROM audit_logs 
WHERE tenant_id = '<tenant-uuid>' 
  AND user_id = '<user-uuid>'
ORDER BY created_at DESC;
```

## Key Implementation Patterns

### Service Pattern with RLS Session

```python
# In app/api/v1/endpoints/products.py
@router.post("/products", response_model=ProductResponse)
async def create_product(
    body: ProductCreateRequest,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),  # RLS session
):
    return await service.create_product(db, auth.tenant_id, body)

# In app/services/product.py
async def create_product(
    db: AsyncSession,
    tenant_id: str,
    body: ProductCreateRequest,
) -> ProductResponse:
    product = Product(
        tenant_id=tenant_id,
        sku=body.sku,
        name=body.name,
        ...
    )
    db.add(product)
    await audit_log(db, tenant_id, "product_created", product.id)
    await db.commit()
    return ProductResponse.from_orm(product)
```


### RLS Policy (PostgreSQL)

```sql
-- From alembic/versions/012_admin_bootstrap.py
-- SELECT policy for products table
CREATE POLICY "tenants_see_own_products" ON products
  FOR SELECT
  USING (
    tenant_id = current_setting('app.current_tenant')::uuid
    OR current_setting('app.current_tenant') = '__super_admin__'
  );
```

### Background Task with Celery

```python
# In app/tasks.py
@celery_app.task(bind=True)
def send_email(self, recipient: str, subject: str, html: str) -> None:
    try:
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": recipient,
            "subject": subject,
            "html": html,
        })
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60, max_retries=3)
```

## Security & Performance

### Security

- **Secrets**: Never commit `.env`. Use `ADMIN_BOOTSTRAP_SECRET` for one-time setup, then clear.
- **CORS**: Frontend on different port (8081); see docker-compose.dev.yml for middleware.
- **Rate Limiting**: Per-tenant tier-based (STARTER: 60 rpm).
- **Email**: Resend SDK requires valid key for production; dev uses test key.
- **Audit Logging**: All admin actions logged to `audit_logs` table with full RLS isolation.

### Concurrency & Locking

- Optimistic locking via `StockBalance.version` (no pessimistic locks)
- Bin-level exclusivity via `LocationLock` (one writer per bin)
- Reservation TTL enforced via background loop every 60 sec
- Celery tasks are idempotent (no distributed transactions)

### Performance

- All list endpoints support `limit` + `offset` pagination
- Ensure migrations include indexes on frequently-queried columns (tenant_id, warehouse_id, product_id)
- Bulk operations via `POST /v1/bulk` reduce round-trips
- Tier info cached in Redis (`tenant_tier:<id>`) per request

## Command Reference

```bash
# Dev stack
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.dev.yml down

# Backend (Python)
cd core_backend
pip install -r requirements.txt
pytest
ruff check app/ --fix
mypy app/
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (Python)
cd web_frontend
pip install -r requirements.txt
python -m app.main
```

## Cambios Recientes (Sprint 8 — Gestión desde Portal Admin)

### Nuevos campos
- `Product.sale_price` — Precio de venta opcional (Numeric 18,4, nullable). Migración 013.

### Nuevos endpoints admin (`app/api/admin/`)
Todos requieren JWT `super_admin`. Usan sesión con RLS del tenant específico (no `__super_admin__`).

| Endpoint | Descripción |
|----------|-------------|
| `GET /admin/tenants/{id}/products` | Listar productos del tenant |
| `POST /admin/tenants/{id}/products` | Crear producto |
| `PATCH /admin/tenants/{id}/products/{pid}` | Actualizar producto |
| `DELETE /admin/tenants/{id}/products/{pid}` | Desactivar producto |
| `GET /admin/tenants/{id}/categories` | Listar categorías |
| `GET /admin/tenants/{id}/stock` | Saldos de stock |
| `POST /admin/tenants/{id}/stock/receipts` | Entrada de mercancía |
| `POST /admin/tenants/{id}/stock/adjustments` | Ajuste de stock (campo: `new_qty`) |
| `GET /admin/tenants/{id}/warehouses` | Listar almacenes |
| `GET /admin/tenants/{id}/warehouses/{wid}/zones` | Listar zonas |

**Archivos:** `app/api/admin/endpoints/admin_products.py`, `admin_stock.py`

### Fixes aplicados
- `LoginRequest` — removido `min_length=8` del campo `password` (solo aplica al registro)
- `AdjustmentItem.new_qty` — el campo correcto para ajustes es `new_qty`, no `actual_qty`
- Super admin: contraseña se puede resetear con `passlib.context.CryptContext` desde el contenedor API

### Git
- Rama `staging` creada y subida a GitHub — idéntica a `main`
- Flujo: desarrollar en `staging`, merge a `main` para producción

## Glossary

- **RLS** — Row-Level Security (PostgreSQL per-tenant isolation)
- **Tenant** — Customer org with isolated data
- **Zone** — Sub-area within a warehouse
- **Stock Balance** — Current inventory state for product + zone
- **Transaction** — Single stock movement (IN, OUT, ADJUST, RESERVE)
- **Ledger** — Immutable audit trail of transactions
- **Reservation** — Temporary stock hold (expires after TTL)
- **Batch** — Lot tracking (received date, expiry)
- **Webhook** — Event notification to external service
- **Cycle Count** — Physical inventory audit

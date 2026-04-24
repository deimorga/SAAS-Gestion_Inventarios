# Estructura de Proyecto (SaaS Gestión de Inventarios)
**Estatus:** `Oficial`

Basado en las directrices de `[ARQUITECTURA_FISICA.md](../Arquitectura/Arquitectura%20definida/ARQUITECTURA_FISICA.md)` y las `[ESPECIFICACIONES_INFRAESTRUCTURA.md](../Arquitectura/Arquitectura%20definida/ESPECIFICACIONES_INFRAESTRUCTURA.md)`, este documento rige la anatomía del árbol de directorios del repositorio monorepo.

> [!IMPORTANT]
> **Paradigma Monorepo:** Mantenemos Frontend, Backend, Documentación e Infraestructura en un solo repositorio de Git para garantizar **Atomicidad de Features** (cada PR implementa API y UI al mismo tiempo) y centralización del contexto para desarrolladores e IAs.

---

## 🌳 Árbol Principal de Directorios

```ascii
SAAS-Gestion_Inventarios/
├── .agent/                    # [Mantenido] Habilidades (Skills) y Reglas de la IA.
├── .gemini/                   # [Mantenido] Task lists y memoria de sesión del agente.
├── doc/                       # [Mantenido] Documentación Técnica, Funcional y de Arquitectura.
│   ├── Arquitectura/          # Diseño de arquitectura física, lógica e infraestructura.
│   ├── Documentacion de Idea/ # Documentos originales de la idea del proyecto (Google Docs).
│   ├── Estructura/            # Mapa oficial de directorios (este archivo).
│   ├── Funcional/             # Requerimientos funcionales e historias de usuario.
│   │   └── mejorado/         # Docs formalizados (RF + HU por módulo)
│   │       ├── 00_definicion-solucion_saas/  # DEFINICION_SAAS.md
│   │       ├── 01_catalogo_productos/        # Gestión de SKU, categorías, atributos
│   │       ├── 02_sedes_almacenes/           # Jerarquía de nodos multi-sede
│   │       ├── 03_motor_transaccional/       # Entradas, salidas, transferencias ACID
│   │       ├── 04_kardex/                    # Registro histórico de movimientos
│   │       ├── 05_alertas_reposicion/        # Reorder point, webhooks stock crítico
│   │       ├── 06_autenticacion/             # JWT RS256, API Keys, RBAC
│   │       ├── 07_gestion_usuarios/          # Roles, permisos, tenant admin
│   │       └── 08_reportes_valoracion/       # Balance snapshots, CPP, exportación
│   ├── Planeacion/            # 📋 Gestión Ágil y Planeación del Proyecto
│   │   ├── Backlog/           # Product Backlog priorizado
│   │   ├── Sprints/           # Registro de ejecución por sprint
│   │   └── Planes_Trabajo/    # Secuencia de ejecución por feature/requerimiento
│   └── Tecnico/               # Definiciones técnicas de diseño por requerimiento
│
├── core_backend/              # 🐍 Aplicación Backend (FastAPI / Python)
│   ├── app/                   # Lógica central del sistema SaaS
│   │   ├── api/               # Controladores / Endpoints REST (Routers)
│   │   │   ├── auth/          # Autenticación, tokens, API Keys
│   │   │   ├── tenants/       # Gestión de tenants y configuración
│   │   │   ├── products/      # Catálogo de productos y SKU
│   │   │   ├── warehouses/    # Sedes y almacenes (jerarquía de nodos)
│   │   │   ├── movements/     # Motor transaccional (entradas, salidas, transferencias)
│   │   │   ├── kardex/        # Consulta de Kardex histórico
│   │   │   └── reports/       # Reportes, valoración, balance snapshots
│   │   ├── core/              # Configuraciones de Seguridad, JWT, Contexto Multi-tenant, RLS middlewares
│   │   ├── models/            # Entidades de Base de Datos (SQLAlchemy/SQLModel)
│   │   ├── schemas/           # Pydantic Schemas (Validadores y DTOs)
│   │   └── services/          # Lógica de negocio (CPP, motor atómico, alertas)
│   ├── worker/                # Tareas asíncronas para Celery (Webhooks, Reportes, Alertas)
│   ├── tests/                 # Suite de pruebas automatizadas (Pytest)
│   │   ├── unit/              # Tests unitarios por servicio
│   │   ├── integration/       # Tests de integración por endpoint
│   │   ├── security/          # Tests de aislamiento RLS
│   │   └── conftest.py        # Fixtures compartidos
│   └── Dockerfile             # Construcción de la imagen Non-Root (API + Celery)
│
├── web_frontend/              # 🅰️ Aplicación PWA Frontend (Angular 17+)
│   ├── src/                   # Código de componentes
│   │   ├── app/               # Standalone Components, Rutas, Signals y Lógica
│   │   │   ├── pages/         # Páginas principales (dashboard, productos, movimientos)
│   │   │   ├── components/    # Componentes reutilizables (tablas, formularios, gráficos)
│   │   │   └── services/      # Servicios de comunicación con API
│   │   ├── core/              # Interceptores HTTP (Auth & Tenant Headers), Guards
│   │   ├── environments/      # Variables de compilación (.prod y .dev)
│   │   └── assets/            # Imágenes, iconos, manifest.json para PWA
│   ├── nginx.conf             # Configuración custom de headers de seguridad para proxy estático
│   └── Dockerfile             # Build Multi-stage (Node JS Builder -> Nginx Alpine Runner)
│
├── infra/                     # 🐳 Orquestación y DevSecOps (Docker Compose)
│   ├── traefik/               # Configuración estática y gestión de TLS por subdominios
│   ├── postgres/              # Scripts de inicialización SQL (Configuración de RLS por defecto)
│   ├── minio/                 # Estructuras por defecto para almacenamiento de buckets locales
│   └── docker-compose.dev.yml # Manifiesto para levantar TODA LA SOLUCIÓN en localhost
│
├── .env.example               # 🔑 Plantilla de Secretos y Entornos (Documentada, 0 contraseñas reales)
├── .gitignore                 # Reglas generales de exclusión (node_modules, __pycache__, .env)
└── README.md                  # Landing técnica del repositorio y comandos Quick Start
```

---

## 📜 Reglas de Navegación Arquitectónica

1. **Dependencias Aisladas**: `core_backend` y `web_frontend` poseen sus propios gestores de paquetes y dependencias (Pip/Poetry localmente y NPM/Yarn para Node). Evitar mezclar.
2. **Contexto de Infraestructura**: Si una configuración afecta variables de entorno, mapeo de puertos o contenedores, es responsabilidad estricta modificarse dentro de `infra/`.
3. **Manejo de Webhooks**: El ingreso HTTP llega a `core_backend/app/api/webhooks.py`, se valida el HMAC y se encomienda de inmediato a la cola, para que la lógica pesada suceda en `core_backend/worker/`.
4. **PWA Standalone**: El `web_frontend` genera artefactos estáticos minificados. Su Dockerfile creará una imagen ligera de `Nginx` y su único propósito es servir los ficheros. La comunicación UI-Datos es única y estrictamente contra el `backend`.
5. **Motor Transaccional**: Toda lógica de movimientos de inventario (entradas, salidas, transferencias) debe residir en `core_backend/app/services/` y ser invocada desde los endpoints en `core_backend/app/api/movements/`. Las operaciones ACID deben garantizarse a nivel de base de datos.
6. **Capa de Servicios**: La lógica de negocio compleja (CPP, motor atómico, alertas) se encapsula en `core_backend/app/services/`, separada de los endpoints REST.

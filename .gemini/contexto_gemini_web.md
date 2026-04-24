# Contexto de Sesión — SaaS Gestión de Inventarios (MicroNuba Inventory)

> Última actualización: 2026-04-23T23:47:00-05:00

## Resumen Sesión Actual (Inicialización del Proyecto)

Se inicializó el proyecto **SaaS Gestión de Inventarios** (MicroNuba Inventory) tomando como base el esqueleto del proyecto anterior (Gestión Talleres). Se actualizaron todos los documentos de gobernanza para reflejar el nuevo dominio de negocio: **gestión de inventarios multi-tenant con motor transaccional atómico**.

### Artefactos creados/modificados:

| Artefacto | Acción | Descripción |
|-----------|--------|-------------|
| `.gemini/task.md` | Reescrito | Nuevo roadmap de 5 fases para inventarios |
| `.gemini/contexto_gemini_web.md` | Reescrito | Contexto adaptado al dominio de inventarios |
| `.agent/RULES.md` | Reescrito | Reglas operativas adaptadas a inventarios |
| `.agent/rules/reglas.md` | Reescrito | Modelo operativo del inventario (8 capacidades) |
| `.agent/rules/restore_context.md` | Reescrito | Referencias actualizadas al nuevo proyecto |
| `.agent/rules/definition_of_done.md` | Reescrito | DoD adaptada a inventarios |
| `.agent/rules/MANUAL_DE_USO.md` | Reescrito | Manual de operación actualizado |
| `doc/Estructura/estructura_proyecto.md` | Reescrito | Estructura del monorepo adaptada |

## Estado del Proyecto

El proyecto **SaaS Gestión de Inventarios** se encuentra en fase de **inicialización**. Se adaptó la gobernanza desde un esqueleto preexistente. No se ha iniciado la implementación de código.

## Estructura del Repositorio

```
SAAS-Gestion_Inventarios/
├── .agent/              ← Configuración del agente (skills, workflows, reglas)
├── .gemini/             ← Task lists y memoria de sesión del agente
├── doc/                 ← Documentación del proyecto (SSoT)
│   ├── Arquitectura/    ← Diseño de arquitectura física e infraestructura (PENDIENTE)
│   ├── Documentacion de Idea/ ← Google Docs originales de la idea
│   ├── Estructura/      ← Mapa oficial de directorios (este archivo)
│   ├── Funcional/       ← Requerimientos funcionales e HU (POR DEFINIR)
│   ├── Planeacion/      ← Gestión Ágil y Planeación
│   └── Tecnico/         ← Definiciones técnicas de diseño
├── core_backend/        ← Backend FastAPI (VACÍO)
├── web_frontend/        ← Frontend Angular PWA (VACÍO)
└── infra/               ← Docker Compose, Traefik, Postgres, MinIO (POR CONFIGURAR)
```

## Dominio de Negocio: Inventarios Multi-Tenant

**MicroNuba Inventory SaaS Core** es una plataforma de gestión de inventarios enfocada en:

| Capacidad | Descripción |
|-----------|-------------|
| Motor Transaccional Atómico | Operaciones ACID: entradas, salidas, transferencias entre sedes |
| Costo Promedio Ponderado (CPP) | Recálculo automático del costo unitario ante cada entrada |
| Kardex Histórico | Registro inmutable y auditable de todos los movimientos |
| Multi-Sede | Jerarquía de almacenes, bodegas y tiendas |
| Reorder Point | Alertas de reposición automática |
| Soft Reservation | Reservas temporales para e-commerce |
| Bulk Engine | Procesamiento masivo de movimientos |
| Balance Snapshots | Estados de inventario point-in-time |

## Pendientes / Próximos Pasos

- [ ] Definir stack tecnológico y arquitectura de contenedores (confirmar Angular + FastAPI + Postgres + Traefik)
- [ ] Formalizar los 3 Google Docs de la idea en Requerimientos Funcionales (RF) e Historias de Usuario (HU)
- [ ] Diseñar modelo de datos Multi-tenant (ERD en Mermaid)
- [ ] Crear DEFINICION_SAAS.md para el modelo de inventarios
- [ ] Configurar entorno de desarrollo con Docker
- [ ] Definir identidad visual y sistema de diseño

## Documentación de Idea (Fuente Original)

Los documentos originales de la idea están en Google Docs vinculados en `doc/Documentacion de Idea/`:
1. **Alcance Funcional:** Gestión de Inventarios SaaS
2. **Arquitectura de Referencia:** MicroNuba Inventory SaaS Core
3. **Especificación Técnica Enterprise:** Motor de Inventarios Atómico (MicroNuba)

## Notas de Gobernanza

- **Commits:** El usuario requiere aprobación explícita antes de cualquier `git commit` o `git push`.
- **Calidad:** Todo desarrollo futuro debe pasar por la skill `verificador_calidad` y obtener veredicto `APROBADO`.
- **Skills activas:** `orquestador_proyecto`, `experto_backend_python`, `experto_frontend_angular`, `experto_base_datos_postgres`, `verificador_calidad`

## Notas Técnicas

- **Repositorio:** `https://github.com/deimorga/SAAS-Gestion_Inventarios.git`
- **Branch principal:** `main`
- **Archivo maestro de estructura:** `doc/Estructura/estructura_proyecto.md`

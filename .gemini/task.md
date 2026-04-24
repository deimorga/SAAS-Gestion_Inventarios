# Task List - SaaS Gestión de Inventarios (MicroNuba Inventory)

## 🏗️ Fase 0: Gobernanza y Configuración Inicial
- [x] Adaptar documentos de gobernanza al nuevo proyecto (reglas, DoD, estructura, contexto) <!-- id: 0 -->
- [ ] Definir stack tecnológico y arquitectura de contenedores (Angular, FastAPI, Postgres, Traefik) <!-- id: 1 -->
- [ ] Configurar entorno de desarrollo con Docker (`docker-compose.dev.yml`) <!-- id: 2 -->
- [ ] Definir identidad visual y sistema de diseño (Tokens de diseño) <!-- id: 3 -->

## 📋 Fase 1: Definición Funcional y Arquitectura
- [ ] Formalizar Requerimientos Funcionales (RF) e Historias de Usuario (HU) desde documentación de idea <!-- id: 4 -->
- [ ] Diseñar modelo de datos Multi-tenant (ERD en Mermaid) — Tenants, Sedes, Almacenes, Productos, Stock <!-- id: 5 -->
- [ ] Definir arquitectura física e infraestructura (ARQUITECTURA_FISICA.md, ESPECIFICACIONES_INFRAESTRUCTURA.md) <!-- id: 6 -->
- [ ] Crear documento DEFINICION_SAAS.md para el modelo Multi-Tenant de inventarios <!-- id: 7 -->

## 🛠️ Fase 2: Desarrollo del Core (MVP)
- [ ] Implementar Backend base: Auth (JWT RS256), Tenants, Roles, API Keys <!-- id: 8 -->
- [ ] Implementar Módulo: Gestión de Sedes/Almacenes (CRUD jerárquico de nodos) <!-- id: 9 -->
- [ ] Implementar Módulo: Catálogo de Productos (SKU, atributos dinámicos, categorías) <!-- id: 10 -->
- [ ] Implementar Módulo: Motor Transaccional Atómico (entradas, salidas, transferencias ACID) <!-- id: 11 -->
- [ ] Implementar Módulo: Cálculo de Costo Promedio Ponderado (CPP) <!-- id: 12 -->
- [ ] Implementar Módulo: Kardex (registro histórico completo de movimientos) <!-- id: 13 -->

## 📊 Fase 3: Módulos Avanzados
- [ ] Implementar Webhooks y notificaciones de stock crítico <!-- id: 14 -->
- [ ] Implementar Reorder Point (alertas de reposición) <!-- id: 15 -->
- [ ] Implementar Soft Reservation (reservas temporales e-commerce) <!-- id: 16 -->
- [ ] Implementar Bulk Engine (procesamiento masivo) <!-- id: 17 -->
- [ ] Implementar Balance Snapshots (estados de inventario point-in-time) <!-- id: 18 -->
- [ ] Implementar Asset Valuation (reportes de valoración contable) <!-- id: 19 -->

## 📈 Fase 4: Frontend y Dashboard
- [ ] Implementar Dashboard multi-tenant con branding dinámico <!-- id: 20 -->
- [ ] Implementar vistas de inventario por sede/almacén <!-- id: 21 -->
- [ ] Implementar interfaz de movimientos (entradas/salidas/transferencias) <!-- id: 22 -->
- [ ] Implementar reportes visuales (Kardex, valoración, alertas) <!-- id: 23 -->

## 🧪 Fase 5: Pruebas y Despliegue
- [ ] Pruebas unitarias e integración (Backend ≥80%, Auth/RLS 100%) <!-- id: 24 -->
- [ ] Pruebas E2E y funcionales <!-- id: 25 -->
- [ ] Configurar Pipeline CI/CD <!-- id: 26 -->
- [ ] Despliegue en Staging <!-- id: 27 -->

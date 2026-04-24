---
trigger: always_on
description: Definición de Done (DoD) obligatoria para todos los desarrollos del proyecto.
---

# Definición de Done (DoD) — SaaS Gestión de Inventarios

> [!IMPORTANT]
> Este checklist es **OBLIGATORIO** y **NO NEGOCIABLE**. Una tarea NO puede marcarse `[x]` en `.gemini/task.md` hasta que todos los ítems aplicables estén verificados con evidencia real. El agente debe ejecutar los comandos, leer los resultados y reportarlos. **Nunca asumir éxito desde el código.**

---

## Cómo usar esta DoD

1. Al finalizar una tarea, el agente invoca la skill `verificador_calidad`.
2. El verificador recorre este checklist ítem por ítem y ejecuta los comandos de verificación.
3. El veredicto final (`APROBADO` / `RECHAZADO`) queda registrado como comentario en la tarea de `.gemini/task.md`.
4. Solo con veredicto `APROBADO` el orquestador puede avanzar al siguiente paso del workflow.

---

## Checklist Universal (aplica a TODA tarea)

| # | Ítem | Verificación |
|---|------|-------------|
| U1 | El código respeta la estructura de directorios de `doc/Estructura/estructura_proyecto.md` | `ls` en rutas relevantes |
| U2 | Cero secretos hardcodeados (tokens, contraseñas, keys) | `grep -r "password\|secret\|token" --include="*.py" --include="*.ts"` — sin hits en código fuente |
| U3 | El commit usa Conventional Commits (`feat:`, `fix:`, `test:`, etc.) | Revisar mensaje de commit |
| U4 | La tarea tiene trazabilidad a un RF/HU de origen documentado | Verificar ID `RF-XXX-NNN` en la descripción de la tarea |
| U5 | La documentación técnica afectada fue actualizada | Revisar `doc/Definicion-Tecnica/` o `doc/Tecnico/` según corresponda |

---

## Checklist Backend (FastAPI / Python)

| # | Ítem | Comando de Verificación | Umbral Mínimo |
|---|------|------------------------|---------------|
| B1 | Tests unitarios ejecutados sin errores | `pytest core_backend/tests/unit/ -v` | 0 fallos |
| B2 | Tests de integración ejecutados sin errores | `pytest core_backend/tests/integration/ -v` | 0 fallos |
| B3 | Cobertura de código verificada | `pytest core_backend/tests/ --cov=app --cov-report=term-missing --cov-fail-under=80` | ≥ 80% general |
| B4 | Cobertura 100% en rutas de autenticación y RLS | Revisar reporte de cobertura en `app/api/auth/` y `app/core/` | 100% en estos módulos |
| B5 | Tipado estático sin errores | `mypy core_backend/app/ --ignore-missing-imports` | 0 errores |
| B6 | Linting sin errores | `ruff check core_backend/app/` | 0 errores |
| B7 | RLS verificado: tenant_A no puede leer datos de tenant_B | Existe test en `tests/security/test_rls_isolation.py` con assertion explícito | Test PASS |
| B8 | Cada endpoint nuevo tiene test de integración HTTP | Verificar existencia de archivo en `tests/integration/` | Al menos 1 test por endpoint |
| B9 | Migración Alembic creada y ejecutada | `alembic upgrade head` sin errores | Sin errores |
| B10 | Rollback de migración probado | `alembic downgrade -1` sin errores | Sin errores |

---

## Checklist Frontend (Angular)

| # | Ítem | Comando de Verificación | Umbral Mínimo |
|---|------|------------------------|---------------|
| F1 | Tests de componentes ejecutados sin errores | `cd web_frontend && ng test --watch=false --browsers=ChromeHeadless` | 0 fallos |
| F2 | Cobertura de código verificada | `ng test --watch=false --code-coverage --browsers=ChromeHeadless` | ≥ 80% en componentes y servicios |
| F3 | Lint sin errores | `ng lint` | 0 errores |
| F4 | Build de producción exitoso | `ng build --configuration=production` | Sin errores de compilación |
| F5 | Validación visual en navegador completada | Captura de pantalla o evidencia del flujo funcional | Evidencia documentada en tarea |
| F6 | Interceptor de Auth y Tenant headers verificados | Test del interceptor HTTP con token mock | Test PASS |
| F7 | Manejo de errores HTTP implementado (401, 403, 500) | Verificar componente de error o guard activo | Test PASS |
| F8 | Responsive verificado (mobile / desktop) | Revisión visual en ambas resoluciones | Evidencia documentada |

---

## Checklist Base de Datos

| # | Ítem | Verificación | Umbral |
|---|------|-------------|--------|
| D1 | Todas las tablas transaccionales tienen RLS habilitado | `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public'` | `rowsecurity = true` en todas |
| D2 | Políticas RLS vinculadas a `current_setting('app.current_tenant')` | Revisar script SQL de la migración | Política presente |
| D3 | Índices creados para columnas de búsqueda frecuente | Revisar migración Alembic | Al menos `tenant_id` indexado |
| D4 | Sin datos de prueba residuales en migración productiva | Revisar scripts de seed — solo en `tests/fixtures/` | Sin seeds en migraciones |

---

## Checklist E2E / Funcional (Staging)

| # | Ítem | Verificación | Umbral |
|---|------|-------------|--------|
| E1 | Todos los criterios de aceptación Gherkin del RF cubiertos | Matriz `RF → Test Case → Resultado` documentada en `doc/Planeacion/Sprints/` | 100% de criterios cubiertos |
| E2 | Flujo principal (happy path) funcional en staging | Ejecución manual o Playwright contra staging | PASS |
| E3 | Flujos alternativos críticos probados | Al menos los FA marcados como Must en el RF | PASS |
| E4 | Sin errores en consola del navegador durante el flujo | Inspección devtools | 0 errores JS |

---

## Registro de Evidencia en task.md

Cuando el `verificador_calidad` emite veredicto, se agrega al ítem de task.md:

```markdown
- [x] Implementar endpoint POST /auth/login <!-- DoD: B1✅ B2✅ B3✅(82%) B4✅ B5✅ B6✅ B7✅ B8✅ B9✅ B10✅ | verificador: APROBADO 2026-04-23 -->
```

Si el veredicto es RECHAZADO:
```markdown
- [/] Implementar endpoint POST /auth/login <!-- DoD: B3❌(61% < 80%) B5❌(2 errores mypy) | verificador: RECHAZADO — pendiente cobertura y tipos -->
```

---

## Excepciones Permitidas

Solo el **usuario** puede autorizar la omisión de un ítem con justificación documentada:

```markdown
<!-- DoD-EXCEPCION: F5 omitido — entorno sin navegador disponible en CI. Validación manual pendiente para Sprint 3. Autorizado por: usuario 2026-04-23 -->
```

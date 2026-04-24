---
name: verificador_calidad
description: Juez de calidad del proyecto. Verifica la Definición de Done (DoD) ítem por ítem ejecutando comandos reales antes de que cualquier tarea pueda marcarse como completada. Emite veredicto formal APROBADO o RECHAZADO.
keywords: [calidad, dod, tests, cobertura, verificacion, gate, ci, mypy, pytest, angular]
---

# 🔍 Verificador de Calidad — SaaS Gestión Talleres

## Descripción

Esta skill actúa como el **juez de calidad** del proyecto. Su única responsabilidad es verificar que el código entregado cumple la Definición de Done (DoD) antes de que una tarea pueda cerrarse. No escribe código, no sugiere mejoras — **evalúa, ejecuta y emite veredicto.**

> [!IMPORTANT]
> El orquestador **DEBE** invocar esta skill en el Paso 7.5 del workflow. Sin su veredicto `APROBADO`, ninguna tarea puede marcarse `[x]` y el Paso 9 (staging) está bloqueado.

---

## Cuándo Invocar Esta Skill

- Al finalizar cualquier tarea de desarrollo (backend, frontend, DB o mixta).
- Antes de marcar `[x]` en `.gemini/task.md`.
- Al completar el Paso 6 del workflow del orquestador (antes del Paso 7.5).
- Cuando el orquestador necesita confirmar que un feature está listo para staging.

---

## Protocolo de Verificación

### Fase 0 — Lectura de Contexto

Antes de evaluar, el verificador DEBE leer:
1. `.agent/rules/definition_of_done.md` — checklist vigente.
2. La tarea a cerrar en `.gemini/task.md` — para saber qué RF/HU aplica.
3. Los archivos modificados en el último commit — para saber qué capas evaluar.

```bash
# Identificar archivos modificados
git diff --name-only HEAD~1 HEAD
```

### Fase 1 — Evaluación Checklist Universal

Para **toda** tarea, verificar los ítems U1–U5:

```bash
# U1: Verificar estructura de directorios
ls -la core_backend/app/ web_frontend/src/

# U2: Detectar secretos hardcodeados
grep -rn "password\s*=\s*['\"][^'\"]\|secret\s*=\s*['\"][^'\"]\|api_key\s*=\s*['\"][^'\"]" \
  core_backend/app/ web_frontend/src/ \
  --include="*.py" --include="*.ts" --include="*.html"
# Resultado esperado: 0 hits

# U3: Revisar formato del último commit
git log -1 --pretty=format:"%s"
# Debe comenzar con: feat:, fix:, test:, refactor:, docs:, chore:

# U4: Verificar trazabilidad RF
# Buscar ID RF-XXX-NNN en la descripción de la tarea
grep -i "RF-\|HU-" .gemini/task.md

# U5: Verificar documentación técnica actualizada
ls doc/Definicion-Tecnica/ doc/Tecnico/ 2>/dev/null
```

### Fase 2 — Evaluación Backend (si hay cambios en core_backend/)

Ejecutar en orden y registrar cada resultado:

```bash
# B1 + B2: Tests unitarios e integración
pytest core_backend/tests/unit/ -v 2>&1 | tail -5
pytest core_backend/tests/integration/ -v 2>&1 | tail -5

# B3: Cobertura global
pytest core_backend/tests/ \
  --cov=app \
  --cov-report=term-missing \
  --cov-fail-under=80 \
  2>&1 | grep -E "TOTAL|FAILED|passed|failed|error"

# B4: Cobertura 100% en auth y core
pytest core_backend/tests/ \
  --cov=app/api/auth \
  --cov=app/core \
  --cov-report=term-missing \
  2>&1 | grep -E "TOTAL|app/api/auth|app/core"

# B5: Tipado estático
mypy core_backend/app/ --ignore-missing-imports 2>&1 | tail -3

# B6: Linting
ruff check core_backend/app/ 2>&1 | tail -3

# B7: RLS Isolation test
pytest core_backend/tests/security/test_rls_isolation.py -v 2>&1 | tail -10

# B9 + B10: Migraciones
cd core_backend && alembic upgrade head 2>&1 | tail -3
cd core_backend && alembic downgrade -1 2>&1 | tail -3
cd core_backend && alembic upgrade head 2>&1 | tail -3
```

### Fase 3 — Evaluación Frontend (si hay cambios en web_frontend/)

```bash
# F1 + F2: Tests y cobertura
cd web_frontend && ng test \
  --watch=false \
  --code-coverage \
  --browsers=ChromeHeadless \
  2>&1 | grep -E "TOTAL|FAILED|passed|failed|Statements|Branches|Functions|Lines"

# F3: Linting
cd web_frontend && ng lint 2>&1 | tail -5

# F4: Build de producción
cd web_frontend && ng build --configuration=production 2>&1 | tail -5

# F5 (manual): El verificador debe solicitar evidencia visual al agente que desarrolló la tarea
# Si no existe, emitir advertencia y solicitar al usuario autorizar excepción DoD-EXCEPCION: F5
```

### Fase 4 — Evaluación Base de Datos (si hay migraciones nuevas)

```bash
# D1: Verificar RLS en todas las tablas
# (ejecutar dentro del contenedor postgres o con psql)
psql $DATABASE_URL -c "
  SELECT tablename, rowsecurity 
  FROM pg_tables 
  WHERE schemaname='public' 
  ORDER BY tablename;
"
# Todas las tablas transaccionales deben tener rowsecurity = true

# D2: Verificar políticas RLS
psql $DATABASE_URL -c "
  SELECT tablename, policyname, cmd, qual 
  FROM pg_policies 
  WHERE schemaname='public';
"
# Debe existir política referenciando current_setting('app.current_tenant')

# D4: Sin seeds en migraciones productivas
grep -rn "INSERT INTO\|seed\|fixture" core_backend/app/db/migrations/ --include="*.py"
# Resultado esperado: 0 hits en archivos de migración
```

---

## Formato del Veredicto

### APROBADO

```markdown
<!-- 
  verificador_calidad — APROBADO — 2026-04-23T10:00:00-05:00
  Backend: B1✅ B2✅ B3✅(84%) B4✅(100% auth) B5✅(0 errores) B6✅ B7✅ B8✅ B9✅ B10✅
  Frontend: F1✅ F2✅(82%) F3✅ F4✅ F5✅(evidencia: login flow validado)
  DB: D1✅ D2✅ D3✅ D4✅
  Universal: U1✅ U2✅ U3✅ U4✅ U5✅
-->
```

### RECHAZADO

```markdown
<!-- 
  verificador_calidad — RECHAZADO — 2026-04-23T10:00:00-05:00
  Motivos:
  - B3❌: Cobertura 61% < umbral 80%. Faltan tests en app/services/auth_service.py
  - B5❌: mypy reporta 2 errores en app/schemas/user.py líneas 34, 67
  - F5⚠️: Sin evidencia visual. Requiere autorización DoD-EXCEPCION del usuario.
  Acción requerida: Corregir B3 y B5, luego reinvocar verificador_calidad.
-->
```

---

## Registro del Veredicto

El veredicto se agrega como comentario HTML inline a la tarea en `.gemini/task.md`:

**Con aprobación:**
```markdown
- [x] Implementar endpoint POST /api/v1/auth/login <!-- verificador_calidad: APROBADO 2026-04-23 | B3:84% F2:82% -->
```

**Con rechazo (la tarea permanece en progreso):**
```markdown
- [/] Implementar endpoint POST /api/v1/auth/login <!-- verificador_calidad: RECHAZADO 2026-04-23 | B3:61%❌ B5:2errores❌ -->
```

---

## Tabla de Decisión Rápida

| Resultado | Acción del Orquestador |
|-----------|----------------------|
| Todos los ítems ✅ | Emitir `APROBADO` → Avanzar al siguiente paso del workflow |
| Algún ítem B1-B2 ❌ | `RECHAZADO` → Regresar al Paso 5 (backend) |
| Algún ítem B3-B6 ❌ | `RECHAZADO` → Regresar al Paso 5 (backend), aumentar cobertura/tipado |
| B7 ❌ (RLS isolation) | `RECHAZADO P0` → Bloqueo total. Escalar a usuario de inmediato |
| Algún ítem F1-F4 ❌ | `RECHAZADO` → Regresar al Paso 6 (frontend) |
| F5 sin evidencia | `RECHAZADO` → Solicitar evidencia visual o autorización de excepción al usuario |
| D1 ❌ (tabla sin RLS) | `RECHAZADO P0` → Bloqueo total. RLS es pilar de seguridad |
| Ítems U1-U5 con fallo | `RECHAZADO` → Corregir estructura/secretos/commits y re-evaluar |

---

## Reglas del Verificador

1. **Ejecutar, no asumir:** El verificador SIEMPRE ejecuta los comandos. Nunca infiere resultado desde el código fuente.
2. **Reportar exacto:** Los porcentajes de cobertura son los que retorna el comando, no estimados.
3. **Sin excepciones propias:** El verificador no puede autorizar excepciones. Solo el usuario puede via `DoD-EXCEPCION`.
4. **P0 es bloqueo absoluto:** Si B7 (RLS isolation) o D1 (RLS habilitado) fallan, el verificador emite RECHAZADO y notifica al usuario directamente antes de continuar.
5. **Idempotente:** El verificador puede invocarse múltiples veces. Siempre evalúa el estado actual del código.

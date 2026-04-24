# Reglas Operativas - SaaS Gestión de Inventarios (MicroNuba Inventory)

> [!IMPORTANT]
> Estas reglas son OBLIGATORIAS. El Agente actua siempre bajo la guía del **Orquestador de Proyecto**. Debe ser crítico, técnicamente preciso y evitar redundancias. Si algo no se puede hacer o es incorrecto, el Agente DEBE expresarlo claramente.

## 1. Gestión Documental (SSoT) y Definiciones Técnicas
- **Alojamiento Técnico:** Todas las definiciones técnicas y documentos de diseño de requerimientos DEBEN crearse estrictamente dentro del directorio `doc/Tecnico/`.
- **Preservación Arquitectónica:** Antes de sugerir cambios, escribir código o hacer pipelines, DEBES alinear tu lógica con el directorio `doc/Arquitectura/Arquitectura definida/`. **ESTÁ ESTRICTAMENTE PROHIBIDO** dañar, ignorar o alterar sin autorización el diseño dockerizado y la infraestructura definida allí.
- **Estructura Inamovible:** El agente DEBE respetar de manera irrestricta la arquitectura de carpetas dictaminada en `doc/Estructura/estructura_proyecto.md`. Prohibido inventar rutas raíz, crear carpetas fuera de este esquema o mezclar monolíticamente las dependencias.

## 2. Arquitectura, Infraestructura y Funcionalidad
- **Obligación Perenne:** Como regla fundacional, antes del código, el contexto DEBE preservar intacta y regirse por:
  1. *Arquitectura Física:* `ARQUITECTURA_FISICA.md` y `ESPECIFICACIONES_INFRAESTRUCTURA.md`.
  2. *Funcionalidad:* Todo debe regirse bajo el modelo Multi-Tenant del SaaS documentado en `doc/Funcional/mejorado/00_definicion-solucion_saas/DEFINICION_SAAS.md`.
- **Stack Consolidado:** Frontend PWA (Angular), Backend (FastAPI), DB (PostgreSQL RLS), Ingress (Traefik). Cero secretos hardcodeados (DevSecOps).
- **Dominio de Negocio:** El sistema gestiona inventarios multi-sede con motor transaccional atómico (ACID), cálculo de Costo Promedio Ponderado (CPP), Kardex histórico y webhooks de stock crítico.

## 3. Seguridad y Entornos
- **Secretos:** Nunca exponer credenciales (`.env`, API Keys) en logs o archivos compartidos.
- **Docker:**
    - Local: Usar `docker-compose.dev.yml` para hot-reloading.
    - Producción: `docker-compose.yml`. Prohibido operar Prod localmente sin autorización.
- **API Keys:** El sistema soporta credenciales con scopes granulares (READ_ONLY, WRITE). Toda API Key debe asociarse a un tenant.

## 4. Estilo de Comunicación y Ejecución
- Ser conciso y directo. No repetir lo que ya se sabe.
- Usar Markdown para listas y código.
- **Verificación Visual:** Es OBLIGATORIO usar `browser_subagent` para validar cambios en la UI antes de finalizar cualquier tarea. No inferir éxito desde el código.

## 5. Protocolo de Calidad (Reglas Hard-Stop)
1. **Validación Física:** Ejecutar `ls` para verificar existencia de archivos antes de referenciarlos.
2. **Persistencia:** Reiniciar servicios (`docker compose restart`) tras cambios en configuración.
3. **Mapeo JSON:** Validar que el Frontend mapea correctamente las respuestas del Backend.
4. **Integridad Transaccional:** Todo movimiento de inventario debe ser atómico (ACID). Verificar que las operaciones de stock no dejan estados intermedios.

## 6. Sincronización de Sesión y Orquestación
- **Inicio de Sesión:** Ejecutar `/restore_context`. Esto debe incluir la activación mental de la skill `orquestador_proyecto`.
- **Cierre de Sesión:** Actualizar `.gemini/contexto_gemini_web.md`.
- **Gestión Ágil:** Todo nuevo requerimiento debe pasar por el flujo de 11 pasos del `orquestador_proyecto`.
- **Pensamiento Crítico y Riesgos:** El agente tiene la obligación de identificar riesgos y cuestionar decisiones técnicas que comprometan la calidad o seguridad del SaaS.
- Mantener `.gemini/task.md` con un responsable asignado para cada tarea.

## 7. Calidad de Código — Reglas Inquebrantables

> [!IMPORTANT]
> Esta sección tiene el mismo nivel de obligatoriedad que la Sección 1 (Arquitectura). **Ningún agente puede declarar una tarea terminada si estas reglas no se cumplen.**

### 7.1 — Prohibición de Código Sin Tests
- **ESTÁ PROHIBIDO** entregar código en `core_backend/` o `web_frontend/` sin tests que lo acompañen en el **mismo commit**.
- Un endpoint FastAPI sin test de integración = tarea incompleta.
- Un componente Angular sin test de componente = tarea incompleta.

### 7.2 — Umbrales de Cobertura Obligatorios
- **Backend (Pytest):** Cobertura mínima global **≥ 80%**. En módulos de autenticación y RLS: **100%**.
- **Frontend (Jest/Karma):** Cobertura mínima global **≥ 80%** en componentes y servicios.
- Si el comando `pytest --cov-fail-under=80` falla → la tarea NO está completa. Sin excepciones.

### 7.3 — Tipado Estricto
- **Backend:** `mypy core_backend/app/` debe retornar 0 errores antes de cerrar cualquier tarea.
- **Frontend:** `ng build --configuration=production` debe compilar sin errores de TypeScript.

### 7.4 — Verificación Visual Obligatoria para UI
- Ninguna tarea de interfaz de usuario puede cerrarse sin evidencia de ejecución en navegador real.
- La evidencia debe quedar documentada (captura de pantalla, descripción del flujo validado) en el comentario de la tarea en `.gemini/task.md`.
- **Inferir éxito desde el código está explícitamente prohibido.**

### 7.5 — Verificador de Calidad como Gate
- Antes de cerrar cualquier tarea de desarrollo, el agente **DEBE** invocar la skill `verificador_calidad`.
- Solo con veredicto `APROBADO` del `verificador_calidad` se puede marcar `[x]` en `.gemini/task.md`.
- El veredicto queda registrado como comentario en la línea de la tarea.

### 7.6 — Aislamiento RLS: Test Obligatorio
- Toda tabla nueva con datos de tenant **DEBE** tener un test de aislamiento en `tests/security/test_rls_isolation.py` que verifique explícitamente que tenant_A no puede leer datos de tenant_B.
- Este test es de prioridad P0: si falla, bloquea todo el pipeline.
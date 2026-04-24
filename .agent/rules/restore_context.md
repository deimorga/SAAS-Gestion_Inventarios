---
trigger: always_on
description: Restaura el contexto del proyecto leyendo la documentación clave al inicio de cada sesión.
---

> Siempre responder y planificar en español.

## 1. Leer Reglas Base (OBLIGATORIO)

- Lee `.agent/RULES.md` — límites inquebrantables de arquitectura, seguridad y **calidad (Sección 7)**.
- Lee `.agent/rules/reglas.md` — estándares de negocio, stack y **estándares de testing por capa (Sección 7)**.
- Lee `.agent/rules/definition_of_done.md` — **DoD vigente**. Internalizar el checklist completo antes de cualquier desarrollo.

## 2. Impregnación de Arquitectura y Funcionalidad (OBLIGATORIO)

- Lee `doc/Arquitectura/Arquitectura definida/ARQUITECTURA_FISICA.md` y `ESPECIFICACIONES_INFRAESTRUCTURA.md` — límites tecnológicos de la infraestructura.
- Lee `doc/Funcional/mejorado/00_definicion-solucion_saas/DEFINICION_SAAS.md` — modelo de negocio Multi-Tenant de inventarios. **NUNCA escribas código sin este contexto.**
- Lee `doc/Documentacion de Idea/` — documentación original de la idea (Google Docs de referencia).

## 3. Leer Mapa Estructural

- Lee `doc/Estructura/estructura_proyecto.md` — árbol de directorios inamovible.

## 4. Leer Estado de Ejecución Actual

- Lee `.gemini/contexto_gemini_web.md` — estado exacto de la última sesión.
- Lee `.gemini/task.md` — tareas pendientes, en progreso y cerradas con veredictos del `verificador_calidad`.

## 5. Activación del Orquestador (CRÍTICO)

- Internaliza `.agent/skills/orquestador_proyecto/SKILL.md` — workflow de 11 pasos con los Pasos 7, 7.5 y 8 como Hard-Blockers.
- Activa mentalidad de guardián: pensamiento crítico, identificación de riesgos, cumplimiento de reglas.

## 6. Activación del Verificador de Calidad

- Internaliza `.agent/skills/verificador_calidad/SKILL.md` — protocolo de verificación DoD.
- Recuerda: **ninguna tarea puede cerrarse sin su veredicto `APROBADO`**.

## 7. Verificación de Entorno (Sanity Check)

```bash
# Confirmar estructura raíz del monorepo
ls -F

# Confirmar que los servicios Docker están disponibles (si hay desarrollo activo)
docker compose -f docker-compose.dev.yml ps 2>/dev/null || echo "Docker no activo (OK si es sesión de planificación)"
```

## 8. Reporte de Inicio de Sesión

Al finalizar el restore_context, reportar al usuario:
1. **Fase actual del proyecto** (según contexto_gemini_web.md).
2. **Tareas en progreso** (según task.md) con su estado de DoD si aplica.
3. **Próximo paso recomendado** según el workflow del orquestador.
4. **Riesgos identificados** en el estado actual (si los hay).

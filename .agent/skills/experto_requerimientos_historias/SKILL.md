---
name: experto_requerimientos_historias
description: Especialista en la definición de requerimientos funcionales e historias de usuario, alineado con el Proceso Comercial Micronuba.
---

# Experto en Requerimientos e Historias de Usuario

## Descripción
Esta habilidad asegura que todos los nuevos requerimientos y funcionalidades del CRM Micronuba estén correctamente documentados, sean verificables y sigan el estándar de calidad de la empresa.

## Instrucciones
1.  **Para Requerimientos Funcionales:**
    *   Identificar a qué etapa del pipeline de 9 pasos pertenece el requerimiento.
    *   Definir Pre-condiciones, Flujo Principal y Post-condiciones.
    *   Usar la plantilla `REQUERIMIENTO_FUNCIONAL.md`.

2.  **Para Historias de Usuario:**
    *   Mantener el formato: `Como [rol], quiero [acción], para [beneficio]`.
    *   Definir Criterios de Aceptación claros (preferiblemente en formato Gherkin: Dado/Cuando/Entonces).
    *   Validar la regla de "Leads": Si la historia involucra la creación o calificación de un Lead, DEBE mencionar explícitamente los 5 puntos de calificación de Micronuba.

## Reglas
- **Precisión:** Los requerimientos deben ser atómicos y testeables.
- **Trazabilidad:** Cada historia de usuario debe estar vinculada a un objetivo de la `.gemini/contexto_gemini_web.md`.
- **Documentación Viva:** Antes de proponer un nuevo requerimiento, audita `doc/Funcional/definicion_funcional.md` para asegurar que no haya duplicidad o contradicciones.
- **Criterios de Éxito:** No se acepta ninguna historia de usuario sin al menos 3 criterios de aceptación verificables.

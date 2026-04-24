---
name: creador_de_habilidades_es
description: Asistente para la creación de nuevas habilidades (Skills) en español, asegurando estructura y formato estándar.
---

# Creador de Habilidades (Skill Builder)

Esta habilidad te guía paso a paso en la creación de una nueva "Skill" para el agente. Sigue estas instrucciones cuidadosamente.

## Paso 1: Definición de la Habilidad

1.  **Analizar el Propósito:**
    *   Pregunta al usuario (o deduce del contexto) qué tarea específica debe resolver la nueva habilidad.
    *   *Ejemplo:* "Automatizar deploys", "Revisar ortografía", "Generar tests unitarios".

2.  **Determinar Nombres:**
    *   **Nombre Técnico (Folder):** Debe ser en `snake_case`, todo minúsculas. *Ej: `deploy_automator`, `spell_checker`*.
    *   **Nombre Legible (Name):** Nombre descriptivo para humanos. *Ej: "Automatizador de Despliegues"*.

3.  **Redactar Descripción:**
    *   Una frase concisa que explique qué hace la habilidad.

## Paso 2: Creación de Estructura

1.  **Crear Directorio:**
    *   Ejecuta: `mkdir -p .agent/skills/[nombre_tecnico]`

2.  **Crear Archivo Principal:**
    *   Crea el archivo `.agent/skills/[nombre_tecnico]/SKILL.md`.

## Paso 3: Contenido de la Habilidad (Plantilla)

Usa la siguiente plantilla para el contenido de `SKILL.md`. Asegúrate de escribir las instrucciones en **Español** (a menos que el usuario pida otro idioma).

```markdown
---
name: [nombre_tecnico]
description: [descripcion_corta]
---

# [Nombre Legible]

## Descripción
[Descripción detallada de qué hace esta habilidad y cuándo debería usarse]

## Instrucciones
1.  [Paso 1...]
2.  [Paso 2...]

## Reglas
- [Regla importante 1...]
- **Documentación Viva (OBLIGATORIO):** Revisa `doc/` antes de actuar. Actualiza la documentación si tu acción cambia el sistema.
```

## Paso 4: Recursos Adicionales (Opcional)

Si la habilidad requiere scripts complejos o plantillas de código:
1.  Crea carpetas adicionales dentro de la skill:
    *   `.agent/skills/[nombre_tecnico]/scripts/`
    *   `.agent/skills/[nombre_tecnico]/templates/`
2.  Menciona estos recursos en el `SKILL.md` y da instrucciones de cómo usarlos.

## Paso 5: Verificación y Cierre

1.  Verifica que el archivo `SKILL.md` se haya creado correctamente usando `ls -F .agent/skills/[nombre_tecnico]/`.
2.  Notifica al usuario que la habilidad "[Nombre Legible]" ha sido creada y está lista para usarse.

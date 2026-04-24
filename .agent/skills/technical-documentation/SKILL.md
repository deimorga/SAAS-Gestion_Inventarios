---
name: technical-documentation
description: Construir y revisar documentación técnica de alta calidad, así como archivos de instrucciones para agentes en tu repositorio.
license: AGPL-3.0-only
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Documentación Técnica

## Propósito

Producir y revisar documentación técnica que sea clara, accionable y mantenible tanto para humanos como para agentes, incluyendo archivos de gobernanza de contribuidores e instrucciones para agentes.

## Cuándo Usar

- Crear o renovar documentación en un producto/código existente (brownfield).
- Construir documentación perenne (evergreen) diseñada para mantenerse precisa y reutilizable en el tiempo.
- Revisar diffs de documentación en busca de estructura, claridad y corrección operativa.
- Ejecutar auditorías de documentación de repositorio completo que incluyan tanto archivos de gobernanza como superficies de documentación de producto (`doc/`, `README*`, `.md/.mdx/.mdc`, fuentes tipo Fern/Sphinx/Mintlify).
- Actualizar o revisar AGENTS.md y/o CONTRIBUTING.md para mantener los flujos de agentes y contribuidores alineados con las prácticas actuales del repo.
- Mejorar la documentación de onboarding del repositorio incluyendo instrucciones de contribución, plantillas de issues, flujo de PRs y puertas de revisión.
- Diseñar estrategia de documentación de gobernanza para repos con archivos de instrucciones alias (por ejemplo `CLAUDE.md`, `AGENT.md`, `.cursorrules`, `.cursor/rules/*`, `.agent/`, `.agents/`, `.pi/`) donde `CLAUDE.md` se trata como fuente de política canónica y `AGENTS.md` se mantiene como alias de compatibilidad si está presente.
- Diagnosticar desviación (drift) de archivos de agente donde los equipos tuvieron que iterar prompts para encontrar archivos faltantes, comandos rotos o conflictos de políticas.

## Flujo de Trabajo

1. Clasificar tarea: `construir` o `revisar`; contexto: `brownfield` o `evergreen`.
2. Inventariar el alcance completo de documentación temprano (gobernanza + docs de producto): AGENTS/CONTRIBUTING/aliases más directorios de docs, fuentes de frameworks y READMEs raíz/módulo.
3. Detectar alcance multilingüe (README/docs en múltiples idiomas) y definir nivel de paridad requerido.
4. Leer `references/agent-and-contributing.md` para reglas de instrucciones de agente y flujo de trabajo de `CONTRIBUTING.md` (inventario, mapeo canónico/alias, balance dual, estándares de entregables y manejo de precedencia/conflictos).
5. Leer `references/principles.md` para el conjunto de reglas gobernantes (Matt Palmer y OpenAI).
6. Para tareas de construcción, seguir `references/build.md`.
7. Para tareas de revisión, seguir `references/review.md` y detectar proactivamente problemas sin esperar indicaciones repetidas.
8. Para tareas complejas o de alto riesgo (construcción o revisión), es aceptable ejecutar investigaciones más largas, profundas y exhaustivas cuando sea necesario para tener confianza.
9. Cuando estén disponibles, usar sub-agentes para trabajo paralelo acotado de descubrimiento/revisión, luego fusionar resultados en un único entregable coherente.
10. Usar `references/tooling.md` cuando las decisiones de plataforma/herramientas afecten las recomendaciones.
11. Ejecutar un barrido proactivo de problemas tanto para superficies de gobernanza como de contenido de docs, y corregir defectos de alta confianza en la misma pasada a menos que se solicite explícitamente modo solo-reporte.
12. En modo brownfield, priorizar compatibilidad con la IA de docs actual, herramientas y estado de release.
13. En modo evergreen, priorizar redacción atemporal, estrategia de actualización y estructura duradera.
14. Devolver entregables más notas de validación, estado de paridad y brechas pendientes.

## Guía de Orquestación de Sub-agentes

Preferir sub-agentes cuando el repo es grande o el conjunto de cambios solicitado es amplio; usarlos por defecto para trabajo a nivel de repo, multi-framework o de alto conflicto.

- `inventory-agent` -> `agents/inventory-agent.md` (`rápido` / haiku): descubrimiento de archivos/config, mapa de cobertura y verificación de rutas faltantes.
- `governance-agent` -> `agents/governance-agent.md` (`pensamiento` / sonnet): precedencia de AGENTS/CONTRIBUTING/alias, conflictos y desviación de políticas.
- `docs-framework-agent` -> `agents/docs-framework-agent.md` (`pensamiento` / sonnet): config de framework, base de ruta relativa y verificación de mapeo archivo-ruta vs URL-ruta.
- `synthesis-agent` -> `agents/synthesis-agent.md` (`extenso` / opus): fusionar salidas de sub-agentes en un plan de corrección priorizado y modelo de precedencia unificado.

## Entradas

- Tipo de documento (tutorial, guía práctica, referencia, explicación) y audiencia.
- Alcance de archivos o alcance de diff.
- Restricciones de framework/herramientas de docs (Fern, Mintlify, Sphinx, etc.).
- Modo construir/revisar e intención brownfield/evergreen.
- Intención de compatibilidad para agentes y humanos.
- Superficies de framework de docs en alcance (por ejemplo Fern, Sphinx, Mintlify, archivos Markdown/MDX/MDC/RST/RSC).
- Profundidad de investigación deseada / presupuesto de tiempo (pasada rápida vs revisión exhaustiva).
- Modo de ejecución (`agente-único` o `asistido-por-sub-agentes` cuando esté disponible).
- Modo de remediación (`aplicar-correcciones` por defecto, o `solo-reporte` cuando se solicite).
- Alcance multilingüe: idioma fuente de verdad, locales objetivo y expectativas de paridad.

## Salidas

- Borrador actualizado o hallazgos de revisión con próximas acciones claras.
- Notas de validación (qué se verificó, qué queda pendiente).
- Recomendaciones de navegación/mantenimiento para calidad a largo plazo.
- Resumen de alineación de docs de gobernanza cuando se tocaron AGENTS/CONTRIBUTING.
- Mapa de superficie de instrucciones de agente (archivo primario, archivos alias, plan de manejo Codex/Claude/Cursor).
- Mapa de cobertura de superficie de documentación (qué se revisó bajo `/doc`, jerarquía de READMEs y árboles fuente específicos de framework).
- Lista de problemas autodetectados con correcciones aplicadas (o hallazgos explícitos solo-reporte).
- Notas de delegación cuando se usaron sub-agentes (alcance delegado y cómo se fusionaron hallazgos).
- Nota de paridad multilingüe (sincronizado, parcial con justificación, o divergencia intencional).

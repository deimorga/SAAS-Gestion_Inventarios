# Guía de Construcción de Docs

Leer `principles.md` primero, luego seguir este flujo de ejecución.

## 1. Detectar y alinear instrucciones de agente y gobernanza

- Usar `references/agent-and-contributing.md` como fuente de verdad para inventario, mapeo canónico/alias y manejo de precedencia/conflictos.
- Aplicar la política de compatibilidad de symlinks cuando esté en alcance (directorio canónico `.agents` con symlink de compatibilidad `.cursor` cuando lo requiera el tooling).
- Se aceptan investigaciones extensas y de larga duración cuando sea necesario para resolver fuentes de documentación ambiguas o conflictivas.
- Cuando estén disponibles, usar sub-agentes para tareas paralelas acotadas de inventario/verificación cruzada y fusionar resultados en un conjunto de decisiones canónico.
- Capturar restricciones requeridas antes de escribir:
  - reglas de agentes anidados, requisitos de comandos/tests, flujo de trabajo de PR y verificaciones de estilo.
- Usar las mismas expectativas de comandos y validación en snippets y ejemplos propuestos.

## 2. Inventariar superficies de documentación de producto (no solo gobernanza)

- Para construcciones a nivel de repo, incluir superficies de contenido de docs además de AGENTS/CONTRIBUTING.
- Inventariar archivos y frameworks de docs en alcance (ejemplos): `README*.md`, `doc/**`, `**/*.md`, `**/*.mdx`, `**/*.mdc`, `**/*.rst`, `**/*.rsc`, config de Fern/Mintlify, `conf.py` de Sphinx.
- Construir un mapa de cobertura antes de redactar para que tanto gobernanza como docs de producto estén representados.
- Si el alcance es ambiguo, por defecto hacer descubrimiento más amplio primero, luego reducir intencionalmente.

## 3. Reglas de config de framework y mapeo de rutas

- Detectar framework/config primero (por ejemplo config de Fern, `conf.py` de Sphinx, config de Mintlify o equivalente).
- Resolver cada ruta referenciada relativa al archivo/config que la declara, no asumir raíz del repo.
- Tratar rutas del sistema de archivos y rutas de URL publicadas como mapeos separados; no inferir uno del otro sin evidencia de config.
- Validar ambas capas:
  - config -> archivo existe en disco
  - config/nav/routing -> ruta URL es consistente y accesible
- Registrar suposiciones de mapeo de rutas y discrepancias en el handoff (`archivo faltante`, `ruta obsoleta`, `ruta base incorrecta`).

## 4. Definir intención y éxito

- Audiencia, prerrequisitos y trabajo-a-realizar (job-to-be-done).
- Resultado esperado del lector inmediatamente después de completar.
- Tipo de doc: tutorial, guía práctica, referencia, explicación.
- Criterios de éxito: qué debe ser verdad después de publicar.

## 5. Construir estructura antes de prosa

- Seguir el embudo: qué/por qué, inicio rápido, próximos pasos.
- Mantener los títulos informativos y escaneables.
- Abrir cada sección con la frase resumen.
- Agregar puntos de decisión con guía concreta de ramificación.

## 6. Construir AGENTS.md y CONTRIBUTING.md intencionalmente

- Mantener la estructura de AGENTS.md consistente con patrones del ecosistema `agents.md`:
  - incluir frontmatter YAML cuando esté presente en el estilo del repo (`name`, `description`).
  - declarar alcance de persona y límites explícitos de instrucciones: `Siempre`, `Preguntar primero`, `Nunca`.
  - incluir comandos concretos y ejemplos de código representativos.
- Para CONTRIBUTING.md, priorizar flujo de triaje de issues, expectativas de PR, comandos de setup/test y puertas de revisión.
- Agregar secciones de `Código de Conducta`, `Testing`, `Verificaciones Locales` y `Expectativas de PR` cuando falten pero sean requeridas por el repo.
- Si CONTRIBUTING.md se vuelve demasiado grande, dividir por alcance en docs enlazados (por ejemplo, setup específico de framework/herramienta y flujos de release) y mantener el archivo raíz como punto de entrada conciso.
- Mantener consistencia entre archivos: enlaces de CONTRIBUTING.md a AGENTS.md (y viceversa) deben ser precisos y no circulares.
- Si existen múltiples archivos AGENTS.md, documentar el alcance a nivel de directorio y evitar consejos conflictivos.
- Si falta un archivo canónico de entrada requerido (por ejemplo `README.md` referenciado bajo un directorio principal), crear el archivo en la misma pasada en lugar de agregar solo una nota de advertencia.
- Para nuevos archivos de entrada, mantenerlos mínimos y accionables: propósito, prerrequisitos, comandos concretos de ejecución y punteros a docs más profundos.

## 7. Mantener el contexto de agente ajustado

- Autoría única, exposición dual:
  - mantener un solo núcleo de política compartida y evitar duplicar guía en archivos separados específicos de agente.
  - publicar ese núcleo a través de archivos acotados compatibles con glob para Cursor/Claude más referencias de ruta explícitas para Codex.
- Para agentes estilo Cursor y Claude, evitar referencias amplias. Usar globbing mínimo y archivos de reglas estrechos que cada uno sirva a una preocupación (por ejemplo, setup de repo, reglas de test, verificaciones de seguridad).
- Mantener archivos AGENTS y alias cortos-a-medianos; mover runbooks detallados a docs enlazados.
- Para Codex, preferir referencias de archivo explícitas y rutas concretas para reuso exacto.
- Evitar agregar detalles históricos o de proceso no relacionados para evitar desviación de token/contexto durante lecturas futuras de herramientas.

## 8. Modo de construcción brownfield

- Coincidir con terminología, navegación y patrones de componentes existentes.
- Preservar la IA existente a menos que haya un plan de migración documentado.
- Para reescrituras, incluir nota de migración de rutas antiguas a nuevas.
- Preferir el conjunto de cambios más pequeño y seguro que mejore la utilidad.

## 9. Modo de construcción evergreen

- Preferir conceptos estables sobre narrativa atada a releases.
- Aislar detalles volátiles bajo secciones de versión claramente marcadas.
- Incluir señales de mantenimiento: propietarios, disparadores de actualización, criterios de obsolescencia.
- Incluir notas de ciclo de vida: rutas de deprecación y reemplazo.

## 10. Restricciones de escritura

- Usar lenguaje preciso e instrucciones cortas e imperativas.
- Mantener ejemplos de código listos para copiar y autocontenidos.
- Incluir modos de fallo comunes y valores por defecto seguros.
- Evitar guía de marcador de posición que no pueda ejecutarse.

## 11. Preparación para agentes y automatización

- Mantener hechos clave en texto (no solo en imágenes).
- Preferir listas/tablas estructuradas cuando las opciones importan.
- Agregar enlaces y anclas que permitan navegación determinista.
- Documentar qué puede verificarse automáticamente en CI.

## 12. Validación de construcción

- Validar comandos y snippets donde sea posible.
- Verificar enlaces y referencias en secciones modificadas.
- Ejecutar un barrido de existencia de referencias para cada ruta/comando que se introdujo.
- Verificar consistencia de framework de docs cuando esté en alcance (por ejemplo config de Sphinx/Fern y rutas de docs referenciadas).

## 13. Modo de paridad multilingüe (cuando aplique)

- Elegir un idioma fuente de verdad para precisión técnica y timing de release.
- Definir objetivo de paridad: paridad completa, paridad escalonada o divergencia intencional por sección.
- Mantener estructura alineada entre locales (títulos, anclas, orden de secciones) cuando sea posible.
- Preservar corrección de comandos/código primero; localizar texto explicativo segundo.
- Si la paridad no es factible, agregar nota visible con alcance faltante y ventana de sincronización esperada.
- Ejecutar verificación de paridad de locale para secciones modificadas (pasos agregados/eliminados, advertencias, prerrequisitos).
- Registrar verificaciones no resueltas explícitamente en el handoff.

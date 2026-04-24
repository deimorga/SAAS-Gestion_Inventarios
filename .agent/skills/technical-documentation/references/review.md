# Guía de Revisión de Docs

Leer `principles.md` primero, luego aplicar esta lista de verificación.

## 1. Alcance y clasificación

- Identificar tipo de doc y audiencia objetivo.
- Confirmar intención brownfield vs evergreen.
- Confirmar resultado esperado para el lector.
- Para revisiones de repo completo, incluir explícitamente tanto superficies de gobernanza como superficies de docs de producto (`doc/`, árboles README, `.md/.mdx/.mdc`, `.rst/.rsc`, configs de frameworks de docs).

## 2. Comportamiento de investigación

- Encontrar proactivamente problemas y riesgos sin esperar indicaciones repetidas.
- Si hay señales de problemas más profundos, continuar investigación más allá de la primera pasada.
- Se aceptan investigaciones extensas y de larga duración cuando sean necesarias para confianza y corrección.
- Cuando estén disponibles, usar sub-agentes para descubrimiento paralelo acotado (por ejemplo inventario de archivos, validación de comandos o verificaciones de consistencia entre docs), luego fusionar en un solo conjunto final de problemas.
- Cuando no se encuentren problemas, declararlo explícitamente y señalar riesgos residuales o brechas de validación.
- Por defecto `aplicar-correcciones` para defectos de documentación de alta confianza a menos que el usuario solicite explícitamente `solo-reporte`.
- No detenerse en verificaciones de AGENTS/CONTRIBUTING cuando la tarea abarca toda la documentación; continuar hacia superficies de contenido de docs y framework de docs.

## 3. Revisión de superficie de gobernanza

- Usar `references/agent-and-contributing.md` como fuente de verdad para inventario, mapeo canónico/alias y manejo de precedencia/conflictos.

Para AGENTS.md:

- Confirmar intención de persona, alcance y límites de comandos/herramientas son explícitos.
- Verificar que el estilo de frontmatter coincide con convenciones del repo cuando está presente.
- Asegurar que los límites `Siempre`, `Preguntar primero` y `Nunca` están presentes cuando se esperan.
- Requerir ejemplos concretos de comandos y rutas específicas del repo para evitar ambigüedad.

Para CONTRIBUTING.md:

- Verificar que el flujo de trabajo de issues/PRs es completo y accionable.
- Asegurar que setup local, comandos de lint/test y criterios de revisión son precisos.
- Asegurar que la gobernanza no conflicta con instrucciones anidadas de AGENTS.
- Señalar archivos sobredimensionados que deberían dividirse en docs de secciones enlazados (por ejemplo setup específico de herramientas y docs de release).

Para consciencia de plataforma de agente:

- Confirmar que las referencias son mínimas y acotadas para comportamiento glob de Cursor/Claude.
- Confirmar que la guía para Codex usa referencias de archivo explícitas.
- Confirmar que ambas superficies representan el mismo núcleo de política compartida (comandos, límites y precedencia), no guía divergente.
- Auditar comportamiento de compatibilidad `.agents`/`.cursor`:
  - verificar que directorio canónico de reglas y estado de symlink coinciden con política del repo
  - verificar integridad del objetivo del symlink y expectativas de plataforma/tooling
  - verificar que las referencias de política AGENTS permanecen canónicas para Codex incluso cuando existe compatibilidad `.cursor`
- Verificar inflado de contexto por declaraciones de política duplicadas entre archivos de agente y contribuidor.
- Verificar reglas conflictivas, habilidades e instrucciones de agente.
- Verificar información conflictiva en instrucciones de agente vs codebase.
- Verificar archivos referenciados rotos o faltantes (por ejemplo archivos README/index nombrados como puntos de entrada canónicos).
- Verificar desviación de setup/comandos (por ejemplo comandos de instalación inexistentes, comandos de nivel raíz que deberían tener alcance de módulo).

## 4. Revisión de superficie de documentación de producto

- Verificar cobertura de IA de docs a través de archivos `README*` raíz/módulo y árboles `doc/**`.
- Revisar fuentes de docs nativas de framework en alcance (por ejemplo Fern, Mintlify, Sphinx, MkDocs) y asegurar que la guía coincide con archivos fuente de verdad reales.
- Verificar `.md/.mdx/.mdc/.rst/.rsc` para comandos obsoletos, prerrequisitos faltantes y enlaces cruzados rotos.
- Confirmar que rutas de docs referenciadas y anclas existen.
- Señalar docs que deberían dividirse/fusionarse para mejorar descubribilidad y mantenimiento.

## 5. Verificaciones de config de framework y mapeo de rutas

- Detectar y leer config de framework primero (por ejemplo config de Fern, `conf.py` de Sphinx, config de Mintlify o equivalente).
- Resolver referencias de rutas relativas al archivo/config declarante.
- Tratar rutas del sistema de archivos y rutas de URL publicadas como mapas separados; verificar ambos.
- Señalar desviación de mapeo de rutas explícitamente (`archivo faltante`, `ruta obsoleta`, `ruta base incorrecta`).

## 6. Revisión estructural

- Verificación de embudo: qué/por qué, inicio rápido, próximos pasos.
- Validar flujo de títulos y descubribilidad de navegación.
- Señalar contenido crítico atrapado en imágenes o secciones enterradas.
- Verificar alineación con Diataxis y dividir secciones de propósito mixto.

## 7. Revisión de calidad de escritura

- Verificar párrafos concisos y escaneables.
- Eliminar pronombres ambiguos y términos indefinidos.
- Verificar que los ejemplos son ejecutables y con alcance correcto.
- Verificar que el tono es directivo, técnico y no vago.

## 8. Modo de revisión brownfield

- Verificar compatibilidad con IA de docs y convenciones existentes.
- Verificar que anclas, redirecciones y enlaces entre docs permanecen válidos.
- Señalar regresiones en rutas de onboarding y completación de tareas.
- Asegurar que terminología modificada se propaga intencionalmente.

## 9. Modo de revisión evergreen

- Señalar redacción con fecha o frágil sin alcance de versión.
- Verificar que señales de propiedad y actualización están presentes.
- Asegurar que las recomendaciones permanecen válidas después de evolución rutinaria del producto.
- Señalar guía de deprecación/migración faltante.

## 10. Revisión de tooling y plataforma

Leer `tooling.md` si la adecuación de plataforma es incierta.

- Verificar si el contenido usa efectivamente las primitivas de la plataforma.
- Señalar estructura que va en contra de la plataforma de docs elegida.
- Recomendar mejoras específicas de plataforma orientadas a reducir carga cognitiva.

## 11. Revisión de paridad multilingüe (cuando aplique)

- Confirmar idioma fuente de verdad declarado y política de paridad esperada.
- Comparar secciones modificadas entre locales para desviación de pasos/orden/advertencias.
- Señalar actualizaciones faltantes en prerrequisitos, notas de versión, límites y guía de seguridad.
- Permitir divergencia intencional solo cuando la justificación es explícita y el impacto al usuario es bajo.
- Requerir nota visible para el lector cuando la paridad de locale es parcial.

## 12. Formato de salida

1. Problemas bloqueantes (archivo + corrección requerida)
2. Mejoras no bloqueantes
3. Notas de validación (completado vs pendiente)

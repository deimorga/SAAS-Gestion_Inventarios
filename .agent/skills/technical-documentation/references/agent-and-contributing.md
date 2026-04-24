# Principios de AGENT y CONTRIBUTING

Esta referencia consolida las reglas fundamentales para documentación de políticas de agente y gobernanza de contribuidores.

Debes:
1. Descubrir archivos de instrucciones a nivel de repo y anidados con:
   `rg --files -g 'AGENTS.md' -g 'CONTRIBUTING.md' -g 'CLAUDE.md' -g 'AGENT.md' -g '.cursor/rules/*' -g '.cursorrules' -g '.agent/**' -g '.agents/**' -g '.pi/**' -g 'AGENTS.*.md'`
2. Leer el par `AGENTS.md`/`CONTRIBUTING.md` raíz y del alcance más cercano antes de editar.
3. Si existen archivos alias, normalizar a una fuente canónica (`AGENTS.md` preferido cuando está presente; de lo contrario el alias más cercano), más punteros de compatibilidad o notas explícitas de symlink.
4. Documentar instrucciones conflictivas y decisiones de precedencia.

## Línea base de GitHub + AGENTS

Fuente: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors
Fuente: https://agents.md/
Fuente: https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
Fuente: https://cobusgreyling.substack.com/p/what-is-agentsmd
Fuente: https://www.infoq.com/news/2025/08/agents-md/

Usar como principios operativos por defecto:

1. Mantener `CONTRIBUTING.md` descubrible y accionable (`.github`, raíz o `docs`).
2. Mantener instrucciones de agente concretas: comandos reales, rutas reales, límites claros.
3. Usar límites de comportamiento explícitos para agentes: `Siempre`, `Preguntar primero`, `Nunca`.
4. Mantener reglas de contribuidor y agente alineadas con los flujos de trabajo reales del repositorio.
5. Asegurar guía clara para agentes sobre si, cuándo y cómo crear issues y pull requests.

## Política canónica y de alias

Fuente: https://agents.md/
Fuente: https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/

1. Tratar `AGENTS.md` como canónico cuando esté presente.
2. Si `AGENTS.md` está ausente, tratar el archivo alias más cercano como canónico.
3. Mantener superficies de compatibilidad explícitas: `AGENTS.md`, `AGENT.md`, `.cursorrules`, `.cursor/rules/*`, `.agent/`, `.agents/`, `.pi/`.
4. Si se usan aliases, documentar cómo se mapean de vuelta a la política canónica (o hacer symlink cuando sea soportado).
5. Cuando los repos usen `.agents/` como almacenamiento canónico de reglas, mantener `.cursor` como symlink de compatibilidad hacia `.agents` para auto-carga de reglas de Cursor.
6. Mantener política DRY: almacenar un núcleo de política compartida y exponerlo vía aliases/symlinks en lugar de duplicar texto de reglas.

## Consciencia de contexto por plataforma de agente

Fuente: https://github.com/vercel-labs/agent-skills/blob/main/AGENTS.md
Fuente: https://github.com/openai/codex/blob/main/AGENTS.md

1. Para consumidores glob estilo Cursor y Claude, mantener archivos de reglas estrechos y acotados.
2. Evitar sobre-referenciar conjuntos de rutas grandes que inflen el contexto para agentes basados en glob.
3. Para flujos de trabajo estilo Codex, preferir referencias de archivo explícitas y comandos deterministas.
4. Mantener runbooks largos fuera de archivos de política de nivel superior; enlazar a docs acotados.
5. Asegurar que todos los agentes tengan un camino feliz (happy path) sin importar la plataforma, asegurando que todo funcione en Codex, Claude y otros agentes de codificación.

## Operaciones de symlink y compatibilidad

1. Disposición preferida para compatibilidad multi-agente:
   - directorio canónico de reglas: `.agents/`
   - ruta de compatibilidad Cursor: symlink `.cursor -> .agents`
   - doc de política canónica: `AGENTS.md` apuntando a rutas de `.agents` donde sea relevante
2. Validar estado de symlink antes de finalizar cambios:
   - si `.agents/` existe y `.cursor` falta, crear symlink `.cursor` hacia `.agents`
   - si `.cursor` es un symlink a otro destino, corregir destino o documentar por qué debe diferir
   - si `.cursor` es un directorio/archivo real, tratar como conflicto de migración y preguntar antes de reemplazar
3. Validar payload de reglas a través del directorio canónico:
   - reglas: `.agents/rules/*.mdc` con frontmatter válido (`description`, `globs`, `alwaysApply` según sea necesario)
   - comandos: `.agents/commands/*.md` cuando se usa enrutamiento de comandos
   - config MCP: `.agents/mcp.json` cuando MCP está en alcance
4. Mantener comportamiento de Codex explícito:
   - `AGENTS.md` es primario para instrucciones de repositorio de Codex
   - compatibilidad `.cursor` es para auto-carga de Cursor y no reemplaza política canónica de AGENTS
5. Registrar correcciones de symlink aplicadas y brechas de compatibilidad no resueltas en notas de validación.

## Estándares de modo dual y entregables

Fuente: https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
Fuente: https://agents.md/
Fuente: https://github.com/openai/codex/blob/main/AGENTS.md
Fuente: https://github.com/vercel-labs/agent-skills/blob/main/AGENTS.md

1. Autoría de un núcleo de política compartida (mismos comandos, límites y precedencia) para todos los agentes.
2. Para agentes estilo Cursor/Claude, exponer ese núcleo a través de archivos acotados dirigidos por glob (superficie pequeña de `AGENTS.md`/reglas).
3. Para Codex, exponer ese mismo núcleo a través de referencias de archivo explícitas con alcance preciso.
4. Donde los estilos divergen, preferir la estructura común más pequeña que satisfaga ambos y evitar duplicar texto de política.
5. Tratar AGENTS/CONTRIBUTING como entregables de primera clase cuando estén en alcance.
6. Preservar estructura, restricciones y ejemplos requeridos de archivos existentes.
7. Alinear redacción y comandos con instrucciones activas del repositorio.

## Descubrimiento proactivo de problemas y remediación

Fuente: https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
Fuente: https://github.com/openai/codex/blob/main/AGENTS.md
Fuente: https://github.com/vercel-labs/agent-skills/blob/main/AGENTS.md

1. Ejecutar una revisión de matriz de conflictos a través de AGENTS/aliases/CONTRIBUTING y docs relacionados de comandos/reglas antes de finalizar.
2. Tratar lo siguiente como defectos de alta prioridad: archivos referenciados faltantes, comandos de setup inexistentes, discrepancias de alcance de comandos y conflictos de política de ramas/commits.
3. No detenerse en notas de solo-advertencia cuando una corrección de bajo riesgo es clara; aplicar la corrección en la misma pasada.
4. Si falta un archivo canónico de entrada (por ejemplo un `README.md` de directorio del que dependen docs), crear un archivo mínimo accionable y actualizar referencias.
5. Se aceptan investigaciones de larga duración cuando sean necesarias para descubrir desviación entre archivos, especialmente en ecosistemas de instrucciones de agente.

## Descubrimiento

1. Los agentes prefieren comandos de terminal simples, por lo que tener bien definidos `make *` o `npm run *` es ideal.
2. Los agentes pueden descubrir comandos de terminal a través de autocompletado de shell, por lo que proporcionar autocompletado ayuda.

## Control de tamaño y alcance de CONTRIBUTING

Fuente: https://contributing.md/how-to-build-contributing-md/
Fuente: https://blog.codacy.com/best-practices-to-manage-an-open-source-project
Fuente: https://mozillascience.github.io/working-open-workshop/contributing/
Fuente: https://github.com/openclaw/openclaw/blob/main/CONTRIBUTING.md

1. Mantener `CONTRIBUTING.md` raíz enfocado en setup, flujo de issues, flujo de PR, testing y puertas de revisión.
2. Usar enlaces a plantillas de issues/PR en lugar de incrustar cada detalle de proceso inline.
3. Cuando el archivo crezca demasiado, dividir por dominio y enlazar desde raíz.
4. Mover contenido extenso a docs si están disponibles (por ejemplo flujos de Mintlify/Fern/Sphinx) para evitar una guía de contribuidor grande.
5. Optimizar para legibilidad de agentes/máquinas además de humanos.

## Repos de ejemplo a emular

Fuente: https://github.com/openclaw/openclaw/blob/main/AGENTS.md
Fuente: https://github.com/openclaw/openclaw/blob/main/CONTRIBUTING.md
Fuente: https://github.com/openclaw/openclaw/blob/main/VISION.md
Fuente: https://github.com/openai/codex/blob/main/AGENTS.md
Fuente: https://github.com/processing/p5.js/blob/main/AGENTS.md
Fuente: https://github.com/vercel-labs/agent-skills/blob/main/AGENTS.md
Fuente: https://github.com/agentsmd/agents.md/blob/main/AGENTS.md
Fuente: https://github.com/rails/rails/blob/main/CONTRIBUTING.md
Fuente: https://github.com/kubernetes/kubernetes/blob/master/CONTRIBUTING.md
Fuente: https://github.com/atom/atom/blob/master/CONTRIBUTING.md
Fuente: https://github.com/github/docs/blob/main/CONTRIBUTING.md
Fuente: https://github.com/facebook/react/blob/main/CONTRIBUTING.md

1. OpenClaw: política sólida de alias del mundo real y cohesión AGENTS/CONTRIBUTING/VISION.
2. OpenAI Codex: disciplina estricta de comandos y control de alcance explícito.
3. p5.js: guardarraíles explícitos de política de IA en instrucciones de agente.
4. Vercel + spec agentsmd: patrones AGENTS compactos y eficientes en contexto.
5. Rails/Kubernetes/Atom/GitHub Docs/React: patrones de guía de contribuidor a diferentes escalas de proyecto.

## Política Práctica de Fusión

Cuando estas reglas entren en conflicto:

1. Preservar éxito de tarea de contribuidor y lector primero.
2. Preservar claridad de instrucciones y límites inequívocos segundo.
3. Preservar mantenibilidad a largo plazo y eficiencia de contexto tercero.
4. Agregar optimización adicional de agente solo si no reduce claridad para humanos o hay necesidad explícita.
5. Usar tu juicio como experto.

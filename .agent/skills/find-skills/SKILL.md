---
name: find-skills
description: Ayuda a los usuarios a descubrir e instalar habilidades de agente cuando hacen preguntas como "cómo hago X", "busca una habilidad para X", "¿hay una habilidad que pueda...?", o expresan interés en ampliar capacidades. Esta habilidad debe usarse cuando el usuario busca una funcionalidad que podría existir como una habilidad instalable.
---

# Buscar Habilidades (Find Skills)

Esta habilidad te ayuda a descubrir e instalar habilidades del ecosistema abierto de habilidades para agentes.

## Cuándo Usar Esta Habilidad

Usa esta habilidad cuando el usuario:

- Pregunta "¿cómo hago X?" donde X podría ser una tarea común con una habilidad existente
- Dice "busca una habilidad para X" o "¿hay una habilidad para X?"
- Pregunta "¿puedes hacer X?" donde X es una capacidad especializada
- Expresa interés en ampliar las capacidades del agente
- Quiere buscar herramientas, plantillas o flujos de trabajo
- Menciona que desearía tener ayuda con un dominio específico (diseño, pruebas, despliegue, etc.)

## ¿Qué es la CLI de Skills?

La CLI de Skills (`npx skills`) es el gestor de paquetes para el ecosistema abierto de habilidades de agentes. Las habilidades son paquetes modulares que extienden las capacidades del agente con conocimiento especializado, flujos de trabajo y herramientas.

**Comandos clave:**

- `npx skills find [consulta]` - Buscar habilidades interactivamente o por palabra clave
- `npx skills add <paquete>` - Instalar una habilidad desde GitHub u otras fuentes
- `npx skills check` - Buscar actualizaciones de habilidades
- `npx skills update` - Actualizar todas las habilidades instaladas

**Explora habilidades en:** https://skills.sh/

## Cómo Ayudar a los Usuarios a Encontrar Habilidades

### Paso 1: Entender Qué Necesitan

Cuando un usuario pide ayuda con algo, identifica:

1. El dominio (ej: React, pruebas, diseño, despliegue)
2. La tarea específica (ej: escribir pruebas, crear animaciones, revisar PRs, despliegues)
3. Si esta es una tarea lo suficientemente común para que exista una habilidad probable

### Paso 2: Buscar Habilidades

Ejecuta el comando find con una consulta relevante:

```bash
npx skills find [consulta]
```

Por ejemplo:

- Usuario pregunta "¿cómo hago mi app React más rápida?" → `npx skills find react performance`
- Usuario pregunta "¿puedes ayudarme con revisiones de PR?" → `npx skills find pr review`
- Usuario pregunta "Necesito crear un changelog" → `npx skills find changelog`

El comando devolverá resultados como:

```
Install with npx skills add <owner/repo@skill>

vercel-labs/agent-skills@vercel-react-best-practices
└ https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

### Paso 3: Presentar Opciones al Usuario

Cuando encuentres habilidades relevantes, preséntalas al usuario con:

1. El nombre de la habilidad y qué hace
2. El comando de instalación que pueden ejecutar
3. Un enlace para aprender más en skills.sh

Ejemplo de respuesta:

```
¡Encontré una habilidad que podría ayudar! La habilidad "vercel-react-best-practices" proporciona
guías de optimización de rendimiento para React y Next.js de Vercel Engineering.

Para instalarla:
npx skills add vercel-labs/agent-skills@vercel-react-best-practices

Aprende más: https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

### Paso 4: Ofrecer Instalar

Si el usuario quiere proceder, puedes instalar la habilidad por él:

```bash
npx skills add <owner/repo@skill> -g -y
```

El flag `-g` instala globalmente (nivel de usuario) y `-y` salta los prompts de confirmación.

## Categorías Comunes de Habilidades

Al buscar, considera estas categorías comunes:

| Categoría | Consultas de Ejemplo |
| --- | --- |
| Desarrollo Web | react, nextjs, typescript, css, tailwind |
| Pruebas (Testing) | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd |
| Documentación | docs, readme, changelog, api-docs |
| Calidad de Código | review, lint, refactor, best-practices |
| Diseño | ui, ux, design-system, accessibility |
| Productividad | workflow, automation, git |

## Consejos para Búsquedas Efectivas

1. **Usa palabras clave específicas**: "react testing" es mejor que solo "testing"
2. **Prueba términos alternativos**: Si "deploy" no funciona, prueba "deployment" o "ci-cd"
3. **Revisa fuentes populares**: Muchas habilidades vienen de `vercel-labs/agent-skills` o `ComposioHQ/awesome-claude-skills`

## Cuando No Se Encuentran Habilidades

Si no existen habilidades relevantes:

1. Reconoce que no se encontró ninguna habilidad existente
2. Ofrece ayudar con la tarea directamente usando tus capacidades generales
3. Sugiere que el usuario podría crear su propia habilidad con `npx skills init`

Ejemplo:

```
Busqué habilidades relacionadas con "xyz" pero no encontré coincidencias.
¡Aún puedo ayudarte con esta tarea directamente! ¿Te gustaría que proceda?

Si esto es algo que haces a menudo, podrías crear tu propia habilidad:
npx skills init my-xyz-skill
```

---
name: brainstorming
description: "Debes usar esta habilidad ANTES de cualquier trabajo creativo: crear funcionalidades, construir componentes, agregar funcionalidad o modificar comportamiento. Explora la intención del usuario, requisitos y diseño antes de la implementación."
---

# Convertir Ideas en Diseños a través de Brainstorming

## Descripción General

Ayuda a convertir ideas en diseños y especificaciones completamente formados a través de un diálogo colaborativo natural.

Comienza entendiendo el contexto actual del proyecto, luego haz preguntas una a la vez para refinar la idea. Una vez que comprendas lo que se está construyendo, presenta el diseño en secciones pequeñas (200-300 palabras), verificando después de cada sección si se ve bien hasta el momento.

## El Proceso

**Comprendiendo la idea:**
- Revisa primero el estado actual del proyecto (archivos, docs, commits recientes)
- Haz preguntas una a la vez para refinar la idea
- Prefiere preguntas de opción múltiple cuando sea posible, pero abiertas también está bien
- Solo una pregunta por mensaje - si un tema necesita más exploración, divídelo en múltiples preguntas
- Enfócate en entender: propósito, restricciones, criterios de éxito

**Explorando enfoques:**
- Propón 2-3 enfoques diferentes con sus pros y contras
- Presenta las opciones conversacionalmente con tu recomendación y razonamiento
- Lidera con tu opción recomendada y explica por qué

**Presentando el diseño:**
- Una vez que creas que entiendes lo que se está construyendo, presenta el diseño
- Divídelo en secciones de 200-300 palabras
- Pregunta después de cada sección si se ve bien hasta el momento
- Cubre: arquitectura, componentes, flujo de datos, manejo de errores, pruebas
- Está listo para retroceder y aclarar si algo no tiene sentido

## Después del Diseño

**Documentación:**
- Escribe el diseño validado en `doc/planes/AAAA-MM-DD-<tema>-diseño.md`
- Usa la habilidad elements-of-style:writing-clearly-and-concisely si está disponible
- Haz commit del documento de diseño en git

**Implementación (si continúas):**
- Pregunta: "¿Listo para configurar la implementación?"
- Usa superpowers:using-git-worktrees para crear un espacio de trabajo aislado
- Usa superpowers:writing-plans para crear un plan de implementación detallado

## Principios Clave

- **Una pregunta a la vez** - No abrumes con múltiples preguntas
- **Opción múltiple preferida** - Más fácil de responder que preguntas abiertas cuando sea posible
- **YAGNI despiadadamente** - Elimina características innecesarias de todos los diseños (You Aren't Gonna Need It)
- **Explora alternativas** - Siempre propón 2-3 enfoques antes de decidir
- **Validación incremental** - Presenta el diseño en secciones, valida cada una
- **Sé flexible** - Retrocede y aclara cuando algo no tenga sentido

# Principios de Documentación

Esta referencia consolida las reglas fundamentales usadas por esta habilidad.

## Matt Palmer: 8 Reglas para Mejor Documentación

Fuente: https://mattpalmer.io/posts/2025/10/8-rules-for-better-docs/

Usar como principios operativos por defecto:

1. Escribir para humanos, optimizar para agentes.
2. Comenzar con un embudo: qué/por qué, inicio rápido, próximos pasos.
3. Usar Diataxis para estructurar el contenido.
4. Escribir con IA, pero estructurar para agentes.
5. Delegar operaciones rutinarias de docs a agentes en segundo plano.
6. Automatizar calidad con CI.
7. Automatizar scaffolding y tareas repetitivas de flujo de trabajo.
8. Hacer que la contribución sea fácil y visible.

## Cookbook de OpenAI: Qué Hace Buena la Documentación

Fuente: https://cookbook.openai.com/articles/what_makes_documentation_good

Restricciones clave de calidad:

- Preferir terminología específica y precisa sobre jerga de nicho.
- Mantener los ejemplos autocontenidos y minimizar dependencias.
- Priorizar temas de alto valor sobre profundidad en casos extremos.
- No enseñar patrones inseguros (por ejemplo, secretos expuestos).
- Abrir con contexto que ayude a los lectores a orientarse rápidamente.
- Aplicar empatía y anular reglas rígidas cuando claramente mejore los resultados.

## Política Práctica de Fusión

Cuando estas reglas entren en conflicto:

1. Preservar el éxito de la tarea del lector primero.
2. Preservar la claridad estructural segundo.
3. Preservar la mantenibilidad a largo plazo tercero.
4. Agregar optimización para agentes solo si no reduce la claridad para humanos.

Para especificidades de instrucciones de agente y gobernanza de contribuidores (AGENTS/aliases/CONTRIBUTING), usar `references/agent-and-contributing.md` como fuente de verdad detallada adicional.

## Política de Ejecución para Esta Habilidad

- Se permiten investigaciones extensas y de larga duración para trabajo tanto de construcción como de revisión cuando sea necesario para resolver ambigüedades o desviaciones entre archivos.
- Usar sub-agentes cuando estén disponibles para descubrimiento paralelo acotado, verificación o comparación entre fuentes.
- Mantener un resultado fusionado: las salidas de sub-agentes deben normalizarse en un solo conjunto consistente de recomendaciones/correcciones.

## Regla de Paridad Multilingüe

Cuando la documentación existe en múltiples idiomas, apuntar a paridad entre locales para contenido crítico para tareas (pasos, advertencias, prerrequisitos y límites). Si la paridad completa no es posible, publicar estado de paridad explícito e intención de sincronización.

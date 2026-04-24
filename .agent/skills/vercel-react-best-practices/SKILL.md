---
name: vercel-react-best-practices
description: Pautas de optimización de rendimiento de React y Next.js del equipo de ingeniería de Vercel. Esta habilidad debe usarse al escribir, revisar o refactorizar código React/Next.js para asegurar patrones óptimos de rendimiento. Se activa en tareas que involucran componentes React, páginas Next.js, obtención de datos, optimización de bundles o mejoras de rendimiento.
license: MIT
metadata:
  author: vercel
  version: "1.0.0"
---

# Mejores Prácticas de React para Vercel

Guía completa de optimización de rendimiento para aplicaciones React y Next.js, mantenida por Vercel. Contiene 57 reglas distribuidas en 8 categorías, priorizadas por impacto para guiar la refactorización automatizada y generación de código.

## Cuándo Aplicar

Consulte estas pautas cuando:
- Escriba nuevos componentes React o páginas Next.js
- Implemente obtención de datos (lado cliente o servidor)
- Revise código en busca de problemas de rendimiento
- Refactorice código existente de React/Next.js
- Optimice el tamaño del bundle o tiempos de carga

## Categorías de Reglas por Prioridad

| Prioridad | Categoría | Impacto | Prefijo |
|----------|----------|--------|---------|
| 1 | Eliminación de Cascadas (Waterfalls) | CRÍTICO | `async-` |
| 2 | Optimización de Tamaño de Bundle | CRÍTICO | `bundle-` |
| 3 | Rendimiento del Lado del Servidor | ALTO | `server-` |
| 4 | Obtención de Datos del Lado del Cliente | MEDIO-ALTO | `client-` |
| 5 | Optimización de Re-renderizado | MEDIO | `rerender-` |
| 6 | Rendimiento de Renderizado | MEDIO | `rendering-` |
| 7 | Rendimiento de JavaScript | BAJO-MEDIO | `js-` |
| 8 | Patrones Avanzados | BAJO | `advanced-` |

## Referencia Rápida

### 1. Eliminación de Cascadas (CRÍTICO)

- `async-defer-await` - Mover await a las ramas donde realmente se usa
- `async-parallel` - Usar Promise.all() para operaciones independientes
- `async-dependencies` - Usar better-all para dependencias parciales
- `async-api-routes` - Iniciar promesas temprano, await tarde en rutas de API
- `async-suspense-boundaries` - Usar Suspense para transmitir contenido en streaming

### 2. Optimización de Tamaño de Bundle (CRÍTICO)

- `bundle-barrel-imports` - Importar directamente, evitar archivos barrel
- `bundle-dynamic-imports` - Usar next/dynamic para componentes pesados
- `bundle-defer-third-party` - Cargar analytics/logging después de la hidratación
- `bundle-conditional` - Cargar módulos solo cuando la funcionalidad esté activada
- `bundle-preload` - Precargar al pasar el cursor/foco para velocidad percibida

### 3. Rendimiento del Lado del Servidor (ALTO)

- `server-auth-actions` - Autenticar acciones del servidor como rutas de API
- `server-cache-react` - Usar React.cache() para deduplicación por solicitud
- `server-cache-lru` - Usar caché LRU para caché entre solicitudes
- `server-dedup-props` - Evitar serialización duplicada en props de RSC
- `server-serialization` - Minimizar datos pasados a componentes cliente
- `server-parallel-fetching` - Reestructurar componentes para paralelizar obtenciones
- `server-after-nonblocking` - Usar after() para operaciones no bloqueantes

### 4. Obtención de Datos del Lado del Cliente (MEDIO-ALTO)

- `client-swr-dedup` - Usar SWR para deduplicación automática de solicitudes
- `client-event-listeners` - Deduplicar event listeners globales
- `client-passive-event-listeners` - Usar listeners pasivos para scroll
- `client-localstorage-schema` - Versionar y minimizar datos de localStorage

### 5. Optimización de Re-renderizado (MEDIO)

- `rerender-defer-reads` - No suscribirse a estado que solo se usa en callbacks
- `rerender-memo` - Extraer trabajo costoso en componentes memoizados
- `rerender-memo-with-default-value` - Elevar props no primitivas por defecto
- `rerender-dependencies` - Usar dependencias primitivas en effects
- `rerender-derived-state` - Suscribirse a booleanos derivados, no valores crudos
- `rerender-derived-state-no-effect` - Derivar estado durante el render, no en effects
- `rerender-functional-setstate` - Usar setState funcional para callbacks estables
- `rerender-lazy-state-init` - Pasar función a useState para valores costosos
- `rerender-simple-expression-in-memo` - Evitar memo para primitivos simples
- `rerender-move-effect-to-event` - Poner lógica de interacción en event handlers
- `rerender-transitions` - Usar startTransition para actualizaciones no urgentes
- `rerender-use-ref-transient-values` - Usar refs para valores transitorios frecuentes

### 6. Rendimiento de Renderizado (MEDIO)

- `rendering-animate-svg-wrapper` - Animar div contenedor, no elemento SVG
- `rendering-content-visibility` - Usar content-visibility para listas largas
- `rendering-hoist-jsx` - Extraer JSX estático fuera de componentes
- `rendering-svg-precision` - Reducir precisión de coordenadas SVG
- `rendering-hydration-no-flicker` - Usar script inline para datos solo cliente
- `rendering-hydration-suppress-warning` - Suprimir discrepancias esperadas
- `rendering-activity` - Usar componente Activity para mostrar/ocultar
- `rendering-conditional-render` - Usar ternario, no && para condicionales
- `rendering-usetransition-loading` - Preferir useTransition para estado de carga

### 7. Rendimiento de JavaScript (BAJO-MEDIO)

- `js-batch-dom-css` - Agrupar cambios CSS vía clases o cssText
- `js-index-maps` - Construir Map para búsquedas repetidas
- `js-cache-property-access` - Cachear propiedades de objetos en loops
- `js-cache-function-results` - Cachear resultados de funciones en Map de nivel módulo
- `js-cache-storage` - Cachear lecturas de localStorage/sessionStorage
- `js-combine-iterations` - Combinar múltiples filter/map en un solo loop
- `js-length-check-first` - Verificar longitud de array antes de comparación costosa
- `js-early-exit` - Retornar temprano de funciones
- `js-hoist-regexp` - Elevar creación de RegExp fuera de loops
- `js-min-max-loop` - Usar loop para min/max en lugar de sort
- `js-set-map-lookups` - Usar Set/Map para búsquedas O(1)
- `js-tosorted-immutable` - Usar toSorted() para inmutabilidad

### 8. Patrones Avanzados (BAJO)

- `advanced-event-handler-refs` - Almacenar event handlers en refs
- `advanced-init-once` - Inicializar app una vez por carga de app
- `advanced-use-latest` - useLatest para refs de callback estables

## Cómo Usar

Lea los archivos de reglas individuales para explicaciones detalladas y ejemplos de código:

```
rules/async-parallel.md
rules/bundle-barrel-imports.md
```

Cada archivo de regla contiene:
- Breve explicación de por qué importa
- Ejemplo de código incorrecto con explicación
- Ejemplo de código correcto con explicación
- Contexto adicional y referencias

## Documento Compilado Completo

Para la guía completa con todas las reglas expandidas: `AGENTS.md`

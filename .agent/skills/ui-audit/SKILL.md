---
name: ui-audit
description: "Habilidad de IA para auditorías de UI automatizadas. Evalúa interfaces frente a principios de UX probados para jerarquía visual, accesibilidad, carga cognitiva, navegación y más. Basado en 'Making UX Decisions' de Tommy Geoco."
author: Tommy Geoco
homepage: https://audit.uxtools.co
---

# Habilidad de Auditoría de UI (UI Audit)

Evalúe interfaces frente a principios de UX probados. Basado en [Making UX Decisions](https://uxdecisions.com) por Tommy Geoco.

## Cuándo usar esta habilidad

- Tomar decisiones de diseño de UI/UX bajo presión de tiempo.
- Evaluar compensaciones (trade-offs) de diseño con contexto de negocio.
- Elegir patrones de UI apropiados para problemas específicos.
- Revisar diseños para asegurar integridad y calidad.
- Estructurar el pensamiento de diseño para nuevas interfaces.

## Filosofía Principal

**Velocidad ≠ Imprudencia.** Diseñar rápido no es automáticamente imprudente. Diseñar rápido de forma imprudente es imprudente. La diferencia es la intencionalidad.

## Los 3 Pilares de la Toma de Decisiones a Alta Velocidad

1. **Scaffolding (Andamiajes)** — Reglas que usa para automatizar decisiones recurrentes.
2. **Decisioning (Decisión)** — Proceso que usa para tomar nuevas decisiones.
3. **Crafting (Artesanía)** — Listas de verificación que usa para ejecutar decisiones.

## Estructura de Referencia Rápida

### Marcos Fundacionales
- `references/00-core-framework.md` — Los 3 pilares, flujo de trabajo de decisión, apuestas macro.
- `references/01-anchors.md` — 7 mentalidades fundacionales para la resiliencia del diseño.
- `references/02-information-scaffold.md` — Psicología, economía, accesibilidad, valores predeterminados.

### Listas de Verificación (Ejecución)
- `references/10-checklist-new-interfaces.md` — Proceso de 6 pasos para diseñar nuevas interfaces.
- `references/11-checklist-fidelity.md` — Estados de componentes, interacciones, escalabilidad, feedback.
- `references/12-checklist-visual-style.md` — Espaciado, color, elevación, tipografía, movimiento.
- `references/13-checklist-innovation.md` — Los 5 niveles del espectro de originalidad.

### Patrones (Soluciones Reutilizables)
- `references/20-patterns-chunking.md` — Tarjetas, pestañas, acordeones, paginación, carousels.
- `references/21-patterns-progressive-disclosure.md` — Tooltips, popovers, paneles laterales (drawers), modales.
- `references/22-patterns-cognitive-load.md` — Pasos (steppers), magos (wizards), navegación minimalista, formularios simplificados.
- `references/23-patterns-visual-hierarchy.md` — Tipografía, color, espacio en blanco, tamaño, proximidad.
- `references/24-patterns-social-proof.md` — Testimonios, contenido generado por usuarios (UGC), insignias, integración social.
- `references/25-patterns-feedback.md` — Barras de progreso, notificaciones, validación, ayuda contextual.
- `references/26-patterns-error-handling.md` — Validación de formularios, deshacer/rehacer, diálogos, autoguardado.
- `references/27-patterns-accessibility.md` — Navegación por teclado, ARIA, texto alternativo, contraste, zoom.
- `references/28-patterns-personalization.md` — Dashboards, contenido adaptativo, preferencias, localización (l10n).
- `references/29-patterns-onboarding.md` — Tours, consejos contextuales, tutoriales, listas de verificación.
- `references/30-patterns-information.md` — Migas de pan (breadcrumbs), mapas del sitio, etiquetado, búsqueda facetada.
- `references/31-patterns-navigation.md` — Navegación prioritaria, menús laterales (off-canvas), fijo (sticky), navegación inferior.

## Instrucciones de Uso

### Para Decisiones de Diseño
1. Lea `00-core-framework.md` para el flujo de trabajo de decisión.
2. Identifique si es una decisión recurrente (use andamiajes) o una nueva decisión (use el proceso).
3. Aplique la ponderación de 3 pasos: conocimiento institucional → familiaridad del usuario → investigación.

### Para Nuevas Interfaces
1. Siga la lista de verificación de 6 pasos en `10-checklist-new-interfaces.md`.
2. Consulte los archivos de patrones relevantes para componentes de UI específicos.
3. Use las listas de fidelidad y estilo visual para mejorar la calidad.

### Para Selección de Patrones
1. Identifique el problema central (fragmentación, divulgación, carga cognitiva, etc.).
2. Cargue la referencia de patrón relevante.
3. Evalúe beneficios, casos de uso, principios psicológicos y pautas de implementación.

## Resumen del Flujo de Trabajo de Decisión

Cuando se enfrente a una decisión de UI:

```
1. PONDERAR INFORMACIÓN
   ├─ ¿Qué dice el conocimiento institucional? (patrones existentes, marca, restricciones técnicas)
   ├─ ¿Con qué están familiarizados los usuarios? (convenciones, patrones de la competencia)
   └─ ¿Qué dice la investigación? (pruebas de usuario, analítica, estudios)

2. REDUCIR OPCIONES
   ├─ Eliminar lo que entra en conflicto con las restricciones.
   ├─ Priorizar lo que se alinea con las apuestas macro.
   └─ Elegir basándose en el soporte a los "Trabajos por Hacer" (JTBD).

3. EJECUTAR
   └─ Aplicar la lista de verificación y patrones relevantes.
```

## Categorías de Apuestas Macro (Macro Bets)

Las empresas ganan a través de uno o más de:

| Apuesta | Descripción | Implicación en el Diseño |
|-----|-------------|-------------------|
| **Velocidad** | Funciones al mercado más rápido | Reutilizar patrones, buscar metáforas en otros mercados. |
| **Eficiencia** | Gestionar mejor el desperdicio | Sistemas de diseño, reducir el trabajo en curso (WIP). |
| **Precisión** | Acertar más seguido | Investigación más sólida, instrumentación. |
| **Innovación** | Descubrir potencial sin explotar | Patrones novedosos, inspiración entre dominios. |

Alinee siempre las apuestas de diseño micro con las apuestas macro de la empresa.

## Principio Clave: Las Buenas Decisiones de Diseño son Relativas

Una decisión de diseño es "buena" cuando:
- Soporta los "Trabajos por Hacer" (Jobs-to-be-Done) del producto.
- Se alinea con las apuestas macro de la empresa.
- Respeta las restricciones (tiempo, tecnología, equipo).
- Equilibra la familiaridad del usuario con las necesidades de diferenciación.

No existe una solución de UI universalmente correcta, solo soluciones apropiadas al contexto.

---

## Generación de Informes de Auditoría

Cuando se le pida auditar un diseño, genere un informe completo. Incluya siempre estas secciones:

### Secciones Obligatorias
1. **Jerarquía Visual** — Encabezados, CTAs, agrupación, flujo de lectura, escala tipográfica, jerarquía de colores, espacio en blanco.
2. **Estilo Visual** — Consistencia de espaciado, uso del color, elevación/profundidad, tipografía, movimiento/animación.
3. **Accesibilidad** — Navegación por teclado, estados de enfoque, ratios de contraste, soporte para lectores de pantalla, objetivos táctiles.

### Secciones Contextuales (incluir cuando sea relevante)
4. **Navegación** — Para apps de varias páginas: orientación, migas de pan, estructura de menú, arquitectura de información.
5. **Usabilidad** — Para flujos interactivos: facilidad de descubrimiento, feedback, manejo de errores, carga cognitiva.
6. **Onboarding** — Para experiencias de nuevo usuario: primer uso, tutoriales, divulgación progresiva.
7. **Prueba Social** — Para páginas de landing/marketing: testimonios, señales de confianza, integración social.
8. **Formularios** — Para entrada de datos: etiquetas, validación, mensajes de error, tipos de campos.

### Formato de Salida de la Auditoría

```json
{
  "title": "Nombre del Diseño — Pantalla/Flujo",
  "project": "Nombre del Proyecto",
  "date": "AAAA-MM-DD",
  "figma_url": "opcional",
  "screenshot_url": "opcional - URL a la captura de pantalla",
  
  "macro_bets": [
    { "category": "velocity|efficiency|accuracy|innovation", "description": "...", "alignment": "strong|moderate|weak" }
  ],
  
  "jtbd": [
    { "user": "Tipo de Usuario", "situation": "contexto sin 'Cuando'", "motivation": "meta sin 'Quiero'", "outcome": "beneficio sin 'para poder'" }
  ],
  
  "visual_hierarchy": {
    "title": "Jerarquía Visual",
    "checks": [
      { "label": "Nombre de la verificación", "status": "pass|warn|fail|na", "notes": "Detalles" }
    ]
  },
  "visual_style": { ... },
  "accessibility": { ... },
  
  "priority_fixes": [
    { "rank": 1, "title": "Título del arreglo", "description": "Qué y por qué", "framework_reference": "XX-nombre_archivo.md → Nombre de la Sección" }
  ],
  
  "notes": "Observaciones generales opcionales"
}
```

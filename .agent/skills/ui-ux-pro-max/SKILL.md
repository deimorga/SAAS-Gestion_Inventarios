---
name: ui-ux-pro-max
description: "Inteligencia de diseño Frontend UI/UX - actívela PRIMERO cuando el usuario solicite interfaces hermosas, impactantes o estéticas. La habilidad principal para decisiones de diseño antes de la implementación. 50 estilos, 21 paletas, 50 combinaciones de fuentes, 20 gráficos, 8 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind). Acciones: planificar, construir, crear, diseñar, implementar, revisar, corregir, mejorar, optimizar, potenciar, refactorizar, verificar código Frontend UI/UX. Proyectos: sitio web, landing page, dashboard, panel de administración, e-commerce, SaaS, portafolio, blog, aplicación móvil, .html, .tsx, .vue, .svelte. Elementos: botón, modal, navbar, sidebar, tarjeta, tabla, formulario, gráfico. Estilos: glassmorphism, claymorphism, minimalismo, brutalismo, neumorphism, cuadrícula bento, modo oscuro, responsivo, skeuomorphism, diseño plano. Temas: paleta de colores, accesibilidad, animación, diseño, tipografía, combinación de fuentes, espaciado, hover, sombra, degradado."
---

# UI/UX Pro Max - Inteligencia de Diseño

Base de datos de búsqueda de estilos de interfaz de usuario, paletas de colores, combinaciones de fuentes, tipos de gráficos, recomendaciones de productos, pautas de UX y mejores prácticas específicas de la tecnología (stack).

## Prerrequisitos

Verifique si Python está instalado:

```bash
python3 --version || python --version
```

Si Python no está instalado, instálelo según el sistema operativo del usuario:

**macOS:**
```bash
brew install python3
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3
```

**Windows:**
```powershell
winget install Python.Python.3.12
```

---

## Cómo usar esta habilidad

Cuando el usuario solicite trabajo de UI/UX (diseñar, construir, crear, implementar, revisar, corregir, mejorar), siga este flujo de trabajo:

### Paso 1: Analizar los requisitos del usuario

Extraiga información clave de la solicitud del usuario:
- **Tipo de producto**: SaaS, e-commerce, portafolio, dashboard, landing page, etc.
- **Palabras clave de estilo**: minimalista, lúdico, profesional, elegante, modo oscuro, etc.
- **Industria**: salud, fintech, juegos, educación, etc.
- **Tecnología (Stack)**: React, Vue, Next.js, o por defecto `html-tailwind`

### Paso 2: Buscar dominios relevantes

Use `search.py` varias veces para recopilar información completa. Busque hasta que tenga suficiente contexto.

```bash
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "<palabra_clave>" --domain <dominio> [-n <max_resultados>]
```

**Orden de búsqueda recomendado:**

1. **Product** (Producto) - Obtener recomendaciones de estilo para el tipo de producto.
2. **Style** (Estilo) - Obtener una guía de estilo detallada (colores, efectos, frameworks).
3. **Typography** (Tipografía) - Obtener combinaciones de fuentes con importaciones de Google Fonts.
4. **Color** - Obtener paleta de colores (Primario, Secundario, CTA, Fondo, Texto, Borde).
5. **Landing** - Obtener estructura de página (si es una landing page).
6. **Chart** (Gráfico) - Obtener recomendaciones de gráficos (si es un dashboard/analítica).
7. **UX** - Obtener mejores prácticas y anti-patrones.
8. **Stack** - Obtener pautas específicas de la tecnología (predeterminado: html-tailwind).

### Paso 3: Pautas de tecnología (Predeterminado: html-tailwind)

Si el usuario no especifica una tecnología, **use por defecto `html-tailwind`**.

```bash
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "<palabra_clave>" --stack html-tailwind
```

Tecnologías disponibles: `html-tailwind`, `react`, `nextjs`, `vue`, `svelte`, `swiftui`, `react-native`, `flutter`

---

## Referencia de Búsqueda

### Dominios Disponibles

| Dominio | Uso para | Palabras clave de ejemplo |
|---------|---------|------------------|
| `product` | Recomendaciones por tipo de producto | SaaS, e-commerce, portafolio, salud, belleza, servicio |
| `style` | Estilos de UI, colores, efectos | glassmorphism, minimalismo, modo oscuro, brutalismo |
| `typography` | Combinaciones de fuentes, Google Fonts | elegante, lúdico, profesional, moderno |
| `color` | Paletas de colores por tipo de producto | saas, ecommerce, salud, belleza, fintech, servicio |
| `landing` | Estructura de página, estrategias de CTA | hero, hero-centric, testimonio, precios, prueba social |
| `chart` | Tipos de gráficos, recomendaciones de librerías | tendencia, comparación, cronología, embudo, pastel |
| `ux` | Mejores prácticas, anti-patrones | animación, accesibilidad, z-index, carga |
| `prompt` | Prompts de IA, palabras clave de CSS | (nombre del estilo) |

### Tecnologías (Stacks) Disponibles

| Stack | Enfoque |
|-------|-------|
| `html-tailwind` | Utilidades Tailwind, responsivo, a11y (PREDETERMINADO) |
| `react` | Estado, hooks, rendimiento, patrones |
| `nextjs` | SSR, enrutamiento, imágenes, rutas de API |
| `vue` | Composition API, Pinia, Vue Router |
| `svelte` | Runes, stores, SvelteKit |
| `swiftui` | Vistas, Estado, Navegación, Animación |
| `react-native` | Componentes, Navegación, Listas |
| `flutter` | Widgets, Estado, Diseño, Tematización |

---

## Ejemplo de flujo de trabajo

**Solicitud del usuario:** "Crear una landing page para un servicio de cuidado de la piel profesional"

**El Agente debería:**

```bash
# 1. Buscar tipo de producto
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "beauty spa wellness service" --domain product

# 2. Buscar estilo (basado en la industria: belleza, elegante)
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "elegant minimal soft" --domain style

# 3. Buscar tipografía
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "elegant luxury" --domain typography

# 4. Buscar paleta de colores
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "beauty spa wellness" --domain color

# 5. Buscar estructura de landing page
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "hero-centric social-proof" --domain landing

# 6. Buscar pautas de UX
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "animation" --domain ux
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "accessibility" --domain ux

# 7. Buscar pautas de tecnología (predeterminado: html-tailwind)
python3 .agent/skills/ui-ux-pro-max/scripts/search.py "layout responsive" --stack html-tailwind
```

**Luego:** Sintetizar todos los resultados de búsqueda e implementar el diseño.

---

## Consejos para mejores resultados

1. **Sea específico con las palabras clave**: "healthcare SaaS dashboard" > "app"
2. **Busque varias veces**: Diferentes palabras clave revelan diferentes ideas.
3. **Combine dominios**: Estilo + Tipografía + Color = Sistema de diseño completo.
4. **Siempre verifique el UX**: Busque "animación", "z-index", "accesibilidad" para problemas comunes.
5. **Use el flag de tecnología**: Obtenga mejores prácticas específicas para su implementación.
6. **Itere**: Si la primera búsqueda no coincide, intente con diferentes palabras clave.

---

## Reglas comunes para una UI profesional

Estos son problemas que se pasan por alto con frecuencia y hacen que la interfaz parezca poco profesional:

### Iconos y elementos visuales

| Regla | Hacer | No Hacer |
|------|----|----- |
| **No usar emojis como iconos** | Use iconos SVG (Heroicons, Lucide, Simple Icons) | Use emojis como 🎨 🚀 ⚙️ como iconos de UI |
| **Estados de hover estables** | Use transiciones de color/opacidad al pasar el cursor | Use transformaciones de escala que desplacen el diseño |
| **Logotipos de marca correctos** | Investigue el SVG oficial en Simple Icons | Adivine o use rutas de logotipos incorrectas |
| **Tamaño de icono consistente** | Use viewBox fijo (24x24) con w-6 h-6 | Mezcle diferentes tamaños de iconos al azar |

### Interacción y cursor

| Regla | Hacer | No Hacer |
|------|----|----- |
| **Cursor pointer** | Agregue `cursor-pointer` a todas las tarjetas interactuables | Deje el cursor predeterminado en elementos interactivos |
| **Feedback de hover** | Proporcione feedback visual (color, sombra, borde) | Que no haya indicación de que el elemento es interactivo |
| **Transiciones suaves** | Use `transition-colors duration-200` | Cambios de estado instantáneos o demasiado lentos (>500ms) |

### Contraste en modo claro/oscuro

| Regla | Hacer | No Hacer |
|------|----|----- |
| **Tarjeta "glass" modo claro** | Use `bg-white/80` o una opacidad mayor | Use `bg-white/10` (demasiado transparente) |
| **Contraste de texto claro** | Use `#0F172A` (slate-900) para el texto | Use `#94A3B8` (slate-400) para el texto principal |
| **Texto tenue claro** | Use mínimo `#475569` (slate-600) | Use gray-400 o más claro |
| **Visibilidad de bordes** | Use `border-gray-200` en modo claro | Use `border-white/10` (invisible) |

### Diseño y espaciado

| Regla | Hacer | No Hacer |
|------|----|----- |
| **Navbar flotante** | Agregue espaciado `top-4 left-4 right-4` | Pegue la navbar a `top-0 left-0 right-0` |
| **Padding de contenido** | Tenga en cuenta la altura de la navbar fija | Deje que el contenido se oculte tras elementos fijos |
| **Ancho máximo consistente** | Use el mismo `max-w-6xl` o `max-w-7xl` | Mezcle diferentes anchos de contenedor |

---

## Lista de verificación previa a la entrega

Antes de entregar código de UI, verifique estos puntos:

### Calidad Visual
- [ ] No se usan emojis como iconos (use SVG en su lugar).
- [ ] Todos los iconos pertenecen a un conjunto consistente (Heroicons/Lucide).
- [ ] Los logotipos de marca son correctos (verificados en Simple Icons).
- [ ] Los estados de hover no causan saltos en el diseño.

### Interacción
- [ ] Todos los elementos interactuables tienen `cursor-pointer`.
- [ ] Los estados de hover proporcionan un feedback visual claro.
- [ ] Las transiciones son suaves (150-300ms).
- [ ] Los estados de enfoque (focus) son visibles para la navegación con teclado.

### Modo Claro/Oscuro
- [ ] El texto en modo claro tiene suficiente contraste (mínimo 4.5:1).
- [ ] Los elementos glass/transparentes son visibles en modo claro.
- [ ] Los bordes son visibles en ambos modos.
- [ ] Pruebe ambos modos antes de la entrega.

### Diseño (Layout)
- [ ] Los elementos flotantes tienen un espaciado adecuado desde los bordes.
- [ ] No hay contenido oculto detrás de navbars fijas.
- [ ] Responsivo en 320px, 768px, 1024px, 1440px.
- [ ] Sin desplazamiento horizontal en móviles.

### Accesibilidad
- [ ] Todas las imágenes tienen texto alternativo (alt).
- [ ] Los campos de formulario tienen etiquetas (labels).
- [ ] El color no es el único indicador de información.
- [ ] Se respeta `prefers-reduced-motion`.

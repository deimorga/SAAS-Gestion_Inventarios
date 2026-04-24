---
name: changelog-generator
description: Crea automáticamente registros de cambios (changelogs) orientados al usuario a partir de commits de git, analizando el historial, categorizando los cambios y transformando commits técnicos en notas de lanzamiento claras y amigables para el cliente. Convierte horas de escritura manual de changelogs en minutos de generación automatizada.
---

# Generador de Changelogs

Esta habilidad transforma los commits técnicos de git en registros de cambios pulidos y fáciles de entender que tus clientes y usuarios realmente comprenderán y apreciarán.

## Cuándo usar esta habilidad

- Al preparar notas de lanzamiento para una nueva versión.
- Al crear resúmenes semanales o mensuales de actualizaciones del producto.
- Al documentar cambios para los clientes.
- Al escribir entradas de changelog para envíos a tiendas de aplicaciones.
- Al generar notificaciones de actualización.
- Al crear documentación interna de lanzamientos.
- Al mantener una página pública de changelog o actualizaciones del producto.

## Qué hace esta habilidad

1. **Escanea el historial de Git**: Analiza los commits de un período de tiempo específico o entre versiones.
2. **Categoriza los cambios**: Agrupa los commits en categorías lógicas (características, mejoras, correcciones de errores, cambios disruptivos, seguridad).
3. **Traduce Técnico → Amigable para el usuario**: Convierte los commits de los desarrolladores al lenguaje del cliente.
4. **Formatea profesionalmente**: Crea entradas de changelog limpias y estructuradas.
5. **Filtra el ruido**: Excluye commits internos (refactorización, pruebas, etc.).
6. **Sigue las mejores prácticas**: Aplica pautas de changelog y la voz de tu marca.

## Cómo usarla

### Uso básico

Desde el repositorio de tu proyecto:

```
Crea un changelog a partir de los commits desde el último lanzamiento
```

```
Genera un changelog para todos los commits de la última semana
```

```
Crea notas de lanzamiento para la versión 2.5.0
```

### Con rango de fechas específico

```
Crea un changelog para todos los commits entre el 1 y el 15 de marzo
```

### Con pautas personalizadas

```
Crea un changelog para los commits desde v2.4.0, usando mis pautas 
de changelog de CHANGELOG_STYLE.md
```

## Ejemplo

**Usuario**: "Crea un changelog para los commits de los últimos 7 días"

**Salida**:
```markdown
# Actualizaciones - Semana del 10 de marzo de 2024

## ✨ Nuevas Características

- **Espacios de trabajo en equipo**: Cread espacios de trabajo separados para diferentes 
  proyectos. Invitad a miembros del equipo y mantened todo organizado.

- **Atajos de teclado**: Presiona ? para ver todos los atajos disponibles. 
  Navega más rápido sin tocar el ratón.

## 🔧 Mejoras

- **Sincronización más rápida**: Los archivos ahora se sincronizan el doble de rápido entre dispositivos.
- **Mejor búsqueda**: La búsqueda ahora incluye el contenido de los archivos, no solo los títulos.

## 🐛 Correcciones

- Se corrigió el error por el cual las imágenes grandes no se subían.
- Se resolvió la confusión de zona horaria en las publicaciones programadas.
- Se corrigió el conteo de la insignia de notificación.
```

**Inspirado por:** Caso de uso de Manik Aggarwal de Lenny's Newsletter.

## Consejos

- Ejecútalo desde la raíz del repositorio de git.
- Especifica rangos de fechas para changelogs enfocados.
- Usa tu archivo CHANGELOG_STYLE.md para un formato consistente.
- Revisa y ajusta el changelog generado antes de publicarlo.
- Guarda la salida directamente en CHANGELOG.md.

## Casos de uso relacionados

- Crear notas de lanzamiento en GitHub.
- Escribir descripciones de actualización para tiendas de aplicaciones.
- Generar correos de actualización para usuarios.
- Crear publicaciones de anuncios en redes sociales.

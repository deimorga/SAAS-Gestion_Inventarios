---
name: error-handling-patterns
description: Domina los patrones de manejo de errores en múltiples lenguajes, incluyendo excepciones, tipos Result, propagación de errores y degradación elegante para construir aplicaciones resilientes. Úsalo al implementar el manejo de errores, diseñar APIs o mejorar la confiabilidad de la aplicación.
---

# Patrones de Manejo de Errores

Construye aplicaciones resilientes con estrategias robustas de manejo de errores que gestionen fallas con elegancia y proporcionen excelentes experiencias de depuración.

## Cuándo usar esta habilidad

- Al implementar el manejo de errores en nuevas funcionalidades.
- Al diseñar APIs resilientes a errores.
- Al depurar problemas en producción.
- Al mejorar la confiabilidad de la aplicación.
- Al crear mejores mensajes de error para usuarios y desarrolladores.
- Al implementar patrones de reintento (retry) y disyuntor (circuit breaker).
- Al manejar errores asíncronos o concurrentes.
- Al construir sistemas distribuidos tolerantes a fallos.

## Conceptos Core

### 1. Filosofías de Manejo de Errores

**Excepciones vs Tipos Result:**

- **Excepciones**: try-catch tradicional, interrumpe el flujo de control.
- **Tipos Result**: éxito/falla explícitos, enfoque funcional.
- **Códigos de Error**: estilo C, requiere disciplina.
- **Tipos Option/Maybe**: para valores que pueden ser nulos.

**Cuándo usar cada uno:**

- Excepciones: errores inesperados, condiciones excepcionales.
- Tipos Result: errores esperados, fallas de validación.
- Panics/Crashes: errores irrecuperables, errores de programación.

### 2. Categorías de Errores

**Errores Recuperables:**

- Timeouts de red.
- Archivos faltantes.
- Entrada de usuario inválida.
- Límites de tasa de API (rate limits).

**Errores Irrecuperables:**

- Memoria agotada (Out of memory).
- Desbordamiento de pila (Stack overflow).
- Errores de programación (punteros nulos, etc.).

## Patrones por Lenguaje

### Manejo de Errores en Python

**Jerarquía de Excepciones Personalizadas:**

```python
class ErrorDeAplicacion(Exception):
    """Excepción base para todos los errores de la aplicación."""
    def __init__(self, mensaje: str, codigo: str = None, detalles: dict = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.detalles = detalles or {}
        self.timestamp = datetime.utcnow()

class ErrorDeValidacion(ErrorDeAplicacion):
    """Lanzada cuando la validación falla."""
    pass

class ErrorNoEncontrado(ErrorDeAplicacion):
    """Lanzada cuando no se encuentra el recurso."""
    pass

class ErrorDeServicioExterno(ErrorDeAplicacion):
    """Lanzada cuando un servicio externo falla."""
    def __init__(self, mensaje: str, servicio: str, **kwargs):
        super().__init__(mensaje, **kwargs)
        self.servicio = servicio
```

### Manejo de Errores en TypeScript/JavaScript

**Clases de Error Personalizadas:**

```typescript
class ApplicationError extends Error {
  constructor(
    public message: string,
    public code: string,
    public statusCode: number = 500,
    public details?: Record<string, any>,
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }
}

class ValidationError extends ApplicationError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, "VALIDATION_ERROR", 400, details);
  }
}
```

## Patrones Universales

### Patrón 1: Disyuntor (Circuit Breaker)

Previene fallas en cascada en sistemas distribuidos.

### Patrón 2: Agregación de Errores

Recolecta múltiples errores en lugar de fallar en el primero (común en validaciones de formularios).

### Patrón 3: Degradación Elegante (Graceful Degradation)

Proporciona funcionalidad de respaldo (fallback) cuando ocurren errores.

## Buenas Prácticas

1. **Fallo Rápido (Fail Fast)**: Valida las entradas temprano.
2. **Preserva el Contexto**: Incluye stack traces, metadatos y timestamps.
3. **Mensajes Significativos**: Explica qué pasó y cómo arreglarlo.
4. **Loguea Apropiadamente**: Error = log, falla esperada = no satures los logs.
5. **No Te Tragues los Errores**: Loguea o vuelve a lanzar, no los ignores silenciosamente.
6. **Limpia Recursos**: Usa try-finally o manejadores de contexto.

---
name: experto_typescript
description: Especialista en TypeScript avanzado enfocado en React, Firebase y Clean Architecture.
---

# Experto TypeScript (TypeScript Expert)

## Descripción
Esta habilidad proporciona conocimiento especializado sobre TypeScript moderno (5.x+). Se enfoca en el tipado estricto, seguridad de datos (especialmente con Firebase) y patrones de diseño escalables para el CRM Comercial Micronuba.

## Instrucciones

### 1. Tipado de Datos y Entidades
- Siempre utiliza `interfaces` o `types` para definir los esquemas de datos que vienen de Firestore.
- No uses `any`. Si un tipo es desconocido, usa `unknown` y realiza un type guard.
- Sincroniza los tipos de `src/types/` con `firebase-blueprint.json`.

### 2. React + TypeScript
- Usa `Functional Components` con inferencia de tipos siempre que sea posible.
- Define tipos explícitos para los `props` de cada componente.
- Tipado correcto de Hooks:
    - `useState<Type>(initialValue)`
    - `useRef<HTMLDivElement>(null)`

### 3. Firebase & Async
- Tipa las respuestas de los servicios de Firebase para evitar errores de "undefined" en tiempo de ejecución.
- Usa `try/catch` con bloques de manejo de errores tipados.

### 4. Patrones de Proyecto
- **Zod (Recomendado):** Aunque no esté actualmente en el proyecto, se recomienda para validación de formularios y esquemas de API.
- **Utility Types:** Familiaridad con `Partial<T>`, `Omit<T, K>`, `Pick<T, K>` para manipulación de entidades.

## Reglas
- **Strict Mode:** Seguir las reglas de `tsconfig.json` (strict: true).
- **Inferencia vs Explicit:** Deja que TS infiera tipos simples, pero sé explícito en retornos de funciones complejas y props de componentes.
- **Documentación Viva (OBLIGATORIO):** Revisa `doc/` antes de actuar. Actualiza los tipos si cambian en el esquema.

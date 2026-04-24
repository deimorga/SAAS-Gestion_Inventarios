---
name: qa-expert
description: Esta habilidad debe usarse al establecer procesos integrales de pruebas QA para cualquier proyecto de software. Úsela para crear estrategias de prueba, escribir casos de prueba siguiendo los Estándares de Google, ejecutar planes de prueba, rastrear errores con clasificación P0-P4, calcular métricas de calidad o generar informes de progreso. Incluye capacidad de ejecución autónoma mediante prompts maestros y plantillas de documentación completas para transferencias a equipos de QA externos. Implementa pruebas de seguridad OWASP y logra objetivos de cobertura del 90%.
keywords: [qa, pruebas, casos-de-prueba, seguimiento-errores, estandares-google, owasp, seguridad, automatizacion, puertas-de-calidad, metricas]
---

# Experto QA

Establezca procesos de prueba QA de clase mundial para cualquier proyecto de software utilizando metodologías probadas de los Estándares de Pruebas de Google y las mejores prácticas de seguridad OWASP.

## Cuándo Usar Esta Habilidad

Active esta habilidad cuando:
- Configure la infraestructura de QA para un proyecto nuevo o existente
- Escriba casos de prueba estandarizados (cumplimiento del patrón AAA)
- Ejecute planes de prueba integrales con seguimiento de progreso
- Implemente pruebas de seguridad (Top 10 OWASP)
- Reporte errores con clasificación de severidad adecuada (P0-P4)
- Genere informes de QA (resúmenes diarios, progreso semanal)
- Calcule métricas de calidad (tasa de aprobación, cobertura, puertas de calidad)
- Prepare documentación de QA para transferencias a equipos externos
- Habilite la ejecución de pruebas autónoma impulsada por LLM

## Inicio Rápido

**Inicialización con un solo comando**:
```bash
python .agent/skills/qa-expert/scripts/init_qa_project.py <nombre-proyecto> [directorio-salida]
```

**Lo que se crea**:
- Estructura de directorios (`tests/docs/`, `tests/e2e/`, `tests/fixtures/`)
- CSVs de seguimiento (`TEST-EXECUTION-TRACKING.csv`, `BUG-TRACKING-TEMPLATE.csv`)
- Plantillas de documentación (`BASELINE-METRICS.md`, `WEEKLY-PROGRESS-REPORT.md`)
- Prompt Maestro de QA para ejecución autónoma
- README con guía completa de inicio rápido

**Para ejecución autónoma** (recomendado): Ver `.agent/skills/qa-expert/references/master_qa_prompt.md` - comando único de copiar y pegar para una velocidad 100x.

## Capacidades Principales

### 1. Inicialización de Proyecto QA

Inicialice la infraestructura completa de QA con todas las plantillas:

```bash
python .agent/skills/qa-expert/scripts/init_qa_project.py <nombre-proyecto> [directorio-salida]
```

Crea estructura de directorios, CSVs de seguimiento, plantillas de documentación y prompt maestro para ejecución autónoma.

**Cuándo usar**: Al comenzar QA desde cero o migrar a un proceso de QA estructurado.

### 2. Escritura de Casos de Prueba

Escriba casos de prueba estandarizados y reproducibles siguiendo el patrón AAA (Arrange-Act-Assert):

1. Lea la plantilla: `.agent/skills/qa-expert/assets/templates/TEST-CASE-TEMPLATE.md`
2. Siga la estructura: Prerrequisitos (Arrange) → Pasos de Prueba (Act) → Resultados Esperados (Assert)
3. Asigne prioridad: P0 (bloqueante) → P4 (bajo)
4. Incluya casos borde y errores potenciales

**Formato de caso de prueba**: TC-[CATEGORIA]-[NUMERO] (ej: TC-CLI-001, TC-WEB-042, TC-SEC-007)

**Referencia**: Ver `.agent/skills/qa-expert/references/google_testing_standards.md` para guías completas del patrón AAA y umbrales de cobertura.

### 3. Ejecución y Seguimiento de Pruebas

**Principio de Verdad Absoluta** (crítico):
- **Documentos de casos de prueba** (ej: `02-CLI-TEST-CASES.md`) = **fuente autorizada** para pasos de prueba
- **CSV de Seguimiento** = solo estado de ejecución (NO confíe en el CSV para especificaciones de prueba)
- Ver `.agent/skills/qa-expert/references/ground_truth_principle.md` para prevenir problemas de sincronización doc/CSV

**Ejecución manual**:
1. Lea el caso de prueba del documento de categoría (ej: `02-CLI-TEST-CASES.md`) ← **siempre comience aquí**
2. Ejecute los pasos de prueba exactamente como están documentados
3. Actualice `TEST-EXECUTION-TRACKING.csv` **inmediatamente** después de CADA prueba (nunca en lote)
4. Reporte error en `BUG-TRACKING-TEMPLATE.csv` si la prueba falla

**Ejecución autónoma** (recomendado):
1. Copie el prompt maestro de `.agent/skills/qa-expert/references/master_qa_prompt.md`
2. Pegue en la sesión del LLM
3. El LLM auto-ejecuta, auto-rastrea, auto-reporta errores, auto-genera informes

**Innovación**: 100x más rápido vs manual + cero error humano en seguimiento + capacidad de auto-resumen.

### 4. Reporte de Errores

Reporte errores con clasificación de severidad adecuada:

**Campos requeridos**:
- ID de Error: Secuencial (BUG-001, BUG-002, ...)
- Severidad: P0 (fix 24h) → P4 (opcional)
- Pasos para Reproducir: Numerados, específicos
- Entorno: SO, versiones, configuración

**Clasificación de severidad**:
- **P0 (Bloqueante)**: Vulnerabilidad de seguridad, funcionalidad central rota, pérdida de datos
- **P1 (Crítico)**: Característica mayor rota con solución alternativa
- **P2 (Alto)**: Problema menor de característica, caso borde
- **P3 (Medio)**: Problema cosmético
- **P4 (Bajo)**: Error tipográfico en documentación

**Referencia**: Ver `BUG-TRACKING-TEMPLATE.csv` para plantilla completa con ejemplos.

### 5. Cálculo de Métricas de Calidad

Calcule métricas integrales de QA y estado de puertas de calidad:

```bash
python .agent/skills/qa-expert/scripts/calculate_metrics.py <ruta/a/TEST-EXECUTION-TRACKING.csv>
```

**Panel de métricas incluye**:
- Progreso de ejecución de pruebas (X/Y pruebas, Z% completado)
- Tasa de aprobación (pasadas/ejecutadas %)
- Análisis de errores (errores únicos, desglose P0/P1/P2)
- Estado de puertas de calidad (✅/❌ para cada puerta)

**Puertas de calidad** (todas deben pasar para lanzamiento):
| Puerta | Objetivo | Bloqueante |
|--------|----------|------------|
| Ejecución de Pruebas | 100% | Sí |
| Tasa de Aprobación | ≥80% | Sí |
| Errores P0 | 0 | Sí |
| Errores P1 | ≤5 | Sí |
| Cobertura de Código | ≥80% | Sí |
| Seguridad | 90% OWASP | Sí |

### 6. Informes de Progreso

Genere informes de QA para interesados:

**Resumen diario** (fin del día):
- Pruebas ejecutadas, tasa de aprobación, errores reportados
- Bloqueantes (o Ninguno)
- Plan para mañana

**Informe semanal** (cada viernes):
- Use plantilla: `WEEKLY-PROGRESS-REPORT.md` (creada por script init)
- Compare contra línea base: `BASELINE-METRICS.md`
- Evalúe puertas de calidad y tendencias

**Referencia**: Ver `.agent/skills/qa-expert/references/llm_prompts_library.md` para 30+ prompts listos para usar en reportes.

### 7. Pruebas de Seguridad (OWASP)

Implemente pruebas de seguridad Top 10 OWASP:

**Objetivos de cobertura**:
1. **A01: Control de Acceso Roto** - Bypass RLS, escalada de privilegios
2. **A02: Fallas Criptográficas** - Encriptación de tokens, hash de contraseñas
3. **A03: Inyección** - Inyección SQL, XSS, inyección de comandos
4. **A04: Diseño Inseguro** - Límite de tasa, detección de anomalías
5. **A05: Configuración de Seguridad Incorrecta** - Errores detallados, credenciales por defecto
6. **A07: Fallas de Autenticación** - Secuestro de sesión, CSRF
7. **Otros**: Integridad de datos, logging, SSRF

**Objetivo**: 90% cobertura OWASP (9/10 amenazas mitigadas).

Cada prueba de seguridad sigue el patrón AAA con vectores de ataque específicos documentados.

## Incorporación Día 1

Para nuevos ingenieros de QA que se unen a un proyecto, complete la guía de incorporación de 5 horas:

**Leer**: `.agent/skills/qa-expert/references/day1_onboarding.md`

**Línea de tiempo**:
- Hora 1: Configuración de entorno (base de datos, servidor dev, dependencias)
- Hora 2: Revisión de documentación (estrategia de prueba, puertas de calidad)
- Hora 3: Configuración de datos de prueba (usuarios, CLI, DevTools)
- Hora 4: Ejecutar primer caso de prueba
- Hora 5: Incorporación al equipo y planificación Semana 1

**Punto de control**: Al final del Día 1, entorno funcionando, primera prueba ejecutada, listo para Semana 1.

## Ejecución Autónoma (⭐ Recomendado)

Habilite pruebas QA autónomas impulsadas por LLM con un solo prompt maestro:

**Leer**: `.agent/skills/qa-expert/references/master_qa_prompt.md`

**Características**:
- Auto-resumen desde última prueba completada (lee CSV de seguimiento)
- Auto-ejecutar casos de prueba (progresión Semana 1-5)
- Auto-rastrear resultados (actualiza CSV después de cada prueba)
- Auto-reportar errores (crea reportes de error para fallos)
- Auto-generar informes (resúmenes diarios, informes semanales)
- Auto-escalar errores P0 (detiene pruebas, notifica a interesados)

**Beneficios**:
- 100x más rápido ejecución vs manual
- Cero error humano en seguimiento
- Documentación de errores consistente
- Visibilidad de progreso inmediata

**Uso**: Copie el prompt maestro, pegue en LLM, deje correr autónomamente por 5 semanas.

## Documentos de Referencia

Acceda a directrices detalladas de referencias empaquetadas:

- **`.agent/skills/qa-expert/references/day1_onboarding.md`** - Guía de incorporación
  **`.agent/skills/qa-expert/references/master_qa_prompt.md`** - Comando único para ejecución autónoma LLM
- **`.agent/skills/qa-expert/references/google_testing_standards.md`** - Patrón AAA, umbrales de cobertura
- **`.agent/skills/qa-expert/references/ground_truth_principle.md`** - Prevención de desincronización

## Scripts

Scripts de automatización para infraestructura QA:

- **`.agent/skills/qa-expert/scripts/init_qa_project.py`** - Inicializar infraestructura QA

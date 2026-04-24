# Manual de Operación: SaaS Gestión de Inventarios (MicroNuba Inventory)

Este documento define la metodología de trabajo entre el Humano y la IA para garantizar el éxito, la seguridad y la coherencia del proyecto.

## 1. Protocolo de Inicio de Sesión (`/restore_context`)
Al iniciar cada sesión, el agente debe "activar" su mentalidad operativa mediante la lectura obligatoria de:
1.  **Gobernanza:** `.agent/RULES.md` y `.agent/rules/reglas.md`.
2.  **Arquitectura:** `doc/Arquitectura/Arquitectura definida/ARQUITECTURA_FISICA.md`.
3.  **Orquestación:** `.agent/skills/orquestador_proyecto/SKILL.md` (Activación mental del cerebro operativo).
4.  **Memoria:** `.gemini/contexto_gemini_web.md`.
5.  **Idea Original:** `doc/Documentacion de Idea/` (Google Docs de referencia).

## 2. Flujo de Trabajo Mandatorio (Brain-First)
Ningún desarrollo (código) debe iniciarse sin pasar por el **Orquestador de Proyecto**:
1.  **Definición:** El Orquestador desglosa el requerimiento en `doc/Planeacion/`.
2.  **Diseño Técnico:** Se documenta la solución técnica en `doc/Tecnico/` antes de tocar el código.
3.  **Ejecución:** Se activan las **Skills Especialistas** (Angular, FastAPI, DB) según sea necesario.
4.  **Verificación:** Validación visual obligatoria con `browser_subagent` antes de cerrar cualquier tarea de UI.
5.  **Calidad:** La skill `verificador_calidad` debe emitir veredicto `APROBADO` antes de cerrar cualquier tarea.

## 3. Seguimiento y Tareas (`task.md`)
El archivo `.gemini/task.md` es el SSoT del progreso del Sprint actual. 
- Cada tarea debe tener un estado claro (`[ ]`, `[/]`, `[x]`).
- Los impedimentos técnicos o riesgos identificados deben reportarse de inmediato.
- El veredicto del `verificador_calidad` queda registrado como comentario HTML en cada tarea.

## 4. Auditoría de Capas y Capacidad Crítica
El agente actuará con pensamiento crítico, validando siempre:
- **Aislamiento Multi-Tenant:** ¿Esta consulta tiene Row Level Security (RLS)?
- **Atomicidad Transaccional:** ¿Este movimiento de inventario es ACID? ¿Puede dejar estados intermedios?
- **Integridad del CPP:** ¿El Costo Promedio Ponderado se recalcula correctamente ante cada entrada?
- **Alineación de Estructura:** ¿Esta carpeta nueva respeta `doc/Estructura/estructura_proyecto.md`?
- **Hot-Reloading:** Verificación de que los servicios en Docker se reiniciaron tras cambiar configuraciones.

## 5. Dominio de Negocio: Inventarios
El sistema gestiona inventarios multi-sede con las siguientes capacidades core:
- **Motor Transaccional Atómico:** Entradas, salidas y transferencias ACID.
- **Costo Promedio Ponderado (CPP):** Recálculo automático del costo unitario.
- **Kardex Histórico:** Registro inmutable de movimientos.
- **Multi-Sede:** Jerarquía de almacenes, bodegas y tiendas.
- **Alertas:** Reorder Point y webhooks de stock crítico.
- **Reservas:** Soft Reservation para e-commerce.

## 6. Cierre de Sesión y Persistencia
Al finalizar, el agente actualizará el **Contexto de Sesión** (`.gemini/contexto_gemini_web.md`) para que la siguiente IA sepa exactamente en qué fase del flujo de 11 pasos del orquestador se encuentra el proyecto.

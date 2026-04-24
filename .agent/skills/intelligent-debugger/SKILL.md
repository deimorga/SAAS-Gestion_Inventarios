---
name: intelligent-debugger
description: Agente de depuración sistemática integral para cazar errores complejos, causas raíz y propagación de errores en todo el stack (frontend, backend, APIs, bases de datos). Úselo al diagnosticar errores, solucionar problemas, analizar trazas de pila (stack traces), investigar bugs, examinar logs, depurar problemas de rendimiento o rastrear causas de errores. También úselo cuando los usuarios mencionen depuración, errores, bugs, fallas, bloqueos, excepciones o comportamientos inesperados.
license: MIT
---

# Depurador Inteligente (Intelligent Debugger)

## Descripción General

El Depurador Inteligente es un agente de depuración sistemático y metódico que asiste en el diagnóstico y resolución de problemas de software complejos en todo el stack tecnológico. Esta habilidad emplea metodologías de depuración probadas, técnicas de análisis forense y enfoques de investigación sistemáticos para identificar causas raíz y proporcionar soluciones accionables.

## Filosofía Principal de Depuración

**Investigación Sistemática sobre Arreglos Aleatorios**
- Nunca adivine ni haga cambios al azar.
- Siga el método científico: observar, hipotetizar, probar, concluir.
- Documente cada hallazgo y decisión.
- El objetivo final siempre es el análisis de la causa raíz.

**Conciencia de Todo el Stack (Cross-Stack)**
- Rastree la propagación de errores desde el frontend hasta el backend y la base de datos.
- Entienda cómo las fallas se cascada a través de los límites del sistema.
- Identifique la fuente original, no solo los síntomas.

**Resolución de Problemas Colaborativa**
- Haga preguntas aclaratorias antes de profundizar.
- Explique los hallazgos en términos claros y accionables.
- Proporcione oportunidades de aprendizaje durante la depuración.

---

## Proceso Sistemático de Depuración de 7 Pasos

### Paso 1: Reproducir el Problema

**Objetivo:** Establecer una reproducibilidad consistente.

**Acciones:**
1. Recopilar detalles de reproducción del usuario:
   - Pasos exactos para activar el bug.
   - Detalles del entorno (SO, navegador, versiones).
   - Frecuencia (siempre, intermitente, condiciones específicas).
   - ¿Cuándo empezó a ocurrir?
   - ¿Algún cambio reciente en el sistema?

2. Intentar reproducir:
   - Siga los pasos exactos proporcionados.
   - Pruebe variaciones para entender el alcance.
   - Note cualquier factor ambiental.

3. Documentar los criterios de reproducción:
   ```
   REPORTE DE REPRODUCCIÓN DE BUG:
   - Activador (Trigger): [pasos exactos]
   - Entorno: [SO/navegador/versión]
   - Frecuencia: [siempre/intermitente/condicional]
   - Prerrequisitos: [estado/datos requeridos]
   ```

**Si no es reproducible:**
- Recopile más detalles del entorno.
- Busque "Heisenbugs" (errores que desaparecen al ser observados).
- Busque condiciones de carrera (race conditions) o problemas de temporización.

### Paso 2: Recopilar Información

**Objetivo:** Recopilar datos de diagnóstico completos.

**Información Esencial:**
1. **Mensajes de Error y Trazas de Pila (Stack Traces)**
   - Texto completo del error (sin truncar).
   - Traza de pila completa con números de línea.
   - Códigos de error y estados HTTP.
   - Salida de la consola.

2. **Contexto del Sistema**
   - Logs de la aplicación (use scripts de análisis de logs).
   - Logs del servidor.
   - Logs de la base de datos.
   - Consola del navegador (para frontend).
   - Pestaña de Red/Network (para problemas de API).

3. **Detalles del Entorno**
   - Versiones del framework.
   - Dependencias y versiones de paquetes.
   - Archivos de configuración.
   - Variables de entorno (oculte secretos).

4. **Cambios Recientes**
   - Commits recientes (git log).
   - Despliegues recientes.
   - Cambios de configuración.
   - Actualizaciones de dependencias.

**Preguntas para la Recopilación de Información:**
```
1. ¿Qué mensaje(s) de error ve? (texto exacto)
2. ¿Dónde ocurre el error? (archivo/línea/función)
3. ¿Qué intentaba hacer cuando falló?
4. ¿Qué sucedió vs. qué esperaba que sucediera?
5. ¿Esto funciona en algún otro lugar? (diferente entorno/navegador)
6. ¿Qué cambió recientemente? (código/config/despliegue)
7. ¿Puede compartir los logs relevantes?
```

### Paso 3: Entender el Sistema

**Objetivo:** Construir un modelo mental antes de depurar.

**Mapeo del Sistema:**
1. **Rastrear el Flujo de la Petición**
   - Acción del usuario → Frontend → API → Backend → Base de datos.
   - Identifique todos los puntos de contacto.
   - Mapee las transformaciones de datos.

2. **Inventario de Componentes**
   ```
   Frontend: [framework/librerías/versión]
   Backend: [framework/lenguaje/versión]
   Base de Datos: [tipo/versión]
   APIs: [servicios externos]
   Infraestructura: [hosting/contenedores]
   ```

3. **Preguntas Clave**
   - ¿Qué componentes están involucrados?
   - ¿Cómo se comunican?
   - ¿Qué dependencias existen?
   - ¿Dónde se almacenan/cachean los datos?
   - ¿Qué autenticación/autorización se utiliza?

**Crear Diagrama del Sistema:**
```
[Usuario] → [Navegador] → [Balanceador de Carga] → [Servidor API]
                                                   ↓
                                              [Base de Datos]
                                                   ↓
                                              [Capa de Caché]
```

### Paso 4: Formular y Probar Hipótesis

**Objetivo:** Reducir sistemáticamente la causa.

**Formación de Hipótesis:**
1. Basado en síntomas y datos recopilados, liste las causas posibles.
2. Clasifique por probabilidad (la más probable primero).
3. Considere múltiples categorías:
   - Errores de lógica.
   - Problemas de datos.
   - Problemas de configuración.
   - Fallas de integración.
   - Cuellos de botella de rendimiento.
   - Condiciones de carrera.
   - Seguridad/permisos.

**Prueba de Hipótesis:**
```
PARA CADA HIPÓTESIS:
1. Declare la hipótesis claramente: "El bug es causado por [X]"
2. Prediga qué evidencia apoyaría/refutaría la misma.
3. Diseñe una prueba mínima para validar.
4. Ejecute la prueba.
5. Observe los resultados.
6. Actualice la hipótesis basándose en los hallazgos.

EJEMPLO:
Hipótesis: Tiempo de espera de consulta de BD causando error 500.
Prueba: Revisar logs de BD para consultas lentas.
Resultado: Se encontró consulta tomando más de 30 segundos.
Conclusión: Hipótesis confirmada → optimizar consulta.
```

**Técnicas de Aislamiento:**
- **Búsqueda Binaria:** Comente la mitad del código, pruebe, repita.
- **Depuración del Patito de Goma (Rubber Duck Debugging):** Explique el código línea por línea.
- **Reproducción Mínima:** Cree el ejemplo más pequeño que muestre el bug.
- **Agregar Logs:** Inserte declaraciones de depuración estratégicas.
- **Usar Depurador:** Establezca puntos de interrupción (breakpoints), inspeccione variables.

### Paso 5: Implementar la Solución

**Objetivo:** Corregir la causa raíz, no los síntomas.

**Desarrollo de la Solución:**
1. **Entender la Causa Raíz**
   - ¿Por qué ocurrió el bug?
   - ¿Cuál fue la suposición fallida?
   - ¿Cómo pasó las pruebas iniciales?

2. **Diseñar el Arreglo (Fix)**
   - Aborde la causa raíz directamente.
   - Considere casos de borde (edge cases).
   - Asegúrese de que no haya efectos secundarios.
   - Verifique el impacto en el rendimiento.

3. **Lista de Verificación de Implementación**
   ```
   [ ] El arreglo aborda la causa raíz, no el síntoma.
   [ ] El código sigue los estándares del proyecto.
   [ ] No se introdujeron nuevos bugs.
   [ ] Maneja casos de borde.
   [ ] Incluye manejo de errores.
   [ ] Mantiene el rendimiento.
   [ ] Documentado/comentado.
   ```

### Paso 6: Probar y Verificar

**Objetivo:** Confirmar que el arreglo funciona y no rompe nada.

**Pasos de Verificación:**
1. **Reproducir el Bug Original**
   - Confirme que el bug aún ocurre en el código sin arreglar.
   - Documente el comportamiento actual.

2. **Aplicar el Arreglo y Probar**
   - El bug ya no debería ocurrir.
   - La funcionalidad original debe preservarse.
   - Casos de borde manejados.

3. **Pruebas de Regresión**
   - Ejecute la suite de pruebas existente.
   - Pruebe la funcionalidad relacionada.
   - Verifique efectos secundarios.

4. **Validación de Rendimiento**
   - Compare métricas antes/después.
   - Asegúrese de que no haya degradación.

**Matriz de Pruebas:**
```
Escenario         | Antes del Fix | Después del Fix | Estado
------------------|---------------|-----------------|-------
Bug original      | Falla         | Pasa            | ✅
Caso de borde 1   | ?             | Pasa            | ✅
Caso de borde 2   | ?             | Pasa            | ✅
Función relac. A  | Pasa          | Pasa            | ✅
Rendimiento       | Base          | +5%             | ✅
```

### Paso 6: Documentar y Aprender

**Objetivo:** Capturar conocimiento para depuraciones futuras.

**Plantilla de Resumen de Depuración:**
```
POST-MORTEM DE DEPURACIÓN:
Fecha: [FECHA]
Bug: [DESCRIPCIÓN BREVE]
Severidad: [Crítica/Alta/Media/Baja]

SÍNTOMAS:
- [Mensaje de error o comportamiento]
- [Dónde se manifestó]

CAUSA RAÍZ:
[Problema fundamental que causó el bug]

CAMINO DE INVESTIGACIÓN:
1. [Qué intentamos primero]
2. [Qué nos llevó a la respuesta]
3. [Información clave que lo resolvió]

ARREGLO (FIX):
[Descripción de la solución]
Archivo: [RIDER]
Cambios: [RESUMEN]

PREVENCIÓN:
[ ] Caso de prueba agregado.
[ ] Documentación actualizada.
[ ] Monitoreo/alertas agregadas.
[ ] Proceso de revisión de código actualizado.
[ ] Regla de linter agregada.

LECCIONES APRENDIDAS:
- [Qué aprendimos]
- [Cómo prevenir bugs similares]
```

---

## Técnicas de Depuración por Categoría

### Depuración de Frontend

**Herramientas de Desarrollador del Navegador:**
1. **Pestaña de Consola (Console Tab)**
   - Busque errores de JavaScript.
   - Busque advertencias (warnings).
   - Examine la salida de `console.log`.

2. **Pestaña de Red (Network Tab)**
   - Inspeccione llamadas a la API.
   - Verifique encabezados de solicitud/respuesta.
   - Valide datos del payload.
   - Verifique códigos de estado.
   - Busque peticiones fallidas.

3. **Pestaña de Elementos (Elements Tab)**
   - Inspeccione la estructura del DOM.
   - Verifique estilos CSS.
   - Busque problemas de diseño (layout).
   - Valide la visibilidad de los elementos.

4. **Pestaña de Aplicación (Application Tab)**
   - Verifique localStorage/sessionStorage.
   - Inspeccione cookies.
   - Revise service workers.
   - Verifique la caché.

**Problemas Comunes de Frontend:**
```javascript
// Problema: Variable es undefined
// Depuracion: Verificar si el elemento existe antes de acceder
const element = document.getElementById('myId');
if (element) {
  element.textContent = 'Actualizado';
}

// Problema: Problema de temporización asíncrona
// Depuracion: Usar async/await correctamente
async function fetchData() {
  try {
    const response = await fetch('/api/data');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error en fetch:', error);
  }
}

// Problema: El estado no se actualiza
// Depuracion: Verificar inmutabilidad en React
// MAL: state.items.push(newItem)
// BIEN: setState({ items: [...state.items, newItem] })
```

### Depuración de Backend

**Estrategia de Logs (Laravel):**
```php
use Illuminate\Support\Facades\Log;

// Usar niveles de log adecuados
Log::debug('Datos recibidos: ', ['id' => $id]);
Log::info('Procesando solicitud de usuario: ' . $userId);

try {
    $result = $service->execute($data);
    Log::debug('Resultado de la operacion: ', ['result' => $result]);
} catch (\Exception $e) {
    Log::error('La operacion fallo: ' . $e->getMessage(), [
        'exception' => $e,
        'trace' => $e->getTraceAsString()
    ]);
    throw $e;
}
```

**Depuración de API:**
1. Pruebe endpoints con curl o Postman.
2. Verifique encabezados de solicitud.
3. Valide tokens de autenticación.
4. Inspeccione cuerpos de solicitud/respuesta.
5. Verifique códigos de estado HTTP.
6. Revise los logs de la API.

**Problemas Comunes de Backend:**
```
HTTP 400: Bad Request → Validar datos de entrada.
HTTP 401: Unauthorized → Verificar tokens de autenticación.
HTTP 403: Forbidden → Verificar permisos/roles.
HTTP 404: Not Found → Verificar que la ruta/recurso exista.
HTTP 500: Server Error → Revisar logs del servidor (laravel.log).
HTTP 503: Service Unavailable → Revisar dependencias/servicios.
```

### Depuración de Base de Datos

**Análisis de Consultas (PostgreSQL):**
```sql
-- Explicar el rendimiento de la consulta
EXPLAIN ANALYZE
SELECT * FROM users
WHERE created_at > '2025-01-01'
AND tenant_id = 5;

-- Buscar consultas lentas
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

---

## Reconocimiento de Patrones de Error

### Análisis de Trazas de Pila (Stack Traces)

**Lectura de Stack Traces:**
1. **Tipo de Error:** ¿Qué clase de error es? (ej. `KeyError`, `NullReference`).
2. **Ubicación Raíz:** Archivo y línea donde se originó.
3. **Cadena de Llamadas:** Secuencia de funciones que llevaron al error.
4. **Problema:** Qué dato o condición falló en ese punto.

---

## Herramientas y Comandos de Depuración

### Git Bisect (Encontrar el commit que introdujo el bug)
```bash
git bisect start
git bisect bad HEAD
git bisect good v1.2.0
# Probar commits...
git bisect reset
```

---

## Comunicación Durante la Depuración

### Plantilla de Comunicación con el Usuario

**Respuesta Inicial:**
```
Gracias por reportar este problema. Te ayudaré a depurarlo de forma sistemática.

ENTENDIMIENTO ACTUAL:
- Problema: [descripción breve]
- Impacto: [severidad/quién se ve afectado]
- Frecuencia: [qué tan a menudo ocurre]

PARA INVESTIGAR:
Necesito recopilar información:
1. [pregunta específica 1]
2. [pregunta específica 2]

Te mantendré informado conforme avance la investigación.
```
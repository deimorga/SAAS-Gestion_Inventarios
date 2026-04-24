# **ESPECIFICACIÓN TÉCNICA ENTERPRISE: MICRO-INVENTORY ENGINE (MICRONUBA)**

**Versión:** 4.0 (Global Enterprise Architecture)

**Arquitectura:** API-First / Event-Driven / High-Concurrency Multi-tenant

**Estado:** Documento de Diseño Funcional y Técnico Expandido

## **1\. CAPA DE GOBIERNO, SEGURIDAD Y MULTI-TENANCY**

### **RF-001: Aislamiento de Inquilinos (Strict Tenancy Isolation)**

* **Descripción:** El sistema deberá garantizar el aislamiento lógico y físico (opcional) de los datos de cada cliente mediante un identificador único global (tenant\_id).  
* **Lógica de Implementación:** El backend inyectará automáticamente un filtro en la capa de persistencia (Row-Level Security) basado en el claim del token JWT. Ninguna consulta a la base de datos podrá ejecutarse sin un tenant\_id válido.  
* **Consecuencias:** Se previene la fuga de datos (Data Leakage) entre competidores que usen la misma infraestructura.

### **RF-002: Gestión de API Keys y Perfiles de Aplicación**

* **Descripción:** Permitir que los inquilinos creen credenciales de acceso con niveles de permiso granulares (Scopes).  
* **Ejemplo:** Un cliente puede crear una API Key con permiso READ\_ONLY para su aplicación de reportes y otra WRITE\_INVENTORY para su sistema de punto de venta (POS).  
* **Regla:** Cada API Key puede tener una lista blanca de IPs y una fecha de expiración forzada.

### **RF-003: Rate Limiting Dinámico por Tier de Suscripción**

* **Descripción:** Controlar la carga del sistema mediante límites de peticiones (Throttling) basados en el plan comercial del inquilino.  
* **Mecanismo:** Uso de algoritmos de *Token Bucket* distribuidos en Redis para conteo en milisegundos.  
* **Tiers Sugeridos:** \- **Starter:** 60 RPM (Requests Per Minute).  
  * **Professional:** 1,000 RPM.  
  * **Enterprise:** 10,000 RPM con soporte para picos estacionales.

### **RF-004: Auditoría Forense de Logs (Audit Trail)**

* **Descripción:** El sistema deberá registrar cada mutación de datos (Insert, Update, Delete) en un log inmutable.  
* **Detalle de Datos:** Debe capturar el user\_id, timestamp, ip\_address, el payload original y el diff (valor anterior vs. valor nuevo) de los campos afectados.  
* **Implicación:** Esencial para cumplir con normativas contables y auditorías de seguridad externas.

### **RF-005: Motor de Configuración de Políticas de Negocio**

* **Descripción:** Permitir a cada inquilino parametrizar el comportamiento del motor de inventario.  
* **Parámetros:** \- allow\_negative\_stock: Si se permite vender sin existencias físicas.  
  * valuation\_method: Elección entre CPP (Costo Promedio) o PEPS (Primeras Entradas, Primeras Salidas).  
  * auto\_reserve\_on\_order: Si el sistema bloquea stock automáticamente al recibir una orden.

## **2\. MAESTROS AVANZADOS Y ESTRUCTURA DE DATOS**

### **RF-006: Gestión Maestra de SKUs (Global Catalog)**

* **Descripción:** Creación y mantenimiento del catálogo de productos con soporte para metadatos dinámicos.  
* **Atributos Obligatorios:** SKU (único por tenant), EAN/UPC, Nombre, Descripción.  
* **Flexibilidad:** Uso de campos JSONB para almacenar atributos específicos de industria (ej: "talla/color" para retail o "voltaje" para electrónica).

### **RF-007: Taxonomía Jerárquica e Indexación**

* **Descripción:** Clasificación de productos en múltiples niveles de categorías y etiquetas.  
* **Funcionalidad:** El API deberá permitir búsquedas recursivas (ej: buscar en "Electrónica" y que devuelva "Celulares" y "Accesorios").

### **RF-008: Conversión de Unidades de Medida (UOM Engine)**

* **Descripción:** Manejo de múltiples unidades para un mismo SKU con factores de conversión automáticos.  
* **Ejemplo:** El sistema recibe una compra en "Pallets", lo almacena en "Cajas" y lo vende en "Unidades".  
* **Lógica:** ![][image1].

### **RF-009: Orquestación de Bill of Materials (Kits/Combos)**

* **Descripción:** Definición de productos "Padre" que dependen de la existencia de productos "Hijos".  
* **Regla de Oro:** El stock disponible de un KIT es el valor mínimo de la disponibilidad de sus componentes dividida por la cantidad requerida en la receta.

### **RF-010: Configuración de Atributos de Trazabilidad**

* **Descripción:** Definir por cada SKU si requiere control estricto de:  
  1. **Lote (Batch):** Para industrias químicas o alimenticias.  
  2. **Número de Serie:** Para electrónica o activos fijos.  
  3. **Vencimiento:** Para productos perecederos.

### **RF-011: Directorio de Proveedores y Marcas**

* **Descripción:** Vinculación de SKUs con entidades externas.  
* **Funcionalidad:** Permite filtrar inventarios por fabricante o identificar rápidamente a quién comprarle cuando el stock es bajo.

### **RF-012: Motor de Listas de Precios y Costos**

* **Descripción:** Gestión multi-moneda de precios de venta y costos base.  
* **Implicación:** El sistema debe diferenciar entre el "Costo de Reposición" y el "Costo Promedio Contable".

## **3\. GESTIÓN DE INFRAESTRUCTURA LOGÍSTICA**

### **RF-013: Gestión de Almacenes Multisede (Warehouses)**

* **Descripción:** Definir múltiples nodos lógicos y físicos de inventario.  
* **Tipos de Almacén:** \- **Distribución:** Grandes volúmenes.  
  * **Tienda:** Stock de proximidad.  
  * **Tránsito:** Almacén virtual para productos en movimiento.

### **RF-014: Zonificación y Ubicaciones (Bins/Slots)**

* **Descripción:** El sistema deberá permitir mapear el interior de cada almacén.  
* **Jerarquía:** Almacén \-\> Pasillo \-\> Estante \-\> Nivel \-\> Posición (Bin).  
* **Meta:** Optimizar las rutas de recolección (Picking) mediante el API.

### **RF-015: Gestión de Estados de Ubicación y Bloqueos**

* **Descripción:** Capacidad de inhabilitar ubicaciones específicas por mantenimiento, inventario o sospecha de contaminación/daño.

## **4\. MOTOR TRANSACCIONAL Y LEDGER INMUTABLE**

### **RF-016: Registro de Entrada de Mercancía (Purchase Receipt)**

* **Descripción:** El sistema deberá procesar ingresos de stock incrementando el físico y disponible.  
* **Regla:** Al ingresar, el sistema debe solicitar obligatoriamente el costo de compra para recalcular la valoración del inventario.

### **RF-017: Registro de Salida de Mercancía (Sales/Consumption)**

* **Descripción:** Disminución de existencias por venta o consumo interno.  
* **Validación:** Si allow\_negative\_stock es falso, el API debe rechazar la transacción si no hay suficiente disponibilidad.

### **RF-018: Transferencias entre Almacenes (Inter-Warehouse Logic)**

* **Descripción:** Proceso de dos fases para garantizar que el stock no "desaparezca" en el aire.  
* **Fase 1:** Salida del origen (Estado: *In-Transit*).  
* **Fase 2:** Recepción en destino (Estado: *Available*).

### **RF-019: Ajustes de Inventario por Auditoría**

* **Descripción:** Incrementos o decrementos manuales para alinear el sistema con la realidad física.  
* **Control:** Requiere un reason\_code (ej: Sobrante, Faltante, Error de digitación) para el reporte de pérdidas y ganancias.

### **RF-020: Gestión de Devoluciones (RMA)**

* **Descripción:** Reingreso de stock por devoluciones de clientes.  
* **Lógica:** El API debe preguntar el estado del producto (Nuevo, Re-acondicionado, Dañado) para asignar la ubicación correcta.

### **RF-021: Procesos de Re-empaque y Transformación**

* **Descripción:** "Destruir" unidades de un SKU para "Crear" unidades de otro (ej: Desarmar un kit o re-etiquetar productos).

### **RF-022: Gestión de Bajas por Avería (Scrap)**

* **Descripción:** Salida definitiva de inventario por daño físico, obsolescencia o pérdida, sin estar vinculada a una transacción de venta.

### **RF-023: Control de Lotes y Trazabilidad de Vencimiento**

* **Descripción:** El sistema debe impedir la venta de lotes cuya fecha de expiración haya pasado, moviéndolos automáticamente a un estado de "Bloqueado".

### **RF-024: Validación de Unicidad de Seriales**

* **Descripción:** Impedir el reingreso de un número de serie que ya existe actualmente en stock dentro del mismo tenant.

## **5\. GESTIÓN DE LA DEMANDA (RESERVAS)**

### **RF-025: Reservas Temporales (Soft Reservations)**

* **Descripción:** Bloqueo de stock desde el carrito de compras para evitar el *overselling*.  
* **Lógica:** Se resta del stock\_available pero se mantiene en el stock\_physical.

### **RF-026: Confirmación de Reservas (Hard Commitment)**

* **Descripción:** Vinculación definitiva de una reserva con una orden de venta pagada.

### **RF-027: Motor de Liberación Automática (Auto-Expiration)**

* **Descripción:** Un servicio en segundo plano deberá liberar las reservas que superen el tiempo límite (TTL) configurado (ej: liberar tras 30 minutos sin pago).

### **RF-028: Reservas por Prioridad de Canal (Inventory Allocation)**

* **Descripción:** Permitir "apartar" una cantidad de stock específica para un canal (ej: 100 unidades exclusivas para la App Móvil), impidiendo que el POS físico las consuma.

## **6\. INTELIGENCIA, REPORTES Y ANALÍTICA**

### **RF-029: Kárdex Multidimensional de Movimientos**

* **Descripción:** Consulta histórica que permite rastrear cada unidad desde su entrada hasta su salida final.

### **RF-030: Consulta de Saldos en Tiempo Real (Snapshot API)**

* **Descripción:** Endpoint optimizado para devolver existencias totales, reservadas y disponibles en milisegundos.

### **RF-031: Motor de Alertas de Stock Crítico (Reorder Point)**

* **Descripción:** El sistema deberá evaluar constantemente los niveles de stock contra el min\_threshold definido en el SKU.

### **RF-032: Valoración de Existencias (Asset Valuation)**

* **Descripción:** Generar el valor monetario del inventario total por almacén basado en el método contable seleccionado (CPP/PEPS).

## **7\. INTEGRACIÓN Y OPERACIONES MASIVAS**

### **RF-033: Webhooks de Eventos Transaccionales**

* **Descripción:** Notificar a sistemas externos (Shopify, SAP, Slack) cuando ocurra un evento clave (ej: stock.out).  
* **Seguridad:** Uso de firmas HMAC-SHA256 para verificar la integridad del mensaje.

### **RF-034: Importación y Exportación Masiva Asíncrona**

* **Descripción:** Procesamiento de archivos de gran volumen (hasta 100k registros) mediante colas de trabajo.  
* **Flujo:** El cliente sube el archivo, recibe un job\_id y consulta el progreso.

### **RF-035: API de Reconciliación (Inventario Físico)**

* **Descripción:** Soporte para inventarios cíclicos.  
* **Proceso:** 1\. Congelar stock del SKU.  
  2\. Registrar conteo.  
  3\. Aplicar ajuste automático de diferencia.  
  4\. Desbloquear SKU.

## **MATRIZ DE OPERACIONES EXPANDIDA (REST ENDPOINTS)**

| Módulo | Endpoint | Método | Acción Atómica |
| :---- | :---- | :---- | :---- |
| **Auth** | /v1/auth/keys | POST | Genera API Key con Scopes específicos. |
| **Catalog** | /v1/products | POST | Registra SKU con lógica de trazabilidad. |
| **Catalog** | /v1/products/kits | POST | Define relación Padre/Hijo de SKUs. |
| **Whse** | /v1/warehouses | GET | Listado de almacenes y sus capacidades. |
| **Whse** | /v1/locations | POST | Crea posiciones de estantería (Bins). |
| **Inv** | /v1/inventory/entry | POST | Incrementa físico y recalcula CPP. |
| **Inv** | /v1/inventory/exit | POST | Decrementa físico (Venta/Consumo). |
| **Inv** | /v1/inventory/transfer | POST | Orquesta movimiento entre almacenes. |
| **Resv** | /v1/reservations | POST | Bloquea stock temporalmente (TTL). |
| **Resv** | /v1/reservations/confirm | POST | Ejecuta salida física de una reserva. |
| **Audit** | /v1/inventory/balances | GET | Snapshot: Físico, Reservado, Disponible. |
| **Audit** | /v1/inventory/ledger | GET | Historial detallado (Kárdex). |
| **Sync** | /v1/bulk/sync | POST | Sincronización masiva de saldos iniciales. |
| **Alert** | /v1/webhooks | POST | Suscripción a eventos de stock bajo. |

[image1]: <data:image/png;base64,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>
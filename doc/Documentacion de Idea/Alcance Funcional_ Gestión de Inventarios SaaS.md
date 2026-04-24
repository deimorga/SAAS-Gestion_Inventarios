# **DOCUMENTO DE ALCANCE FUNCIONAL: MICRONUBA INVENTORY SAAS CORE**

**Versión:** 1.0

**Estado:** Definición Inicial

**Responsable:** \[MN\] Product Architect

## **1\. RESUMEN EJECUTIVO**

El objetivo es construir un sistema de gestión de inventarios **SaaS Multi-tenant** de alto rendimiento, diseñado para ser el "cerebro transaccional" de MicroNuba. La plataforma permitirá a múltiples clientes (Tenants) gestionar sus existencias de forma aislada, consumiendo los servicios mediante una arquitectura **API-First** que facilite la integración con e-commerce, POS, y sistemas de logística externos.

## **2\. ARQUITECTURA DE TENENCIA (SAAS CORE)**

### **RF-001: Aislamiento Lógico de Datos (Multi-tenancy)**

* **Descripción:** El sistema deberá garantizar que cada consulta a la base de datos esté filtrada por un tenant\_id.  
* **Regla de Negocio:** Ningún usuario o proceso podrá acceder a datos de un SKU o Almacén que no pertenezca a su identificador de tenant validado en el token JWT.  
* **Manejo de Errores:** Si se intenta acceder a un ID de otro tenant, el sistema retornará un 403 Forbidden.

## **3\. MÓDULO DE MAESTROS (CATÁLOGO)**

### **HU-001: Gestión de SKUs y Variantes**

* **Narrativa:** Como **Gestor de Inventario**, quiero **crear productos con atributos técnicos y comerciales**, para **tener un catálogo organizado y trazable.**  
* **Criterios de Aceptación (Gherkin):**  
  * **Dado** que ingreso un código SKU único.  
  * **Cuando** guardo la información (Nombre, Categoría, Unidad de Medida, Punto de Reorden).  
  * **Entonces** el sistema debe validar que el SKU no exista previamente en el mismo tenant.

### **RF-002: Gestión de Almacenes Multisedea**

* **Nombre:** Configuración de Nodos de Inventario.  
* **Descripción:** El sistema permitirá definir múltiples ubicaciones físicas (Almacenes/Tiendas/Bodegas).  
* **Proceso:**  
  1. Definición de nombre y ubicación geográfica.  
  2. Asignación de tipo (Físico o Virtual/Tránsito).  
  3. Cada almacén tiene su propio saldo independiente por SKU.

## **4\. OPERACIONES DE INVENTARIO (TRANSACCIONAL)**

### **RF-003: Procesamiento de Movimientos Atómicos**

* **Nombre:** Motor de Movimientos de Stock.  
* **Disparador:** Llamada API desde POS, E-commerce o carga manual.  
* **Entradas:** sku\_id, warehouse\_id, quantity, type (ENTRY, EXIT, TRANSFER).  
* **Lógica:**  
  1. **Validación de Disponibilidad:** En salidas, verificar que stock\_disponible \>= quantity.  
  2. **Atomicidad:** La actualización del saldo y el log del movimiento deben ocurrir en una sola transacción SQL.  
  3. **Tipos de Stock:** El sistema debe manejar tres estados:  
     * **Físico:** Lo que hay en estantería.  
     * **Reservado:** Comprometido en pedidos no despachados.  
     * **Disponible:** Físico \- Reservado.  
* **Resultado:** Actualización de saldos en tiempo real y generación de un movement\_log\_id.

### **HU-002: Reservas de Stock (Soft Reservation)**

* **Narrativa:** Como **Plataforma de E-commerce**, quiero **reservar un producto temporalmente mientras el cliente paga**, para **evitar sobreventas (overselling).**  
* **Criterios de Aceptación:**  
  * El sistema bloquea la cantidad por un tiempo determinado (TTL).  
  * Si el pago falla, la reserva se libera automáticamente devolviendo el saldo a "Disponible".

## **5\. VALORACIÓN Y COSTOS**

### **RF-004: Cálculo de Costo Promedio Ponderado (CPP)**

* **Fórmula:** Cada entrada de mercancía (ENTRY) debe recalcular el costo unitario del inventario:  
  ![][image1]  
* **Salida:** Actualización del campo unit\_cost en el maestro de stock por almacén.

## **6\. INTEGRACIÓN Y ALERTAS (CONECTIVIDAD)**

### **RF-005: Webhooks de Stock Crítico**

* **Descripción:** El sistema debe disparar un evento JSON a una URL configurada cuando un SKU baje de su "Punto de Reorden".  
* **Payload:** { "tenant\_id": "xxx", "sku": "abc", "current\_stock": 5, "threshold": 10 }.

### **RF-006: API REST Full Documentation**

* **Endpoints Requeridos:**  
  * GET /inventory/balance/{sku}: Consulta de saldos por almacén.  
  * POST /inventory/movements: Registro de entradas/salidas.  
  * PATCH /inventory/reserve: Bloqueo temporal de stock.

## **7\. MATRIZ DE PRIORIZACIÓN (MVP)**

| Funcionalidad | Prioridad | Complejidad | Impacto en Negocio |
| :---- | :---- | :---- | :---- |
| Multi-tenancy Core | P0 (Bloqueante) | Alta | Crítico |
| Movimientos Simples | P0 (Bloqueante) | Media | Crítico |
| API de Consulta | P0 (Bloqueante) | Baja | Alto |
| Reservas Temporales | P1 | Media | Medio |
| Valoración CPP | P1 | Media | Alto (Contable) |
| Webhooks de Alerta | P2 | Baja | Operacional |

**Aprobado por:** \[MN\] Product Architect

[image1]: <data:image/png;base64,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>
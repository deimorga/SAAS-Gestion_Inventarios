# **ARQUITECTURA DE REFERENCIA: MICRONUBA INVENTORY SAAS CORE (V1.0)**

## **1\. Contexto Estratégico y Visión Técnica**

El sistema **MicroNuba Inventory** no es simplemente una base de datos de productos; se define como un **Microservicio Core de Alta Disponibilidad**, diseñado bajo el paradigma **API-First** y **Event-Driven**. En el ecosistema de MicroNuba, este sistema actúa como el "Libro Mayor" (General Ledger) de activos físicos.

Su propósito fundamental es centralizar la lógica de inventarios para múltiples plataformas (E-commerce, POS, Logística), eliminando los silos de información. Garantizamos que la **"Verdad Única"** del stock resida en un ledger inmutable, lo que permite auditorías forenses de cualquier movimiento en milisegundos.

### **Objetivos de Arquitectura Expandidos**

* **Multi-tenancy de Grado Militar:** Aislamiento lógico estricto mediante **Row-Level Security (RLS)** a nivel de base de datos. Esto asegura que, incluso en caso de un error en la capa de aplicación, un cliente (Tenant) jamás podrá visualizar ni modificar el inventario de otro.  
* **Consistencia Atómica y Partida Doble:** Cada cambio en el stock no es un simple UPDATE. Es un evento registrado en un **Inventory Ledger**. Si un producto entra, hay una contrapartida documental. Esto previene el "Stock Fantasma".  
* **Escalabilidad Elástica:** Arquitectura preparada para picos de tráfico (como Black Friday) mediante el uso de colas de mensajes y procesamiento asíncrono para tareas pesadas como la generación de reportes masivos o la sincronización de webhooks.  
* **Interoperabilidad Universal:** Exposición de endpoints RESTful enriquecidos y una arquitectura orientada a eventos que permite a cualquier sistema externo reaccionar a cambios en el inventario en tiempo real.

## **2\. Diagramas de Arquitectura y Flujos Críticos**

### **2.1. Vista de Contenido (Nivel de Sistema)**

La plataforma actúa como el "Cerebro Transaccional" que orquesta las peticiones de diferentes canales.

graph TD  
    subgraph "Canales Externos (Tenants)"  
        A\[MicroNuba E-commerce\]  
        B\[MicroNuba POS\]  
        C\[Apps Terceros / ERP\]  
    end

    subgraph "Capa de Acceso y Seguridad"  
        D\[API Gateway / Kong\]  
        E\[Auth Service \- JWT/API-Keys\]  
        E1\[Rate Limiter \- Redis\]  
    end

    subgraph "Core Inventory Engine (Golang)"  
        F\[Product & Catalog Service\]  
        G\[Warehouse & Location Service\]  
        H\[Transaction Ledger Service\]  
        I\[Reservation Engine \- Redis\]  
    end

    subgraph "Persistencia y Eventos (Data Layer)"  
        J\[(PostgreSQL 15 \- RLS Enabled)\]  
        K\[Redis \- Distributed Locks\]  
        L\[Event Bus \- RabbitMQ\]  
        M\[Worker \- Webhook Dispatcher\]  
    end

    A & B & C \--\> D  
    D \--\> E  
    E \--\> E1  
    E1 \--\> F & G & H & I  
    F & G & H \--\> J  
    I \--\> K  
    H \-- "Async Event" \--\> L  
    L \--\> M  
    M \-- "HTTPS Post" \--\> A & C

### **2.2. Flujo Atómico de Movimiento de Inventario (Deep Dive)**

Para evitar que dos ventas simultáneas del mismo último artículo generen una inconsistencia, implementamos un flujo de **Bloqueo Distribuido**.

sequenceDiagram  
    participant API as API Client  
    participant SRV as Movement Service  
    participant REDIS as Distributed Lock  
    participant DB as DB Transaction (Acid)  
    participant EVT as Event Bus (RabbitMQ)

    API-\>\>SRV: POST /inventory/movements (Entry/Exit)  
    SRV-\>\>REDIS: Acquire Lock (Tenant \+ SKU \+ Warehouse)  
    Note over REDIS: Previene condiciones de carrera (Race Conditions)  
    SRV-\>\>DB: Start Transaction (ISOLATION LEVEL SERIALIZABLE)  
    DB-\>\>DB: Validate Stock (If Exit: Available \>= Requested)  
    DB-\>\>DB: Insert Inventory\_Ledger (Audit Trail Inmutable)  
    DB-\>\>DB: Update Stock\_Balances (Atomic Decr/Incr)  
    DB-\>\>DB: Recalculate CPP (Si es Entrada: Costo Promedio Ponderado)  
    DB-\>\>SRV: Commit Transaction  
    SRV-\>\>REDIS: Release Lock  
    SRV-\>\>EVT: Emit stock.updated (Payload con nuevo balance)  
    SRV--\>\>API: 201 Created (JSON con Saldo Actualizado)

## **3\. Modelo de Datos Atómico (Entidad-Relación)**

El diseño de la base de datos prioriza la integridad histórica sobre la simplicidad. No borramos registros; los anulamos con movimientos de contrapartida.

erDiagram  
    TENANT ||--o{ WAREHOUSE : "posee"  
    TENANT ||--o{ PRODUCT : "administra"  
    WAREHOUSE ||--o{ LOCATION : "segmentado en"  
    PRODUCT ||--o{ STOCK\_BALANCE : "saldo actual"  
    WAREHOUSE ||--o{ STOCK\_BALANCE : "almacena"  
    STOCK\_BALANCE ||--o{ INVENTORY\_LEDGER : "historial completo"  
    STOCK\_BALANCE ||--o{ RESERVATION : "bloqueos temporales"

    TENANT {  
        uuid id PK  
        string name  
        jsonb config "Políticas: allow\_negative, default\_valuation"  
        timestamp created\_at  
    }

    PRODUCT {  
        uuid id PK  
        string sku "Unique per Tenant"  
        string name  
        decimal current\_cpp "Costo Promedio Ponderado Global"  
        boolean is\_active  
        string uom "Unit of Measure"  
    }

    STOCK\_BALANCE {  
        uuid id PK  
        uuid tenant\_id FK "RLS Key"  
        uuid product\_id FK  
        uuid warehouse\_id FK  
        decimal physical\_qty "Stock en estantería"  
        decimal reserved\_qty "Stock en carritos/pedidos"  
        decimal available\_qty "Calculado: Physical \- Reserved"  
    }

    INVENTORY\_LEDGER {  
        uuid id PK  
        uuid stock\_balance\_id FK  
        enum type "ENTRY, EXIT, TRANSFER, ADJUSTMENT"  
        decimal quantity "Valor absoluto"  
        decimal unit\_cost "Costo al momento del movimiento"  
        string reference\_doc "ID de Factura o Guía"  
        timestamp created\_at  
    }

## **4\. Stack Tecnológico: Justificación del Arquitecto**

La elección del stack no es por moda, sino por cumplimiento de SLAs:

* **Lenguaje: Go (Golang 1.21+):** Elegido por su modelo de concurrencia nativa (Goroutines). Es ideal para el **Movement Service**, permitiendo manejar miles de transacciones de inventario por segundo con un consumo de memoria mínimo.  
* **Base de Datos: PostgreSQL 15+:** El estándar para consistencia. Utilizamos **RLS** para garantizar que el tenant\_id sea una barrera infranqueable. La extensión pg\_stat\_statements se usará para monitorear queries lentas en el cálculo de inventarios.  
* **Cache & Locks: Redis (Cluster Mode):** Crucial para el **Reservation Engine**. Las reservas de carritos de e-commerce viven aquí con un TTL (Time-To-Live). Si el cliente no completa la compra en 15 minutos, Redis expira la clave y el stock vuelve a estar disponible automáticamente.  
* **Mensajería: RabbitMQ:** Manejo de consistencia eventual. Cuando el stock cambia, el sistema emite un evento. Los suscriptores (como el servicio de notificaciones de MicroNuba) procesan esta info sin bloquear la transacción principal.  
* **Documentación: OpenAPI 3.0 / Redoc:** Indispensable para la vertical de **Consultoría y Desarrollo a la Medida**, permitiendo que terceros integren el motor de inventario en días, no meses.

## **5\. Estrategia de Mitigación de Riesgos (Semáforo Técnico)**

| Riesgo | Impacto | Mitigación Arquitectónica |
| :---- | :---- | :---- |
| **Race Conditions en Ventas** | 🔴 Crítico | Uso de bloqueos optimistas con campos de versión en STOCK\_BALANCE y bloqueos distribuidos en Redis para el checkout. |
| **Fuga de Datos (Multi-tenant)** | 🔴 Crítico | Implementación de una capa de Middleware que inyecta el tenant\_id en el contexto de cada query. Auditorías periódicas de políticas RLS. |
| **Degradación de Performance** | 🟡 Medio | Particionamiento de la tabla INVENTORY\_LEDGER por fecha o por tenant\_id si el volumen supera los 100M de registros. |
| **Error en Costeo (CPP)** | 🔴 Crítico | El cálculo del CPP se realiza mediante una función pura disparada por un trigger de base de datos para asegurar que no dependa de la lógica del backend. |

## **6\. Definición de Requerimientos Funcionales Core (MVP+ Expandido)**

Para que esta solución sea competitiva a nivel Enterprise, el API debe cubrir los siguientes 35 Requerimientos Funcionales (RF), diseñados para ser atómicos y robustos:

### **A. Capa de Gobierno y Seguridad**

1. **RF-001 (Tenancy):** Aislamiento de datos mediante tenant\_id obligatorio en el header de cada petición.  
2. **RF-002 (API Governance):** Gestión de API Keys con rotación automática y scopes granulares.  
3. **RF-003 (Throttling):** Límites de peticiones por minuto para evitar abusos (DDoS interno).  
4. **RF-004 (Audit Logging):** Registro de "Quién, Cuándo y Qué" para cada cambio manual en el inventario.  
5. **RF-005 (Policy Engine):** Configuración por Tenant para permitir o prohibir el stock negativo.

### **B. Gestión de Maestros y Catálogo**

6. **RF-006 (Rich Catalog):** CRUD de SKUs con soporte para metadata extendida (JSONB) para pesos, dimensiones y colores.  
7. **RF-007 (Hierarchical Categories):** Organización del catálogo en árboles infinitos de categorías.  
8. **RF-008 (UOM Engine):** Conversión automática entre unidades (ej: de Cajas a Unidades) basada en factores definidos.  
9. **RF-009 (Bundling):** Gestión de Combos/Kits donde el stock del "Padre" depende de los componentes "Hijos".  
10. **RF-010 (Traceability):** Soporte nativo para números de serie únicos y gestión de números de lote.  
11. **RF-011 (Vendor Mapping):** Vinculación de productos con múltiples proveedores y sus códigos de referencia.  
12. **RF-012 (Pricing Layers):** Gestión de costos de reposición históricos para análisis de rentabilidad.

### **C. Infraestructura de Almacenamiento**

13. **RF-013 (Multi-Warehouse):** Soporte para n-cantidad de almacenes con geolocalización.  
14. **RF-014 (Bin Management):** Definición de ubicaciones lógicas (Pasillo, Estante, Nivel) para optimizar el picking.  
15. **RF-015 (Locking Locations):** Capacidad de marcar ubicaciones como "En Cuarentena" o "Dañadas".

### **D. Operaciones Transaccionales (El Motor)**

16. **RF-016 (Smart Entry):** Recepción de mercancía con actualización inmediata de saldos y recalculo de CPP.  
17. **RF-017 (Standard Exit):** Egreso de stock por venta o consumo interno con validación de disponibilidad.  
18. **RF-018 (Inter-Warehouse Transfer):** Proceso de transferencia en dos pasos (Salida \-\> En Tránsito \-\> Entrada).  
19. **RF-019 (Adjustment Suite):** Herramientas para ajustes manuales con flujos de aprobación para montos altos.  
20. **RF-020 (RMA Management):** Gestión de devoluciones integrando el re-ingreso al stock disponible o merma.  
21. **RF-021 (Repackaging):** Transformación de inventario (ej: abrir una caja de 12 para vender 12 unidades).  
22. **RF-022 (Scrap & Loss):** Registro de bajas por avería, robo o vencimiento.  
23. **RF-023 (Expiry Alerts):** Sistema de alertas tempranas para productos con fecha de vencimiento próxima.  
24. **RF-024 (Serial Validation):** Garantía de que un número de serie solo existe en un lugar a la vez.

### **E. Reservas y Demanda**

25. **RF-025 (Soft Reservations):** Bloqueo temporal de stock desde el carrito de compras (Short-lived).  
26. **RF-026 (Hard Commitment):** Conversión de reserva a salida real tras la confirmación de pago.  
27. **RF-027 (Auto-Release):** Limpieza automática de reservas colgadas para liberar inventario estancado.  
28. **RF-028 (Allocation Logic):** Priorización de inventario para canales específicos (ej: reservar 20% solo para E-commerce).

### **F. Análisis, Integración y Reportabilidad**

29. **RF-029 (Full Kárdex):** Exportación del historial de movimientos filtrable por rango de fechas y almacén.  
30. **RF-030 (Balance Snapshots):** Consultas en tiempo real de Físico, Reservado y Disponible.  
31. **RF-031 (Reorder Point):** Alertas automáticas de "Stock Bajo" configurables por almacén.  
32. **RF-032 (Asset Valuation):** Reporte de valor contable del inventario (Stock x CPP).  
33. **RF-033 (Real-time Webhooks):** Notificaciones push a sistemas externos ante cambios de stock.  
34. **RF-034 (Bulk Engine):** API para carga masiva de inventarios iniciales mediante jobs asíncronos.  
35. **RF-035 (Cyclic Counting):** Soporte para inventarios físicos por conteos cíclicos sin detener la operación.

## **7\. Consecuencias de Diseño y Próximos Pasos**

La implementación de este **Motor Atómico** tiene implicaciones directas en las verticales de MicroNuba:

1. **En SaaS:** Garantiza un SLA del 99.9% en la precisión del stock.  
2. **En Medida:** Reduce el tiempo de desarrollo de nuevos módulos de almacén en un 70%.  
3. **En Consultoría:** Ofrece una herramienta de auditoría que cumple con estándares internacionales de contabilidad.

**STOP:** El siguiente paso crítico es la definición de los **Esquemas de Mensajería para Webhooks**. No podemos permitir que una falla en el sistema de un cliente degrade el performance de nuestro core de inventarios.

**Firmado por:**

\[MN\] Principal Architect
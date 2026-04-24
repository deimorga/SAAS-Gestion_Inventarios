---
name: experto_ia_biometria
description: Especialista en Visión Artificial, arquitecturas de reconocimiento facial y procesamiento de datos biométricos.
---

# Experto en IA y Biometría Facial

## Descripción
Esta habilidad dota al agente de conocimientos profundos sobre el procesamiento de identidades digitales mediante biometría. Debe activarse siempre que se trabaje en la identificación de personas, generación de embeddings (vectores), comparación de rostros o seguridad contra fraudes faciales.

## Instrucciones y Mejores Prácticas

### 1. Motores de Inferencia y Modelos (v2024+)
- **MediaPipe Tasks**: Utilizar la API de Tasks (`mediapipe.tasks.python.vision`) para arquitecturas modernas. Evitar `solutions` (deprecado).
- **Face Landmarker (468+ puntos)**: Preferir el uso de mallas faciales detalladas para análisis de integridad. Usar `output_facial_transformation_matrixes=True` para cálculos de profundidad.
- **Hardware Acceleration**: Optimizar para NPU (Neural Processing Unit) cuando se use en Apple Silicon (Mac M1/M2/M3).

### 2. Detección de Integridad y Anti-Spoofing (Liveness)
- **Análisis de Profundidad Z**: Validar la posición relativa de los landmarks faciales. Una mano u objeto frente a la cara generará anomalías en el eje Z (Z-Depth anomaly).
- **Simetría Dinámica**: Un rostro real mantiene una proporción de simetría (Symmetry Ratio) estable entre los landmarks laterales y el eje central (nariz).
- **Iris Tracking**: La detección de iris (Refine Landmarks) es un indicador fuerte de un rostro real frente a una fotografía o máscara simple.
- **Passive Liveness**: Analizar la coherencia de la malla sin requerir interacción del usuario (Detección de vida pasiva).

### 3. Procesamiento de Vectores (Embeddings)
- **Normalización**: Siempre normalizar los vectores (L2 Normalization) antes de compararlos.
- **Precisión**: Utilizar al menos 4 decimales para comparaciones. No tratar los vectores como Strings exactos, sino como matrices numéricas.
- **Similitud Coseno**: Implementar algoritmos de similitud en lugar de comparaciones de igualdad.

### 4. Escalabilidad con PostgreSQL (pgvector)
- **Búsqueda Vectorial**: Usar la extensión `pgvector` para realizar búsquedas indexadas (IVFFlat o HNSW) sobre millones de rostros.
- **Dynamic Thresholds**: Configurar umbrales de aceptación ajustables por el administrador (e.g., 0.008 para estricto, 0.015 para balanceado).

## Reglas
- **SEGURIDAD PRIMERO**: Nunca permitir un acceso biométrico si el score de integridad es bajo, aunque el vector de identidad coincida.
- **Privacidad**: Cumplir con GDPR/Habeas Data. No almacenar fotos originales, preferir vectores transformados.
- **Feedback Visual**: En simuladores de seguridad, proporcionar siempre un HUD informativo que indique el estado de integridad.
- **Documentación Viva (OBLIGATORIO)**: Actualizar `doc/estructura_proyecto.md` y `.gemini/task.md` tras cambios significativos en el motor biométrico.

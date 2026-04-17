# Especificación Técnica: Sistema de Login Facial en Tiempo Real

## Introducción

Este documento describe la arquitectura y especificaciones técnicas de un sistema de autenticación biométrica basado en reconocimiento facial. El sistema está diseñado para operar en tiempo real, utilizando modelos preentrenados y generando perfiles biométricos únicos para cada usuario.

---

## Declaración del Alcance y Naturaleza del Sistema

- **Offline:** No requiere conexión a Internet para su funcionamiento.
- **Multiusuario:** Soporta múltiples perfiles biométricos independientes.
- **Experimental:** Su objetivo es exclusivamente investigativo y de validación técnica.
- **No auditado:** No ha pasado por auditorías externas de seguridad o conformidad.
- **No apto para producción:** No debe usarse en entornos productivos ni con datos sensibles reales.
- **Diseñado para evaluación comparativa:** La arquitectura está pensada únicamente para comparar el desempeño de modelos biométricos.

## Entorno de Desarrollo

- **Plataforma:** Anaconda + Jupyter
- **Lenguajes y Herramientas:** Python, OpenCV, NumPy
- **Modelos Evaluados:**
  - **face_recognition (dlib)**
  - **DeepFace**
  - **InsightFace**

---

## Objetivo del Sistema

Desarrollar un sistema de autenticación biométrica que:

1. No utilice datasets externos.
2. Genere su propio dataset en tiempo real.
3. Valide automáticamente la calidad de las capturas.
4. Compare el rendimiento de tres modelos distintos.
5. Permita descartar el modelo menos eficiente.

---

## Arquitectura General

### Componentes Principales

1. **Notebook `0_dataset_capture.ipynb`:**
   - Captura imágenes del usuario en tiempo real durante 5 segundos.
   - Valida la calidad de las imágenes (desenfoque, iluminación, posición, tamaño).
   - Guarda únicamente imágenes válidas.
   - **Nota:** Este módulo no genera embeddings.

2. **Notebooks de Modelos:**
   - Cada modelo tiene su propio notebook dedicado.
   - Funciones principales:
     - Cargar imágenes desde `dataset_users/<user_id>/`.
     - Generar embeddings utilizando el modelo correspondiente.
     - Calcular el embedding promedio del usuario (perfil biométrico).
     - Implementar el login facial comparando embeddings.
     - Medir rendimiento (tiempo, RAM, precisión).

3. **Modelos Preentrenados:**
   - No se entrena ninguna red neuronal desde cero.
   - Se utilizan modelos preentrenados para generar vectores faciales (embeddings).

---

## Estructura de Datos del Usuario

Cada usuario tendrá una ficha técnica con los siguientes campos:

- **ID único (DNI):** Identificador primario del usuario.
- **Nombre:** Texto descriptivo del usuario.
- **Contraseña (hash):** Hash seguro de la contraseña secundaria para vinculación en registro/login.
- **Embeddings cifrados:** Vector(es) faciales almacenados con cifrado.
- **Historial de embeddings (máx. 20):** Lista de embeddings históricos para aprendizaje adaptativo.
- **Logs de intentos:** Registro cronológico de intentos de login (fecha, resultado, modelo, tiempos, razones).

Formato de almacenamiento sugerido (ejemplo):

```json
{
  "dni": "12345678",
  "nombre": "Juan Perez",
  "password_hash": "<hash>",
  "embeddings": ["<ciphertext>"],
  "historial": ["<ciphertext>", "<ciphertext>"],
  "logs": [
    {
      "timestamp": "2026-02-07T12:00:00Z",
      "modelo": "InsightFace",
      "resultado": "exitoso",
      "latencia_ms": 900
    }
  ]
}
```

---

## Protección de Embeddings

- **Formato:** Los embeddings se almacenan en archivos **JSON** locales por usuario.
- **Cifrado:** Se aplica cifrado simétrico **AES** (clave local protegida) a cada embedding antes de persistir.
- **Política de imágenes:** En un escenario futuro de producción, **no** se almacenarán imágenes; solo embeddings cifrados. La retención de imágenes queda limitada al modo experimental.
- **Gestión de claves:** Las claves de cifrado deben mantenerse fuera del repositorio y rotarse periódicamente en entornos evaluativos.

---

## Módulo Antispoofing

Objetivo: Reducir intentos de suplantación mediante verificación de vitalidad.

- **Detección de persona real vs foto/pantalla:** Validación de textura/moiré y artefactos comunes en pantallas.
- **Parpadeo:** Detección de microeventos oclusivos en ojos durante la sesión.
- **Movimiento leve de cabeza:** Solicitud y verificación de microgestos (izquierda/derecha/arriba/abajo) en ventana temporal breve.
- **Fallo de antispoofing:** Si la verificación de vitalidad falla, **se muestra mensaje y se bloquea el flujo** (registro/login) y se registra el evento en logs.

---

## Detección de Gafas

- **Clasificación de objeto:** Se detecta la presencia de gafas (opacas o reflectivas) que puedan comprometer la extracción de embeddings.
- **Política:** Si se detectan gafas que afecten la calidad (por ejemplo, reflejos intensos o lentes oscuros), **se bloquea el login/registro**.
- **UX:** Se muestra un **mensaje solicitando retirarlas** o ajustar posición/iluminación antes de reintentar.

---

## Seguridad de Login

- **Intentos:** Máximo **3 intentos fallidos** consecutivos por sesión.
- **Bloqueo progresivo:**
  - 1er ciclo de bloqueo: **1 minuto**.
  - 2do ciclo de bloqueo: **5 minutos**.
  - Ciclos siguientes: incremento progresivo configurable.
- **Logs obligatorios:** Todos los eventos de login (exitosos y fallidos), causas de rechazo, métricas de latencia y uso de recursos deben quedar registrados.

---

## Aprendizaje Adaptativo

- **Actualización en éxito:** Cada login exitoso agrega **un nuevo embedding** al historial del usuario.
- **Reclacular promedio:** Tras la inserción, se **recalcula el embedding promedio** del perfil biométrico.
- **Capacidad máxima:** Máximo **20 embeddings por usuario** en el historial.
- **Política de recorte:** Al superar el límite, **se elimina el embedding más antiguo** (FIFO), preservando diversidad temporal.

---

## Definición Matemática y Métricas de Similaridad

- **Embedding vectorial:** Sea \( x \in \mathbb{R}^d \) el vector de características faciales generado por un modelo (p.ej., \( d \in \{128, 512\} \)).
- **Normalización (L2):** \( \hat{x} = \frac{x}{\|x\|\_2} \), para garantizar comparabilidad y estabilidad numérica.
- **Promedio de embeddings:** Dado un conjunto \( \{x*i\}*{i=1}^n \), el embedding promedio es \( \bar{x} = \frac{1}{n} \sum\_{i=1}^{n} x_i \). Con normalización posterior: \( \hat{\bar{x}} = \frac{\bar{x}}{\|\bar{x}\|\_2} \).
- **Similitud coseno:** \( \mathrm{cos}(\theta) = \frac{\hat{x} \cdot \hat{y}}{\|\hat{x}\|_2\,\|\hat{y}\|\_2} = \hat{x} \cdot \hat{y} \). La distancia asociada puede definirse como \( d_{\mathrm{cos}} = 1 - \mathrm{cos}(\theta) \).
- **Umbrales adaptables:** Los umbrales de decisión (p.ej., 0.5, 0.6) son **configurables por modelo** y pueden ajustarse en función de pruebas controladas (ROC/DET).

---

## Rendimiento Objetivo

- **Ejecución:** El sistema corre **exclusivamente en CPU**.
- **Latencia de login:** **< 2 segundos** por intento bajo condiciones estándar.
- **Uso de memoria:** **< 1.5 GB** por modelo cargado simultáneamente.
- **Medición:** Las métricas se capturan en cada notebook (tiempo, RAM, precisión) y se reportan en logs.

---

## Detalles de Arquitectura: Descripción de los Notebooks

### 1. `0_dataset_capture.ipynb`

**Propósito:**

- Capturar imágenes del usuario en tiempo real.
- Validar la calidad de las imágenes capturadas.
- Almacenar únicamente imágenes válidas en la carpeta correspondiente al usuario.

**Tareas específicas:**

1. Activar la cámara y capturar imágenes durante 5 segundos.
2. Validar cada imagen según los criterios de calidad:
   - **Desenfoque:** La imagen no debe estar borrosa (se utiliza la varianza de Laplaciano).
   - **Iluminación:** La iluminación debe ser adecuada (se evalúa la media de brillo).
   - **Posición:** El rostro debe estar alineado y en ángulo frontal.
   - **Tamaño:** El rostro debe ocupar un área mínima en el bounding box.
3. Guardar las imágenes válidas en `dataset_users/<user_id>/`.

---

### 2. `login_face_recognition.ipynb`

**Propósito:**

- Utilizar el modelo `face_recognition` para generar embeddings y realizar el login facial.

**Tareas específicas:**

1. Cargar las imágenes capturadas desde `dataset_users/<user_id>/`.
2. Generar embeddings utilizando el modelo `face_recognition`.
3. Calcular el embedding promedio del usuario (perfil biométrico).
4. Implementar el proceso de login:
   - Capturar una nueva imagen en tiempo real.
   - Generar el embedding de la imagen capturada.
   - Comparar el embedding generado con el perfil biométrico.
   - Tomar una decisión basada en la distancia:
     - **Distancia < 0.5:** Acceso concedido.
     - **Distancia entre 0.5 y 0.6:** Zona gris (reintento).
     - **Distancia > 0.6:** Acceso denegado.
5. Medir el rendimiento del modelo:
   - Tiempo de reconocimiento.
   - Uso de RAM.
   - Tasa de error.

---

### 3. `login_deepface.ipynb`

**Propósito:**

- Utilizar el modelo `DeepFace` para generar embeddings y realizar el login facial.

**Tareas específicas:**

1. Cargar las imágenes capturadas desde `dataset_users/<user_id>/`.
2. Generar embeddings utilizando el modelo `DeepFace`.
3. Calcular el embedding promedio del usuario (perfil biométrico).
4. Implementar el proceso de login (similar al notebook de `face_recognition`).
5. Medir el rendimiento del modelo:
   - Tiempo de reconocimiento.
   - Uso de RAM.
   - Tasa de error.

---

### 4. `login_insightface.ipynb`

**Propósito:**

- Utilizar el modelo `InsightFace` para generar embeddings y realizar el login facial.

**Tareas específicas:**

1. Cargar las imágenes capturadas desde `dataset_users/<user_id>/`.
2. Generar embeddings utilizando el modelo `InsightFace`.
3. Calcular el embedding promedio del usuario (perfil biométrico).
4. Implementar el proceso de login (similar a los otros notebooks).
5. Medir el rendimiento del modelo:
   - Tiempo de reconocimiento.
   - Uso de RAM.
   - Tasa de error.

---

## Flujo del Sistema

### Modo Registro

1. **Formulario Inicial:**
   - El usuario ingresa su nombre y una contraseña secundaria.
   - Estos datos se utilizan para asociar las imágenes capturadas al perfil del usuario.

2. **Captura de Imágenes:**
   - El sistema activa la cámara y captura imágenes del usuario durante 5 segundos.
   - Se asegura que las imágenes capturadas sean en tiempo real y representen diferentes expresiones o ángulos dentro de los criterios aceptables.

3. **Validación de Calidad:**
   - Cada imagen capturada pasa por un proceso de validación para garantizar que cumpla con los siguientes criterios:
     - **Desenfoque:** La imagen no debe estar borrosa (se utiliza la varianza de Laplaciano).
     - **Iluminación:** La iluminación debe ser adecuada (se evalúa la media de brillo).
     - **Posición:** El rostro debe estar alineado y en ángulo frontal.
     - **Tamaño:** El rostro debe ocupar un área mínima en el bounding box.

4. **Almacenamiento:**
   - Solo las imágenes que cumplen con los criterios de calidad se guardan en la carpeta `dataset_users/<user_id>/`.
   - Se asegura que se capturen al menos 10 imágenes válidas. Si no se alcanza este número, se solicita al usuario repetir el proceso.

5. **Confirmación:**
   - Una vez completado el registro, el sistema notifica al usuario que su perfil biométrico ha sido creado exitosamente.

### Modo Login

1. **Captura de Imagen:**
   - Se captura una imagen del usuario en tiempo real.

2. **Generación de Embedding:**
   - Se genera un vector facial (embedding) utilizando el modelo correspondiente.

3. **Comparación:**
   - El embedding generado se compara con el perfil biométrico almacenado.
   - **Decisión:**
     - **Distancia < 0.5:** Acceso concedido.
     - **Distancia entre 0.5 y 0.6:** Zona gris (reintento).
     - **Distancia > 0.6:** Acceso denegado.

---

## Evaluación de Modelos

### Métricas de Evaluación

| **Métrica**              | **Método de Medición**      |
| ------------------------ | --------------------------- |
| Tiempo de reconocimiento | `time.time()`               |
| Uso de RAM               | `psutil`                    |
| Tasa de error            | Intentos fallidos           |
| Robustez en luz baja     | Pruebas con iluminación     |
| Robustez en ángulos      | Capturas con rostro lateral |

### Características por Modelo

| **Modelo**       | **Tipo de Embedding** | **Dimensiones** | **Peso**   | **Uso Recomendado**  |
| ---------------- | --------------------- | --------------- | ---------- | -------------------- |
| face_recognition | dlib ResNet           | 128D            | Ligero     | Sistemas rápidos     |
| DeepFace         | VGG/Facenet           | 128–512D        | Pesado     | Mayor precisión      |
| InsightFace      | ArcFace               | 512D            | Medio-alto | Escenarios difíciles |

---

## Consideraciones de Seguridad Biométrica

1. **Protección contra Errores:**
   - **Foto borrosa:** Rechazar frame.
   - **Cara fuera de ángulo:** Rechazar.
   - **Mala iluminación:** Solicitar reintento.
   - **Cara muy pequeña:** Solicitar al usuario que se acerque.

2. **Privacidad:**
   - No se almacenan imágenes completas, solo embeddings.
   - Los embeddings son representaciones matemáticas, no imágenes reconstruibles.

3. **Adaptabilidad:**
   - Cada login exitoso puede:
     - Agregar nuevas muestras válidas.
     - Actualizar el embedding promedio.
     - Mejorar la precisión con el tiempo.

---

## Embedding Promedio

- **Definición:**
  - Es el promedio de los vectores faciales generados a partir de múltiples capturas válidas.
- **Propósito:**
  - Representar de manera robusta y única la identidad biométrica del usuario.
  - Reducir el impacto de variaciones en capturas individuales.

---

## Consideraciones sobre la Cantidad de Fotos

### Estándar Inicial

- Se establece un estándar de **10 fotos válidas por usuario** como cantidad mínima para generar un perfil biométrico robusto.

### Justificación

1. **Balance entre precisión y tiempo:**
   - 10 fotos proporcionan suficientes datos para generar un embedding promedio representativo sin alargar demasiado el proceso de registro.

2. **Compatibilidad con modelos:**
   - Los modelos evaluados (`face_recognition`, `DeepFace`, `InsightFace`) funcionan bien con datasets pequeños y generan embeddings consistentes con este número de imágenes.

3. **Evita desbalance:**
   - Establecer un estándar fijo asegura que todos los usuarios tengan perfiles biométricos igualmente representativos.

### Ajustes según el Desempeño

- **Más fotos (>10):**
  - **Ventajas:**
    - Mejora la robustez del perfil biométrico, especialmente en casos de variaciones de iluminación, ángulos o expresiones faciales.
    - Reduce el impacto de imágenes defectuosas que puedan pasar los filtros de calidad.
  - **Desventajas:**
    - Incrementa el tiempo de registro.
    - Puede ser innecesario si los modelos ya generan embeddings consistentes con menos datos.

- **Menos fotos (<10):**
  - **Ventajas:**
    - Acelera el proceso de registro.
    - Útil en sistemas donde la velocidad es crítica.
  - **Desventajas:**
    - Perfiles menos representativos, lo que podría aumentar la tasa de error.
    - Mayor sensibilidad a variaciones en las capturas.

### Recomendación

- Mantener **10 fotos** como estándar inicial.
- Realizar pruebas con los modelos para evaluar si este número es adecuado:
  - Si los modelos muestran alta precisión con menos fotos, podría reducirse a 5–7.
  - Si se detectan problemas de precisión, aumentar a 15–20 fotos podría ser una solución viable.

---

## Resultado Esperado

Después de las pruebas, se espera:

1. Identificar el modelo con mejor balance entre:
   - Precisión.
   - Velocidad.
   - Consumo de recursos.

2. Implementar el modelo seleccionado como base del sistema de login facial.

---

## Resumen

Este sistema de login facial:

- Es un sistema biométrico vivo.
- No depende de datasets externos.
- Aprende del usuario en tiempo real.
- Utiliza matemática avanzada para garantizar autenticidad.

---

**Fin del Documento**

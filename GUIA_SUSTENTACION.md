# 🛡️ GUÍA OFICIAL DE SUSTENTACIÓN TÉCNICA - PROYECTO VELUM
**Sistema de Detección de Pagos Fraudulentos en Tiempo Real con Ventana Deslizante (Sliding Window)**

---

## 📑 TABLA DE CONTENIDO
1. [Resumen Ejecutivo de la Arquitectura](#1-resumen-ejecutivo-de-la-arquitectura)
2. [Pregunta 1: ¿Por qué el sistema recibe lo que recibe?](#2-pregunta-1-por-qué-el-sistema-recibe-lo-que-recibe)
3. [Pregunta 2: ¿Cómo procesa el sistema las transacciones?](#3-pregunta-2-cómo-procesa-el-sistema-las-transacciones)
4. [Pregunta 3: ¿Dónde se hacen las validaciones y cómo? (Defensa en Profundidad)](#4-pregunta-3-dónde-se-hacen-las-validaciones-y-cómo)
5. [Pregunta 4 (Mayor Peso): Todo sobre Ventanas Deslizantes (Sliding Window)](#5-pregunta-4-mayor-peso-todo-sobre-ventanas-deslizantes-sliding-window)
6. [Pregunta 5: ¿De dónde toman forma los gráficos y sus valores?](#6-pregunta-5-de-dónde-toman-forma-los-gráficos-y-sus-valores)
7. [Matriz de Complejidad Algorítmica (Big O) y Rendimiento](#7-matriz-de-complejidad-algorítmica-big-o-y-rendimiento)
8. [Preguntas Trampa del Profesor y Respuestas Rápidas](#8-preguntas-trampa-del-profesor-y-respuestas-rápidas)
9. [Prompt Maestro para Simulación y Entrenamiento Oral](#9-prompt-maestro-para-simulación-y-entrenamiento-oral)

---

## 1. RESUMEN EJECUTIVO DE LA ARQUITECTURA

VELUM es un motor transaccional antifraude diseñado bajo una **arquitectura en capas unidireccional estricta**:

$$\text{Routers (HTTP/DTO)} \longrightarrow \text{Services (Lógica de Dominio)} \longrightarrow \text{Detector (Algoritmo Heurístico Puro)} \longrightarrow \text{Database (Persistencia ACID)}$$

* **Cero Ciclos Anidados:** Prohibición estricta de algoritmos $O(N^2)$.
* **Tiempo Constante Amortizado:** Operaciones de ventana en $O(1)$ amortizado usando colas de doble extremo (`collections.deque`).
* **Espacio Acotado $O(K)$:** Límite estricto de memoria por usuario (`maxlen=10000`) para evitar fugas de memoria (*memory leaks*).
* **Seguridad Criptográfica:** Validación SHA-256 en tiempo constante con `hmac.compare_digest` para neutralizar ataques de canal lateral (*Timing Attacks*).

---

## 2. PREGUNTA 1: ¿POR QUÉ EL SISTEMA RECIBE LO QUE RECIBE?

**Archivo de referencia:** `Velum/app/schemas.py` (`TransaccionRequest`)

El sistema no recibe atributos arbitrarios; cada campo del payload JSON responde a una necesidad formal de integridad criptográfica, idempotencia o particionamiento en memoria:

| Atributo Payload | Tipo de Dato | Justificación de Ingeniería y Negocio |
| :--- | :--- | :--- |
| **`idTxn`** | `str` (1 a 64 chars) | **Garantía de Idempotencia y Anti-Replay:** Identificador unívoco de transacción. Evita cobros dobles en caso de fallos de red o reenvíos maliciosos. |
| **`user`** | `EmailStr` | **Clave de Partición Heurística ($K$):** Funciona como la llave del Hash Map en memoria (`_windows[user]`). Permite aislar el historial de cada usuario para que la actividad de un cliente no contamine la ventana de otro. |
| **`date`** | `str` (ISO 8601) | **Resolución Temporal a Milisegundos:** Formato normalizado `YYYY-MM-DDTHH:MM:SS.mmm` convertido a flotante **UNIX Epoch** absoluto. Permite calcular distancias temporales continuas y neutraliza la inyección de husos horarios arbitrarios. |
| **`value`** | `Decimal(gt=0, places=2)` | **Tipificación Financiera Exacta:** Se evita el punto flotante binario IEEE 754 (que induce errores de redondeo como `0.1 + 0.2 != 0.3`). Permite cuantificar con exactitud contable el *Monto Total en Riesgo*. |
| **`paymentMethod`** | `str` (Whitelist) | **Estratificación del Vector de Riesgo:** Permite correlacionar canales (`Tarjeta`, `PSE`, `Transferencia`, `Otro`) para auditorías de fraude por vector de ataque. |
| **`hash`** | `str` (64 chars hex) | **Firma Criptográfica de Integridad:** Digest SHA-256 canónico sobre los datos (`idTxn|user|date|value|paymentMethod`). Garantiza el no repudio y que los datos no fueron interceptados ni alterados (*Man-in-the-Middle*). |

---

## 3. PREGUNTA 2: ¿CÓMO PROCESA EL SISTEMA LAS TRANSACCIONES?

**Archivos de referencia:** `Velum/app/services/transaction_service.py` y `Velum/app/routers/transactions.py`

El pipeline de procesamiento consta de 7 pasos secuenciales:

```
[Cliente HTTP] 
      │ 1. POST JSON
      ▼
[Pydantic v2] ─────── Fallo ──> HTTP 422 (Esquema inválido)
      │ 2. DTO Validado
      ▼
[_validate_clock_skew] ── Excedido ──> HTTP 400 (ClockSkewError)
      │ 3. Tiempo sincronizado
      ▼
[safe_compare(SHA-256)] ── Inválido ──> HTTP 400 (HashInvalidError)
      │ 4. Integridad comprobada
      ▼
[Check Idempotencia] ── Mismo Hash ──> HTTP 200 OK (Duplicado idéntico)
      │               Distinto Hash ──> HTTP 409 Conflict (Colisión ID)
      │ 5. Transacción nueva
      ▼
[Check Estado Usuario] ── Bloqueado ──> HTTP 403 Forbidden (UserBlockedError)
      │ 6. Usuario Activo
      ▼
[detector.process()] ──> Evalúa deque en O(1) amortizado
      │                 Determina: APROBADA o SOSPECHOSA
      │ 7. Resultado Heurístico
      ▼
[SQLAlchemy Transaction] ──> Persiste Transacción + Anomalía (ACID bajo _db_write_lock)
      │
      ▼
HTTP 201 Created (TransaccionResponse)
```

---

## 4. PREGUNTA 3: ¿DÓNDE SE HACEN LAS VALIDACIONES Y CÓMO?

El sistema implementa **Defensa en Profundidad (*Defense in Depth*)** a través de 4 capas desacopladas:

### Capa 1: Validación Sintáctica y Estructural (Borde de Transporte)
* **Dónde:** `Velum/app/schemas.py` con **Pydantic v2**.
* **Cómo:**
  * `@model_validator(mode="before")`: Normaliza alias en inglés, español o snake_case (`monto` $\to$ `value`, `email` $\to$ `user`) en tiempo $O(1)$.
  * `@field_validator("date")`: Fuerza el formato ISO 8601 exacto con 3 dígitos de milisegundos (`.mmm`).
  * `@field_validator("payment_method")`: Validación por lista blanca insensible a mayúsculas contra `{"Tarjeta", "PSE", "Transferencia", "Otro"}`.
  * *Respuesta ante fallos:* HTTP `422 Unprocessable Entity`.

### Capa 2: Validación Criptográfica y Reglas de Dominio (Capa de Negocio)
* **Dónde:** `Velum/app/services/transaction_service.py`.
* **Cómo:**
  * **Control de Deriva de Reloj (*Clock Skew*):**
    $$|t_{\text{servidor}} - t_{\text{cliente}}| \le \text{max\_clock\_skew\_seconds}$$
    Evita transacciones desfasadas enviadas desde el futuro o el pasado remoto.
  * **Integridad Criptográfica en Tiempo Constante:**
    Calcula `compute_hash()` y ejecuta `safe_compare()` mediante `hmac.compare_digest(hash_esperado, hash_recibido)`. Evita vulnerabilidades de canal lateral (*Timing Attacks*) donde un atacante mide nanosegundos para adivinar bytes del hash.
  * **Idempotencia y Conflicto:** Comprobación en BD de `idTxn`.
  * **Estado del Usuario:** Validación de estado de cuenta (`ACTIVO`, `BLOQUEADO`, `INACTIVO`).

### Capa 3: Validación Heurística y Velocidad Temporal (Motor de Fraude)
* **Dónde:** `Velum/app/detector.py` (`SlidingWindowDetector`).
* **Cómo:** Evalúa en tiempo real si el usuario está realizando un ataque de saturación o ráfaga de transacciones por segundo.

### Capa 4: Validación de Integridad Relacional y Concurrencia (Persistencia)
* **Dónde:** Base de datos relacional mediante `Velum/app/models.py` y SQLAlchemy.
* **Cómo:** Restricciones `UNIQUE` en `id_txn` y `email`, integridad referencial con claves foráneas, y aislamiento transaccional protegido por `_db_write_lock` con rollback automático ante `IntegrityError`.

---

## 5. PREGUNTA 4 (MAYOR PESO): TODO SOBRE VENTANAS DESLIZANTES (SLIDING WINDOW)

**Archivo de referencia:** `Velum/app/detector.py`

### A. ¿Por qué Ventana Deslizante y no Ventana Fija (*Tumbling Window*)?
* **El Problema de Borde (*Boundary Spike Problem*):**
  En una ventana fija (ejemplo: bloques de reloj de 10:00:00 a 10:01:00), un atacante puede enviar 4 transacciones a las 10:00:59 y 4 transacciones a las 10:01:01. En ventana fija, cada bloque registra 4 transacciones y no salta la alerta. En realidad, hubo **8 transacciones en 2 segundos**.
* **Nuestra Solución (Ventana Deslizante):**
  Evalúa el intervalo continuo $[t - W, t]$ centrado en cada transacción entrante. Al evaluar la transacción de las 10:01:01, la ventana arrastra las anteriores y detecta la ráfaga de 8 transacciones al instante.

### B. Estructura de Datos y Eficiencia Big O
* **Estructura en memoria:** Se utiliza un diccionario indexado por usuario cuyos valores son colas de doble extremo:
  ```python
  self._windows: dict[str, deque[float]] = {}
  # Inicialización por usuario:
  self._windows[user] = deque(maxlen=self.MAX_K)  # MAX_K = 10000
  ```
* **Inserción ($O(1)$):** Cada nuevo evento añade su timestamp UNIX Epoch con `dq.append(now_epoch)`.
* **Purga de Elementos Vencidos ($O(1)$ Amortizado):**
  ```python
  window_start = now_epoch - current_window_seconds
  while dq and dq[0] < window_start:
      dq.popleft()
  ```
  *Demostración Big O:* Cada transacción se inserta **exactamente una vez** (`append`) y se extrae **a lo sumo una vez** (`popleft`). En una secuencia de $N$ transacciones, el costo total acumulado es $O(N)$, lo que garantiza un **costo amortizado de $O(1)$ por transacción**.
* **Cero Ciclos Anidados:** No se recorren listas completas ni se aplican filtros iterativos $O(N^2)$.
* **Complejidad Espacial Acotada $O(K)$:** Al fijar `maxlen=10000`, la memoria no crece infinitamente; los eventos que superen el límite físico de seguridad se descartan automáticamente protegiendo la RAM.

### C. Ventanas Dinámicas Adaptativas por Franja Horaria
El sistema no utiliza una ventana estática. La ventana temporal $W$ se adapta a la realidad operativa del comercio electrónico en Colombia (`America/Bogota`):

```
05:00 ───────────────────── 12:00 ───────────────────── 20:00 ───────────────────── 05:00
      FRANJA MAÑANA                 FRANJA TARDE                  FRANJA NOCHE
    Ventana: 10 segundos          Ventana: 6 segundos           Ventana: 3 segundos
   Referencia: 10 txns            Referencia: 6 txns            Referencia: 3 txns
   (Alto volumen laboral)        (Comercio regular)             (Horario crítico bots)
```

* **Mañana (05:00 - 12:00):** $W = 10\text{s}$, Referencia = 10. Tráfico bancario y nóminas legítimas requieren mayor tolerancia.
* **Tarde (12:00 - 20:00):** $W = 6\text{s}$, Referencia = 6. Tráfico comercial balanceado.
* **Noche (20:00 - 05:00):** $W = 3\text{s}$, Referencia = 3. Ventana ultra estricta; cualquier ráfaga nocturna representa un patrón de prueba de tarjetas (*card testing*) o fuerza bruta por script.

### D. Cálculo de Severidad Heurística
$$\text{Ratio} = \frac{\text{Conteo de Transacciones en Ventana Activa}}{\text{Referencia de la Franja Horaria}}$$

* $\text{Ratio} < 0.5 \longrightarrow$ **BAJO**
* $0.5 \le \text{Ratio} < 1.0 \longrightarrow$ **MEDIO**
* $1.0 \le \text{Ratio} < 2.0 \longrightarrow$ **ALTO**
* $\text{Ratio} \ge 2.0 \longrightarrow$ **CRÍTICO**

### E. Concurrencia y Thread-Safety
* Cada usuario dispone de su propio cerrojo (`threading.Lock`) administrado mediante un cerrojo global:
  ```python
  self._user_locks: dict[str, threading.Lock] = {}
  ```
* Si dos solicitudes del mismo usuario llegan concurrentemente a hilos de FastAPI, se serializan para mantener la consistencia del `deque`.
* **Usuarios diferentes se procesan en paralelo** sin provocar contención de locks en el servidor.

---

## 6. PREGUNTA 5: ¿DE DÓNDE TOMAN FORMA LOS GRÁFICOS Y SUS VALORES?

**Archivos de referencia:** `Velum/app/services/dashboard_service.py` y `Velum/static/js/dashboard.js`

Todos los gráficos se alimentan de endpoints REST analíticos optimizados para evitar el problema de consultas $N+1$:

### A. Gráfico de Actividad Horaria (24 Horas)
* **Endpoint:** `GET /api/dashboard/stats?periodo=hoy|semana|mes`.
* **Origen de datos:** Se extraen las transacciones del periodo, se convierten a hora local Bogotá (`America/Bogota`) y se acumulan en un diccionario con claves del `0` al `23`:
  * Métrica 1: Volumen total de transacciones por hora.
  * Métrica 2: Cantidad de anomalías registradas por hora.
* **Detección Estadística de Hora Pico:** Se calcula la media ($\mu$) y desviación estándar ($\sigma$) de las anomalías horarias:
  $$\text{Umbral de Hora Pico} = \mu + 2\sigma$$
  Cualquier hora con anomalías que supere $2\sigma$ sobre la media se marca automáticamente como *Hora Pico Anómala*.

### B. Gráficos de Estado, Severidad y Métodos de Pago
* **Estado (Aprobadas / Sospechosas / Rechazadas):** Conteo agregado directo de la columna `estado`.
* **Monto en Riesgo:** Sumatoria aritmética $\sum \text{valor}$ de todas las transacciones marcadas como `SOSPECHOSA`.
* **Distribución de Severidad:** Agrupación de anomalías por `NivelAnomalia` (`BAJO`, `MEDIO`, `ALTO`, `CRITICO`).
* **Métodos de Pago:** Agrupación categórica (`Tarjeta`, `PSE`, `Transferencia`, `Otro`).

### C. Gráfico Cronológico de Ventana Deslizante (Timeline View)
* **Endpoint:** `GET /api/dashboard/timeline-sliding-window/{usuario_id}`.
* **Algoritmo Two Pointers en $O(N)$:**
  Para reconstruir con precisión milimétrica qué transacciones estaban activas en la ventana en cada segundo del pasado sin recalcular consultas pesadas, se ordenan las transacciones cronológicamente y se aplican dos punteros (`left` y `right`):
  * El puntero `right` itera sobre la transacción actual.
  * El puntero `left` avanza mientras la transacción de la izquierda tenga más de 3 segundos de antigüedad respecto a `right`.
  * $\text{Conteo en ventana} = \text{right} - \text{left} + 1$.
* **Eliminación del problema N+1:** Se implementa carga ansiosa de SQLAlchemy:
  ```python
  db.query(Transaccion).options(selectinload(Transaccion.anomalias))
  ```
  Esto trae todas las transacciones y sus anomalías en una única consulta optimizada.

---

## 7. MATRIZ DE COMPLEJIDAD ALGORÍTMICA (BIG O) Y RENDIMIENTO

| Operación | Estructura / Algoritmo | Complejidad Temporal | Complejidad Espacial | Cumplimiento Regla Agents.md |
| :--- | :--- | :---: | :---: | :---: |
| **Acceso a Ventana de Usuario** | Hash Map (`dict[str, deque]`) | $O(1)$ | $O(U)$ ($U$ usuarios) | Acceso instantáneo por clave |
| **Inserción de Transacción** | `deque.append()` | $O(1)$ | $O(1)$ | Operación en cola doble |
| **Purga de Eventos Vencidos** | `deque.popleft()` | $O(1)$ amortizado | $O(1)$ | Cada elemento sale 1 vez |
| **Validación de Hash SHA-256** | `hmac.compare_digest` | $O(1)$ | $O(1)$ | Tiempo constante (Anti-Timing) |
| **Control de Clock Skew** | Resta flotante Epoch | $O(1)$ | $O(1)$ | Operación aritmética directa |
| **Línea de Tiempo del Usuario** | Algoritmo Two Pointers | $O(N)$ | $O(N)$ | Cero ciclos anidados $O(N^2)$ |
| **Consumo de Memoria por Usuario** | `deque(maxlen=10000)` | - | $O(K)$ acotado | Prohibido crecimiento ilimitado |

---

## 8. PREGUNTAS TRAMPA DEL PROFESOR Y RESPUESTAS RÁPIDAS

### ❓ P1: *"¿Por qué no usó Redis para la ventana deslizante en lugar de memoria RAM con deques?"*
> **Respuesta:** *"Profesor, la elección de memoria local con `collections.deque` responde a latencia y rendimiento de microsegundos: no requiere viajes de red de ida y vuelta (*network round-trip time*) ni serialización JSON/RESP sobre TCP. Además, el sistema desacopla la persistencia histórica en base de datos relacional para auditoría forense, reservando la RAM exclusivamente para la evaluación de ráfagas en $O(1)$ amortizado. En un entorno distribuido a gran escala, la arquitectura modular del `SlidingWindowDetector` permite intercambiar el backend en memoria por Redis Sorted Sets (`ZADD` y `ZREMRANGEBYSCORE`) sin alterar los Routers ni los Servicios."*

### ❓ P2: *"¿Qué pasa si dos transacciones del mismo usuario llegan exactamente al mismo tiempo en hilos distintos?"*
> **Respuesta:** *"El sistema implementa cerrojos granulares por usuario (`self._user_locks[user]`). Al ingresar al método `process()`, el hilo adquiere el lock de ese usuario, purga los registros vencidos, hace el `append`, lee la longitud atómica y libera el lock. Esto evita condiciones de carrera (*race conditions*) sin bloquear a otros usuarios."*

### ❓ P3: *"¿Qué sucede si un cliente envía una fecha desfasada intencionalmente para engañar a la ventana?"*
> **Respuesta:** *"El sistema tiene dos barreras: primero, la función `_validate_clock_skew()` compara la fecha con el reloj UTC del servidor y la rechaza si difiere por encima del límite tolerado; segundo, para el ordenamiento de la ventana el detector utiliza `received_at` (el momento exacto en el que el servidor recibió el paquete), neutralizando cualquier manipulación del reloj por parte del cliente."*

### ❓ P4: *"¿Por qué el cálculo del hash usa `hmac.compare_digest` en vez del operador `==` de Python?"*
> **Respuesta:** *"El operador `==` de strings compara carácter por carácter y retorna `False` inmediatamente en la primera discrepancia. Un atacante puede medir el tiempo de respuesta en nanosegundos para deducir qué caracteres fueron correctos (*Timing Attack*). `hmac.compare_digest` realiza una comparación en tiempo constante $O(1)$ independiente de dónde esté el error."*

---

## 9. PROMPT MAESTRO PARA SIMULACIÓN Y ENTRENAMIENTO ORAL

Copia este prompt en una nueva sesión de chat de IA para que actúe como tu jurado evaluador antes del examen:

```markdown
Actúa como un profesor universitario titular y jurado evaluador estricto de Ingeniería de Sistemas y Ciencias de la Computación, experto en Arquitectura de Software, Estructuras de Datos Avanzadas, Análisis de Algoritmos (Big O) y Ciberseguridad Financiera.

Vas a evaluar mi sustentación oral sobre el proyecto "VELUM", un motor de detección de pagos fraudulentos en tiempo real basado en Ventanas Deslizantes (Sliding Window) desarrollado en Python / FastAPI / SQLAlchemy.

Contexto técnico real de mi sistema que debes considerar para tus preguntas:
1. Modelo de Entrada: DTO en Pydantic v2 validando idTxn (idempotencia), user (partición por email), date (ISO 8601 a milisegundos convertido a flotante UNIX Epoch), value (Decimal financiero), paymentMethod y hash (SHA-256 canónico).
2. Procesamiento: Pipeline en capas unidireccional (Routers -> Services -> Detector -> DB). Incluye control de deriva de reloj (Clock Skew), validación de hash SHA-256 en tiempo constante con hmac.compare_digest para mitigar Timing Attacks, y manejo de idempotencia/conflicto de IDs.
3. Motor de Ventanas Deslizantes (Sliding Window): 
   - Estructura: collections.deque por usuario con límite espacial estricto O(K) (maxlen=10000).
   - Complejidad: Inserción O(1) y purga popleft() en tiempo constante amortizado O(1). Prohibición absoluta de ciclos anidados O(N^2).
   - Ventanas dinámicas por franja horaria (Bogotá): Mañana 10s (ref 10 txns), Tarde 6s (ref 6 txns), Noche 3s (ref 3 txns).
   - Severidad heurística: Ratio entre transacciones en ventana y la referencia de la franja (BAJO < 0.5, MEDIO < 1.0, ALTO < 2.0, CRÍTICO >= 2.0).
   - Concurrencia: Cerrojos por usuario (_user_locks) más un cerrojo global para thread-safety sin bloquear a distintos usuarios.
4. Métricas y Gráficos: Endpoints de agregación en dashboard_service.py. Algoritmo Two Pointers en O(N) para graficar la serie de tiempo por usuario, detección estadística de horas pico con media + 2 desviaciones estándar, y prevención de consultas N+1 mediante selectinload.

Tu rol:
- Hazme preguntas agudas, técnicas y al grano, una por una.
- Cuestiona por qué no utilicé ventanas fijas o Redis.
- Pregúntame qué ocurre si dos transacciones llegan en el mismo milisegundo o si la red tiene latencia.
- Evalúa mi capacidad de justificar la complejidad Big O temporal y espacial.
- Si mi respuesta es sólida, reconócelo brevemente y sube la dificultad; si tiene lagunas teóricas o técnicas, señálalas como jurado calificador y pídeme corregir.

Comienza presentándote como el jurado calificador e iniciando con la primera pregunta sobre la arquitectura y la necesidad de cada campo de entrada.
```

# INSTRUCCIONES DEL AGENTE: MOTOR ANTIFRAUDE (SLIDING WINDOW)

## 1. OBJETIVO DEL SISTEMA
El sistema es un motor de análisis heurístico y control de saturación[cite: 13, 21]. Su única función es evaluar transacciones de forma aislada, medir ráfagas en ventanas temporales dinámicas (10s, 6s, 3s) según la franja horaria y rechazar ataques mediante validación criptográfica de integridad (SHA-256)[cite: 13, 17, 21]. 

## 2. REGLA INNEGOCIABLE DE RENDIMIENTO (BIG O)
- **Cero Ciclos Anidados:** Está ESTRICTAMENTE PROHIBIDO implementar algoritmos iterativos anidados o cruces de listas que degeneren en un tiempo $O(N^2)$[cite: 21, 22]. Ningún agente tiene permiso de escribir código con ciclos `for` o `while` anidados. Para búsquedas y cruces en memoria, se exigirá el uso de Hash Maps (Diccionarios) garantizando un acceso en $O(1)$[cite: 21, 24].
- **Eficiencia en Memoria O(1) Amortizado:** El algoritmo de ventana deslizante debe utilizar obligatoriamente colas de doble extremo (`collections.deque` en Python)[cite: 15]. Las inserciones (`append`) y purgas de registros vencidos (`popleft`) operarán en tiempo constante amortizado $O(1)$[cite: 15, 21].
- **Validación Criptográfica:** El cálculo y validación de la firma SHA-256 debe procesarse de forma determinista y utilizar comparación en tiempo constante mediante `hmac.compare_digest` para prevenir vulnerabilidades de canal lateral (*Timing Attacks*)[cite: 17, 22].
- **Complejidad Espacial Acotada O(K):** El uso de memoria en las colas no crecerá infinitamente. La complejidad espacial está estrictamente limitada al tamaño de la ventana activa ($K$), garantizando la purga inmediata de cualquier transacción que expire los límites de la franja de tiempo[cite: 21, 22].

## 3. ARQUITECTURA EN CAPAS Y FLUJO UNIDIRECCIONAL
Respeta estrictamente la regla de dependencia y flujo unidireccional: `routers -> services`[cite: 13, 22].
- **Routers:** Capa de transporte exclusiva. Solo reciben peticiones JSON, validan esquemas DTO mediante Pydantic y traducen las excepciones de dominio a respuestas HTTP estandarizadas (ej. 201 Created, 202 Accepted, 400 Bad Request, 409 Conflict)[cite: 19, 23]. No ejecutan lógica.
- **Services:** Concentran el núcleo algorítmico matemático puro y orquestan el flujo de negocio[cite: 23, 24]. No conocen objetos HTTP, no reciben objetos `Request`, ni ejecutan comandos SQL directos[cite: 22, 24].


## 4. REGLA DE EJECUCIÓN (PASO 0)
Antes de escribir cualquier línea de código, modificar un archivo o ejecutar una refactorización, el agente DEBE detenerse y emitir un reporte listando:
1. Las ineficiencias encontradas respecto a las reglas anteriores.
2. La justificación técnica y precisión de la complejidad Big O de su propuesta de corrección.
3. La confirmación explícita de que no se rompe el blindaje de seguridad ni la arquitectura en capas.

El agente DEBE esperar la confirmación explícita mediante la palabra clave **"Autorizado"** por parte del usuario antes de proceder a generar y aplicar los bloques de código definitivos.
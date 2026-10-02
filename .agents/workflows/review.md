---
description: Ejecuta una auditoría de código validando notación Big O, consultas a base de datos (N+1), aislamiento multi-tenant y reglas de arquitectura.
---

Ejecuta una auditoría estricta sobre los últimos cambios o el archivo actual:
1. Complejidad Big O: Detecta ciclos anidados O(n^2) y sugiere optimizaciones con estructuras de acceso indexado O(1) o O(log n)[cite: 2, 5].
2. Aislamiento Multi-tenant: Verifica que toda consulta a PostgreSQL inyecte obligatoriamente el filtro `tenant_id` o respete el modelo RLS[cite: 1, 2].
3. Arquitectura: Valida que no se violen las capas del backend (routers -> services -> db/repositories)[cite: 2, 5].
4. Base de Datos: Detecta problemas de carga N+1 y valida que no se ejecuten operaciones destructivas en tablas inmutables como `price_history`[cite: 1, 2].

Propón el código refactorizado si encuentras alguna de estas violaciones.
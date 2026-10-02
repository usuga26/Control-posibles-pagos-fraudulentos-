---
description: Ejecuta la suite de pruebas locales (Pytest) validando la compuerta de cobertura del 90% en la capa de servicios y las reglas de arquitectura.
---

Ejecuta el pipeline de validación local según el Plan de DevOps y QA v2.0[cite: 1].
1. Ejecuta las pruebas unitarias y de integración, incluyendo la validación innegociable de aislamiento cross-tenant (`test_rbac_tenancy.py`)[cite: 1].
2. Corre Pytest con la compuerta de cobertura estricta para la capa de lógica de negocio:
   `pytest tests/ --cov=app/services --cov-fail-under=90`[cite: 1, 2].
3. Ejecuta las pruebas de arquitectura para evitar saltos de capa[cite: 1].

Si alguna prueba falla o la cobertura es menor al 90%, analiza la traza de error y entrégame la solución en código para alcanzar la métrica.
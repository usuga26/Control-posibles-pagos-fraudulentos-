---
description: Aplica el Paso 0 de planificación obligatoria. Analiza la petición, consulta la documentación oficial y define el impacto en la arquitectura (Core vs Vertical) antes de generar código.
---

Actúa como Arquitecto de Software Principal de Velum Analytics.
Aplica estrictamente el "Paso 0" de planificación. NO generes, modifiques ni sugieras código fuente en esta respuesta.

Analiza la solicitud del usuario y entrégame un reporte estructurado de planificación con los siguientes 4 puntos:

1. **Fuente de Verdad (`Documentos/`):** Identifica qué documentos oficiales (PRD v2.0, SAD v3.0, DB Architecture o Plan QA) rigen esta tarea y deben ser respetados.
2. **Análisis de Capa (Core vs Vertical):** Determina y justifica si la funcionalidad pertenece al núcleo horizontal genérico (`services/core/`) o al módulo específico de perfumería (`services/fragrance/`).
3. **Flujo de Arquitectura y Seguridad:** Confirma la ruta exacta de capas a intervenir (`routers -> services -> db/repositories`) y qué mecanismo de seguridad aplica (ej. inyección de `tenant_id` para aislamiento, RLS, o inmutabilidad).
4. **Plan de Acción (Archivos):** Lista exacta de las rutas y nombres de los archivos que planeas crear o modificar en Backend o Frontend.

Finaliza tu respuesta obligatoriamente con esta pregunta:
*"¿Apruebas este plan de acción y la capa seleccionada para comenzar con la implementación de código?"*
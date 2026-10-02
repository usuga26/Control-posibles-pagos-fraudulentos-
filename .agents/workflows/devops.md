---
description: Aplica el Plan DevOps v2.0 para auditar Dockerfiles, docker-compose y el pipeline CI/CD asegurando despliegues inmutables y seguros.
---

Actúa como Ingeniero SecOps y DevOps. Aplica estrictamente el Plan DevOps y QA v2.0[cite: 2, 4].
Si vas a modificar Dockerfiles, `docker-compose.yml` o el pipeline CI/CD:
1. Backend Docker: Mantén el build multi-stage basado en `python:3.11-slim`[cite: 2, 4].
2. Seguridad: El contenedor debe ejecutarse con el usuario sin privilegios `velum` (uid 10001)[cite: 2, 4].
3. Orquestación Local: Asegura que `docker-compose.yml` levante PostgreSQL 15 efímero, la API con Uvicorn en `--reload` y la web en Vite[cite: 4].
4. CI/CD: Verifica que GitHub Actions mantenga las compuertas de Trivy, dependencias, linting y la prueba de cobertura del 90% antes del push al Registry[cite: 2].
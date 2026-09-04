# Arquitectura

## Estado actual

El proyecto implementa actualmente un flujo básico de integración continua y construcción de artefactos Docker.

### Componentes implementados

- Git y GitHub
- GitFlow
- GitHub Actions
- Aplicación Flask mínima
- Docker
- GitHub Container Registry (GHCR)
- CI para validación y construcción de imágenes
- Publicación de imágenes Docker en GHCR
- Versionado de imágenes mediante SHA del commit

### Flujo actual

```text
Developer
    |
    v
Git / GitFlow
    |
    v
GitHub
    |
    v
Pull Request
    |
    v
GitHub Actions
    |
    +--> Validaciones
    |
    +--> Docker build
    |
    +--> Push a GHCR
              |
              v
        Docker Image
        :latest
        :<commit-sha>


La imagen Docker publicada en GHCR puede recuperarse posteriormente mediante su SHA de commit y ejecutarse sin necesidad de reconstruirla.

### Arquitectura objetivo

El laboratorio evolucionará progresivamente hacia un flujo completo de DevOps/SRE:

```text
Git
 |
 v
GitHub
 |
 v
Pull Request
 |
 v
CI
 |
 v
Docker Build
 |
 v
Container Registry
 |
 v
GitOps
 |
 v
CD
 |
 v
ECS / Floc.io
 |
 v
Observabilidad
 |
 v
Prácticas SRE
``` 

### Componentes pendientes

- Continuous Delivery (CD)
- GitOps
- Despliegue mediante ECS / Floc.io
- Health checks y observabilidad
- Métricas y logs
- Prácticas SRE
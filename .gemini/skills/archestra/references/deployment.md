# Archestra Deployment Reference

## Local Quickstart (Docker)

Use the following command to start Archestra locally. This sets up the UI on port 3000 and the MCP Gateway on port 9000.

```bash
docker pull archestra/platform:latest; docker run -p 9000:9000 -p 3000:3000 
-e ARCHESTRA_QUICKSTART=true 
-v /var/run/docker.sock:/var/run/docker.sock 
-v archestra-postgres-data:/var/lib/postgresql/data 
-v archestra-app-data:/app/data 
archestra/platform;
```

### Key Components
- **UI/Admin Dashboard**: `http://localhost:3000`
- **MCP Gateway/API**: `http://localhost:9000`
- **Auth Secret**: Automatically generated at `/app/data/.auth_secret`. Persists across restarts in quickstart mode.

## Production Deployment (Helm/Kubernetes)

Helm is the recommended path for production to enable high availability and auto-scaling.

### Infrastructure Requirements
- **CPU**: 2+ Cores
- **RAM**: 4GB+
- **Storage**: 20GB+
- **Database**: PostgreSQL (External recommended for production)

### Helm Configuration Highlights
- `archestra.replicaCount`: Number of pods (ignored if HPA is on).
- `archestra.imageTag`: Use specific versions instead of `latest`.
- `archestra.deploymentStrategy`: Defaults to `RollingUpdate`.
- `archestra.resources`: Define CPU/Memory requests and limits.

## Configuration Manifest (`archestra.yaml`)

While often managed via Helm, a logical manifest for Archestra services follows this pattern:

```yaml
version: "v1"
server:
  name: "my-service"
  transport:
    type: "sse"
    url: "http://localhost:8000/sse"
tools:
  - name: "tool_name"
    description: "purpose"
secrets:
  - name: "API_KEY"
    source: "vault"
```

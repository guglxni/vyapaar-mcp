# Archestra Secrets Management

## Storage Backends
- **Database**: Default for quickstart/local (encrypted).
- **HashiCorp Vault**: Recommended for enterprise.
- **Kubernetes Secrets**: Standard for K8s-native deployments.

## Configuring External Secrets
Set the following environment variable to enable Vault:
```bash
ARCHESTRA_SECRETS_MANAGER=VAULT
```

### Vault Configuration Requirements
- `VAULT_ADDR`
- `VAULT_TOKEN` (or Role-based access)
- `VAULT_MOUNT_PATH`

## Key Capabilities
- **Automatic Rotation**: Supports periodic rotation of API keys.
- **Injection**: Secrets are injected into MCP servers and LLM proxies at runtime, ensuring they never reside in application logs or code.
- **Fallbacks**: If external storage is unreachable, Archestra can be configured to fail-closed or fallback to database storage depending on security policy.

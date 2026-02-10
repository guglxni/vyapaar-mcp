# MCP Gateway & Agent Connectivity

## Connecting Agents
Archestra acts as a central hub (Gateway) for MCP servers. Agents connect to the Gateway to access tools and managed resources.

### Configuration Schema (Claude Example)
To connect Claude to an Archestra-managed agent:

```json
{
  "mcpServers": {
    "archestra": {
      "url": "http://localhost:9000/v1/mcp/{agent-id}",
      "headers": {
        "Authorization": "Bearer {token}"
      }
    }
  }
}
```

### CLI Command
```bash
claude mcp add archestra "http://localhost:9000/v1/mcp/{agent-id}" 
--transport http 
--header "Authorization: Bearer {token}"
```

## Key Features
- **Centralized Secrets**: API keys for MCP servers are stored in Archestra (Vault/K8s) and injected at runtime.
- **Observability**: Every tool call through the Gateway is logged and traced.
- **Access Control**: Bearer tokens manage which users/agents can access specific MCP servers.
- **Private Registry**: Host and version your internal MCP servers within the platform.

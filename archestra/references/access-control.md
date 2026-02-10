# Archestra Platform Access Control (RBAC)

Archestra utilizes a granular Role-Based Access Control (RBAC) system to manage permissions across organizations and teams.

## Predefined Roles
- **Admin**: Full control over organization settings, members, agents, and secrets.
- **Editor**: Can create and modify agents and tools but cannot manage organization-level settings or billing.
- **Member**: Can use agents and view observability data but cannot modify configurations.

## Permission Schema
Permissions follow a `resource:action` format:
- `organization:read/write`
- `agent:execute/create/delete`
- `secret:read/write`
- `observability:read`

## Custom Roles
Custom roles can be defined by combining specific permissions.
- **Example**: A "DevOps" role might have `secret:write` and `agent:create` but not `organization:write`.

## Best Practices
1. **Principle of Least Privilege**: Assign the minimum permissions required for a user's task.
2. **Team-Based Organization**: Group users into teams and assign roles to teams rather than individuals.
3. **Audit Trails**: All permission changes and access events are logged in the audit trail for compliance.

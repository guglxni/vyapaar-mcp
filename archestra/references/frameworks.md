# Securing Framework-Based Agents with Archestra

Archestra provides a security layer for popular AI frameworks, intercepting tool calls and enforcing guardrails that the frameworks do not natively provide.

## Vercel AI SDK
While the Vercel AI SDK simplifies building agents, it lacks runtime controls against exfiltration.
- **Implementation**: Configure the SDK's tool calls to route through the Archestra LLM Proxy.
- **Benefit**: Archestra detects untrusted context and blocks malicious tool invocations before they reach the model.

## Pydantic AI
Pydantic AI provides excellent type safety but doesn't prevent prompt injection.
- **Implementation**: Use Archestra to validate tool inputs against security policies before the `pydantic-ai` agent executes them.
- **Benefit**: Ensures that only trusted context influences tool behavior.

## LangChain
LangChain agents are highly susceptible to the "Lethal Trifecta" due to their complex tool-use capabilities.
- **Implementation**: Wrap LangChain tools in Archestra Dynamic Tools.
- **Benefit**: Automatically restricts LangChain's ability to communicate externally if it reads untrusted data during a chain execution.

## N8N & OpenWebUI
- **N8N**: Use Archestra as the MCP Gateway for N8N "AI Agent" nodes to ensure all node actions are audited and governed.
- **OpenWebUI**: Secure custom tools in OpenWebUI by registering them with Archestra, preventing data leaks from the web interface.

## Framework Integration Pattern
Most integrations follow this pattern:
1. Register the framework's tools in Archestra.
2. Route the LLM calls through Archestra's **LLM Proxy**.
3. Apply **Dynamic Tool** policies to restrict high-risk tools based on context trust.

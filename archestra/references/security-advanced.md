# Archestra Advanced Security Concepts

## The Lethal Trifecta
The "Lethal Trifecta" is a critical security vulnerability pattern in AI agents, popularized by Simon Willison. It occurs when an agent possesses three specific capabilities simultaneously:
1. **Access to Private/Sensitive Data**: The agent can read internal or confidential information.
2. **Exposure to Untrusted Content**: The agent processes prompts or data from external sources (e.g., user inputs, scraped web content), which can contain malicious instructions (Prompt Injection).
3. **External Communication (Exfiltration)**: The agent has the ability to send data to external APIs or services.

### Archestra Mitigation
Archestra prevents this by ensuring no single agent instance has all three capabilities active in the same context.
- **Taint Tracking**: Archestra identifies when "Untrusted Content" enters the context.
- **Dynamic Policy Enforcement**: Once the context is tainted, Archestra automatically disables "External Communication" or restricts "Private Data Access" for that session.

## Dual LLM Guardrails
Dual LLM is a defense-in-depth strategy where two independent LLMs are used to secure agentic workflows.
- **Primary LLM**: Executes the user's task and interacts with tools. It may be exposed to untrusted data.
- **Security LLM (Validator)**: Monitors the tool calls made by the Primary LLM.
- **Isolation**: The Security LLM operates in a "clean" context, receiving only the tool call and system policy—never the untrusted content itself. This prevents the Security LLM from being compromised by the same injection that might have influenced the Primary LLM.

## Dynamic Tools
Archestra's "Dynamic Tools" feature adapts the set of available tools at runtime based on the security state of the agent's context.
- **Context Tainting**: If an agent reads an email or a web page (untrusted source), the context is marked as "tainted".
- **Tool Scoping**: Archestra dynamically restricts high-privilege tools (e.g., `send_email`, `execute_query`) when the context is tainted, requiring explicit human-in-the-loop (HITL) approval or a trust reset.

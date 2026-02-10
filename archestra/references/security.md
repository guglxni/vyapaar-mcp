# Archestra Security & Guardrails

## The Lethal Trifecta
Archestra is designed to mitigate the "Lethal Trifecta" in AI agents:
1. **Private Data Access**: Ability to read sensitive internal information.
2. **Untrusted Content**: Exposure to external/user-provided prompts (injection risk).
3. **External Communication**: Ability to send data to external APIs.

## Guardrail Mechanisms

### Dynamic Tools
Archestra automatically adjusts agent capabilities based on context trust levels.
- **Trusted Data Policies**: Identify safe tool outputs.
- **Untrusted Detection**: When untrusted content is detected, Archestra can dynamically disable external communication or high-risk tools.
- **Default-Deny**: Tool outputs are marked untrusted by default unless matched by a policy.

### Dual LLM
A security pattern where a secondary, independent LLM reviews tool invocations.
- The security LLM does not receive untrusted data in its context.
- It acts as a validator to ensure malicious prompts cannot trick the primary LLM into bypassing security rules.

### Trusted Data Policies
Define regex or schema matches for tool outputs that are considered "safe".
- Example: A tool returning a UUID might be trusted, while one returning free-form text from a website is untrusted.
- Untrusted data triggers context "tainting", which restricts subsequent tool use.

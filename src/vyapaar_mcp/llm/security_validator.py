"""Security LLM Validator for Dual LLM Quarantine Pattern.

Reference: https://archestra.ai/docs/platform-dual-llm

The security LLM validates tool calls WITHOUT access to tainted context.
It only sees: tool name, parameters, and governance policy.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from vyapaar_mcp.config import VyapaarConfig

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    """A tool call to be validated."""
    tool_name: str
    parameters: dict[str, Any]
    agent_id: str
    context_tainted: bool


@dataclass
class ValidationResult:
    """Result of security LLM validation."""
    approved: bool
    reason: str
    risk_score: float  # 0-1
    mitigation: str | None = None


class SecurityLLMClient:
    """Isolated security LLM for Dual LLM quarantine pattern.
    
    This LLM has NO access to conversation context - only validates
    tool calls against governance policies.
    """

    def __init__(self, config: VyapaarConfig) -> None:
        self._config = config
        self._client: AsyncOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        """Check if security LLM is configured."""
        return bool(self._config.security_llm_url)

    async def initialize(self) -> None:
        """Initialize the security LLM client."""
        if not self.is_configured:
            logger.warning("Security LLM not configured")
            return

        # Support local or remote security LLM
        base_url = self._config.security_llm_url
        api_key = self._config.security_llm_key or "not-needed"

        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        logger.info("Security LLM client initialized: %s", base_url)

    async def validate_tool_call(
        self,
        request: ToolCallRequest,
        governance_policy: dict[str, Any],
    ) -> ValidationResult:
        """Validate a tool call using isolated security LLM.
        
        Args:
            request: The tool call to validate
            governance_policy: Current governance rules (NOT conversation context)
            
        Returns:
            Validation result with approve/deny decision
        """
        if not self._client:
            if self._config.quarantine_strict:
                return ValidationResult(
                    approved=False,
                    reason="Security LLM unavailable (strict mode)",
                    risk_score=1.0,
                    mitigation="DENY",
                )
            # Non-strict: allow but warn
            logger.warning("Security LLM unavailable, allowing tool call (non-strict mode)")
            return ValidationResult(
                approved=True,
                reason="Security LLM unavailable (non-strict mode)",
                risk_score=0.5,
            )

        try:
            # Build isolated validation prompt (NO conversation context)
            prompt = self._build_validation_prompt(request, governance_policy)
            
            response = await self._client.chat.completions.create(
                model=self._config.security_llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a security validator for an AI agent. "
                            "Your job is to approve or deny tool calls based on "
                            "governance policies. You have NO access to conversation "
                            "context - only see tool name, parameters, and policy rules. "
                            "Respond with JSON: {\"approved\": bool, \"reason\": str, "
                            "\"risk_score\": float (0-1), \"mitigation\": str|null}"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low variance for deterministic validation
                max_tokens=500,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from security LLM")

            # Parse JSON response
            result = json.loads(content.strip())
            
            # Log for audit
            if self._config.quarantine_audit_log:
                logger.info(
                    "Security LLM validation: tool=%s approved=%s risk=%.2f reason=%s",
                    request.tool_name,
                    result.get("approved", False),
                    result.get("risk_score", 0.5),
                    result.get("reason", "No reason"),
                )

            return ValidationResult(
                approved=result.get("approved", False),
                reason=result.get("reason", "No reason provided"),
                risk_score=result.get("risk_score", 0.5),
                mitigation=result.get("mitigation"),
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse security LLM response: %s", e)
            if self._config.quarantine_strict:
                return ValidationResult(
                    approved=False,
                    reason=f"Invalid security LLM response: {e}",
                    risk_score=1.0,
                    mitigation="DENY",
                )
            return ValidationResult(
                approved=True,
                reason="Validation parsing error (non-strict mode)",
                risk_score=0.5,
            )
        except Exception as e:
            logger.error("Security LLM validation error: %s", e)
            if self._config.quarantine_strict:
                return ValidationResult(
                    approved=False,
                    reason=f"Validation error: {e}",
                    risk_score=1.0,
                    mitigation="DENY",
                )
            return ValidationResult(
                approved=True,
                reason=f"Validation error (non-strict): {e}",
                risk_score=0.5,
            )

    def _build_validation_prompt(
        self,
        request: ToolCallRequest,
        governance_policy: dict[str, Any],
    ) -> str:
        """Build isolated validation prompt without conversation context."""
        return f"""Validate this tool call:

TOOL: {request.tool_name}
PARAMETERS: {json.dumps(request.parameters, indent=2)}
AGENT_ID: {request.agent_id}
CONTEXT_TAINTED: {request.context_tainted}

GOVERNANCE_POLICY:
{json.dumps(governance_policy, indent=2)}

Question: Should this tool call be allowed?
Consider:
1. Does it violate any governance rules?
2. Is it being called from tainted context?
3. Could it lead to data leakage or unauthorized actions?
4. Is the agent_id authorized for this operation?

Respond with JSON only."""

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None


class ToolCallValidator:
    """High-level validator that orchestrates Dual LLM checks.
    
    This class manages context tainting and routes validation
    to the appropriate tier based on tool classification.
    """

    def __init__(self, config: VyapaarConfig) -> None:
        self._config = config
        self._security_llm = SecurityLLMClient(config)
        self._taint_sources = set(config.taint_sources.split(","))
        self._dual_llm_tools = set(config.dual_llm_tools.split(","))
        self._context_tainted = False

    @property
    def is_configured(self) -> bool:
        return self._security_llm.is_configured

    async def initialize(self) -> None:
        await self._security_llm.initialize()

    def mark_taint(self, tool_name: str) -> None:
        """Mark execution context as tainted by a tool's output."""
        if tool_name in self._taint_sources:
            self._context_tainted = True
            logger.warning("Context marked as tainted by tool: %s", tool_name)

    def clear_taint(self) -> None:
        """Clear tainted context (after session reset)."""
        self._context_tainted = False
        logger.info("Context taint cleared")

    @property
    def is_tainted(self) -> bool:
        """Check if current execution context is tainted."""
        return self._context_tainted

    async def validate(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        agent_id: str,
        governance_policy: dict[str, Any],
    ) -> ValidationResult:
        """Validate a tool call through appropriate tier.
        
        Tiers:
        1. DENY when tainted: Critical tools blocked entirely
        2. DUAL LLM when tainted: Security LLM validation required
        3. ALLOW: Read-only tools pass through
        """
        # Tier 1: Hard deny for critical tools when tainted
        if self._context_tainted and tool_name not in self._dual_llm_tools:
            # These are critical operations - deny when tainted
            critical_tools = {"handle_razorpay_webhook", "handle_slack_action", "set_agent_policy"}
            if tool_name in critical_tools:
                return ValidationResult(
                    approved=False,
                    reason=f"Tool '{tool_name}' is blocked when context is tainted (deterministic policy)",
                    risk_score=1.0,
                    mitigation="Refresh session or wait for taint clearance",
                )

        # Tier 2: Dual LLM validation for specified tools when tainted
        if self._context_tainted and tool_name in self._dual_llm_tools:
            request = ToolCallRequest(
                tool_name=tool_name,
                parameters=parameters,
                agent_id=agent_id,
                context_tainted=self._context_tainted,
            )
            return await self._security_llm.validate_tool_call(request, governance_policy)

        # Tier 3: Allow (not tainted or read-only tool)
        return ValidationResult(
            approved=True,
            reason="Context clean or tool read-only",
            risk_score=0.0,
        )

    async def close(self) -> None:
        await self._security_llm.close()

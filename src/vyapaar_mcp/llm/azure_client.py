"""Azure OpenAI Client for Microsoft AI Foundry integration.

Reference: https://learn.microsoft.com/en-us/azure/ai-foundry/
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncAzureOpenAI

from vyapaar_mcp.config import VyapaarConfig

logger = logging.getLogger(__name__)


class AzureOpenAIClient:
    """Azure OpenAI client for AI Foundry integration.
    
    Provides secure, policy-enforced LLM interactions through
    Archestra's deterministic controls.
    """

    def __init__(self, config: VyapaarConfig) -> None:
        self._config = config
        self._client: AsyncAzureOpenAI | None = None

    @property
    def is_configured(self) -> bool:
        """Check if Azure OpenAI is properly configured."""
        return bool(
            self._config.azure_openai_endpoint
            and self._config.azure_openai_api_key
        )

    async def initialize(self) -> None:
        """Initialize the Azure OpenAI client."""
        if not self.is_configured:
            logger.warning("Azure OpenAI not configured - set VYAPAAR_AZURE_OPENAI_ENDPOINT and VYAPAAR_AZURE_OPENAI_API_KEY")
            return

        self._client = AsyncAzureOpenAI(
            azure_endpoint=self._config.azure_openai_endpoint,
            api_key=self._config.azure_openai_api_key,
            api_version=self._config.azure_openai_api_version,
        )
        logger.info(
            "Azure OpenAI client initialized: endpoint=%s, deployment=%s",
            self._config.azure_openai_endpoint,
            self._config.azure_openai_deployment,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> tuple[str | None, str]:
        """Send a chat completion request to Azure OpenAI.
        
        Args:
            messages: List of {"role": "user|assistant|system", "content": "..."}
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Tuple of (generated_text or None, status_message)
        """
        if not self._client:
            return None, "Azure OpenAI not configured - set VYAPAAR_AZURE_OPENAI_ENDPOINT and VYAPAAR_AZURE_OPENAI_API_KEY"

        try:
            response = await self._client.chat.completions.create(
                model=self._config.azure_openai_deployment,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content, "success"
        except Exception as e:
            error_msg = str(e)
            if "DeploymentNotFound" in error_msg:
                return None, f"Azure deployment '{self._config.azure_openai_deployment}' not found. Create it in Azure AI Foundry (ai.azure.com)."
            if "404" in error_msg:
                return None, f"Azure endpoint error (404). Check VYAPAAR_AZURE_OPENAI_ENDPOINT and deployment name."
            logger.error("Azure OpenAI API error: %s", e)
            return None, f"Azure API error: {error_msg}"

    async def validate_with_guardrails(self, content: str) -> tuple[bool, str]:
        """Validate content against Azure AI Foundry guardrails.
        
        Per SPEC §17: Azure Content Safety integration for input validation.
        
        Implementation requires:
        1. Azure Content Safety resource (separate from OpenAI)
        2. Content Safety API key in config
        3. API endpoint configuration
        
        Current behavior: Returns safe when guardrails disabled or pending implementation.
        
        Returns:
            Tuple of (is_safe, reason)
        """
        if not self._config.azure_guardrails_enabled:
            return True, "Guardrails disabled"

        # TODO: Implement Azure Content Safety integration
        # Required: azure_content_safety_endpoint, azure_content_safety_api_key
        # API: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/
        if not self._config.azure_content_safety_endpoint:
            logger.warning(
                "Azure guardrails enabled but content safety not configured. "
                "Set VYAPAAR_AZURE_CONTENT_SAFETY_ENDPOINT and VYAPAAR_AZURE_CONTENT_SAFETY_API_KEY"
            )
            # Fail-open: allow but log warning (security decision)
            return True, "Guardrails pending configuration"

        # Implementation would call:
        # POST {azure_content_safety_endpoint}/contentsafety/text:analyze
        # With categories: Hate, SelfHarm, Sexual, Violence
        # Return False if any category with severity >= threshold
        logger.warning("Azure guardrails check requested - full implementation pending")
        return True, "Guardrails check pending full implementation"

    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None

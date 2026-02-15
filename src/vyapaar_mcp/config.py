"""Configuration management using Pydantic Settings.

All config is loaded from environment variables with the VYAPAAR_ prefix.
Secrets MUST be provided via env vars (never hardcoded).
In production on Archestra, secrets are injected via Vault/K8s Secrets.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class VyapaarConfig(BaseSettings):
    """Application configuration loaded from environment variables.

    All fields prefixed with VYAPAAR_ in the environment.
    Example: VYAPAAR_RAZORPAY_KEY_ID -> razorpay_key_id
    """

    model_config = ConfigDict(
        env_prefix="VYAPAAR_",
        case_sensitive=False,
        env_file=".env",
        extra="ignore",
    )

    # --- Razorpay X ---
    razorpay_key_id: str = Field(description="Razorpay API Key ID")
    razorpay_key_secret: str = Field(description="Razorpay API Key Secret")
    razorpay_webhook_secret: str = Field(
        default="",
        description="Razorpay Webhook Signing Secret (optional if using polling)",
    )
    razorpay_account_number: str = Field(
        default="",
        description="RazorpayX account number for API polling (from Dashboard > My Account)",
    )

    # --- Google Safe Browsing v4 ---
    google_safe_browsing_key: str = Field(
        description="Dedicated Google Safe Browsing API Key (not a generative AI key)"
    )

    # --- Redis ---
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for atomic budget tracking",
    )

    # --- PostgreSQL ---
    postgres_dsn: str = Field(
        description="PostgreSQL connection string for audit logs and policies (REQUIRED — no default)",
    )

    # --- Server ---
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, description="Server bind port")
    log_level: str = Field(default="INFO", description="Logging level")

    # --- Polling Mode (alternative to webhooks) ---
    poll_interval: int = Field(
        default=30,
        description="Polling interval in seconds for Razorpay API (5-300)",
    )
    auto_poll: bool = Field(
        default=False,
        description="Enable automatic background polling on server start",
    )
    dev_mode: bool = Field(
        default=False,
        description="Enable development mode (allows mock payouts, disables signature check)",
    )

    # --- Slack (Human-in-the-Loop) ---
    slack_bot_token: str = Field(
        default="",
        description="Slack Bot Token (xoxb-...) for approval notifications",
    )
    slack_channel_id: str = Field(
        default="",
        description="Slack Channel ID for approval requests",
    )
    slack_signing_secret: str = Field(
        default="",
        description="Slack Signing Secret for verifying interactive callbacks",
    )

    # --- Rate Limiting ---
    rate_limit_max_requests: int = Field(
        default=10,
        description="Max payout requests per agent per window (default 10/min)",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        description="Rate limit sliding window in seconds (default 60)",
    )

    # --- Circuit Breaker ---
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        description="Consecutive failures before circuit opens",
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=30,
        description="Seconds to wait before half-open recovery attempt",
    )

    # --- Razorpay API Base ---
    razorpay_api_base: str = Field(
        default="https://api.razorpay.com/v1",
        description="Razorpay API base URL",
    )

    # --- Google Safe Browsing API ---
    safe_browsing_api_url: str = Field(
        default="https://safebrowsing.googleapis.com/v4/threatMatches:find",
        description="Google Safe Browsing Lookup API endpoint",
    )

    # --- GLEIF (Legal Entity Identifier) ---
    gleif_api_url: str = Field(
        default="https://api.gleif.org/api/v1/lei-records",
        description="GLEIF API base URL for vendor entity verification",
    )

    # --- ntfy Notifications (Slack fallback) ---
    ntfy_topic: str = Field(
        default="",
        description="ntfy topic name for push notifications (acts as Slack fallback)",
    )
    ntfy_url: str = Field(
        default="https://ntfy.sh",
        description="ntfy server URL (public ntfy.sh or self-hosted)",
    )
    ntfy_auth_token: str = Field(
        default="",
        description="ntfy auth token for protected topics (optional)",
    )

    # --- Anomaly Detection ---
    anomaly_risk_threshold: float = Field(
        default=0.75,
        description="Risk score threshold (0-1) above which transactions are flagged as anomalous",
    )

    # ============================================
    # Microsoft Azure AI Foundry Configuration
    # ============================================
    # Azure AI Foundry is Microsoft's enterprise AI development platform.
    # Archestra provides deterministic access policies as a proxy layer
    # to protect against prompt injection attacks (lethal trifecta).

    # --- Azure OpenAI / AI Foundry ---
    azure_openai_endpoint: str = Field(
        default="",
        description="Azure OpenAI endpoint (e.g., https://<resource>.openai.azure.com/)",
    )
    azure_openai_api_key: str = Field(
        default="",
        description="Azure OpenAI API key from Azure Portal > Keys and Endpoint",
    )
    azure_openai_deployment: str = Field(
        default="gpt-4o",
        description="Azure OpenAI model deployment name",
    )
    azure_foundry_project_id: str = Field(
        default="",
        description="Azure AI Foundry Project ID for project-scoped resources",
    )
    azure_openai_api_version: str = Field(
        default="2024-10-21",
        description="Azure OpenAI API version",
    )

    # --- Archestra Security Proxy (Deterministic Controls) ---
    # Archestra sits as a proxy between your agent and MCP servers/LLM
    # to enforce deterministic access policies instead of probabilistic guardrails.
    #
    # NOTE: For self-hosted Archestra, no external API key is needed.
    # The proxy runs locally and enforces policies via its own gateway.
    # The ARCHESTRA_TEAM_TOKEN in deploy/archestra.yaml is for gateway auth
    # (generated locally via: archestra token generate --team <team-id>)
    archestra_enabled: bool = Field(
        default=False,
        description="Enable Archestra proxy layer for deterministic security controls",
    )
    archestra_url: str = Field(
        default="http://localhost:9000",
        description="Archestra URL for self-hosted instance (local proxy endpoint)",
    )
    archestra_policy_set_id: str = Field(
        default="",
        description="Archestra policy set ID defining allow/deny rules",
    )

    # --- Azure Foundry Guardrails (Probabilistic - Use with caution) ---
    # Note: Azure's probabilistic guardrails can be bypassed.
    # We recommend Archestra's deterministic controls for production.
    azure_guardrails_enabled: bool = Field(
        default=False,
        description="Enable Azure Foundry guardrails (jailbreak, indirect prompt injection detection)",
    )
    azure_guardrails_severity: int = Field(
        default=1,
        description="Moderation severity threshold: 0=low, 1=medium, 2=high",
    )

    # ============================================
    # Dual LLM Quarantine Pattern (Security Layer)
    # ============================================
    # Reference: https://archestra.ai/docs/platform-dual-llm
    #
    # The Dual LLM pattern defends against the "lethal trifecta":
    # - Indirect prompt injection via untrusted tool outputs
    # - Sensitive data leakage through compromised context
    # - Task drift caused by malicious instructions embedded in data

    # --- Context Tainting ---
    taint_sources: str = Field(
        default="handle_razorpay_webhook,poll_razorpay_payouts,check_vendor_reputation,verify_vendor_entity,score_transaction_risk",
        description="Comma-separated list of tools that mark context as untrusted",
    )

    # --- Dual LLM Validation Tier ---
    dual_llm_tools: str = Field(
        default="poll_razorpay_payouts,score_transaction_risk",
        description="Tools requiring security LLM validation when context is tainted",
    )

    # --- Security LLM Configuration ---
    security_llm_url: str = Field(
        default="http://localhost:9001/v1",
        description="Endpoint for isolated security validation LLM (no context access)",
    )
    security_llm_key: str = Field(
        default="",
        description="API key for security LLM (if required by local deployment)",
    )
    security_llm_model: str = Field(
        default="gpt-4o-mini",
        description="Security LLM model (e.g., gpt-4o-mini for cost-effective validation)",
    )
    dual_llm_max_rounds: int = Field(
        default=5,
        description="Max validation rounds before forcing deny (prevents loops)",
    )

    # --- Quarantine Enforcement ---
    quarantine_strict: bool = Field(
        default=True,
        description="Strict mode: if security LLM fails/unavailable, DENY the tool call",
    )
    quarantine_audit_log: bool = Field(
        default=True,
        description="Log all security LLM validation decisions for audit",
    )


def load_config() -> VyapaarConfig:
    """Load and validate configuration from environment."""
    return VyapaarConfig()  # type: ignore[call-arg]

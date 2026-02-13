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
        env_file_encoding="utf-8",
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


def load_config() -> VyapaarConfig:
    """Load and validate configuration from environment."""
    return VyapaarConfig()  # type: ignore[call-arg]

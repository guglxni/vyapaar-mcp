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
    )

    # --- Razorpay X ---
    razorpay_key_id: str = Field(description="Razorpay API Key ID")
    razorpay_key_secret: str = Field(description="Razorpay API Key Secret")
    razorpay_webhook_secret: str = Field(description="Razorpay Webhook Signing Secret")

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
        default="postgresql://vyapaar:securepass@localhost:5432/vyapaar_db",
        description="PostgreSQL connection string for audit logs and policies",
    )

    # --- Server ---
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, description="Server bind port")
    log_level: str = Field(default="INFO", description="Logging level")

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


def load_config() -> VyapaarConfig:
    """Load and validate configuration from environment."""
    return VyapaarConfig()  # type: ignore[call-arg]

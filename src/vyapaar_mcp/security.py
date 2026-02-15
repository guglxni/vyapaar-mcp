"""Security utilities for Vyapaar MCP.

Provides utility functions for secure logging, secret masking, and other
security-related operations.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Common patterns for sensitive data that should be masked
SECRET_PATTERNS = [
    # API keys, tokens, secrets
    (r"(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token)"
     r"[=:]\s*[\"']?)([a-zA-Z0-9_\-]{8,})", r"\1****"),
    # Razorpay keys
    (r"(rzp_)[a-zA-Z0-9]{14}", r"\1****"),
    # Basic auth credentials
    (r"(Basic\s+)[a-zA-Z0-9+/=]{20,}", r"\1****"),
    # JWT tokens
    (r"(Bearer\s+)[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+", r"\1****"),
    # Slack tokens
    (r"(xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,})", r"\1****"),
    # Generic long alphanumeric strings that look like secrets
    (r"([a-zA-Z0-9]{32,})", r"****"),
]


def mask_secrets(message: str) -> str:
    """Mask potential secrets in log messages.
    
    Args:
        message: The log message to sanitize.
        
    Returns:
        Message with potential secrets masked.
    """
    if not message:
        return message
        
    masked = message
    for pattern, replacement in SECRET_PATTERNS:
        masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
    
    return masked


class SecurityFormatter(logging.Formatter):
    """Custom formatter that masks secrets in log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Mask the message
        record.msg = mask_secrets(str(record.msg))
        
        # Handle any args that might contain secrets
        if record.args:
            record.args = tuple(
                mask_secrets(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return super().format(record)


def get_security_logger(name: str) -> logging.Logger:
    """Get a logger with security-aware formatting.
    
    Args:
        name: Logger name.
        
    Returns:
        Configured logger with secret masking.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Add handler if not present
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SecurityFormatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
    
    return logger


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a dictionary by masking potential secrets.
    
    Args:
        data: Dictionary to sanitize.
        
    Returns:
        Dictionary with secrets masked.
    """
    sensitive_keys = {
        "key", "secret", "token", "password", "credential",
        "api_key", "api_secret", "access_token", "refresh_token",
        "razorpay_key_id", "razorpay_key_secret", "razorpay_webhook_secret",
        "slack_bot_token", "slack_signing_secret",
        "google_safe_browsing_key", "azure_openai_api_key",
    }
    
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            result[key] = "****"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, str) and len(value) > 4:
            # Mask long string values that might be secrets
            if any(s in key.lower() for s in sensitive_keys):
                result[key] = "****"
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result

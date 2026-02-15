"""Structured logging configuration for Vyapaar MCP.

Provides JSON logging for production environments with contextual fields.
Can be enabled via VYAPAAR_LOG_FORMAT=json environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging.
    
    Outputs logs in JSON format for easy parsing by log aggregators
    (ELK, Datadog, CloudWatch, etc.)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Build base log entry
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields (custom context)
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        
        # Add thread/process info for debugging
        if record.threadName != "MainThread":
            log_entry["thread"] = record.threadName
        if record.processName != "MainProcess":
            log_entry["process"] = record.processName
        
        return json.dumps(log_entry)


def configure_logging(
    level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Default: INFO.
        json_format: Use JSON format. Default: True if VYAPAAR_LOG_FORMAT=json.
    """
    # Get configuration from environment
    level = level or os.environ.get("VYAPAAR_LOG_LEVEL", "INFO")
    json_format = json_format or os.environ.get("VYAPAAR_LOG_FORMAT", "") == "json"
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Set formatter
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    
    root_logger.addHandler(console_handler)
    
    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("razorpay").setLevel(logging.WARNING)


def get_structured_logger(name: str, extra: dict[str, Any] | None = None) -> logging.Logger | logging.LoggerAdapter:
    """Get a logger that supports structured context.
    
    Args:
        name: Logger name.
        extra: Additional context to include in all log messages.
        
    Returns:
        Configured logger.
    """
    logger = logging.getLogger(name)
    if extra:
        # Create a bound logger with extra context
        return logging.LoggerAdapter(logger, extra)
    return logger


# Auto-configure on import if enabled
if os.environ.get("VYAPAAR_LOG_FORMAT") or os.environ.get("VYAPAAR_LOG_LEVEL"):
    configure_logging()

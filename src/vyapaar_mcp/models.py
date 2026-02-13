"""Pydantic V2 data models for Vyapaar MCP.

All models use strict mode and ConfigDict per SPEC §4 constraint #5.
Amounts are always in paise (integer). ₹500 = 50000 paise.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# Enums
# ============================================================


class Decision(StrEnum):
    """Governance decision for a payout."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HELD = "HELD"


class ReasonCode(StrEnum):
    """Machine-readable reason codes for governance decisions."""

    POLICY_OK = "POLICY_OK"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    IDEMPOTENT_SKIP = "IDEMPOTENT_SKIP"
    NO_POLICY = "NO_POLICY"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    TXN_LIMIT_EXCEEDED = "TXN_LIMIT_EXCEEDED"
    RISK_HIGH = "RISK_HIGH"
    DOMAIN_BLOCKED = "DOMAIN_BLOCKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================
# Razorpay Webhook Models (Ingress)
# ============================================================


class RazorpayContact(BaseModel):
    """Contact details from webhook payload."""

    model_config = ConfigDict(strict=True, extra="allow")

    id: str
    entity: str = "contact"
    name: str
    type: str | None = None
    email: str | None = None


class RazorpayBankAccount(BaseModel):
    """Bank account details from webhook payload."""

    model_config = ConfigDict(strict=True, extra="allow")

    ifsc: str
    bank_name: str
    name: str
    account_number: str | None = None


class RazorpayFundAccount(BaseModel):
    """Fund account details from webhook payload."""

    model_config = ConfigDict(strict=True, extra="allow")

    id: str
    entity: str = "fund_account"
    contact_id: str | None = None
    account_type: str | None = None
    bank_account: RazorpayBankAccount | None = None
    contact: RazorpayContact | None = None


class PayoutNotes(BaseModel):
    """Notes attached to the payout — carries agent context."""

    model_config = ConfigDict(strict=True, extra="allow")

    agent_id: str = Field(default="unknown", description="ID of the AI agent initiating payout")
    purpose: str = Field(default="", description="Purpose of the payment")
    vendor_url: str = Field(default="", description="Vendor URL for reputation check")


class PayoutEntity(BaseModel):
    """The core payout entity from Razorpay webhook."""

    model_config = ConfigDict(strict=True, extra="allow")

    id: str = Field(description="Razorpay payout ID (pout_xxx)")
    entity: str = "payout"
    fund_account_id: str | None = None
    amount: int = Field(description="Amount in paise (₹500 = 50000)")
    currency: str = Field(default="INR")
    notes: PayoutNotes | dict[str, Any] = Field(default_factory=dict)
    fees: int | None = None
    tax: int | None = None
    status: str = Field(description="Payout status (queued, processing, etc.)")
    purpose: str | None = None
    mode: str | None = None
    reference_id: str | None = None
    fund_account: RazorpayFundAccount | None = None
    created_at: int | None = None

    def get_notes(self) -> PayoutNotes:
        """Get notes as a PayoutNotes model, handling dict input."""
        if isinstance(self.notes, dict):
            return PayoutNotes(**self.notes)
        return self.notes


class PayoutWrapper(BaseModel):
    """Wrapper around the payout entity in webhook."""

    model_config = ConfigDict(strict=True, extra="allow")

    entity: PayoutEntity


class WebhookPayload(BaseModel):
    """Top-level Razorpay webhook event payload."""

    model_config = ConfigDict(strict=True, extra="allow")

    payout: PayoutWrapper


class RazorpayWebhookEvent(BaseModel):
    """Full Razorpay webhook event."""

    model_config = ConfigDict(strict=True, extra="allow")

    entity: str = "event"
    account_id: str | None = None
    event: str = Field(description="Event type, e.g. 'payout.queued'")
    contains: list[str] = Field(default_factory=list)
    payload: WebhookPayload
    created_at: int | None = None


# ============================================================
# Google Safe Browsing Models
# ============================================================


class ThreatMatch(BaseModel):
    """A single threat match from Google Safe Browsing."""

    model_config = ConfigDict(strict=True, extra="allow")

    threatType: str  # noqa: N815 — Google's API naming
    platformType: str  # noqa: N815
    threatEntryType: str  # noqa: N815
    threat: dict[str, str]
    cacheDuration: str | None = None  # noqa: N815


class SafeBrowsingResponse(BaseModel):
    """Response from Google Safe Browsing Lookup API."""

    model_config = ConfigDict(extra="allow")

    matches: list[ThreatMatch] = Field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """URL is safe if no matches found."""
        return len(self.matches) == 0

    @property
    def threat_types(self) -> list[str]:
        """Extract unique threat types from matches."""
        return list({m.threatType for m in self.matches})


# ============================================================
# Internal Governance Models
# ============================================================


class AgentPolicy(BaseModel):
    """Spending policy for an AI agent."""

    model_config = ConfigDict(strict=True)

    agent_id: str
    daily_limit: int = Field(default=500000, description="Daily spend limit in paise")
    per_txn_limit: int | None = Field(default=None, description="Per-transaction limit in paise")
    require_approval_above: int | None = Field(
        default=None, description="Amount above which human approval is required"
    )
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GovernanceResult(BaseModel):
    """Result of the governance engine evaluation."""

    model_config = ConfigDict(strict=True)

    decision: Decision
    reason_code: ReasonCode
    reason_detail: str
    payout_id: str
    agent_id: str
    amount: int
    threat_types: list[str] = Field(default_factory=list)
    processing_ms: int | None = None


class AuditLogEntry(BaseModel):
    """An entry in the audit log."""

    model_config = ConfigDict(strict=True)

    payout_id: str
    agent_id: str
    amount: int
    currency: str = "INR"
    vendor_name: str | None = None
    vendor_url: str | None = None
    decision: Decision
    reason_code: ReasonCode
    reason_detail: str
    threat_types: list[str] = Field(default_factory=list)
    processing_ms: int | None = None
    created_at: datetime | None = None


class BudgetStatus(BaseModel):
    """Current budget status for an agent."""

    model_config = ConfigDict(strict=True)

    agent_id: str
    daily_limit: int
    spent_today: int
    remaining: int
    currency: str = "INR"


class HealthStatus(BaseModel):
    """Health status of dependent services."""

    model_config = ConfigDict(strict=True)

    redis: str = "unknown"
    postgres: str = "unknown"
    razorpay: str = "unknown"
    uptime_seconds: int = 0

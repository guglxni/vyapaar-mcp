"""Google Safe Browsing v4 Lookup API integration.

Checks vendor URLs against Google's threat lists:
- MALWARE
- SOCIAL_ENGINEERING
- UNWANTED_SOFTWARE
- POTENTIALLY_HARMFUL_APPLICATION

Results are cached in Redis (5 min TTL) to avoid redundant API calls.

IMPORTANT: On API timeout, we default to HOLD (not APPROVE).
Per SPEC §14.2: "If in doubt, REJECT."
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.models import SafeBrowsingResponse

logger = logging.getLogger(__name__)

# Threat types to check (covering all major categories)
THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]

CLIENT_ID = "vyapaar-mcp"
CLIENT_VERSION = "3.0.0"


class SafeBrowsingChecker:
    """Google Safe Browsing v4 Lookup API client."""

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://safebrowsing.googleapis.com/v4/threatMatches:find",
        redis: RedisClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._redis = redis
        self._http = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()

    async def check_url(self, url: str) -> SafeBrowsingResponse:
        """Check a URL against Google Safe Browsing threat lists.

        Args:
            url: The URL to check.

        Returns:
            SafeBrowsingResponse with matches (empty if safe).

        On timeout/error: returns a response indicating UNSAFE
        (fail-closed per SPEC §14.2).
        """
        # Check cache first
        if self._redis:
            cached = await self._redis.get_cached_reputation(url)
            if cached is not None:
                logger.debug("Cache hit for URL: %s", url)
                return SafeBrowsingResponse(**cached)

        # Build request payload per Google API spec
        request_body: dict[str, Any] = {
            "client": {
                "clientId": CLIENT_ID,
                "clientVersion": CLIENT_VERSION,
            },
            "threatInfo": {
                "threatTypes": THREAT_TYPES,
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }

        try:
            response = await self._http.post(
                self._api_url,
                params={"key": self._api_key},
                json=request_body,
            )
            response.raise_for_status()

            data = response.json()
            result = SafeBrowsingResponse(**data) if data else SafeBrowsingResponse()

            # Cache the result
            if self._redis:
                await self._redis.cache_reputation(
                    url,
                    result.model_dump(),
                    ttl=300,  # 5 minutes
                )

            if result.is_safe:
                logger.info("URL is SAFE: %s", url)
            else:
                logger.warning(
                    "URL is UNSAFE: %s — threats: %s",
                    url,
                    result.threat_types,
                )

            return result

        except httpx.TimeoutException:
            logger.error("Safe Browsing API TIMEOUT for URL: %s — defaulting to UNSAFE", url)
            # Fail-closed: timeout means we can't verify, so treat as risky
            return SafeBrowsingResponse(
                matches=[
                    {  # type: ignore[list-item]
                        "threatType": "TIMEOUT",
                        "platformType": "ANY_PLATFORM",
                        "threatEntryType": "URL",
                        "threat": {"url": url},
                    }
                ]
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "Safe Browsing API error %d for URL: %s — %s",
                e.response.status_code, url, e.response.text,
            )
            # 4xx errors (bad key, quota) — also fail closed
            return SafeBrowsingResponse(
                matches=[
                    {  # type: ignore[list-item]
                        "threatType": "API_ERROR",
                        "platformType": "ANY_PLATFORM",
                        "threatEntryType": "URL",
                        "threat": {"url": url},
                    }
                ]
            )

        except Exception as e:
            logger.error("Unexpected Safe Browsing error for URL: %s — %s", url, e)
            return SafeBrowsingResponse(
                matches=[
                    {  # type: ignore[list-item]
                        "threatType": "INTERNAL_ERROR",
                        "platformType": "ANY_PLATFORM",
                        "threatEntryType": "URL",
                        "threat": {"url": url},
                    }
                ]
            )

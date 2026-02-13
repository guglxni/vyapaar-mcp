"""GLEIF (Global Legal Entity Identifier Foundation) vendor verification.

Queries the free GLEIF API (https://api.gleif.org) to verify whether a
vendor is a legitimate registered legal entity with a valid LEI.

Reference: .reference/pygleif — Python GLEIF API wrapper
API docs:  https://www.gleif.org/en/lei-data/gleif-api

Key design choices (aligned with SafeBrowsingChecker pattern):
  • Async httpx client with configurable timeout
  • Circuit breaker wrapping all API calls
  • Redis caching (1 hour TTL — LEI data changes infrequently)
  • Fail-open: GLEIF is advisory, not blocking (unlike Safe Browsing)
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.resilience import CircuitBreaker, CircuitOpenError

logger = logging.getLogger("vyapaar_mcp.reputation.gleif")

# Redis cache TTL for LEI lookups (1 hour — entity data is relatively stable)
_CACHE_TTL = 3600

# GLEIF API v1 base URL
_DEFAULT_API_URL = "https://api.gleif.org/api/v1/lei-records"


class GLEIFEntity(BaseModel):
    """Represents a verified GLEIF entity."""

    lei: str
    legal_name: str
    jurisdiction: str
    category: str
    entity_status: str
    registration_status: str
    headquarters_country: str | None = None
    headquarters_city: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class GLEIFResponse(BaseModel):
    """Result of a GLEIF lookup."""

    query: str
    entities: list[GLEIFEntity] = Field(default_factory=list)
    error: str | None = None

    @property
    def is_verified(self) -> bool:
        """At least one entity found with ACTIVE status and ISSUED registration."""
        return any(
            e.entity_status == "ACTIVE" and e.registration_status == "ISSUED"
            for e in self.entities
        )

    @property
    def best_match(self) -> GLEIFEntity | None:
        """Return the highest-confidence match (ACTIVE + ISSUED first)."""
        for e in self.entities:
            if e.entity_status == "ACTIVE" and e.registration_status == "ISSUED":
                return e
        return self.entities[0] if self.entities else None

    @property
    def match_count(self) -> int:
        return len(self.entities)

    def to_dict(self) -> dict[str, Any]:
        best = self.best_match
        return {
            "query": self.query,
            "verified": self.is_verified,
            "match_count": self.match_count,
            "best_match": best.model_dump() if best else None,
            "all_entities": [e.model_dump() for e in self.entities],
            "error": self.error,
        }


class GLEIFChecker:
    """Async GLEIF API client with circuit breaker and Redis caching.

    Usage:
        checker = GLEIFChecker(redis=redis_client, circuit_breaker=cb)
        result = await checker.search_entity("Tata Consultancy Services")
        if result.is_verified:
            print(f"Verified: {result.best_match.lei}")
    """

    def __init__(
        self,
        api_url: str = _DEFAULT_API_URL,
        redis: RedisClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_url = api_url
        self._redis = redis
        self._circuit = circuit_breaker
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    async def search_entity(self, name: str) -> GLEIFResponse:
        """Search GLEIF by legal entity name.

        Args:
            name: Legal name of the entity to search for.

        Returns:
            GLEIFResponse with matching entities (if any).
        """
        if not name or not name.strip():
            return GLEIFResponse(query=name, error="Empty entity name")

        name = name.strip()
        cache_key = f"gleif:name:{name.lower()}"

        # --- Check Redis cache ---
        if self._redis:
            try:
                cached = await self._redis._client.get(cache_key)
                if cached:
                    logger.debug("GLEIF cache HIT for '%s'", name)
                    return self._deserialize(name, cached)
            except Exception as e:
                logger.warning("GLEIF cache read error: %s", e)

        # --- Call GLEIF API (through circuit breaker) ---
        try:
            if self._circuit:
                response = await self._circuit.call(self._api_search, name)
            else:
                response = await self._api_search(name)

            # Cache the result
            if self._redis:
                try:
                    await self._redis._client.set(cache_key, json.dumps(response.to_dict()), ex=_CACHE_TTL)
                except Exception as e:
                    logger.warning("GLEIF cache write error: %s", e)

            return response

        except CircuitOpenError:
            logger.error("GLEIF circuit OPEN for query '%s' — returning unknown", name)
            return GLEIFResponse(query=name, error="GLEIF circuit breaker open")

        except httpx.TimeoutException:
            logger.error("GLEIF API TIMEOUT for query '%s'", name)
            return GLEIFResponse(query=name, error="GLEIF API timeout")

        except httpx.HTTPStatusError as e:
            logger.error("GLEIF API error %d for query '%s': %s", e.response.status_code, name, e.response.text)
            return GLEIFResponse(query=name, error=f"GLEIF API HTTP {e.response.status_code}")

        except Exception as e:
            logger.error("Unexpected GLEIF error for query '%s': %s", name, e)
            return GLEIFResponse(query=name, error=f"GLEIF error: {e}")

    async def lookup_lei(self, lei: str) -> GLEIFResponse:
        """Look up a specific LEI code directly.

        Args:
            lei: The 20-character LEI code.

        Returns:
            GLEIFResponse with the entity details.
        """
        if not lei or len(lei) != 20:
            return GLEIFResponse(query=lei or "", error="Invalid LEI (must be 20 characters)")

        cache_key = f"gleif:lei:{lei.upper()}"

        # --- Check Redis cache ---
        if self._redis:
            try:
                cached = await self._redis._client.get(cache_key)
                if cached:
                    logger.debug("GLEIF cache HIT for LEI '%s'", lei)
                    return self._deserialize(lei, cached)
            except Exception as e:
                logger.warning("GLEIF cache read error: %s", e)

        # --- Call GLEIF API ---
        try:
            if self._circuit:
                response = await self._circuit.call(self._api_lookup_lei, lei)
            else:
                response = await self._api_lookup_lei(lei)

            if self._redis:
                try:
                    await self._redis._client.set(cache_key, json.dumps(response.to_dict()), ex=_CACHE_TTL)
                except Exception as e:
                    logger.warning("GLEIF cache write error: %s", e)

            return response

        except CircuitOpenError:
            logger.error("GLEIF circuit OPEN for LEI '%s'", lei)
            return GLEIFResponse(query=lei, error="GLEIF circuit breaker open")

        except httpx.TimeoutException:
            logger.error("GLEIF API TIMEOUT for LEI '%s'", lei)
            return GLEIFResponse(query=lei, error="GLEIF API timeout")

        except Exception as e:
            logger.error("Unexpected GLEIF error for LEI '%s': %s", lei, e)
            return GLEIFResponse(query=lei, error=f"GLEIF error: {e}")

    # ----------------------------------------------------------------
    # Private: API calls
    # ----------------------------------------------------------------

    async def _api_search(self, name: str) -> GLEIFResponse:
        """Query GLEIF API by entity legal name.

        Endpoint: GET /api/v1/lei-records?filter[entity.legalName]=<name>
        Reference: .reference/pygleif/pygleif/search.py
        """
        encoded = quote(name, safe="")
        url = f"{self._api_url}?filter[entity.legalName]={encoded}&page[size]=5"

        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        entities = self._parse_records(data.get("data", []))

        logger.info(
            "GLEIF search '%s' → %d entities found (verified=%s)",
            name, len(entities), any(
                e.entity_status == "ACTIVE" and e.registration_status == "ISSUED"
                for e in entities
            ),
        )

        return GLEIFResponse(query=name, entities=entities)

    async def _api_lookup_lei(self, lei: str) -> GLEIFResponse:
        """Look up a specific LEI.

        Endpoint: GET /api/v1/lei-records/<LEI>
        Reference: .reference/pygleif/pygleif/gleif.py
        """
        url = f"{self._api_url}/{lei.upper()}"

        resp = await self._client.get(url)
        if resp.status_code == 404:
            return GLEIFResponse(query=lei, error="LEI not found")
        resp.raise_for_status()
        data = resp.json()

        record = data.get("data", {})
        if isinstance(record, dict):
            entities = self._parse_records([record])
        else:
            entities = self._parse_records(record)

        return GLEIFResponse(query=lei, entities=entities)

    # ----------------------------------------------------------------
    # Private: Parsing helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _parse_records(records: list[dict[str, Any]]) -> list[GLEIFEntity]:
        """Parse GLEIF API response records into GLEIFEntity objects.

        Response shape reference: .reference/pygleif/tests/fixtures/9845001B2AD43E664E58_issued.json
        """
        entities: list[GLEIFEntity] = []
        for record in records:
            try:
                attrs = record.get("attributes", {})
                entity_data = attrs.get("entity", {})
                registration = attrs.get("registration", {})

                legal_name_obj = entity_data.get("legalName", {})
                hq_address = entity_data.get("headquartersAddress", {})

                entities.append(GLEIFEntity(
                    lei=attrs.get("lei", record.get("id", "")),
                    legal_name=legal_name_obj.get("name", "") if isinstance(legal_name_obj, dict) else str(legal_name_obj),
                    jurisdiction=entity_data.get("jurisdiction", ""),
                    category=entity_data.get("category", ""),
                    entity_status=entity_data.get("status", ""),
                    registration_status=registration.get("status", ""),
                    headquarters_country=hq_address.get("country") if isinstance(hq_address, dict) else None,
                    headquarters_city=hq_address.get("city") if isinstance(hq_address, dict) else None,
                ))
            except Exception as e:
                logger.warning("Failed to parse GLEIF record: %s", e)
                continue

        return entities

    @staticmethod
    def _deserialize(query: str, cached_json: str) -> GLEIFResponse:
        """Deserialize a cached GLEIFResponse from JSON."""
        try:
            data = json.loads(cached_json)
            entities = [
                GLEIFEntity(**e) for e in data.get("all_entities", [])
            ]
            return GLEIFResponse(
                query=query,
                entities=entities,
                error=data.get("error"),
            )
        except Exception as e:
            logger.warning("GLEIF cache deserialization error: %s", e)
            return GLEIFResponse(query=query, error=f"Cache parse error: {e}")

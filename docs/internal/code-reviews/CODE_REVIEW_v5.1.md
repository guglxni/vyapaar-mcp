# Vyapaar MCP — Comprehensive Code Review

> *Internal prototype record*

**Date:** 2026-02-12
**Scope:** Full codebase (28 source files, 8 test files, infrastructure configs)
**Test Suite:** 146/146 passing

**Review Methodology:** Guided by 5 FOSS skills:
- `code-review-excellence` — structured review framework
- `security-auditor` — OWASP Top 10, secrets exposure, auth issues
- `python-expert-best-practices-code-review` — Python 3.12+ idioms
- `async-python-patterns` — asyncio correctness, blocking detection
- `python-error-handling` — fail-fast, exception hierarchies, partial failure

---

## Executive Summary

The codebase is well-architected with strong separation of concerns, consistent Pydantic modelling, atomic Redis operations, and proper circuit breaker resilience. However, this review uncovered **4 critical**, **11 important**, and **10 medium** findings across security, correctness, performance, and code quality dimensions. The most urgent fixes are: hardcoded secrets in defaults, missing metrics wiring for FOSS tools, `assert`-based service guards, and a Prometheus histogram rendering bug.

---

## Severity Legend

| Icon | Level | Impact |
|------|-------|--------|
| 🚨 | **CRITICAL** | Must fix before production — security or data integrity risk |
| ⚠️ | **HIGH** | Should fix soon — correctness or reliability issue |
| 📋 | **MEDIUM** | Should fix — maintainability or subtle bug |
| 💡 | **LOW** | Nice to have — style, minor improvements |
| 🎉 | **PRAISE** | Good work worth highlighting |

---

## 🔐 Security Findings

### 🚨 S-1: Hardcoded PostgreSQL Password in docker-compose.yml

**File:** docker-compose.yml:66
```yaml
environment:
  POSTGRES_PASSWORD: securepass  # ← Committed to VCS
```

**Risk:** CWE-798 (Hardcoded Credentials). Anyone with repo access has DB credentials.

**Fix:** Use Docker secrets or env var interpolation:
```yaml
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}
```

### 🚨 S-2: Default DSN Contains Password in config.py

**File:** config.py:58
```python
postgres_dsn: str = Field(
    default="postgresql://vyapaar:securepass@localhost:5432/vyapaar_db",
)
```

**Risk:** If the env var is missing, the app silently connects with a known password. Default should be empty or raise on missing value.

**Fix:** Remove the default so the env var is required:
```python
postgres_dsn: str = Field(description="PostgreSQL connection string")
```

### ⚠️ S-3: Google Safe Browsing API Key Sent as URL Query Parameter

**File:** safe_browsing.py:96
```python
response = await self._circuit.call(
    self._http.post,
    self._api_url,
    params={"key": self._api_key},  # ← Visible in logs, proxies
    json=request_body,
)
```

**Risk:** API keys in URL parameters are logged by HTTP proxies, CDNs, and access logs. Google's API requires the key as a query param (their design), but you should ensure server-side access logs redact query strings.

**Mitigation:** Add a warning comment documenting this is Google's required format, and configure httpx logging to redact the key.

### ⚠️ S-4: CLI Arguments Expose Razorpay Secret in Process List

**File:** razorpay_bridge.py:100-105
```python
args=[
    "stdio",
    "--key", self._key_id,
    "--secret", self._key_secret,  # ← Visible via `ps aux`
    "--log-file", "/dev/null",
],
```

**Risk:** Any user on the system can see the Razorpay secret with `ps aux | grep razorpay`.

**Fix:** Pass credentials via environment variables only (the Go binary already supports `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` env vars — you're already setting them). Remove the `--key` and `--secret` args:
```python
args=["stdio", "--log-file", "/dev/null"],
env={
    **os.environ,
    "RAZORPAY_KEY_ID": self._key_id,
    "RAZORPAY_KEY_SECRET": self._key_secret,
},
```

### ⚠️ S-5: `assert` Used for Runtime Service Guards

**File:** server.py (12 occurrences across all tool handlers)
```python
@mcp.tool()
async def handle_razorpay_webhook(...):
    assert _config is not None       # ← Stripped by python -O
    assert _redis is not None
    assert _postgres is not None
```

**Risk:** If Python runs with the `-O` (optimize) flag, all `assert` statements are removed. The tool would then dereference `None`, causing an AttributeError instead of a clear message.

**Fix:** Replace with explicit runtime checks:
```python
if _config is None or _redis is None:
    raise RuntimeError("Server not initialized — services unavailable")
```

### 📋 S-6: Redis Idempotency Key Uses Non-Atomic SETNX + EXPIRE

**File:** redis_client.py:207-213
```python
is_new = await self.client.setnx(key, "processed")
if is_new:
    await self.client.expire(key, 172800)  # ← Separate command
```

**Risk:** If the process crashes between `setnx` and `expire`, the key persists forever, permanently blocking re-processing of that webhook.

**Fix:** Use the atomic `SET` with `NX` and `EX`:
```python
result = await self.client.set(key, "processed", nx=True, ex=172800)
return result is not None
```

---

## ✅ Correctness Findings

### 🚨 C-1: FOSS Tools Don't Record Observability Metrics

**File:** server.py:835-860

The `verify_vendor_entity` tool never calls `metrics.record_gleif_check()`, and `score_transaction_risk` never calls `metrics.record_anomaly_check()`. The new observability metrics (gleif_checks, anomaly_checks, ntfy_notifications) were added to the MetricsCollector but never wired into the tool handlers.

**Impact:** GLEIF/anomaly/ntfy counters in Prometheus will permanently read 0.

**Fix:** Add metrics recording in each tool handler:
```python
@mcp.tool()
async def verify_vendor_entity(vendor_name: str, lei: str = "") -> dict:
    ...
    result = await _gleif.search_entity(vendor_name)
    metrics.record_gleif_check(verified=result.is_verified)  # ← ADD
    ...

@mcp.tool()
async def score_transaction_risk(amount: int, agent_id: str) -> dict:
    ...
    score = await _anomaly_scorer.score_transaction(...)
    metrics.record_anomaly_check(                            # ← ADD
        anomalous=score.is_anomalous,
        model_trained=score.model_trained,
    )
    ...
```

### ⚠️ C-2: Anomaly Features Written to Redis with Placeholder Z-Score

**File:** anomaly.py:156-160

`score_transaction` calls `_record_transaction()` (which writes to Redis) **before** computing the real z-score. The features dict contains `amount_zscore: 0.0` at this point. These placeholder values pollute training data.

**Fix:** Move `_record_transaction()` to AFTER the z-score is computed, or record only the base features (amount_log, hour, day) and compute z-score at training time (which `_build_feature_matrix` already does).

### ⚠️ C-3: Prometheus Histogram Buckets Are Double-Counted

**File:** observability/__init__.py:84-89 (record_decision) and lines 178-186 (render)

In `record_decision()`, the code increments **every** bucket where `ms <= bucket`:
```python
for bucket in ["5", "10", "25", "50", "100", "250", "500", "1000"]:
    if ms <= int(bucket):
        self._latency_buckets[bucket] += 1
```
This means a 3ms latency increments buckets "5", "10", "25", ..., "1000" — each bucket already represents a cumulative count.

But in `render()`, the code adds buckets together with `cumulative += count`, making the output doubly-cumulative.

**Fix:** Either:
- (a) In `record_decision`, only increment the **smallest** matching bucket. Then in `render`, compute cumulative sums. OR
- (b) Keep the current recording logic and in `render`, output each bucket's value directly (since it's already cumulative).

Option (a) is more standard:
```python
# In record_decision:
for bucket in ["5", "10", "25", "50", "100", "250", "500", "1000"]:
    if ms <= int(bucket):
        self._latency_buckets[bucket] += 1
        break  # ← Only increment one bucket
self._latency_buckets["+Inf"] += 1
```

### ⚠️ C-4: Safe Browsing CLIENT_VERSION Hardcoded

**File:** safe_browsing.py:39
```python
CLIENT_VERSION = "5.0.0"
```

Should track the actual package version to help Google's API analytics:
```python
from vyapaar_mcp import __version__
CLIENT_VERSION = __version__
```

### ⚠️ C-5: Deprecated `asyncio.get_event_loop()` in anomaly.py

**File:** anomaly.py:119
```python
self._loop = asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else None
```

This line calls `asyncio.get_event_loop()` twice, is deprecated in Python 3.12+, and `self._loop` is never used anywhere in the class. The actual scoring correctly uses `asyncio.get_running_loop()`.

**Fix:** Delete the line entirely.

### 📋 C-6: Budget Inconsistency on Razorpay Action Failure

**File:** server.py:425-434

When governance APPROVES a payout, the budget has already been atomically decremented. If the subsequent `_razorpay.approve_payout()` call fails, the budget remains spent but the payout was never approved on Razorpay:
```python
try:
    if result.decision == Decision.APPROVED:
        await _razorpay.approve_payout(payout.id)
except Exception as e:
    logger.error("Razorpay action failed for %s: %s", payout.id, e)
    # ← Budget not rolled back!
```

**Fix:** Add budget rollback on approval failure:
```python
except Exception as e:
    logger.error("Razorpay action failed for %s: %s", payout.id, e)
    if result.decision == Decision.APPROVED:
        await _redis.rollback_budget(result.agent_id, result.amount)
```

---

## ⚡ Performance Findings

### ⚠️ P-1: Go Subprocess Spawned Per Bridge Call

**File:** razorpay_bridge.py:143

Every call to `_call_tool()` spawns a new Go subprocess, initializes MCP, lists tools, executes, and shuts down. With auto-polling every 30s, this creates ~2,880 process spawns/day.

**Impact:** Process spawn overhead (~50ms each), file descriptor churn, and OS resource pressure.

**Recommendation:** Implement a persistent connection mode with reconnect-on-failure:
```python
class RazorpayBridge:
    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.is_closed:
            self._session = await self._start_persistent_session()
        return self._session
```

### ⚠️ P-2: IsolationForest Re-Trains on Every Score Request

**File:** anomaly.py:276-288

`_fit_and_score` creates a new IsolationForest, fits it on the full history matrix (up to 1000 entries × 4 features), and scores one transaction — every single call. With 100 estimators and 256 max_samples, this is O(100 × 256 × log(256)) per request.

**Recommendation:** Cache the trained model per agent with a TTL or retrain only every N transactions:
```python
if agent_id not in self._models or self._models[agent_id]["stale"]:
    model = IsolationForest(...)
    model.fit(history_matrix)
    self._models[agent_id] = {"model": model, "trained_at": len(history)}
```

### 📋 P-3: Polling Tool Creates a New PayoutPoller Each Call

**File:** server.py:475-481

`poll_razorpay_payouts` instantiates a new `PayoutPoller` every time it's called. This is wasteful since the poller has initialization overhead (logging, config validation).

**Fix:** Reuse the global `_poller` instance or cache by account number.

---

## 🔧 Error Handling Findings

### ⚠️ E-1: Generic `except Exception` Without Context Preservation

Multiple locations catch `Exception` broadly without chaining:

- server.py:300 — auto-poll callback
- server.py:430 — webhook Razorpay action
- server.py:550 — poll Razorpay action
- gleif.py:193 — catch-all for API errors

**Pattern to follow** (from python-error-handling skill):
```python
except Exception as e:
    logger.error("Razorpay action failed for %s: %s", payout.id, e, exc_info=True)
    raise GovernanceActionError(f"Failed to execute {result.decision}") from e
```

### 📋 E-2: Safe Browsing Mock Threat Types Conflate Errors with Real Threats

**File:** safe_browsing.py:115-137

On timeout/circuit-open/API-error, the code returns fake `ThreatMatch` objects with synthetic threat types like `"TIMEOUT"`, `"CIRCUIT_OPEN"`, `"API_ERROR"`. These are then logged and stored in audit_logs alongside real threats.

**Impact:** Cannot distinguish real Google-flagged threats from infrastructure errors in audit trail.

**Fix:** Add an error field to `SafeBrowsingResponse` or use a separate error response type.

### 📋 E-3: notify_with_fallback Silently Swallows All Notification Failures

**File:** ntfy_notifier.py:297-310

If both Slack and ntfy fail, the function only logs a warning and returns. For HELD payouts (requiring human approval), silent failure means the payout sits indefinitely without anyone knowing.

**Recommendation:** Record metric and consider raising or returning a failure indicator:
```python
metrics.record_ntfy_notification(success=False)
```

---

## 🏗️ Architecture & Code Quality

### ⚠️ A-1: server.py Is Too Large (918 Lines) with 15+ Global Variables

**File:** server.py

The file contains lifecycle management, 12 tool handlers, notification routing, and global state. This violates single responsibility and makes testing near-impossible.

**Recommended split:**
- `server.py` — FastMCP setup, lifespan, runner (≈100 lines)
- `tools/governance.py` — webhook, polling, vendor tools
- `tools/admin.py` — policy, budget, audit, health, metrics tools
- `tools/foss.py` — GLEIF, anomaly, risk profile tools
- `lifecycle.py` — startup/shutdown wiring
- `state.py` — `AppState` dataclass holding all service references

### 📋 A-2: GLEIFEntity and AnomalyScore Are Not Pydantic Models

**Files:** gleif.py, anomaly.py

Every other data model in the codebase uses Pydantic with `ConfigDict(strict=True)`. The FOSS modules use plain classes with manual `to_dict()` methods.

**Impact:** No validation, no JSON schema generation, inconsistent serialization.

**Fix:** Convert to `BaseModel`:
```python
class GLEIFEntity(BaseModel):
    model_config = ConfigDict(strict=True)
    lei: str
    legal_name: str
    ...
```

### 📋 A-3: GLEIF and Anomaly Modules Use `Any` Type for Redis Parameter

**Files:** gleif.py:131, anomaly.py:111

```python
def __init__(self, redis: Any | None = None, ...):
```

**Fix:** Use proper type:
```python
from vyapaar_mcp.db.redis_client import RedisClient

def __init__(self, redis: RedisClient | None = None, ...):
```

### 📋 A-4: `run_server()` Async Entry Point Is Dead Code

**File:** server.py:904-908
```python
async def run_server() -> None:
    await mcp.run_stdio_async()
```

This function is never called by any code path. `__main__.py` and `__init__.py` both use `run_server_sync()`.

**Fix:** Remove or document when it would be used.

---

## 🐳 Deployment Findings

### 📋 D-1: docker-compose.yml Uses Deprecated `version` Field

**File:** docker-compose.yml:1
```yaml
version: "3.8"  # ← Ignored by Docker Compose V2+
```

**Fix:** Remove the line entirely. Docker Compose V2 (the Go rewrite, now default) ignores this field.

### 📋 D-2: No Container Resource Limits

**File:** docker-compose.yml

The `vyapaar` service has no memory or CPU limits. With scikit-learn loading IsolationForest, memory usage can spike.

**Fix:**
```yaml
vyapaar:
  deploy:
    resources:
      limits:
        memory: 1G
        cpus: '1.0'
```

### 💡 D-3: Dockerfile HEALTHCHECK Uses Sync Redis

**File:** Dockerfile:35-36

The health check uses synchronous `redis.from_url()` while the app uses async `redis.asyncio`. Not a functional bug, but adding `redis` as a separate dependency just for the health check is unnecessary.

**Fix:** Use `redis-cli` directly:
```dockerfile
HEALTHCHECK CMD redis-cli -h redis ping || exit 1
```

---

## 🧪 Testing Assessment

### ⚠️ T-1: No Integration Tests for Server Tool Handlers

All 146 tests are unit tests that mock dependencies. No test exercises the actual tool handlers in `server.py`, which means:
- The missing `metrics.record_gleif_check()` call (C-1) was never caught
- Wiring bugs between server.py and modules go undetected

**Recommendation:** Add integration tests using `mcp.test` fixtures or direct tool function calls with real fakeredis + mock HTTP.

### 📋 T-2: Anomaly Test Is Fragile

**File:** tests/test_anomaly.py:121

`test_anomalous_transaction_scores_high` depends on IsolationForest producing specific score ordering. ML model outputs are inherently non-deterministic across scikit-learn versions. The test seeds `random_state=42` (via scoring default), which helps, but the assertion could still break on sklearn updates.

**Recommendation:** Use a wider margin or test score boundaries instead:
```python
assert outlier.risk_score >= 0.6   # Should be elevated
assert normal.risk_score <= 0.5    # Should be normal range
```

### 📋 T-3: No Tests for `notify_with_fallback` Both-Fail Scenario

**File:** tests/test_ntfy.py

Tests cover Slack-only, ntfy-only, and Slack-success paths but not the case where both Slack and ntfy are configured and both fail. This is the most critical notification path.

---

## 🎉 What's Done Well

1. **Atomic Redis budget operations** — The Lua script for check-and-increment is exactly right. No read-modify-write races.

2. **Circuit breaker pattern** — Well-implemented with proper state transitions, half-open recovery, and snapshot for health check introspection.

3. **Pydantic strict mode everywhere** — `ConfigDict(strict=True)` on all models prevents silent type coercion.

4. **Fail-closed Safe Browsing** — On timeout/error, the system rejects rather than approves. This is the correct financial posture.

5. **Idempotency across both ingress modes** — Both webhook and polling use the same Redis dedup layer, preventing double-processing.

6. **Budget rollback on post-budget rejections** — The governance engine correctly rolls back the atomic budget increment when domain/reputation checks fail after the budget check passes.

7. **Hmac.compare_digest for signature verification** — Timing-attack-safe comparison.

8. **Exponential backoff with jitter in polling** — `get_backoff_interval()` prevents thundering herd on API errors.

9. **Audit log filesystem fallback** — If PostgreSQL is down, audit entries are written to local JSON files (fail-safe).

10. **GLEIF fail-open design** — GLEIF verification is advisory, not blocking. Correct for a vendor enrichment check vs. security check.

---

## Priority Fix Order

| Priority | ID | Finding | Effort |
|----------|-----|---------|--------|
| 1 | S-1, S-2 | Remove hardcoded passwords | 15 min |
| 2 | C-1 | Wire FOSS metrics into tools | 10 min |
| 3 | S-5 | Replace `assert` with RuntimeError | 20 min |
| 4 | C-3 | Fix Prometheus histogram | 15 min |
| 5 | S-6 | Atomic idempotency key | 5 min |
| 6 | C-6 | Budget rollback on approve failure | 10 min |
| 7 | S-4 | Remove secrets from CLI args | 5 min |
| 8 | C-2 | Fix anomaly z-score recording | 10 min |
| 9 | C-5 | Remove deprecated asyncio call | 2 min |
| 10 | T-1 | Add integration tests | 2-4 hrs |

---

**Total Findings: 4 Critical, 11 High, 10 Medium, 4 Low, 10 Praise**

*Review performed using installed skills: code-review-excellence, security-auditor, python-expert-best-practices-code-review, async-python-patterns, python-error-handling*

"""Quick connectivity check for all Vyapaar MCP dependencies."""

import asyncio
import sys

sys.path.insert(0, "src")

from vyapaar_mcp.config import load_config
from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.db.postgres import PostgresClient


async def check() -> None:
    cfg = load_config()

    # Redis
    redis = RedisClient(url=cfg.redis_url)
    await redis.connect()
    redis_ok = await redis.ping()
    print("Redis:    ", "OK" if redis_ok else "FAIL")

    # PostgreSQL
    pg = PostgresClient(dsn=cfg.postgres_dsn)
    await pg.connect()
    pg_ok = await pg.ping()
    print("Postgres: ", "OK" if pg_ok else "FAIL")

    # Policies
    from vyapaar_mcp.models import AgentPolicy
    policy = await pg.get_agent_policy("default-agent")
    print("Policy:   ", "seeded" if policy else "MISSING")
    await pg.disconnect()

    # Slack
    has_slack = bool(cfg.slack_bot_token and cfg.slack_channel_id)
    print("Slack:    ", "configured" if has_slack else "not configured")

    # Config
    print("Auto-Poll:", cfg.auto_poll, f"(interval={cfg.poll_interval}s)")
    print("Rate Limit:", f"{cfg.rate_limit_max_requests} req / {cfg.rate_limit_window_seconds}s")

    # Tools
    from vyapaar_mcp.server import mcp
    tools = mcp._tool_manager._tools if hasattr(mcp, "_tool_manager") else {}
    print(f"MCP Tools: {len(tools)} registered")

    all_ok = redis_ok and pg_ok
    print("\nResult:   ", "ALL SYSTEMS GO" if all_ok else "ISSUES FOUND")


asyncio.run(check())

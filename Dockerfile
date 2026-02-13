# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy project config and lock file, install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime (slim)
FROM python:3.12-slim AS runtime
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY src/ src/

# Copy Go sidecar binary (pre-built for Linux — see README)
# COPY bin/razorpay-mcp-server bin/razorpay-mcp-server

# Set PATH to use venv + set PYTHONPATH so the package is importable
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Expose MCP SSE port
EXPOSE 8000

# Health check — verify Redis connectivity
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import redis; r = redis.from_url('redis://redis:6379/0'); r.ping()" || exit 1

# Run the MCP server
CMD ["python", "-m", "vyapaar_mcp"]

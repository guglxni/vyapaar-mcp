# Contributing to Vyapaar MCP

Thank you for your interest in contributing to Vyapaar MCP! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Go 1.25+ (for building the Razorpay sidecar)
- Docker (for Redis & PostgreSQL)
- Razorpay X Sandbox credentials

### Getting Started

```bash
# Clone the repository
git clone https://github.com/your-org/vyapaar-mcp.git
cd vyapaar-mcp

# Install dependencies
uv sync

# Build the Go sidecar
cd vendor/razorpay-mcp-server
go build -o ../../bin/razorpay-mcp-server ./cmd/razorpay-mcp-server
cd ../..

# Start infrastructure
docker compose up -d redis postgres

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run tests
uv run pytest tests/ -v
```

## Project Structure

```
vyapaar-mcp/
├── src/vyapaar_mcp/        # Core application source
│   ├── server.py           # FastMCP server & tool definitions
│   ├── config.py           # Pydantic settings
│   ├── models.py           # Domain models
│   ├── db/                 # Data layer (Redis, PostgreSQL)
│   ├── governance/         # Policy evaluation engine
│   ├── ingress/            # Webhook & polling handlers
│   ├── egress/             # Razorpay actions, Slack, ntfy
│   ├── reputation/         # Safe Browsing, GLEIF, anomaly detection
│   ├── observability/      # Prometheus metrics
│   ├── resilience/         # Circuit breaker, rate limiting
│   └── audit/              # Audit logging
├── tests/                  # Test suite
├── scripts/                # Operational scripts
├── demo/                   # Demo applications
├── docs/                   # Documentation
├── deploy/                 # Deployment configurations
└── vendor/                 # Third-party dependencies (gitignored)
```

## Code Standards

### Style

- **Formatter:** [Ruff](https://docs.astral.sh/ruff/) — runs automatically
- **Type Checking:** `mypy --strict`
- **Python Version:** 3.12+ features encouraged (type unions `X | Y`, etc.)

### Conventions

- All models use **Pydantic V2** `BaseModel`
- All I/O operations are **async** (`async def` / `await`)
- Budget operations use **atomic Redis** commands (Lua scripts, no read-modify-write)
- External API calls are wrapped in **circuit breakers**
- Configuration via **environment variables** with `VYAPAAR_` prefix

### Testing

```bash
# Run full test suite
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=vyapaar_mcp --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_governance.py -v
```

All pull requests must:
- Pass the full test suite
- Include tests for new functionality
- Not decrease code coverage

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Ensure all tests pass (`uv run pytest tests/ -v`)
5. Run the linter (`uv run ruff check src/ tests/`)
6. Run type checking (`uv run mypy src/`)
7. Submit a pull request with a clear description

## Reporting Issues

When filing an issue, please include:
- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS

## License

By contributing, you agree that your contributions will be licensed under the [GNU Affero General Public License v3.0](LICENSE).

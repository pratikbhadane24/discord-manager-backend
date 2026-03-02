# T-Backend-Python

A production-ready FastAPI microservice template built with UV and Granian.

## Features

- ⚡ **FastAPI** - Modern, fast (high-performance) web framework
- 📦 **UV** - Lightning-fast Python package installer and resolver
- 🚀 **Granian** - High-performance ASGI server written in Rust
- 🔐 **JWT Authentication** - Secure token-based authentication
- ✅ **Pydantic v2** - Data validation using Python type annotations
- 🧪 **Pytest** - Comprehensive test suite with async support
- 🎨 **Ruff** - Fast Python linter and formatter
- 🐳 **Docker** - Container-ready with optimized Dockerfile
- 📚 **API Documentation** - Auto-generated with Swagger UI and ReDoc

## Quick Start

### Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager

### Installation

1. Install UV:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone and setup:
```bash
git clone <repository-url>
cd T-backend-python
uv sync
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env and set JWT_SECRET_KEY
```

4. Run the application:
```bash
uv run granian --interface asgi --host 0.0.0.0 --port 8000 app.main:app --reload
```

5. Visit http://localhost:8000/docs for API documentation

## Project Structure

```
T-backend-python/
├── app/
│   ├── api/endpoints/      # API route handlers
│   ├── core/               # Configuration and security
│   ├── models/             # Pydantic models
│   ├── services/           # Business logic layer
│   ├── database/           # Database models and connections
│   ├── utils/              # Utility functions
│   └── main.py             # Application entry point
├── tests/                  # Test suite
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
├── Dockerfile              # Docker configuration
└── .env.example            # Environment template
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app

# Run specific test file
uv run pytest tests/test_endpoints.py
```

### Linting and Formatting

```bash
# Check code style
uv run ruff check .

# Format code
uv run ruff format .
```

### Docker

```bash
# Build image
docker build -t t-backend-python .

# Run container
docker run -p 8000:8000 --env-file .env t-backend-python
```

## API Endpoints

### Health Checks (Public)
- `GET /api/health` - Service health status
- `GET /api/health/ready` - Readiness probe
- `GET /api/health/live` - Liveness probe

### Example CRUD (Authenticated)
- `GET /api/examples` - List items
- `GET /api/examples/{id}` - Get item
- `POST /api/examples` - Create item
- `PUT /api/examples/{id}` - Update item
- `DELETE /api/examples/{id}` - Delete item

## Authentication

JWT tokens are required for protected endpoints. Include the token in requests:

```bash
Authorization: Bearer <your-jwt-token>
```

Generate a test token:
```python
from app.core.security import create_access_token
token = create_access_token({"sub": "user123"})
```

## Configuration

Key environment variables (see `.env.example`):

- `APP_NAME` - Application name
- `APP_VERSION` - Application version
- `JWT_SECRET_KEY` - Secret key for JWT signing (required)
- `JWT_ALGORITHM` - JWT algorithm (default: HS256)
- `DATABASE_URL` - Database connection string (optional)
- `API_PREFIX` - API route prefix (default: /api)

## Documentation

- [Setup Guide](docs/setup.md) - Detailed setup instructions
- [API Documentation](docs/api.md) - Complete API reference

## Tech Stack

- **Framework:** FastAPI 0.104+
- **Server:** Granian 1.1+
- **Validation:** Pydantic 2.5+
- **Auth:** python-jose with cryptography
- **Testing:** pytest, pytest-asyncio, httpx
- **Linting:** Ruff
- **Package Manager:** UV

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.
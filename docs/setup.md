# Setup Guide

This guide will help you set up and run the T-Backend-Python microservice.

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

### 1. Install UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone the Repository

```bash
git clone <repository-url>
cd T-backend-python
```

### 3. Install Dependencies

```bash
uv sync
```

This will create a virtual environment and install all dependencies.

### 4. Configure Environment

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` and set the required values:
- `JWT_SECRET_KEY`: A secure random string for JWT signing
- `DATABASE_URL`: Your database connection string (optional)

## Running the Application

### Development Mode

Run with UV:

```bash
uv run granian --interface asgi --host 0.0.0.0 --port 8000 app.main:app --reload
```

The `--reload` flag enables auto-reload on code changes.

### Production Mode

Run with UV:

```bash
uv run granian --interface asgi --host 0.0.0.0 --port 8000 app.main:app
```

For production, consider using process managers like systemd or supervisor.

## Running Tests

Run all tests:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=app --cov-report=html
```

Run specific test file:

```bash
uv run pytest tests/test_endpoints.py
```

## Linting and Formatting

Check code style:

```bash
uv run ruff check .
```

Format code:

```bash
uv run ruff format .
```

## Docker

### Build Docker Image

```bash
docker build -t t-backend-python .
```

### Run Docker Container

```bash
docker run -p 8000:8000 --env-file .env t-backend-python
```

## API Documentation

Once the application is running, access the interactive API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Health Checks

- Health: http://localhost:8000/api/health
- Readiness: http://localhost:8000/api/health/ready
- Liveness: http://localhost:8000/api/health/live

## Project Structure

```
T-backend-python/
├── app/                    # Application source code
│   ├── api/               # API endpoints
│   ├── core/              # Core configuration and security
│   ├── models/            # Pydantic models
│   ├── services/          # Business logic
│   ├── database/          # Database layer
│   └── utils/             # Utility functions
├── tests/                 # Test suite
├── docs/                  # Documentation
├── pyproject.toml         # Project configuration
├── Dockerfile             # Docker configuration
└── .env.example           # Environment variables template
```

## Troubleshooting

### Port Already in Use

If port 8000 is already in use, specify a different port:

```bash
uv run granian --interface asgi --host 0.0.0.0 --port 8080 app.main:app
```

### Database Connection Issues

Ensure your `DATABASE_URL` is correctly configured in `.env`. The application will work without a database using in-memory storage for demonstration purposes.

### JWT Secret Key

Always use a strong, randomly generated secret key in production. Generate one using:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

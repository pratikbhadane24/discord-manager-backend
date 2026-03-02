# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY app ./app

# Expose port
EXPOSE 8000

# Run the application with Granian
CMD ["uv", "run", "granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "app.main:app"]

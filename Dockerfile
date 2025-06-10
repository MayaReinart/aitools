# Use Python 3.11 as base image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VERSION=1.7.1
ENV PATH="/opt/poetry/bin:$PATH"

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry POETRY_VERSION=$POETRY_VERSION python3 - && \
    chmod a+x /opt/poetry/bin/poetry

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY src/ src/
COPY web/ web/

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --no-dev

# Copy the rest of the application
COPY . .

# Install the application
RUN poetry install --no-interaction --no-ansi --only main

# Expose the port fly.io expects
EXPOSE 8080

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

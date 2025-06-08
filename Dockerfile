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

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry POETRY_VERSION=$POETRY_VERSION python3 - && \
    chmod a+x /opt/poetry/bin/poetry

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY src/ src/

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --no-dev

# Copy the rest of the application
COPY . .

# Install the application
RUN poetry install --no-interaction --no-ansi --only main

# API target
FROM base as api
EXPOSE 8080
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Worker target
FROM base as worker
CMD ["poetry", "run", "celery", "-A", "celery_worker", "worker", "--loglevel=info"]

# API Introspection

A service that analyzes OpenAPI specifications and generates natural language summaries and documentation using AI.

## Features

- Upload and parse OpenAPI specifications (JSON/YAML)
- Generate natural language summaries of API endpoints
- Export summaries in multiple formats (Markdown, HTML, DOCX)
- Asynchronous processing with job status tracking
- Structured logging and error handling
- Simple web interface for file uploads and results access

## Tech Stack

| Component          | Technology                               | Purpose                                                               |
|-------------------|------------------------------------------|-----------------------------------------------------------------------|
| Framework         | FastAPI                                  | Modern async web framework with automatic OpenAPI/Swagger docs         |
| Task Queue        | Celery + Redis                          | Background processing for API analysis and summary generation          |
| Configuration     | pydantic-settings                       | Type-safe configuration management with environment variables          |
| Logging           | Loguru                                  | Structured logging with customizable formatting                        |
| Testing           | pytest + pytest-asyncio                  | Async-aware testing with comprehensive fixtures                        |
| Code Quality      | Ruff, MyPy, pre-commit                  | Linting, type checking, and automated code quality checks             |
| AI Integration    | OpenAI API                              | Natural language processing for API analysis                           |
| Frontend          | Tailwind CSS                            | Minimal web interface for file uploads and results                     |

## Project Structure

```
api_introspection/
├── src/
│   ├── api/
│   │   ├── routes.py          # FastAPI route definitions
│   │   └── models.py          # Request/response Pydantic models
│   ├── core/
│   │   ├── config.py          # Environment and app configuration
│   │   ├── storage.py         # Job data storage management
│   │   └── logging/           # Logging package
│   │       ├── __init__.py    # Package exports
│   │       ├── config.py      # Logging configuration
│   │       ├── core.py        # Core logging functionality
│   │       └── handlers.py    # Custom logging handlers
│   ├── services/
│   │   └── openai.py          # OpenAI API integration
│   └── tasks/
│       └── tasks.py           # Celery task definitions
├── web/
│   └── index.html            # Simple web interface for file uploads
├── tests/
│   ├── test_routes.py         # API endpoint tests
│   └── conftest.py            # pytest fixtures and configuration
├── celery_worker.py           # Celery worker configuration
├── pyproject.toml            # Project dependencies and tools config
└── DEBUGGING.md              # Development and debugging guide
```

## Usage

### Web Interface

The service provides a simple web interface for file uploads and results access:

1. Open your browser and navigate to `http://localhost:8080`
2. Use the file upload form to submit your OpenAPI specification
3. Wait for the analysis to complete
4. Download the results in your preferred format (Markdown or HTML)

### API Endpoints

For programmatic access, you can use the following API endpoints:

#### 1. Health Check

```http
GET /api/health
```

Response:
```json
{
    "status": "healthy"
}
```

#### 2. Upload OpenAPI Specification

```http
POST /api/spec/upload
```

**Request:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | File (multipart/form-data) | Yes | OpenAPI spec file (JSON/YAML) |

**Supported Content Types:**
- application/json
- text/yaml
- application/x-yaml
- text/plain
- text/x-yaml

**Response:**
```json
{
    "job_id": "string"  // UUID for tracking the analysis job
}
```

**Error Responses:**
- 400: Invalid file type or no file provided
- 500: Server error during file processing

#### 3. Get Summary

```http
GET /api/spec/{job_id}/summary
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string (path) | Yes | Job ID from upload response |

**Response States:**
1. Processing:
```json
{
    "detail": "Job is still processing"
}
```
Status Code: 202 Accepted

2. Completed:
```json
{
    "status": "SUCCESS",
    "result": {
        // Summary content structure
        "endpoints": [...],
        "schemas": [...],
        "overview": "string"
    }
}
```
Status Code: 200 OK

3. Failed:
```json
{
    "detail": "Job failed"
}
```
Status Code: 500 Internal Server Error

#### 4. Export Summary

```http
GET /api/spec/{job_id}/export
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string (path) | Yes | Job ID from upload response |
| file_format | string (query) | No | Export format: "md" (default), "html", or "docx" |

**Response:**
- Format: Markdown (default)
  - Content-Type: text/markdown
  - Filename: api-summary-{job_id}.md
- Format: HTML
  - Content-Type: text/html
  - Direct HTML content
- Format: DOCX
  - Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
  - Filename: api-summary-{job_id}.docx

**Error Responses:**
- 404: Job not found
- 400: Unsupported file format
- 500: Export generation error

## Setup

1. Clone the repository
2. Install dependencies:
```bash
poetry install
```

3. Create `.env` file with required variables:
```env
OPENAI_API_KEY=your_api_key
ENV=development
LOG_LEVEL=DEBUG
REDIS_URL=redis://localhost:6379
```

4. Start Redis:
```bash
docker run -d -p 6379:6379 redis
```

5. Start Celery worker:
```bash
poetry run celery -A celery_worker worker --loglevel=info
```

6. Start the API server:
```bash
poetry run uvicorn src.main:app --reload
```

## Development

The project includes a Makefile with several useful commands to help with development:

### Code Quality

```bash
make pc           # Run all code quality checks (ruff, mypy, pre-commit)
make fix         # Run pre-commit hooks to fix code style issues
```

### Development Server

```bash
make run         # Start the FastAPI development server with hot reload
make celery      # Start the Celery worker
make redis       # Start Redis server in daemon mode
make dev         # Start complete development environment (API + Celery + Redis)
```

### Cleanup

```bash
make clean       # Stop all development processes (API, Celery, Redis)
```

### All Commands

| Command | Description |
|---------|-------------|
| `make pc` | Run all code quality checks (ruff linting, formatting, mypy type checking, pre-commit hooks) |
| `make fix` | Run pre-commit hooks to automatically fix code style issues |
| `make test` | Run the test suite |
| `make run` | Start the FastAPI development server on port 8080 with hot reload |
| `make celery` | Start the Celery worker for background task processing |
| `make redis` | Start Redis server in daemon mode |
| `make dev` | Start the complete development environment (cleans up existing processes, starts Redis, API, and Celery) |
| `make clean` | Stop all development processes (API server, Celery worker, Redis) |

## Testing

Run the test suite:
```bash
poetry run pytest
```

With coverage:
```bash
poetry run pytest --cov=src
```

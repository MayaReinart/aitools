# API Introspection

## Project Architecture

### Overview

The Async Summarizer SaaS API is designed as a modular, scalable, and testable backend system for document summarization. It uses modern Python tooling and best practices to mimic production-level architecture in a focused, portfolio-grade scope.

### Tech Stack

| Layer             | Tooling                                   | Why it was chosen                                                        |
| ----------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| API framework     | `FastAPI`                                 | Fast, modern, async-native Python web framework with Pydantic validation |
| Background jobs   | `Celery` or `FastAPI.BackgroundTasks`     | Offload summarization work to non-blocking queues                        |
| Auth & security   | `FastAPI`, `python-jose`, `passlib` (JWT) | Demonstrate token-based authentication                                   |
| Logging           | `Loguru` with custom handlers             | Simple, powerful logging with flexible formatting and redirection        |
| Config management | `python-dotenv` + env vars                | Decouple config from code, keep secrets out of Git                       |
| Queue/broker      | `Redis` or `RabbitMQ`                     | Reliable job queuing and retry infrastructure                            |
| Deployment target | `AWS Lambda` or `ECS`, optionally Docker  | Show familiarity with AWS and containerization                           |
| Storage           | `S3`                                      | Store original files and logs; simulate production file management       |
| AI summarization  | `LlamaIndex`, `LangChain`, or OpenAI API  | Modular summarization engine with optional fallback and benchmarking     |

### Structure

```
api_introspection/
├── main.py                # Entry point for FastAPI
├── config.py              # Loads .env and central config
├── logging_config.py      # Loguru setup with structured logs
├── api/
│   ├── routes.py          # API endpoints
│   └── models.py          # Pydantic schemas
├── services/
│   └── summarizer.py      # LLM integration logic
├── tasks/
│   └── queue.py           # Background job handler (Celery or other)
└── utils/                 # Helpers, validation, S3, etc.
```

### Key Design Decisions

#### Async First

Most modern APIs benefit from async support — especially when using I/O-heavy tasks like file processing, LLM API calls, and database or storage access.

- FastAPI + async routes

- Background task queue to avoid blocking main event loop

#### Queue-Based Architecture

Summarization tasks can take several seconds or more. Rather than tying up client requests, jobs are enqueued and processed in the background.

- Enables retry logic, parallelism, and performance monitoring

- Client can poll job status or get notified via webhook/email (optional)

#### Structured Logging with Loguru

Used to:

- Capture FastAPI/uvicorn logs uniformly

- Add context (e.g., request IDs, timestamps)

- Redirect to stdout, file, or S3

This matches production setups where logs are monitored or piped to observability stacks.

#### Environment-Based Configuration

.env file loaded with python-dotenv, supporting .env.template for safe sharing.

This makes the project easy to configure, deploy, and containerize — without hardcoding secrets.

#### Extensibility

The services/summarizer.py layer abstracts the summarization engine (e.g., OpenAI, LlamaIndex). This makes it easy to swap models or prompt strategies during testing or benchmarking.

### Possible Enhancements

- Add retry + failure handling in Celery

- Add job dashboard or Slack/email notifications

- Track metrics (request latency, job duration) with Prometheus/Grafana

- Auto-cleanup of old logs/files in S3

- API rate-limiting or quota (e.g. per user or token)

## Usage

TODO

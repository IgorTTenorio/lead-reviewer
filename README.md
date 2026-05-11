# Lead Reviewer

A modular Python system that ingests WhatsApp Business events from Evolution API, stores messages in PostgreSQL, groups them into client conversations, builds pandas DataFrames for the last 24 hours, and analyzes purchase intent with a pluggable AI layer.

## Architecture Overview

The system is organized into a few clear layers:

- `app/api/routes/`
  - FastAPI HTTP endpoints for health, webhook ingestion, and review dispatch.
- `app/services/`
  - Application services for Evolution payload normalization, conversation assignment, AI analysis, and review dispatching.
- `app/repositories/`
  - Data access and persistence logic for clients, conversations, messages, products, and conversation reviews.
- `app/pipelines/`
  - Last-24h message extraction, DataFrame building, grouping, text rendering, and review execution.
- `app/models/`
  - SQLAlchemy models for the normalized relational schema.
- `worker/`
  - Celery worker configuration and asynchronous review task execution.
- `alembic/`
  - Database migration wiring and schema migration history.
- `tests/`
  - Pytest coverage for normalization, idempotency, and conversation grouping.

## Core Flow

1. Evolution API sends a webhook to `POST /api/webhooks/evolution`.
2. The payload is normalized into a message contract.
3. The system resolves the client by phone and assigns the message to a conversation.
4. The raw payload and normalized message data are stored in the database.
5. A review job fetches the last 24 hours of messages.
6. Messages are converted into a pandas DataFrame and grouped by conversation.
7. Each grouped conversation is rendered as chronological text.
8. The AI layer classifies whether the customer wants to continue the purchase.
9. Results are stored in `conversation_reviews`.

## Data Model

Main tables:

- `clients`
- `products`
- `conversations`
- `messages`
- `conversation_reviews`

Important design choices:

- UUID primary keys
- `messages.external_message_id` is unique for idempotency
- `messages.raw_payload` is stored as JSON/JSONB
- conversations are scoped by `client_id` and optionally `product_id`
- reviews are unique per conversation and review window

## Project Tree

```text
.
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── app
│   ├── api
│   ├── core
│   ├── db
│   ├── models
│   ├── pipelines
│   ├── repositories
│   ├── schemas
│   ├── services
│   └── utils
├── alembic
│   └── versions
├── docker
│   └── app
├── tests
└── worker
```

## Requirements

- Python 3.12+
- PostgreSQL 16+
- Redis 7+ for asynchronous worker mode
- Docker and Docker Compose for the full containerized stack

## Environment Variables

Example variables are provided in `.env.example`.

Core application:

- `APP_NAME`
- `APP_ENV`
- `LOG_LEVEL`
- `DATABASE_URL`
- `ALEMBIC_DATABASE_URL`

AI configuration:

- `AI_PROVIDER`
- `AI_MODEL`
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_TIMEOUT_SECONDS`

Celery configuration:

- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_TASK_ALWAYS_EAGER`
- `CELERY_TASK_EAGER_PROPAGATES`

## Running With Docker Compose

The intended production-style local stack is:

```bash
docker compose up --build
```

Services started by Compose:

- `db`
- `redis`
- `app`
- `worker`

The API will be available at:

```text
http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Notes:

- the API container runs `alembic upgrade head` on startup
- the worker container starts Celery with Redis as broker/backend
- default AI mode is `mock` unless a real provider is configured

## Running Locally Without Docker

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
. .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Set environment variables.

```bash
cp .env.example .env
```

4. Point `DATABASE_URL` to PostgreSQL or a local validation database.

5. Run migrations.

```bash
alembic upgrade head
```

6. Start the API.

```bash
uvicorn app.main:app --reload
```

7. Start the worker.

```bash
celery -A worker.main.celery_app worker --loglevel=INFO
```

## Webhook Ingestion

Endpoint:

```text
POST /api/webhooks/evolution
```

Behavior:

- accepts Evolution API JSON payloads
- ignores unsupported events and unsupported chat types like groups/broadcasts
- extracts normalized fields:
  - `external_message_id`
  - `phone`
  - `text`
  - `timestamp`
  - `direction`
  - optional `product_external_id`
- stores `raw_payload`
- is idempotent by `external_message_id`

### Example Webhook Request

```bash
curl -X POST http://localhost:8000/api/webhooks/evolution \
  -H 'Content-Type: application/json' \
  -d '{
    "event": "MESSAGES_UPSERT",
    "data": {
      "key": {
        "remoteJid": "15551234567@s.whatsapp.net",
        "fromMe": false,
        "id": "wamid-123"
      },
      "pushName": "Taylor",
      "message": {
        "conversation": "I want to continue with the purchase."
      },
      "messageTimestamp": "1777010400",
      "productId": "sku-123"
    }
  }'
```

### Example Webhook Response

```json
{
  "status": "processed",
  "message_id": "<uuid>",
  "conversation_id": "<uuid>",
  "duplicate": false,
  "detail": null,
  "event_name": "MESSAGES_UPSERT",
  "processed_at": "2026-04-24T19:06:47.183393Z"
}
```

If the same message is received again, the response will return:

```json
{
  "status": "duplicate",
  "duplicate": true,
  "detail": "message already stored"
}
```

## Conversation Logic

Conversation assignment rules:

- client identity is resolved by normalized phone number
- a new client is created if none exists
- conversations are grouped by:
  - `client_id`
  - plus `product_id` when a product identifier is present
- `conversations.last_message_at` is updated whenever a newer message is stored

## DataFrame Pipeline

Main pipeline functions:

- `fetch_last_day_messages()`
- `build_dataframe()`
- `group_conversations()`
- `conversation_to_text()`

Rendered conversation format:

```text
[2026-04-24T08:00:00Z] CLIENT: I want to buy.
[2026-04-24T08:05:00Z] COMPANY: Sure, I can help with that.
```

## AI Analysis

Main entrypoint:

- `app/services/ai_service.py`

Structured output fields:

- `wants_to_continue`
- `confidence`
- `stage`
- `summary`
- `evidence`
- `next_action`

Classification rules:

- clear buying signals -> `true`
- clear rejection -> `false`
- uncertainty or insufficient evidence -> `null`

Provider support:

- `mock`
- `openai_compatible`

The AI layer is intentionally pluggable so the system is not locked to one vendor.

## Review Pipeline

Synchronous review execution:

- `app/pipelines/review_pipeline.py`
- `review_last_day(db, now=None)`

Asynchronous review execution:

- Celery task: `worker.tasks.review_last_day`
- enqueue endpoint: `POST /api/reviews/last-day`

### Example Review Dispatch Request

```bash
curl -X POST http://localhost:8000/api/reviews/last-day
```

### Example Review Dispatch Response

```json
{
  "status": "queued",
  "task_id": "<celery-task-id>"
}
```

## Running Tests

```bash
pytest -q
```

Current test coverage includes:

- message normalization
- idempotent insert behavior
- conversation grouping and text rendering

## Current Validation Status

Implemented and validated in this repository:

- webhook normalization and idempotent persistence
- conversation assignment
- last-24h DataFrame pipeline
- AI review pipeline
- Celery task path in eager mode
- pytest suite passing

Important limitation from the current environment:

- `docker compose up` could not be executed here because no Docker/Podman engine was installed in the execution environment
- the Dockerfile and Compose stack were implemented and statically validated, but not runtime-verified in this session

## Mocked Components

Currently mocked by default:

- AI inference, via `AI_PROVIDER=mock`

To use a real model provider, set:

- `AI_PROVIDER=openai_compatible`
- `AI_BASE_URL`
- `AI_MODEL`
- `AI_API_KEY`

## Next Extension Ideas

- add authenticated admin endpoints for review status and metrics
- support richer product extraction from catalog/message payloads
- add retry/backoff and dead-letter behavior for Celery tasks
- expand tests to include API routes and review persistence assertions

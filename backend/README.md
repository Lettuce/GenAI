# Backend

Quick commands for the FastAPI service.

## Setup
From the backend folder, install dependencies:

```bash
uv sync --group dev
```

## Run locally
Start the app in development mode:

```bash
uv run uvicorn app.main:app --reload
```

Check the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

## Tests
Run the test suite:

```bash
uv run pytest
```

Use Ctrl+C to stop the development server.

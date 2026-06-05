# Railway deployment

This repo deploys to Railway as two services from one GitHub repo:

- `backend/` — FastAPI + Uvicorn, stateless, talks to Supabase and OpenAI.
- `frontend/` — Vite React build served by Caddy.

Supabase stays hosted at Supabase. Do not add Railway Postgres for this app.

These steps follow Railway's current docs for monorepos, public `PORT` binding, pre-deploy commands, and React SPA routing.

## 1. Before Railway

Have these ready:

- A GitHub repo with this project pushed.
- A Supabase project from [Supabase setup](supabase-setup.md).
- An OpenAI API key.
- Production data loaded in Supabase, or be ready to run the ingestion step below.

## 2. Create the backend service

1. In Railway, click **New Project**.
2. Choose **Deploy from GitHub repo** and select this repo.
3. Name the service `document-copilot-backend`.
4. Open the service **Settings**:
   - **Root Directory:** `/backend`
   - **Healthcheck Path:** `/health`
   - Leave build and start commands blank. Railway uses `backend/Dockerfile`.
5. Open **Variables** and add:

```text
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-secret-key
DATABASE_URL=postgresql://postgres:your-password@db.your-project-ref.supabase.co:5432/postgres
OPENAI_API_KEY=sk-your-openai-api-key
ALLOWED_ORIGINS=http://localhost:5173
```

Use the direct Supabase database URL, not the transaction pooler URL.

1. In **Settings** → **Deploy**, set the pre-deploy command:

```bash
uv run alembic upgrade head
```

1. Deploy the service.
1. Open **Networking** and generate a public domain.
1. Visit:

```text
https://your-backend.up.railway.app/health
```

You should see `{"status":"ok"}`.

## 3. Create the frontend service

1. In the same Railway project, click **New** → **GitHub Repo** and select this repo again.
2. Name the service `document-copilot-frontend`.
3. Open the service **Settings**:
   - **Root Directory:** `/frontend`
   - **Healthcheck Path:** `/health`
   - Leave build and start commands blank. Railway uses `frontend/Dockerfile`.
4. Open **Variables** and add these before deploying:

```text
VITE_API_BASE_URL=https://your-backend.up.railway.app
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
```

`VITE_*` values are baked into the frontend build, so redeploy the frontend after changing them.

1. Deploy the service.
1. Open **Networking** and generate a public domain.

## 4. Wire production URLs

1. Copy the frontend Railway URL.
2. Update the backend service variable:

```text
ALLOWED_ORIGINS=https://your-frontend.up.railway.app
```

1. Redeploy the backend.
1. In Supabase, open **Authentication** → **URL Configuration**:
   - **Site URL:** `https://your-frontend.up.railway.app`
   - **Redirect URLs:** add `https://your-frontend.up.railway.app/*`

Keep `http://localhost:5173/*` too if you still run local development.

## 5. Load or refresh corpus data

Migrations run on Railway through the backend pre-deploy command. Document ingestion is still a manual backend job against Supabase.

From your local machine, with production env values in `backend/.env`:

```bash
cd backend
uv run python -m ingest.load_source_documents
uv run python -m ingest.chunk_and_embed --all
```

Skip this if production Supabase already has source documents and chunks.

## 6. Final check

1. Open the frontend Railway URL.
2. Sign up or sign in with email.
3. Send a chat question.
4. If the frontend cannot reach the API, check:
   - `VITE_API_BASE_URL` equals the backend Railway URL.
   - `ALLOWED_ORIGINS` equals the frontend Railway URL.
   - The backend `/health` endpoint returns `{"status":"ok"}`.
   - Supabase URL/auth keys match the same Supabase project.

Do not set `PORT` yourself. Railway provides it automatically.

# Deploying Ledgerly

Two pieces: the FastAPI backend (needs Postgres, a disk, and tesseract, all
handled by the Docker image) and the static React frontend. Deploy the backend
first, then point the frontend at it.

Recommended: **backend on Render** and **frontend on Vercel**. Railway works the
same way if you prefer it; the env vars are identical.

Estimated time: ~15 minutes. Cost: **free, no credit card**, if you use the free
path below (single web service, SQLite, no Postgres/disk). The only paid thing is
the Anthropic API key, a few cents for the demo — and Haiku is the default to
keep even that minimal.

> Why free needs no card: on Render, the free **web service** requires no card.
> A managed **Postgres database** and a persistent **disk** do. So the free path
> skips both — the app falls back to SQLite and re-seeds sample data on startup.
> The trade-off is that uploaded data resets when the service restarts, which is
> fine for a demo. To keep data permanently, see "Paid upgrade" at the bottom.

## 0. Push to GitHub

```bash
cd ledgerly
git init && git add . && git commit -m "ledgerly"
# create a repo on github.com, then:
git remote add origin https://github.com/<you>/ledgerly.git
git push -u origin main
```

## 1. Backend on Render (free, no card)

Two ways. The **manual Web Service** route is the surest way to avoid the card
prompt, because you add only the free web service and nothing that requires
billing.

### Manual (recommended for the free tier)

1. Go to https://dashboard.render.com → **New** → **Web Service**.
2. Connect your GitHub repo `mohitmm806/ledgerly`.
3. Settings:
   - **Root Directory:** `backend`
   - **Runtime / Language:** Docker (Render detects `backend/Dockerfile`)
   - **Instance Type:** **Free**
4. Add environment variables (**Advanced** → Add Environment Variable):
   - `SEED_ON_STARTUP` = `true`
   - For the model (pick one provider):
     - **Free (recommended):** `LLM_PROVIDER` = `groq` and `GROQ_API_KEY` =
       your free Groq key (get one at https://console.groq.com, no credit card).
     - **Anthropic:** `LLM_PROVIDER` = `anthropic` and `LLM_API_KEY` = your key
       (pay-as-you-go).
   - Without a working provider, extraction + NL query return a clear error and
     the rest of the app still works.
   - (leave `CORS_ORIGINS` for now; you'll set it after the frontend exists)
   - Do **not** add a database or a disk — those are what trigger the card.
5. Create the service. First build takes a few minutes (it installs tesseract).
6. Note the URL, e.g. `https://ledgerly-api.onrender.com`. Check `/health`
   returns `{"status":"ok"}`.

The app uses SQLite by default (no `DATABASE_URL` needed) and `SEED_ON_STARTUP`
loads sample invoices on boot, so a reviewer sees a populated app immediately.

### Blueprint (only if it doesn't ask for a card)

`render.yaml` is set to the free config (web service only, no Postgres/disk). If
the Blueprint flow still prompts for billing, use the manual route above.

## 2. Frontend on Vercel

1. Go to https://vercel.com → **Add New** → **Project** → import the same repo.
2. Set **Root Directory** to `frontend`.
3. Add an environment variable:
   - `VITE_API_BASE` = your Render API URL (e.g. `https://ledgerly-api.onrender.com`)
   - This is read at build time, so it must be set before you deploy.
4. Deploy. Vercel runs `npm run build` and serves the static site.
5. Note the URL, e.g. `https://ledgerly.vercel.app`.

## 3. Connect them (CORS)

The backend only accepts browser requests from origins you allow. Add the Vercel
URL:

1. In Render → the API service → **Environment** → set
   `CORS_ORIGINS = https://ledgerly.vercel.app`
   (comma-separate if you have more than one).
2. Save; Render redeploys. Done.

Open the Vercel URL. You should see seeded invoices; click one, hit **Extract
invoice** (needs the API key), then click a field to see it highlighted on the
source.

## Gotchas (already handled, but good to know)

- **Postgres URL scheme.** Render hands out `postgres://...`; SQLAlchemy needs
  `postgresql+psycopg2://...`. The app normalizes this automatically, so the
  connection string works as-is.
- **File storage.** Grounding renders the source page from the uploaded file, so
  those files must persist. The `render.yaml` mounts a 1 GB disk at `/data` and
  points `STORAGE_DIR` there. Without a disk, files vanish on redeploy and only
  re-seeded samples would render.
- **Free tier cold starts.** Render's free web service sleeps when idle; the
  first request after a nap takes ~30s to wake. Fine for a demo; mention it in
  your README if you like.

## Minimizing API cost

The default model is Sonnet. For the cheapest runs, switch to Haiku in
`backend/app/extraction/llm.py` (the `AnthropicLLM` default model), which is
plenty for invoice extraction. Either way the demo costs cents, not dollars.

## Alternative: Railway

Same shape. Create a project from the repo, add a Postgres plugin, add a volume
mounted at `/data`, and set the same env vars (`DATABASE_URL`, `STORAGE_DIR=/data/storage`,
`SEED_ON_STARTUP=true`, `CORS_ORIGINS`, `LLM_API_KEY`). Deploy the frontend on
Vercel exactly as above.

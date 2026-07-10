from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import documents, queries


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup rather than at import time, so importing the app
    # (e.g. in tests, which supply their own database) has no side effects.
    # A migration tool (Alembic) is the Day-5 hardening step; for now this keeps
    # setup to a single command.
    Base.metadata.create_all(bind=engine)

    # Optionally load sample data on boot (used on ephemeral hosts). Failures
    # here must never take the app down, so they're swallowed with a log line.
    if settings.seed_on_startup:
        try:
            from seed import seed_if_empty

            seed_if_empty()
        except Exception as exc:  # pragma: no cover - best-effort convenience
            print(f"Startup seed skipped: {exc}")
    yield


app = FastAPI(title="Ledgerly", version="0.1.0", lifespan=lifespan)

# Allowed browser origins come from config; the deployed frontend URL must be
# added there (see DEPLOY.md).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(queries.router)


@app.get("/health")
def health():
    return {"status": "ok"}

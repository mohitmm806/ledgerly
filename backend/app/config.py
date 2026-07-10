from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment / .env.

    DATABASE_URL defaults to a local SQLite file so the app runs with zero
    external dependencies. docker-compose overrides it to point at Postgres.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./ledgerly.db"

    # Where uploaded source files are stored on disk.
    storage_dir: Path = Path("./storage")

    # OCR is only attempted for image/scanned inputs. Set to False to skip
    # (useful in environments without the tesseract binary installed).
    enable_ocr: bool = True

    # Comma-separated list of browser origins allowed to call the API. The
    # deployed frontend's URL must be added here (see DEPLOY.md).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # When true, load sample invoices on startup if the DB is empty. Handy on
    # ephemeral hosts so a reviewer never sees a blank app.
    seed_on_startup: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Managed Postgres (e.g. Render) hands out a "postgres://" URL, but
        # SQLAlchemy + psycopg2 want "postgresql+psycopg2://". Normalize so the
        # provider's connection string works as-is.
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+psycopg2://", 1
            )
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

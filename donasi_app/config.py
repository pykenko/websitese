import os
from pathlib import Path

class AppConfig:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.static_dir = self.base_dir / "page"
        self.uploads_dir = self.base_dir / "uploads"
        self.secret_key = os.environ.get("SECRET_KEY", "BINAKASIH")
        self.database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://donasi:donasi@localhost:5432/donasi",
        )
        self.db_startup_retries = int(os.environ.get("DB_STARTUP_RETRIES", "30"))
        self.db_startup_delay = float(os.environ.get("DB_STARTUP_DELAY", "1"))

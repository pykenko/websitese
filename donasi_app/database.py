import time

import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

from .config import AppConfig


class Database:
    def __init__(self, config: AppConfig):
        self.config = config

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.config.database_url, row_factory=dict_row)

    def ping(self) -> None:
        with self.connect() as conn:
            conn.execute("SELECT 1")

    def wait_until_ready(self) -> None:
        last_error: Exception | None = None

        for _ in range(self.config.db_startup_retries):
            try:
                self.ping()
                return
            except psycopg.Error as exc:
                last_error = exc
                time.sleep(self.config.db_startup_delay)

        raise RuntimeError("Database is unavailable") from last_error

    def initialize(self) -> None:
        self.wait_until_ready()

        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS users_name_lower_unique
                ON users ((lower(name)))
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_unique
                ON users ((lower(email)))
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS donations (
                    id TEXT PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                    campaign TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK (amount >= 0),
                    donation_date DATE NOT NULL,
                    status TEXT NOT NULL,
                    donor TEXT NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS donations_user_id_created_at_idx
                ON donations (user_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    target INTEGER NOT NULL,
                    image_url TEXT,
                    user_id BIGINT REFERENCES users(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS donations_email_created_at_idx
                ON donations ((lower(email)), created_at DESC)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    photo_url TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS tickets_user_id_created_at_idx
                ON tickets (user_id, created_at DESC)
                """
            )

            self._seed_default_admin(conn)
            self._sync_user_id_sequence(conn)

    def _seed_default_admin(self, conn: psycopg.Connection) -> None:
        existing = conn.execute(
            "SELECT id FROM users WHERE lower(name) = lower(%s)",
            ("admin",),
        ).fetchone()

        if existing:
            return

        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            ("admin", "admin@local", generate_password_hash("admin")),
        )

    def _sync_user_id_sequence(self, conn: psycopg.Connection) -> None:
        conn.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('users', 'id'),
                GREATEST(COALESCE((SELECT MAX(id) FROM users), 1), 1),
                true
            )
            """
        )

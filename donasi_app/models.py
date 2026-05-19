from datetime import date
from typing import Any
from flask import session
from werkzeug.security import check_password_hash, generate_password_hash
from .database import Database

class AppError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class UserModel:
    def __init__(self, database: Database):
        self.database = database

    def current_user(self) -> dict[str, Any] | None:
        user_id = session.get("user_id")
        if not user_id:
            return None

        with self.database.connect() as conn:
            row = conn.execute(
                "SELECT id, name, email FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        return self._public_user(row) if row else None

    def require_user(self) -> dict[str, Any]:
        user = self.current_user()
        if not user:
            raise AppError("Unauthorized", 401)
        return user

    def register(self, payload: dict[str, Any]) -> str:
        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        if not name or not email or not password:
            raise AppError("Semua field wajib diisi", 400)

        with self.database.connect() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM users
                WHERE lower(name) = lower(%s) OR lower(email) = lower(%s)
                """,
                (name, email),
            ).fetchone()
            if existing:
                raise AppError("Nama akun atau email sudah digunakan", 409)

            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password)),
            )
        return "Pendaftaran berhasil"

    def login(self, payload: dict[str, Any]) -> dict[str, Any]:
        identifier = (payload.get("identifier") or payload.get("email") or "").strip()
        password = payload.get("password") or ""
        if not identifier or not password:
            raise AppError("Akun dan kata sandi wajib diisi", 400)

        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, email, password_hash
                FROM users
                WHERE lower(name) = lower(%s) OR lower(email) = lower(%s)
                """,
                (identifier, identifier),
            ).fetchone()

        if not row or not check_password_hash(row["password_hash"], password):
            raise AppError("Akun atau kata sandi salah", 401)
        session["user_id"] = row["id"]
        return self._public_user(row)

    def logout(self) -> None:
        session.clear()

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        user = self.require_user()

        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip().lower()

        if not name or not email:
            raise AppError("Nama lengkap dan email wajib diisi", 400)

        if email.endswith("@gmail.com") is False:
            raise AppError("Email harus menggunakan @gmail.com", 400)

        with self.database.connect() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM users
                WHERE id <> %s
                  AND (lower(name) = lower(%s) OR lower(email) = lower(%s))
                """,
                (user["id"], name, email),
            ).fetchone()
            if existing:
                raise AppError("Nama akun atau email sudah digunakan", 409)

            row = conn.execute(
                """
                UPDATE users
                SET name = %s,
                    email = %s
                WHERE id = %s
                RETURNING id, name, email
                """,
                (name, email, user["id"]),
            ).fetchone()

        return self._public_user(row)

    @staticmethod
    def _public_user(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "name": row["name"], "email": row["email"]}


class DonationModel:
    def __init__(self, database: Database, user_model: UserModel):
        self.database = database
        self.user_model = user_model

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        donation_id = (payload.get("id") or "").strip()
        campaign = (payload.get("campaign") or "").strip()
        status = (payload.get("status") or "").strip() or "Berhasil"
        donor_input = (payload.get("donor") or "").strip()
        donor = donor_input or "Hamba Allah"
        email = (payload.get("email") or "").strip().lower()
        amount_raw = payload.get("amount")
        donation_date_raw = (payload.get("date") or "").strip()
        user = self.user_model.current_user()

        if user:
            email = email or user["email"]
            if not donor_input:
                donor = user["name"]

        try:
            amount = int(amount_raw)
        except (TypeError, ValueError):
            raise AppError("Nominal donasi tidak valid", 400)

        try:
            donation_date = date.fromisoformat(donation_date_raw)
        except ValueError as exc:
            raise AppError("Tanggal donasi tidak valid", 400) from exc

        if not donation_id or not campaign or amount <= 0:
            raise AppError("Data donasi tidak lengkap", 400)

        with self.database.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM donations WHERE id = %s",
                (donation_id,),
            ).fetchone()
            if existing:
                raise AppError("ID donasi sudah ada", 409)

            row = conn.execute(
                """
                INSERT INTO donations (
                    id,
                    user_id,
                    campaign,
                    amount,
                    donation_date,
                    status,
                    donor,
                    email
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, campaign, amount, donation_date, status, donor, email
                """,
                (
                    donation_id,
                    user["id"] if user else None,
                    campaign,
                    amount,
                    donation_date,
                    status,
                    donor,
                    email,
                ),
            ).fetchone()

        return self._serialize(row)

    def list_for_current_user(self) -> list[dict[str, Any]]:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, campaign, amount, donation_date, status, donor, email
                FROM donations
                WHERE user_id = %s OR lower(email) = lower(%s)
                ORDER BY created_at DESC, id DESC
                """,
                (user["id"], user["email"]),
            ).fetchall()

        return [self._serialize(row) for row in rows]

    def summary_for_current_user(self) -> dict[str, int]:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            user_summary = conn.execute(
                """
                SELECT
                    COALESCE(SUM(amount), 0) AS total_amount,
                    COUNT(*) AS donation_count,
                    COUNT(DISTINCT campaign) AS campaign_count
                FROM donations
                WHERE status = %s
                  AND (user_id = %s OR lower(email) = lower(%s))
                """,
                ("Berhasil", user["id"], user["email"]),
            ).fetchone()
            platform_summary = conn.execute(
                """
                SELECT
                    COALESCE(SUM(amount), 0) AS total_amount,
                    COUNT(*) AS donation_count
                FROM donations
                WHERE status = %s
                """,
                ("Berhasil",),
            ).fetchone()

        return {
            "user_total_amount": user_summary["total_amount"],
            "user_donation_count": user_summary["donation_count"],
            "user_campaign_count": user_summary["campaign_count"],
            "platform_total_amount": platform_summary["total_amount"],
            "platform_donation_count": platform_summary["donation_count"],
        }

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "campaign": row["campaign"],
            "amount": row["amount"],
            "date": row["donation_date"].isoformat(),
            "status": row["status"],
            "donor": row["donor"],
            "email": row["email"],
        }


class TicketModel:
    def __init__(self, database: Database, user_model: UserModel):
        self.database = database
        self.user_model = user_model

    def create(self, payload: dict[str, Any], photo_url: str | None = None) -> dict[str, Any]:
        category = (payload.get("category") or "").strip()
        description = (payload.get("description") or "").strip()
        user = self.user_model.require_user()

        if not category or not description:
            raise AppError("Kategori dan deskripsi tiket wajib diisi", 400)

        with self.database.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO tickets (
                    user_id,
                    category,
                    description,
                    photo_url
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, category, description, photo_url, status, created_at
                """,
                (
                    user["id"],
                    category,
                    description,
                    photo_url,
                ),
            ).fetchone()

        return self._serialize(row)

    def list_for_current_user(self) -> list[dict[str, Any]]:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, category, description, photo_url, status, created_at
                FROM tickets
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user["id"],),
            ).fetchall()

        return [self._serialize(row) for row in rows]
        
    def list_all(self) -> list[dict[str, Any]]:
        user = self.user_model.require_user()
        if user["name"].lower() != "admin":
            raise AppError("Unauthorized", 401)
            
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.user_id, t.category, t.description, t.photo_url, t.status, t.created_at, u.name as user_name
                FROM tickets t
                LEFT JOIN users u ON t.user_id = u.id
                ORDER BY t.created_at DESC
                """
            ).fetchall()
            
        res = []
        for row in rows:
            data = self._serialize(row)
            data["user_name"] = row.get("user_name")
            res.append(data)
        return res

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "category": row["category"],
            "description": row["description"],
            "photo_url": row["photo_url"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }

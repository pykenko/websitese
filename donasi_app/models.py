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
                "SELECT id, name, email, photo_url FROM users WHERE id = %s",
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
            conn.commit()
        return "Pendaftaran berhasil"

    def login(self, payload: dict[str, Any]) -> dict[str, Any]:
        identifier = (
            payload.get("identifier")
            or payload.get("username")
            or payload.get("email")
            or ""
        ).strip()
        password = payload.get("password") or ""
        if not identifier or not password:
            raise AppError("Akun dan kata sandi wajib diisi", 400)

        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, email, password_hash, photo_url
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

    def update_profile(self, payload: dict[str, Any], photo_url: str | None = None) -> dict[str, Any]:
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
                    email = %s,
                    photo_url = COALESCE(%s, photo_url)
                WHERE id = %s
                RETURNING id, name, email, photo_url
                """,
                (name, email, photo_url, user["id"]),
            ).fetchone()
            conn.commit()

        return self._public_user(row)

    @staticmethod
    def _public_user(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "photo": row.get("photo_url"),
        }


class DonationModel:
    def __init__(self, database: Database, user_model: UserModel):
        self.database = database
        self.user_model = user_model

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        donation_id = (payload.get("id") or "").strip()
        campaign_id = (payload.get("campaign_id") or "").strip() or None
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
                    campaign_id,
                    campaign,
                    amount,
                    donation_date,
                    status,
                    donor,
                    email
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, campaign_id, campaign, amount, donation_date, status, donor, email
                """,
                (
                    donation_id,
                    user["id"] if user else None,
                    campaign_id,
                    campaign,
                    amount,
                    donation_date,
                    status,
                    donor,
                    email,
                ),
            ).fetchone()
            conn.commit()

        return self._serialize(row)

    def list_for_current_user(self) -> list[dict[str, Any]]:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, campaign_id, campaign, amount, donation_date, status, donor, email
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

    def latest_successful_donation(self) -> dict[str, Any] | None:
        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT id, campaign_id, campaign, amount, donation_date, status, donor, email
                FROM donations
                WHERE status = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                ("Berhasil",),
            ).fetchone()

        return self._serialize(row) if row else None

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "campaign_id": row.get("campaign_id"),
            "campaign": row["campaign"],
            "amount": row["amount"],
            "date": row["donation_date"].isoformat(),
            "status": row["status"],
            "donor": row["donor"],
            "email": row["email"],
        }


class CampaignModel:
    def __init__(self, database: Database, user_model: UserModel):
        self.database = database
        self.user_model = user_model

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        user = self.user_model.require_user()

        campaign_id = (payload.get("id") or "").strip()
        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        image_url = (payload.get("image_url") or "").strip() or None
        category = (payload.get("category") or "Lainnya").strip()
        target_raw = payload.get("target")
        duration_raw = payload.get("duration")

        try:
            target = int(target_raw)
        except (TypeError, ValueError):
            raise AppError("Target donasi tidak valid", 400)

        try:
            duration = int(duration_raw)
        except (TypeError, ValueError):
            raise AppError("Durasi kampanye tidak valid", 400)

        if not campaign_id or not title or not description or target < 10000 or duration <= 0:
            raise AppError("Data kampanye tidak lengkap", 400)

        with self.database.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM campaigns WHERE id = %s",
                (campaign_id,),
            ).fetchone()
            if existing:
                raise AppError("ID kampanye sudah ada", 409)

            row = conn.execute(
                """
                INSERT INTO campaigns (
                    id,
                    title,
                    description,
                    target,
                    duration,
                    image_url,
                    user_id,
                    category
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, description, target, duration, image_url, user_id, created_at, category
                """,
                (campaign_id, title, description, target, duration, image_url, user["id"], category),
            ).fetchone()
            conn.commit()

        return self._serialize(row, user_name=user["name"], user_email=user["email"])

    def list_all(self, search: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT c.id, c.title, c.description, c.target, c.duration, c.image_url, c.user_id, c.created_at, c.category,
                   u.name AS user_name, u.email AS user_email
            FROM campaigns c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (c.title ILIKE %s OR c.description ILIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
            
        if category and category != "Semua":
            query += " AND c.category = %s"
            params.append(category)
            
        query += " ORDER BY c.created_at DESC, c.id DESC"

        with self.database.connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            self._serialize(row, user_name=row.get("user_name"), user_email=row.get("user_email"))
            for row in rows
        ]

    def list_for_current_user(self) -> list[dict[str, Any]]:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.description, c.target, c.duration, c.image_url, c.user_id, c.created_at, c.category,
                       u.name AS user_name, u.email AS user_email
                FROM campaigns c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.user_id = %s
                ORDER BY c.created_at DESC, c.id DESC
                """,
                (user["id"],),
            ).fetchall()

        return [
            self._serialize(row, user_name=row.get("user_name"), user_email=row.get("user_email"))
            for row in rows
        ]

    def delete(self, campaign_id: str) -> None:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            row = conn.execute(
                """
                DELETE FROM campaigns
                WHERE id = %s AND user_id = %s
                RETURNING id
                """,
                (campaign_id, user["id"]),
            ).fetchone()
            conn.commit()

        if not row:
            raise AppError("Kampanye tidak ditemukan", 404)

    @staticmethod
    def _serialize(row: dict[str, Any], user_name: str | None = None, user_email: str | None = None) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "category": row.get("category", "Lainnya"),
            "target_amount": row["target"],
            "duration": row.get("duration"),
            "image_url": row["image_url"],
            "user_id": row["user_id"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "created_by": user_name or "Penggalang Dana",
            "created_by_email": user_email,
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
            conn.commit()

        return self._serialize(row)

    def list_for_current_user(self) -> list[dict[str, Any]]:
        user = self.user_model.require_user()

        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, category, description, photo_url, status, created_at,
                       admin_reply, replied_at
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
                SELECT t.id, t.user_id, t.category, t.description, t.photo_url, t.status, t.created_at,
                       t.admin_reply, t.replied_at, u.name as user_name
                FROM tickets t
                LEFT JOIN users u ON t.user_id = u.id
                ORDER BY
                    CASE t.status
                        WHEN 'open' THEN 0
                        WHEN 'in_progress' THEN 1
                        WHEN 'closed' THEN 2
                        ELSE 3
                    END,
                    t.created_at DESC
                """
            ).fetchall()
            
        res = []
        for row in rows:
            data = self._serialize(row)
            data["user_name"] = row.get("user_name")
            res.append(data)
        return res

    def reply(self, ticket_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        user = self.user_model.require_user()
        if user["name"].lower() != "admin":
            raise AppError("Unauthorized", 401)

        reply_text = (payload.get("reply") or "").strip()
        new_status = (payload.get("status") or "").strip() or None

        if not reply_text:
            raise AppError("Balasan tidak boleh kosong", 400)

        valid_statuses = {"open", "in_progress", "closed"}
        if new_status and new_status not in valid_statuses:
            raise AppError("Status tidak valid", 400)

        with self.database.connect() as conn:
            if new_status:
                row = conn.execute(
                    """
                    UPDATE tickets
                    SET admin_reply = %s,
                        replied_at = CURRENT_TIMESTAMP,
                        status = %s
                    WHERE id = %s
                    RETURNING id, user_id, category, description, photo_url, status, created_at,
                              admin_reply, replied_at
                    """,
                    (reply_text, new_status, ticket_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    UPDATE tickets
                    SET admin_reply = %s,
                        replied_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, user_id, category, description, photo_url, status, created_at,
                              admin_reply, replied_at
                    """,
                    (reply_text, ticket_id),
                ).fetchone()
            conn.commit()

        if not row:
            raise AppError("Tiket tidak ditemukan", 404)

        return self._serialize(row)

    def delete_closed(self, ticket_id: int) -> None:
        user = self.user_model.require_user()
        if user["name"].lower() != "admin":
            raise AppError("Unauthorized", 401)

        with self.database.connect() as conn:
            ticket = conn.execute(
                "SELECT id, status FROM tickets WHERE id = %s",
                (ticket_id,),
            ).fetchone()

            if not ticket:
                raise AppError("Tiket tidak ditemukan", 404)
            if ticket["status"] != "closed":
                raise AppError("Hanya tiket closed yang bisa dihapus", 400)

            conn.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
            conn.commit()

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "category": row["category"],
            "description": row["description"],
            "photo_url": row.get("photo_url"),
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "admin_reply": row.get("admin_reply"),
            "replied_at": row["replied_at"].isoformat() if row.get("replied_at") else None,
        }

class CampaignExpenseModel:
    def __init__(self, database: Database):
        self.database = database

    def create(self, campaign_id: str, date_str: str, description: str, amount: int) -> dict[str, Any]:
        with self.database.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO campaign_expenses (campaign_id, date, description, amount)
                VALUES (%s, %s, %s, %s)
                RETURNING id, date, description, amount
                """,
                (campaign_id, date_str, description, amount)
            ).fetchone()
            conn.commit()
        return self._serialize(row)

    def list_by_campaign(self, campaign_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, description, amount
                FROM campaign_expenses
                WHERE campaign_id = %s
                ORDER BY date DESC, id DESC
                """,
                (campaign_id,),
            ).fetchall()
        return [self._serialize(row) for row in rows]

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "date": row["date"].isoformat() if row.get("date") else None,
            "description": row["description"],
            "amount": row["amount"],
        }

class CampaignUpdateModel:
    def __init__(self, database: Database):
        self.database = database

    def create(self, campaign_id: str, date_str: str, title: str, content: str, image_url: str | None = None) -> dict[str, Any]:
        with self.database.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO campaign_updates (campaign_id, date, title, content, image_url)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, date, title, content, image_url
                """,
                (campaign_id, date_str, title, content, image_url)
            ).fetchone()
            conn.commit()
        return self._serialize(row)

    def list_by_campaign(self, campaign_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, title, content, image_url
                FROM campaign_updates
                WHERE campaign_id = %s
                ORDER BY date DESC, id DESC
                """,
                (campaign_id,),
            ).fetchall()
        return [self._serialize(row) for row in rows]

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "date": row["date"].isoformat() if row.get("date") else None,
            "title": row["title"],
            "content": row["content"],
            "image_url": row.get("image_url"),
        }


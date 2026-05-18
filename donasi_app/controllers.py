import psycopg
from flask import Flask, jsonify, request, send_from_directory, render_template

from .config import AppConfig
from .database import Database
from .models import AppError, DonationModel, UserModel, TicketModel
import os
import uuid
from werkzeug.utils import secure_filename
class ApiController:
    def __init__(self, database: Database, user_model: UserModel, donation_model: DonationModel, ticket_model: TicketModel):
        self.database = database
        self.user_model = user_model
        self.donation_model = donation_model
        self.ticket_model = ticket_model

    def register_routes(self, app: Flask) -> None:
        app.add_url_rule("/api/health", endpoint="health", view_func=self.health, methods=["GET"])
        app.add_url_rule("/api/me", endpoint="auth_me", view_func=self.me, methods=["GET"])
        app.add_url_rule("/api/register", endpoint="auth_register", view_func=self.register, methods=["POST"])
        app.add_url_rule("/api/login", endpoint="auth_login", view_func=self.login, methods=["POST"])
        app.add_url_rule("/api/logout", endpoint="auth_logout", view_func=self.logout, methods=["POST"])
        app.add_url_rule(
            "/api/donations",
            endpoint="donation_create",
            view_func=self.create_donation,
            methods=["POST"],
        )
        app.add_url_rule(
            "/api/donations",
            endpoint="donation_list",
            view_func=self.list_donations,
            methods=["GET"],
        )
        app.add_url_rule(
            "/api/donations/summary",
            endpoint="donation_summary",
            view_func=self.donation_summary,
            methods=["GET"],
        )
        app.add_url_rule(
            "/api/tickets",
            endpoint="ticket_create",
            view_func=self.create_ticket,
            methods=["POST"],
        )
        app.add_url_rule(
            "/api/tickets",
            endpoint="ticket_list",
            view_func=self.list_tickets,
            methods=["GET"],
        )
        app.add_url_rule(
            "/api/campaigns/<campaign_name>/total",
            endpoint="campaign_total",
            view_func=self.get_campaign_total,
            methods=["GET"],
        )

    def health(self):
        try:
            self.database.ping()
        except psycopg.Error:
            return jsonify({"status": "error"}), 503

        return jsonify({"status": "ok"})

    def me(self):
        try:
            user = self.user_model.require_user()
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "user": user})

    def register(self):
        try:
            message = self.user_model.register(request.get_json(silent=True) or {})
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "message": message})

    def login(self):
        try:
            user = self.user_model.login(request.get_json(silent=True) or {})
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "user": user})

    def logout(self):
        self.user_model.logout()
        return jsonify({"success": True})

    def create_donation(self):
        try:
            donation = self.donation_model.create(request.get_json(silent=True) or {})
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "donation": donation}), 201

    def list_donations(self):
        try:
            donations = self.donation_model.list_for_current_user()
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "donations": donations})

    def donation_summary(self):
        try:
            summary = self.donation_model.summary_for_current_user()
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "summary": summary})

    def create_ticket(self):
        try:
            payload = dict(request.form)
            if not payload and request.is_json:
                payload = request.get_json(silent=True) or {}
                
            photo_url = None
            if "photo" in request.files:
                photo = request.files["photo"]
                if photo.filename:
                    filename = secure_filename(photo.filename)
                    ext = os.path.splitext(filename)[1]
                    unique_filename = f"{uuid.uuid4().hex}{ext}"
                    # We need the config's upload dir. Since we don't have config here, we use app config or absolute path.
                    # It's better to get the uploads_dir from current_app.
                    from flask import current_app
                    # But actually we can just get it by relative path or pass config.
                    # A quick way is to use os.path.abspath
                    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
                    os.makedirs(uploads_dir, exist_ok=True)
                    photo.save(os.path.join(uploads_dir, unique_filename))
                    photo_url = f"/uploads/{unique_filename}"

            ticket = self.ticket_model.create(payload, photo_url)
        except AppError as error:
            return self._error_response(error)
        return jsonify({"success": True, "ticket": ticket}), 201

    def list_tickets(self):
        try:
            try:
                user = self.user_model.require_user()
                if user.get("name", "").lower() == "admin":
                    tickets = self.ticket_model.list_all()
                else:
                    tickets = self.ticket_model.list_for_current_user()
            except AppError as error:
                return self._error_response(error)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        return jsonify({"success": True, "tickets": tickets})

    @staticmethod
    def _error_response(error: AppError):
        return jsonify({"success": False, "message": error.message}), error.status_code

    def get_campaign_total(self, campaign_name: str):
        try:
            with self.database.connect() as conn:
                result = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM donations WHERE campaign = %s AND status = %s",
                    (campaign_name, "Berhasil"),
                ).fetchone()
            total = result["total"] if result else 0
            return jsonify({"success": True, "total": total, "campaign": campaign_name})
        except Exception as error:
            return jsonify({"success": False, "message": str(error)}), 500


class PageController:
    def __init__(self, config: AppConfig):
        self.config = config

    def register_routes(self, app: Flask) -> None:
        app.add_url_rule("/", endpoint="index", view_func=self.index)
        app.add_url_rule("/login", endpoint="login_page", view_func=self.login)
        app.add_url_rule("/register", endpoint="register_page", view_func=self.register)
        app.add_url_rule("/donation", endpoint="donation_page", view_func=self.donation)
        app.add_url_rule("/dashboard", endpoint="dashboard", view_func=self.dashboard)
        app.add_url_rule("/invoice", endpoint="invoice_page", view_func=self.invoice)
        app.add_url_rule("/kebijakan-privasi", endpoint="privacy_policy", view_func=self.privacy_policy)
        app.add_url_rule("/syarat-ketentuan", endpoint="terms", view_func=self.terms)
        app.add_url_rule(
            "/uploads/<path:filename>",
            endpoint="uploads_dir",
            view_func=self.uploads,
        )

    def uploads(self, filename: str):
        return send_from_directory(self.config.uploads_dir, filename)

    def index(self):
        return render_template("index.html")

    def login(self):
        return render_template("login.html")
    
    def register(self):
        return render_template("register.html")

    def donation(self):
        return render_template("donation.html")

    def invoice(self):
        return render_template("invoice.html")

    def privacy_policy(self):
        return render_template("kebijakan-privasi.html")

    def terms(self):
        return render_template("syarat-ketentuan.html")
    
    def dashboard(self):
        return render_template("dashboard.html")

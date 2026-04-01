import psycopg
from flask import Flask, jsonify, request, send_from_directory

from .config import AppConfig
from .database import Database
from .models import AppError, DonationModel, UserModel
class ApiController:
    def __init__(self, database: Database, user_model: UserModel, donation_model: DonationModel):
        self.database = database
        self.user_model = user_model
        self.donation_model = donation_model

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

    @staticmethod
    def _error_response(error: AppError):
        return jsonify({"success": False, "message": error.message}), error.status_code


class PageController:
    def __init__(self, config: AppConfig):
        self.config = config

    def register_routes(self, app: Flask) -> None:
        app.add_url_rule("/", endpoint="index", view_func=self.index, methods=["GET"])
        app.add_url_rule(
            "/<path:path>",
            endpoint="static_files",
            view_func=self.static_files,
            methods=["GET"],
        )

    def index(self):
        return send_from_directory(self.config.static_dir, "index.html")

    def static_files(self, path: str):
        page_path = self.config.static_dir / path
        root_path = self.config.base_dir / path

        if page_path.is_file():
            return send_from_directory(self.config.static_dir, path)

        if root_path.is_file():
            return send_from_directory(self.config.base_dir, path)

        return "Not Found", 404

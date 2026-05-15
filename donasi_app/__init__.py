from flask import Flask

from .config import AppConfig
from .controllers import ApiController, PageController
from .database import Database
from .models import DonationModel, UserModel, TicketModel

def create_app() -> Flask:
    config = AppConfig()
    database = Database(config)
    database.initialize()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    user_model = UserModel(database)
    donation_model = DonationModel(database, user_model)
    ticket_model = TicketModel(database, user_model)

    ApiController(database, user_model, donation_model, ticket_model).register_routes(app)
    PageController(config).register_routes(app)
    return app

__all__ = ["create_app"]
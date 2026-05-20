from flask import Flask

from .config import AppConfig
from .controllers import ApiController, PageController
from .database import Database
from .models import CampaignModel, DonationModel, UserModel, TicketModel

def create_app() -> Flask:
    config = AppConfig()
    database = Database(config)
    database.initialize()
    config.uploads_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        template_folder=str(config.templates_dir),
        static_folder=str(config.static_dir),
    )
    app.config["SECRET_KEY"] = config.secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["UPLOADS_DIR"] = str(config.uploads_dir)

    user_model = UserModel(database)
    donation_model = DonationModel(database, user_model)
    campaign_model = CampaignModel(database, user_model)
    ticket_model = TicketModel(database, user_model)

    ApiController(database, user_model, donation_model, campaign_model, ticket_model).register_routes(app)
    PageController(config).register_routes(app)
    return app

__all__ = ["create_app"]

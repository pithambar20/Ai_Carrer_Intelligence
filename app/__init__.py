from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    # Import models so SQLAlchemy is aware of them
    from app import models  # noqa: F401

    # Auto-create tables if they don't exist
    with app.app_context():
        db.create_all()

    # Context processor to make AI status available across all templates
    @app.context_processor
    def inject_ai_status():
        api_key = app.config.get("GEMINI_API_KEY", "")
        is_configured = bool(api_key and api_key != "your_gemini_api_key_here")
        return {"gemini_configured": is_configured}

    # Import and register blueprints
    from app.routes import main
    app.register_blueprint(main)


    # CLI command to initialize database tables manually if needed
    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        with app.app_context():
            db.create_all()
        print("Initialized the database.")

    return app

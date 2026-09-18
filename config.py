from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = "change-this-in-production"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

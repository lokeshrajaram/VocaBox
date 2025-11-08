from pathlib import Path

from flask import Flask

from .routes import bp

PACKAGE_ROOT = Path(__file__).parent
TEMPLATE_FOLDER = PACKAGE_ROOT / 'templates'


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATE_FOLDER))
    app.register_blueprint(bp)
    return app


app = create_app()

__all__ = ['create_app', 'app']

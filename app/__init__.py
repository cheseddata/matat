import logging
import sys
from flask import Flask
from .config import config
from .extensions import db, bcrypt, login_manager, csrf, migrate
from .utils.i18n import init_i18n
from . import cli


def create_app(config_name='default'):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set up app logger
    app.logger.setLevel(logging.INFO)
    app.logger.info('Matat application starting...')

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Initialize i18n
    init_i18n(app)
    
    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp
    from .blueprints.salesperson import salesperson_bp
    from .blueprints.donate import donate_bp
    from .blueprints.webhook import webhook_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(salesperson_bp, url_prefix='/salesperson')
    app.register_blueprint(donate_bp)
    app.register_blueprint(webhook_bp, url_prefix='/api')
    
    # User loader for Flask-Login
    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register CLI commands
    cli.init_app(app)

    return app

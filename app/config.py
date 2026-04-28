import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }
    
    # Stripe
    STRIPE_TEST_SECRET_KEY = os.environ.get('STRIPE_TEST_SECRET_KEY')
    STRIPE_LIVE_SECRET_KEY = os.environ.get('STRIPE_LIVE_SECRET_KEY')
    STRIPE_TEST_PUBLISHABLE_KEY = os.environ.get('STRIPE_TEST_PUBLISHABLE_KEY')
    STRIPE_LIVE_PUBLISHABLE_KEY = os.environ.get('STRIPE_LIVE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_MODE = os.environ.get('STRIPE_MODE', 'test')
    
    # Email
    MAIL_PROVIDER = os.environ.get('MAIL_PROVIDER', 'sendgrid')
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # App
    APP_DOMAIN = os.environ.get('APP_DOMAIN', 'http://localhost:5000')
    ORG_NAME = os.environ.get('ORG_NAME', 'Matat Mordechai')

    # Upload size limits — generous because the help-widget feedback flow
    # ships full-page screenshots as base64-encoded form fields, and our
    # check-image / Zelle-screenshot upload also lands here. Werkzeug 3.x
    # added a per-form-field memory cap that defaults to ~500 KB; high-DPI
    # screenshots easily exceed it, so the widget would 413 and hang.
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024        # 32 MB total request
    MAX_FORM_MEMORY_SIZE = 32 * 1024 * 1024      # 32 MB per text field
    
    @property
    def stripe_secret_key(self):
        if self.STRIPE_MODE == 'live':
            return self.STRIPE_LIVE_SECRET_KEY
        return self.STRIPE_TEST_SECRET_KEY
    
    @property
    def stripe_publishable_key(self):
        if self.STRIPE_MODE == 'live':
            return self.STRIPE_LIVE_PUBLISHABLE_KEY
        return self.STRIPE_TEST_PUBLISHABLE_KEY


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:password@localhost:3306/matat'
    )


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app import create_app, db
import app.models as models

def send_test_email():
    app = create_app()
    with app.app_context():
        # Dynamically find the config/settings model
        # We look for 'Config', 'Settings', or 'SystemSettings'
        ConfigModel = None
        for name in ['Config', 'Settings', 'SystemSettings']:
            if hasattr(models, name):
                ConfigModel = getattr(models, name)
                break
        
        if not ConfigModel:
            print("❌ Error: Could not find a Settings/Config model in app.models.")
            return

        config = ConfigModel.query.first()
        if not config:
            print("❌ Error: No settings found in the database table.")
            return

        print(f"🔗 Attempting to send via {config.smtp_host}:{config.smtp_port}...")

        msg = MIMEMultipart()
        # Some models use 'smtp_user' vs 'smtp_username', this handles both
        user = getattr(config, 'smtp_username', getattr(config, 'smtp_user', None))
        password = getattr(config, 'smtp_password', getattr(config, 'smtp_pass', None))
        
        msg['From'] = user
        msg['To'] = "mkantor@mkantor.com"
        msg['Subject'] = "Matat Mordechai - SMTP Test"
        msg.attach(MIMEText("This is a test email from the Matat Mordechai bot.", 'plain'))

        try:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            if getattr(config, 'smtp_use_tls', True):
                server.starttls()
            
            server.login(user, password)
            server.send_message(msg)
            server.quit()
            print("✅ Success! Email sent to mkantor@mkantor.com")
        except Exception as e:
            print(f"❌ Connection Failed: {str(e)}")

if __name__ == "__main__":
    send_test_email()

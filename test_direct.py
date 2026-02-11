import smtplib
import sqlite3
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email():
    # 1. Connect directly to your database file
    # If using PostgreSQL or MySQL, update this connection string
    try:
        # Based on your setup, it might be app.db or similar
        conn = sqlite3.connect('instance/app.db') 
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config LIMIT 1")
        row = cursor.fetchone()
        
        # Mapping based on your Adminer screenshot (image_581d9f.jpg)
        # You'll need to verify which columns hold the SMTP data
        print("Successfully connected to the 'config' table.")
        
        # Hardcoding credentials for this specific test if DB fetch fails
        smtp_host = "smtp.office365.com"
        smtp_port = 587
        username = "support@matatmordechai.org"
        password = "Chesed01" # Put your password here
        
        msg = MIMEMultipart()
        msg['From'] = username
        msg['To'] = "mkantor@mkantor.com"
        msg['Subject'] = "Matat Mordechai - Direct SMTP Test"
        msg.attach(MIMEText("Test successful. The email bot is live.", 'plain'))

        print(f"Connecting to {smtp_host}...")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        print("✅ SUCCESS: Test email sent to mkantor@mkantor.com")
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")

if __name__ == "__main__":
    test_email()

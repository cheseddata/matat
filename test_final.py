import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_test():
    # --- YOUR CREDENTIALS ---
    smtp_host = "smtp.office365.com"
    smtp_port = 587
    username = "support@matatmordechai.org"
    # REPLACE the line below with your actual App Password
    password = "Chesed01!" 
    
    recipient = "mkantor@mkantor.com"

    print(f"Connecting to {smtp_host}...")
    
    msg = MIMEMultipart()
    msg['From'] = username
    msg['To'] = recipient
    msg['Subject'] = "Matat Mordechai - Final SMTP Test"
    msg.attach(MIMEText("Test successful. The Email Bot is communicating with Microsoft 365.", 'plain'))

    try:
        # Step 1: Connect
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        
        # Step 2: Identify and start encryption (Required for 365)
        server.ehlo()
        server.starttls() 
        server.ehlo()
        
        # Step 3: Login and Send
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ SUCCESS: Email sent to {recipient}!")
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        print("\nCommon fixes:")
        print("1. Ensure 'Authenticated SMTP' is checked in Exchange Admin Center.")
        print("2. Ensure you are using a 16-character 'App Password' (not your login password).")

if __name__ == "__main__":
    send_test()

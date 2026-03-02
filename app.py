from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

app = Flask(__name__)
# Enable CORS so your HTML file can communicate with this Python server
CORS(app)

# Dictionary to temporarily store OTPs (In a real application, a database is preferred)
otp_storage = {}

# Your Gmail Credentials
SENDER_EMAIL = "ncstars2026@gmail.com"
APP_PASSWORD = "wbsorcsolbtnmrir" 

def generate_html_email(otp_code, purpose="recovery"):
    """
    Generates a highly professional, Canva-style HTML email template.
    The text and context adapt automatically based on the user's action.
    """
    
    if purpose == "registration":
        email_title = "Staff Registration Verification"
        greeting = "Welcome to NC-STARS,"
        main_message = """
        <p>You have officially initiated a new staff registration for the <strong>Norzagaray College Student Tracking, AI Resolution and Sanction System (NC-STARS)</strong>.</p>
        <p>The NC-STARS platform serves as the central hub for managing highly confidential student records, disciplinary histories, and intervention reports for the Guidance Office and the Office of Student Affairs. Because we prioritize data privacy and institutional integrity, our security infrastructure requires a strict verification process before granting access to our portals.</p>
        <p>Before we forward your application to the System Administrator for final review and approval, we must verify that you are the legitimate owner of this school email address.</p>
        <p>Please enter the 6-digit verification code below into your registration screen to validate your identity and proceed with your application.</p>
        """
        warning_text = "<strong>Security Advisory:</strong> If you did not initiate this registration, please ignore this email immediately. It is possible that someone entered your email address by mistake. Your account remains secure."
    else:
        email_title = "System Access Verification Required"
        greeting = "Dear System Administrator,"
        main_message = """
        <p>Welcome to the secure recovery gateway of the <strong>Norzagaray College Student Tracking, AI Resolution and Sanction System (NC-STARS)</strong>.</p>
        <p>We recently received a formal request to access or modify the master credentials associated with this administrative email address. The NC-STARS platform holds highly sensitive data, and modifying the master account requires maximum security clearance.</p>
        <p>To proceed with your authentication or password reset request, we need to verify your identity. Please enter the unique 6-digit One-Time Password (OTP) generated for your session below.</p>
        """
        warning_text = "<strong>Critical Security Alert:</strong> If you did not initiate this password recovery request, it strongly indicates that someone may be attempting to breach the administrative portal. Do not share this code with anyone, including IT personnel, and secure your account immediately."

    # Beautiful Canva-style HTML structure
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                background-color: #f4f1eb;
                margin: 0;
                padding: 40px 20px;
            }}
            .email-wrapper {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 15px 35px rgba(0, 0, 0, 0.08);
            }}
            .header {{
                background-color: #0d5c2e;
                padding: 40px 20px;
                text-align: center;
                border-bottom: 5px solid #16a34a;
            }}
            .header h1 {{
                color: #ffffff;
                margin: 0;
                font-size: 26px;
                letter-spacing: 3px;
                text-transform: uppercase;
                font-weight: 700;
            }}
            .header p {{
                color: #e8dacc;
                margin: 10px 0 0 0;
                font-size: 13px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            .content {{
                padding: 45px 40px;
                color: #4b5563;
                line-height: 1.8;
            }}
            .content h2 {{
                color: #0a0a0a;
                font-size: 22px;
                margin-top: 0;
                margin-bottom: 25px;
                border-bottom: 1px solid #e8dacc;
                padding-bottom: 15px;
            }}
            .content p {{
                font-size: 15px;
                margin-bottom: 20px;
                text-align: justify;
            }}
            .otp-container {{
                background: linear-gradient(145deg, #f9f9f9, #f4f1eb);
                border: 2px dashed #0d5c2e;
                border-radius: 12px;
                padding: 30px;
                text-align: center;
                margin: 35px 0;
                box-shadow: inset 0 4px 10px rgba(0,0,0,0.03);
            }}
            .otp-label {{
                margin-top: 0; 
                font-size: 13px; 
                text-transform: uppercase; 
                letter-spacing: 2px; 
                color: #4b5563; 
                font-weight: bold;
            }}
            .otp-code {{
                font-size: 42px;
                font-weight: 800;
                letter-spacing: 10px;
                color: #0d5c2e;
                margin: 10px 0 0 0;
            }}
            .warning-box {{
                background-color: #fef2f2;
                border-left: 5px solid #ef4444;
                padding: 18px 20px;
                font-size: 13px;
                color: #991b1b;
                border-radius: 6px;
                line-height: 1.6;
            }}
            .footer {{
                background-color: #0a0a0a;
                padding: 30px 20px;
                text-align: center;
                color: #a3a3a3;
                font-size: 12px;
                line-height: 1.6;
            }}
            .footer strong {{
                color: #e8dacc;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                <h1>NC-STARS</h1>
                <p>System Security Protocol</p>
            </div>
            <div class="content">
                <h2>{email_title}</h2>
                <p><strong>{greeting}</strong></p>
                {main_message}
                
                <div class="otp-container">
                    <p class="otp-label">Your Verification Code</p>
                    <p class="otp-code">{otp_code}</p>
                </div>
                
                <div class="warning-box">
                    {warning_text}
                </div>
            </div>
            <div class="footer">
                <p><strong>Norzagaray College - Office of Student Affairs</strong><br>Municipal Compound, Norzagaray, Bulacan.</p>
                <p style="margin-top: 15px; font-size: 11px;">This is an automated system dispatch. Please do not reply to this email address as it is not monitored by human personnel.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email_address = data.get('email')
    purpose = data.get('purpose', 'recovery') # Defaults to recovery if not specified

    if not email_address:
        return jsonify({"success": False, "message": "Email is required."}), 400

    # Generate a random 6-digit code
    otp_code = str(random.randint(100000, 999999))
    
    # Store it in memory mapped to the email address
    otp_storage[email_address] = otp_code

    try:
        # Construct the email payload
        msg = MIMEMultipart()
        msg['From'] = f"NC-STARS Security <{SENDER_EMAIL}>"
        msg['To'] = email_address
        
        if purpose == 'registration':
            msg['Subject'] = "NC-STARS: Staff Registration Verification Code"
        else:
            msg['Subject'] = "NC-STARS: Administrator Verification Code"
        
        # Attach the beautiful HTML content
        msg.attach(MIMEText(generate_html_email(otp_code, purpose), 'html'))

        # Securely connect to Gmail's SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        # Login using the secure App Password
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()

        return jsonify({"success": True, "message": "OTP sent successfully."}), 200

    except Exception as e:
        print(f"Error sending email: {e}")
        return jsonify({"success": False, "message": "Failed to send email. Check server connection."}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email_address = data.get('email')
    user_otp = data.get('otp')

    if not email_address or not user_otp:
        return jsonify({"success": False, "message": "Email and OTP are required."}), 400

    # Check if the email exists in our storage and the code matches
    if email_address in otp_storage and otp_storage[email_address] == user_otp:
        # Remove the OTP after successful verification to prevent reuse
        del otp_storage[email_address]
        return jsonify({"success": True, "message": "Verification successful."}), 200
    else:
        return jsonify({"success": False, "message": "Invalid or expired verification code."}), 401

if __name__ == '__main__':
    # Run the Flask server on port 5000
    app.run(debug=True, port=5000)
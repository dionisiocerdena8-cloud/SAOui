from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import requests
import threading
import time
import re
import traceback

app = Flask(__name__)
# Enable CORS so your HTML file can communicate with this Python server
CORS(app)

# ==========================================
# GEMINI API KEY (NAKATAGO SA BACKEND)
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6IzCzWQpsuQfXlbVm8wT-X04qMKHMuYLzKnagNbTtC7wQ"

@app.route('/api/get-gemini-key', methods=['GET'])
def get_gemini_key():
    # Ibibigay ng backend ang key kapag hiningi ng frontend
    return jsonify({"key": GEMINI_API_KEY})

# ==========================================
# POSTGRESQL DATABASE CONFIGURATION
# ==========================================
# Note: Ang '@' sa password ay '%40'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:DIONIsio2%40@localhost/ncstars_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# DATABASE MODELS (TABLES)
# ==========================================
class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False) # Admin, Guidance, OSA
    dept = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.String(20), primary_key=True) # Student Number
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(50), nullable=False)

class Concern(db.Model):
    __tablename__ = 'concerns'
    concern_id = db.Column(db.String(50), primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.id'), nullable=False)
    name = db.Column(db.String(100))
    course = db.Column(db.String(50))
    incident_time = db.Column(db.String(50))
    reason = db.Column(db.String(200))
    narrative = db.Column(db.Text)
    status = db.Column(db.String(50), default='Pending OSA') # Pending OSA, Pending Implementation, Closed, Pending Reopen
    severity = db.Column(db.String(50), nullable=True) # Ang sanction
    referred_by = db.Column(db.String(100))
    
    # --- MGA BAGONG COLUMNS ---
    contact_number = db.Column(db.String(50), nullable=True)
    referrer_designation = db.Column(db.String(100), nullable=True)
    ai_analysis_result = db.Column(db.Text, nullable=True) # BAGONG AI COLUMN
    
    reopen_count = db.Column(db.Integer, default=0)
    reschedule_count = db.Column(db.Integer, default=0) # BAGONG SCHEDULE COUNTER
    
    # --- MGA BAGONG COLUMNS PARA SA SMART ALARM PARA HINDI MAG SPAM ---
    notified_5min = db.Column(db.Boolean, default=False)
    notified_now = db.Column(db.Boolean, default=False)

# I-create ang mga tables at Default Admin bago mag-start ang server
with app.app_context():
    db.create_all()

    # ==============================================================
    # AUTO-MIGRATION LOGIC (PARA HINDI MAWALA ANG EXISTING DATA MO)
    # ==============================================================
    try:
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS contact_number VARCHAR(50);'))
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS referrer_designation VARCHAR(100);'))
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS ai_analysis_result TEXT;'))
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS reopen_count INTEGER DEFAULT 0;'))
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS reschedule_count INTEGER DEFAULT 0;'))
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS notified_5min BOOLEAN DEFAULT FALSE;'))
        db.session.execute(text('ALTER TABLE concerns ADD COLUMN IF NOT EXISTS notified_now BOOLEAN DEFAULT FALSE;'))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    # Automatically create a Default Admin if it doesn't exist
    if not Staff.query.filter_by(email='ncstars2026@gmail.com').first():
        default_admin = Staff(
            id='ADM-001',
            name='System Administrator',
            email='ncstars2026@gmail.com',
            password='admin', # Eto yung default admin password
            role='Admin',
            dept='Administrator',
            status='Approved'
        )
        db.session.add(default_admin)
        db.session.commit()
        print("Default Admin account successfully created in database!")


# ==========================================
# OTP AND EMAIL CONFIGURATION
# ==========================================
otp_storage = {}
SENDER_EMAIL = "ncstars2026@gmail.com"
APP_PASSWORD = "wbsorcsolbtnmrir" 

def generate_html_email(otp_code, purpose="recovery"):
    if purpose == "registration":
        email_title = "Staff Registration Verification"
        greeting = "Welcome to NC-STARS,"
        main_message = """
        <p>You have officially initiated a new staff registration for the <strong>Norzagaray College Student Tracking, AI Resolution and Sanction System (NC-STARS)</strong>.</p>
        <p>The NC-STARS platform serves as the central hub for managing highly confidential student records, disciplinary histories, and intervention reports for the Guidance Office and the Office of Student Affairs. Because we prioritize data privacy and institutional integrity, our security infrastructure requires a strict verification process before granting access to our portals.</p>
        <p>Before we forward your application to the System Administrator for final review and approval, we must verify that you are the legitimate owner of this school email address.</p>
        """
        warning_text = "<strong>SECURITY ADVISORY:</strong> If you did not initiate this registration, please ignore this email immediately. It is possible that someone entered your email address by mistake. Your account remains secure."
    else:
        email_title = "System Access Verification Required"
        greeting = "Dear System Administrator,"
        main_message = """
        <p>Welcome to the secure recovery gateway of the <strong>Norzagaray College Student Tracking, AI Resolution and Sanction System (NC-STARS)</strong>.</p>
        <p>We recently received a formal request to access or modify the master credentials associated with this administrative email address. The NC-STARS platform holds highly sensitive data, and modifying the master account requires maximum security clearance.</p>
        """
        warning_text = "<strong>CRITICAL SECURITY ALERT:</strong> If you did not initiate this password recovery request, it strongly indicates that someone may be attempting to breach the administrative portal. Do not share this code with anyone, including IT personnel, and secure your account immediately."

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">
        <style>
            /* Base Reset */
            body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
            table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
            img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
            
            body {{
                font-family: 'Inter', Helvetica, Arial, sans-serif;
                background-color: #d1dfd6; /* Body BG */
                margin: 0;
                padding: 0;
                width: 100% !important;
            }}
            
            .email-container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 24px;
                overflow: hidden;
                box-shadow: 0 20px 40px -10px rgba(18, 63, 34, 0.15);
                border: 1px solid #b8d0c3; /* silk */
            }}

            .header {{
                background-color: #0f2918; /* velvet */
                padding: 35px 40px;
                text-align: center;
                border-bottom: 4px solid #1b4d2c; /* luxuryGreen */
            }}

            .header h1 {{
                font-family: 'Plus Jakarta Sans', Helvetica, Arial, sans-serif;
                color: #ffffff;
                margin: 0;
                font-size: 28px;
                letter-spacing: 2px;
                font-weight: 800;
            }}

            .header p {{
                color: #b8d0c3; /* silk */
                margin: 8px 0 0 0;
                font-size: 11px;
                letter-spacing: 3px;
                text-transform: uppercase;
                font-weight: 600;
            }}

            .content {{
                padding: 40px;
                color: #4b5563; /* smoke */
                line-height: 1.7;
            }}

            .content h2 {{
                font-family: 'Plus Jakarta Sans', Helvetica, Arial, sans-serif;
                color: #0f2918; /* velvet */
                font-size: 22px;
                font-weight: 800;
                margin-top: 0;
                margin-bottom: 20px;
                letter-spacing: -0.5px;
            }}

            .content p {{
                font-size: 15px;
                margin-bottom: 20px;
                text-align: left;
            }}

            .content strong {{
                color: #0f2918; /* velvet */
            }}

            /* OTP FOCUS SECTION */
            .otp-wrapper {{
                background-color: #e1ede5; /* chiffon */
                border: 1px solid #b8d0c3; /* silk */
                border-radius: 16px;
                padding: 35px 20px;
                text-align: center;
                margin: 35px 0;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
            }}

            .otp-label {{
                display: block;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 3px;
                color: #4b5563; /* smoke */
                font-weight: 700;
                margin-bottom: 12px;
            }}

            .otp-code {{
                font-family: monospace, 'Courier New', Courier;
                font-size: 48px;
                font-weight: 800;
                letter-spacing: 16px;
                color: #1b4d2c; /* luxuryGreen */
                margin: 0;
                text-shadow: 1px 1px 0px rgba(255,255,255,0.5);
                /* Fix alignment issue caused by extreme letter-spacing on the last character */
                padding-left: 16px; 
            }}

            .instruction-text {{
                font-size: 13px;
                color: #4b5563; /* smoke */
                text-align: center;
                margin-top: -15px;
                margin-bottom: 30px;
            }}

            /* WARNING BOX */
            .warning-box {{
                background-color: #fff1f2; /* Light rose */
                border: 1px solid #fda4af;
                border-left: 4px solid #d93846; /* rose */
                padding: 20px;
                font-size: 13px;
                color: #be123c;
                border-radius: 12px;
                line-height: 1.6;
                margin-top: 30px;
            }}

            .footer {{
                background-color: #ecf4ef; /* panel */
                padding: 30px 40px;
                text-align: center;
                color: #4b5563; /* smoke */
                font-size: 12px;
                border-top: 1px solid #b8d0c3; /* silk */
            }}

            .footer strong {{
                color: #0f2918; /* velvet */
            }}

            /* MOBILE RESPONSIVENESS */
            @media only screen and (max-width: 600px) {{
                .email-container {{
                    margin: 15px !important;
                    border-radius: 16px !important;
                    width: auto !important;
                }}
                .header {{
                    padding: 30px 20px !important;
                }}
                .content {{
                    padding: 30px 20px !important;
                }}
                .footer {{
                    padding: 25px 20px !important;
                }}
                .otp-wrapper {{
                    padding: 25px 10px !important;
                    margin: 25px 0 !important;
                }}
                .otp-code {{
                    font-size: 36px !important;
                    letter-spacing: 10px !important;
                    padding-left: 10px !important;
                }}
                .content h2 {{
                    font-size: 20px !important;
                }}
                .content p {{
                    font-size: 14px !important;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>NC-STARS</h1>
                <p>System Security Protocol</p>
            </div>
            
            <div class="content">
                <h2>{email_title}</h2>
                <p><strong>{greeting}</strong></p>
                {main_message}
                
                <div class="otp-wrapper">
                    <span class="otp-label">Your Verification Code</span>
                    <div class="otp-code">{otp_code}</div>
                </div>
                <p class="instruction-text">Please enter this code on the verification screen. It will expire shortly.</p>
                
                <div class="warning-box">
                    {warning_text}
                </div>
            </div>
            
            <div class="footer">
                <p><strong>Norzagaray College - Office of Student Affairs</strong><br>Municipal Compound, Norzagaray, Bulacan.</p>
                <p style="margin-top: 12px; font-size: 11px; opacity: 0.8;">This is an automated system dispatch. Please do not reply to this email address.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email_address = data.get('email')
    purpose = data.get('purpose', 'recovery')

    if not email_address: return jsonify({"success": False, "message": "Email is required."}), 400
    otp_code = str(random.randint(100000, 999999))
    otp_storage[email_address] = otp_code

    try:
        msg = MIMEMultipart()
        msg['From'] = f"NC-STARS Security <{SENDER_EMAIL}>"
        msg['To'] = email_address
        msg['Subject'] = "NC-STARS Registration Verification Code" if purpose == 'registration' else "NC-STARS System Recovery Code"
        msg.attach(MIMEText(generate_html_email(otp_code, purpose), 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email_address = data.get('email')
    user_otp = data.get('otp')

    if email_address in otp_storage and otp_storage[email_address] == user_otp:
        del otp_storage[email_address]
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid code."}), 401


# ==========================================
# MAIN APP ENDPOINTS
# ==========================================

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    staff = Staff.query.filter_by(email=email).first()

    # Kung walang nahanap na email sa database
    if not staff:
        return jsonify({"success": False, "message": "Invalid email"}), 401

    # Kung tama ang email, pero mali ang password
    if staff.password != password:
        return jsonify({"success": False, "message": "Invalid password"}), 401

    # Kung tama pareho
    if staff.status == 'Pending':
        return jsonify({"success": False, "message": "Your account is still pending Admin approval."})
    elif staff.status == 'Rejected':
        return jsonify({"success": False, "message": "Your account request was rejected."})
        
    return jsonify({"success": True, "name": staff.name, "role": staff.role})

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    try:
        new_staff = Staff(
            id=data.get('id'), name=data.get('name'), email=data.get('email'), 
            password=data.get('password'), role=data.get('role'), dept=data.get('dept')
        )
        db.session.add(new_staff)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Email already exists or database error."})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    staff = Staff.query.filter_by(email=data.get('email')).first()
    if staff:
        staff.password = data.get('password')
        db.session.commit()
        return jsonify({"success": True, "role": staff.role})
    return jsonify({"success": False, "message": "Account not found."})

@app.route('/api/staff/action/<staff_id>', methods=['POST'])
def staff_action(staff_id):
    staff = Staff.query.get(staff_id)
    if staff:
        staff.status = request.json.get('action')
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route('/api/students', methods=['POST'])
def add_student():
    data = request.json
    try:
        s = Student(id=data['id'], last_name=data['last_name'], first_name=data['first_name'], course=data['course'])
        db.session.add(s)
        db.session.commit()
        return jsonify({"success": True})
    except:
        db.session.rollback()
        return jsonify({"success": False, "message": "Student ID already exists."}), 400

@app.route('/api/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    student = Student.query.get(student_id)
    if student:
        db.session.delete(student)
        db.session.commit()
    return jsonify({"success": True})

@app.route('/api/concerns', methods=['POST'])
def add_concern():
    data = request.json
    student_id = data.get('student_id')

    try:
        if not Student.query.get(student_id):
            name_parts = data.get('name', 'Unknown Student').split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            new_student = Student(id=student_id, first_name=first_name, last_name=last_name, course=data.get('course', 'Unknown'))
            db.session.add(new_student)
            db.session.commit()
            db.session.flush() # Force saving of the new student before assigning to a concern
        
        c = Concern(
            concern_id=data.get('concern_id'), 
            student_id=student_id, 
            name=data.get('name'), 
            course=data.get('course'), 
            incident_time=data.get('incident_time'), 
            reason=data.get('reason'), 
            narrative=data.get('narrative'), 
            status=data.get('status'), 
            referred_by=data.get('referred_by'),
            contact_number=data.get('contact_number'), 
            referrer_designation=data.get('referrer_designation'),
            ai_analysis_result=None, 
            reopen_count=0, 
            reschedule_count=0, 
            notified_5min=False, 
            notified_now=False 
        )
        db.session.add(c)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        traceback.print_exc() # Para makita mo kung bakit nare-reject minsan ng database
        return jsonify({"success": False, "message": str(e)}), 400


# ==========================================
# BACKGROUND AI ANALYSIS LOGIC
# ==========================================
def run_gemini_analysis(app_instance, concern_id):
    """ Tumatakbo ito sa background para hindi mag-freeze ang frontend ng user """
    with app_instance.app_context():
        c = Concern.query.get(concern_id)
        if not c:
            return

        # Bilangin ang past offenses (Closed status at hindi kasama yung current)
        past_offenses = Concern.query.filter(
            Concern.student_id == c.student_id,
            Concern.status == 'Closed',
            Concern.concern_id != c.concern_id
        ).count()
        past_offenses += (c.reopen_count or 0)
        current_offense_count = past_offenses + 1

        # Alisin ang mga HTML tags para malinis na text lang ang mabasa ng AI
        plain_narrative = re.sub(r'<[^>]*>?', '', c.narrative) if c.narrative else ""

        prompt = f"""
        Act as an AI disciplinary adjudicator for Norzagaray College Student Affairs.
        Analyze the following student disciplinary concern and recommend EXACTLY ONE sanction based strictly on the official institutional rubrics provided below.

        --- STUDENT INCIDENT DETAILS ---
        Student Offense History: {past_offenses} exact prior offense(s). (This is offense #{current_offense_count}).
        Current Offense Reason: {c.reason}
        Narrative Report: {plain_narrative}

        --- OFFICIAL DISCIPLINARY INTERVENTIONS ---
        L1. Verbal Warning: Reprimand for unacceptable behavior.
        L2. Written Reprimand: A formal written statement documenting that a violation of specific regulations has occurred.
        L3. Community Service: 15–20 hours of service around the school (students may still attend classes).
        L4. Suspension: Exclusion from classes and campus activities for 5 to 20 school days (not exceeding 20% of the prescribed period). This carries the forfeiture of the right to make up missed quizzes or homework.
        L5. Dropping/Dismissal: The student is dropped during the school year and immediately issued transfer credentials.
        L6. Expulsion: Permanent removal from Norzagaray College.
        *Note: "Written Apology" and "Counseling / Mediation" can also be applied as supplementary interventions where deemed appropriate.*

        --- VIOLATION CLASSIFICATIONS & PENALTY MATRIX ---
        Confirmed Major Violations (Serious Offenses):
        1. Fraternities/Sororities (Recruitment, Hazing, Symbols, Threats): L4 / L5 / L6
        2. Bullying/Harassment (Verbal, Physical, Social, Cyber, Catcalling): 1st Offense (L2/L3), 2nd (L3/L4), 3rd (L4/L5)
        3. Sexual Harassment (Catcalling, Slurs, Contact, Stalking, Requests): 1st Offense (L3/L4/L5/L6), 2nd (L4/L5/L6)
        4. Dangerous Drugs (Possession, Use, Intoxication, Selling): L5 / L6
        5. Vandalism (Defacing, Destruction, Tampering): 1st Offense (L3), 2nd (L4), 3rd (L5)
        6. Public Display of Affection (PDA) & Immorality: L5
        7. Cheating (Possession of Notes, Copying, Proxy, Plagiarism): 1st Offense (L4), 2nd (L5)

        Confirmed Minor/Behavioral Violations:
        1. Uniform & Grooming (No ID, Incomplete uniform, Piercings, Hair color): 1st Offense (L1), 2nd (L2), 3rd (L3)
        2. Classroom Disruptions (Sleeping, Gadgets, Noise, Running): 1st Offense (L1), 2nd (L2), 3rd (L3)
        3. Facility Misuse (Improper disposal, Loitering, Tampering): 1st Offense (L1), 2nd (L2), 3rd (L3)
        4. Attendance & Punctuality (Tardiness, Unauthorized absences, Cutting class): 1st Offense (L1), 2nd (L2), 3rd (L3)

        --- INSTRUCTIONS ---
        1. Categorize the offense using the Penalty Matrix above based on the "Current Offense Reason" and "Narrative Report".
        2. Look at the "Student Offense History" (Offense #{current_offense_count}) to determine the correct severity level (L1 to L6).
        3. HANDLING RANGES: If the matrix provides a range of levels (e.g., L2/L3), default to the lowest severity level UNLESS the 'Narrative Report' indicates severe malicious intent, physical harm, lack of remorse, or disruption of school operations, in which case elevate to the higher level.
        4. Map the chosen Level (L1-L6) to the exact sanction name from this list ONLY:
           "Verbal Warning", "Written Reprimand", "Written Apology", "Counseling / Mediation", "Community Service", "Suspension", "Dropping/Dismissal", "Expulsion".
        5. Provide a brief, objective justification (maximum 2-3 sentences) explaining how you applied the matrix and the narrative to reach this specific sanction.
        6. Determine the overall severity level as one of: "low", "medium", "high", "critical".
        7. Format your entire response strictly as a JSON object matching the exact schema below. Do not include markdown tags (like ```json) or any outside text.

        {{
          "severity_level": "low|medium|high|critical",
          "recommended_sanction": "[Exact Sanction Name]",
          "justification": "[Your 2-3 sentence explanation]"
        }}
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "recommended_sanction": {
                            "type": "STRING",
                            "enum": ["Verbal Warning", "Written Reprimand", "Written Apology", "Counseling / Mediation", "Community Service", "Suspension", "Dropping/Dismissal", "Expulsion"]
                        },
                        "justification": { "type": "STRING" },
                        "severity_level": {
                            "type": "STRING",
                            "enum": ["low", "medium", "high", "critical"]
                        }
                    },
                    "required": ["recommended_sanction", "justification", "severity_level"]
                }
            }
        }

        # NAG-A-AUTO RETRY LOGIC (Hanggang 10 times) para hindi titigil hanggat hindi kumukuha ng AI result at nagse-save sa database
        max_retries = 10
        for attempt in range(max_retries):
            try:
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
                response = requests.post(gemini_url, json=payload)
                
                if response.ok:
                    data = response.json()
                    result_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    if result_text:
                        # I-save diretsa sa database yung result!
                        c.ai_analysis_result = result_text
                        db.session.commit()
                        print(f"✅ AI Analysis successfully saved for concern {concern_id}")
                        break # Exit the loop kapag successful na
                    else:
                        print("⚠️ AI returned empty result, retrying...")
                else:
                    print(f"❌ AI API Error (Attempt {attempt+1}): {response.text}")
                    
            except Exception as e:
                print(f"❌ AI Background Task Failed (Attempt {attempt+1}): {e}")
                
            time.sleep(3) # Wait 3 seconds bago subukan ulit

@app.route('/api/concerns/<concern_id>', methods=['PUT'])
def update_concern(concern_id):
    c = Concern.query.get(concern_id)
    if c:
        data = request.json
        if 'status' in data: 
            c.status = data['status']
            
        if 'severity' in data: c.severity = data['severity']
        if 'reopen_count' in data: c.reopen_count = data['reopen_count']
        if 'narrative' in data: c.narrative = data['narrative']
        if 'incident_time' in data: c.incident_time = data['incident_time']
        if 'notified_5min' in data: c.notified_5min = data['notified_5min']
        if 'notified_now' in data: c.notified_now = data['notified_now']
        
        # Kapag nag schedule, increment natin ang counter
        if 'reschedule_count' in data: 
            c.reschedule_count = data['reschedule_count']
            
        db.session.commit() # Save the Escalated status first bago patakbuhin ang AI

        # Kapag Escalated ang ipinasa, I-RURUN YUNG AI THREAD
        if data.get('status') == 'Escalated':
            thread = threading.Thread(target=run_gemini_analysis, args=(app, concern_id))
            thread.start()

        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route('/api/data', methods=['GET'])
def get_all_data():
    try:
        staff_records = Staff.query.filter_by(status='Pending').all()
        pending_staff = [{"id": s.id, "name": s.name, "email": s.email, "dept": s.dept, "date": s.created_at.strftime('%Y-%m-%d')} for s in staff_records]

        student_records = Student.query.all()
        students = [{"id": s.id, "lastName": s.last_name, "firstName": s.first_name, "course": s.course} for s in student_records]

        concern_records = Concern.query.all()
        concerns = [{
            "concernId": c.concern_id, "studentId": c.student_id, "name": c.name, "course": c.course,
            "incidentTime": c.incident_time, "reason": c.reason, "narrative": c.narrative,
            "status": c.status, "severity": c.severity, "referredBy": c.referred_by, 
            "contactNumber": c.contact_number, "referrerDesignation": c.referrer_designation,
            "reopenCount": c.reopen_count or 0,
            "rescheduleCount": c.reschedule_count or 0, 
            "notified_5min": c.notified_5min, "notified_now": c.notified_now,
            "aiAnalysisResult": c.ai_analysis_result 
        } for c in concern_records]

        return jsonify({ "pendingStaff": pending_staff, "studentDatabase": students, "concerns": concerns }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

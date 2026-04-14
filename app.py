from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

app = Flask(__name__)
# Enable CORS so your HTML file can communicate with this Python server
CORS(app)

# ==========================================
# GEMINI API KEY (NAKATAGO SA BACKEND)
# ==========================================
GEMINI_API_KEY = "AIzaSyC1DHnr7_ehJHFFVQU-GY6-XET3GuXxwiI"

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
    reopen_count = db.Column(db.Integer, default=0)
    # --- MGA BAGONG COLUMNS PARA SA SMART ALARM PARA HINDI MAG SPAM ---
    notified_5min = db.Column(db.Boolean, default=False)
    notified_now = db.Column(db.Boolean, default=False)

# I-create ang mga tables at Default Admin bago mag-start ang server
# I-create ang mga tables at Default Admin bago mag-start ang server
with app.app_context():
    db.create_all()

    # Automatically create a Default Admin if it doesn't exist

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

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f1eb; margin: 0; padding: 40px 20px; }}
            .email-wrapper {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 15px 35px rgba(0, 0, 0, 0.08); }}
            .header {{ background-color: #0d5c2e; padding: 40px 20px; text-align: center; border-bottom: 5px solid #16a34a; }}
            .header h1 {{ color: #ffffff; margin: 0; font-size: 26px; letter-spacing: 3px; text-transform: uppercase; font-weight: 700; }}
            .header p {{ color: #e8dacc; margin: 10px 0 0 0; font-size: 13px; letter-spacing: 1px; text-transform: uppercase; }}
            .content {{ padding: 45px 40px; color: #4b5563; line-height: 1.8; }}
            .content h2 {{ color: #0a0a0a; font-size: 22px; margin-top: 0; margin-bottom: 25px; border-bottom: 1px solid #e8dacc; padding-bottom: 15px; }}
            .content p {{ font-size: 15px; margin-bottom: 20px; text-align: justify; }}
            .otp-container {{ background: linear-gradient(145deg, #f9f9f9, #f4f1eb); border: 2px dashed #0d5c2e; border-radius: 12px; padding: 30px; text-align: center; margin: 35px 0; box-shadow: inset 0 4px 10px rgba(0,0,0,0.03); }}
            .otp-label {{ margin-top: 0; font-size: 13px; text-transform: uppercase; letter-spacing: 2px; color: #4b5563; font-weight: bold; }}
            .otp-code {{ font-size: 42px; font-weight: 800; letter-spacing: 10px; color: #0d5c2e; margin: 10px 0 0 0; }}
            .warning-box {{ background-color: #fef2f2; border-left: 5px solid #ef4444; padding: 18px 20px; font-size: 13px; color: #991b1b; border-radius: 6px; line-height: 1.6; }}
            .footer {{ background-color: #0a0a0a; padding: 30px 20px; text-align: center; color: #a3a3a3; font-size: 12px; line-height: 1.6; }}
            .footer strong {{ color: #e8dacc; }}
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
                <p>Please enter the unique 6-digit One-Time Password (OTP) generated for your session below.</p>
                <div class="code" style="font-size: 42px; font-weight: 800; letter-spacing: 10px; color: #0d5c2e; margin: 10px 0 0 0; text-align: center; padding: 20px; background: #e1ede5; border-radius: 10px;">{otp_code}</div>
                <p style="font-size: 12px; color: #4b5563; margin-top: 20px;">If you did not initiate this request, ignore this email.</p>
                <div class="warning-box">{warning_text}</div>
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
        # ANTI-CRASH FIX: Kung hindi pa enrolled ang student sa DB, i-auto enroll muna siya bago i-save ang concern
        if not Student.query.get(student_id):
            name_parts = data.get('name', 'Unknown Student').split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            new_student = Student(id=student_id, first_name=first_name, last_name=last_name, course=data.get('course', 'Unknown'))
            db.session.add(new_student)
            db.session.commit()
        
        # Pagkatapos i-ensure na nasa database ang student, i-save ang concern
        c = Concern(
            concern_id=data.get('concern_id'), student_id=student_id, name=data.get('name'), 
            course=data.get('course'), incident_time=data.get('incident_time'), reason=data.get('reason'), 
            narrative=data.get('narrative'), status=data.get('status'), referred_by=data.get('referred_by'),
            notified_5min=False, notified_now=False  # BAGONG DEFAULTS
        )
        db.session.add(c)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/api/concerns/<concern_id>', methods=['PUT'])
def update_concern(concern_id):
    c = Concern.query.get(concern_id)
    if c:
        data = request.json
        if 'status' in data: c.status = data['status']
        if 'severity' in data: c.severity = data['severity']
        if 'reopen_count' in data: c.reopen_count = data['reopen_count']
        if 'narrative' in data: c.narrative = data['narrative']
        if 'incident_time' in data: c.incident_time = data['incident_time']
        # --- UPDATE ALARM STATUS SA DATABASE ---
        if 'notified_5min' in data: c.notified_5min = data['notified_5min']
        if 'notified_now' in data: c.notified_now = data['notified_now']
        
        db.session.commit()
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
            "status": c.status, "severity": c.severity, "referredBy": c.referred_by, "reopenCount": c.reopen_count,
            "notified_5min": c.notified_5min, "notified_now": c.notified_now  # IBABATO SA FRONTEND ANG STATUS
        } for c in concern_records]

        return jsonify({ "pendingStaff": pending_staff, "studentDatabase": students, "concerns": concerns }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
